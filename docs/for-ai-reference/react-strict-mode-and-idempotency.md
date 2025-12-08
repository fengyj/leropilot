# React Strict Mode & API Idempotency Solution

## 问题概述 (Problem Overview)

React 18 的 Strict Mode 在开发环境下会**故意双重调用**某些函数(包括 `useEffect`)来帮助开发者发现副作用问题。这会导致:

1. **前端问题**: API 请求被调用两次,浪费资源且可能导致竞态条件
2. **后端问题**: 对于修改数据的操作(POST/PUT/DELETE),重复调用可能导致数据不一致

React 18's Strict Mode **intentionally double-invokes** certain functions (including `useEffect`) in development to help developers find side effects. This causes:

1. **Frontend Issues**: API requests are called twice, wasting resources and potentially causing race conditions
2. **Backend Issues**: For data-mutating operations (POST/PUT/DELETE), duplicate calls can lead to data inconsistencies

---

## 前端解决方案 (Frontend Solutions)

### 1. useEffect 清理函数 (Cleanup Functions)

**最佳实践**: 使用 AbortController 取消重复请求

```typescript
useEffect(
  () => {
    const abortController = new AbortController();

    const fetchData = async () => {
      try {
        const response = await fetch("/api/data", {
          signal: abortController.signal, // 关键: 传递 signal
        });
        const data = await response.json();
        setData(data);
      } catch (error) {
        if (error.name === "AbortError") {
          // 请求被取消,这是正常的
          return;
        }
        console.error("Failed to fetch:", error);
      }
    };

    fetchData();

    // 清理函数: 组件卸载或重新渲染时取消请求
    return () => {
      abortController.abort();
    };
  },
  [
    /* dependencies */
  ]
);
```

### 2. 使用 useRef 防止重复调用

对于不支持 AbortController 的场景(如 EventSource):

```typescript
const hasFetchedRef = useRef(false);

useEffect(() => {
  // 防止 Strict Mode 双重调用
  if (hasFetchedRef.current) return;
  hasFetchedRef.current = true;

  const fetchData = async () => {
    // ... 执行 API 调用
  };

  fetchData();
}, []);
```

**注意**: 这种方法只适用于依赖数组为空的情况,且在生产环境中可能隐藏真实问题。

### 3. 自定义 Hook: useEffectOnce

创建一个只执行一次的 hook:

```typescript
// src/hooks/useEffectOnce.ts
import { useEffect, useRef } from "react";

export function useEffectOnce(effect: () => void | (() => void)) {
  const hasRun = useRef(false);
  const cleanup = useRef<void | (() => void)>();

  useEffect(() => {
    if (!hasRun.current) {
      hasRun.current = true;
      cleanup.current = effect();
    }

    return () => {
      if (cleanup.current) {
        cleanup.current();
      }
    };
  }, []);
}
```

使用示例:

```typescript
useEffectOnce(() => {
  loadConfig();
  checkEnvironments();
});
```

### 4. 状态管理防抖 (Debouncing State Updates)

对于频繁变化的依赖项:

```typescript
import { useEffect, useState } from "react";
import { debounce } from "lodash-es";

const [searchTerm, setSearchTerm] = useState("");

useEffect(() => {
  const debouncedSearch = debounce(async () => {
    const results = await fetch(`/api/search?q=${searchTerm}`);
    // ...
  }, 300);

  debouncedSearch();

  return () => {
    debouncedSearch.cancel();
  };
}, [searchTerm]);
```

---

## 后端解决方案 (Backend Solutions)

### 1. 幂等性密钥 (Idempotency Keys)

为所有数据修改操作添加幂等性密钥支持:

```python
# src/leropilot/routers/environments.py

from datetime import datetime, timedelta
from typing import Dict
import uuid

# 幂等性缓存: key -> (result, timestamp)
_idempotency_cache: Dict[str, tuple[dict, datetime]] = {}
IDEMPOTENCY_TTL = timedelta(hours=24)

def cleanup_expired_keys():
    """清理过期的幂等性密钥"""
    now = datetime.now()
    expired = [k for k, (_, ts) in _idempotency_cache.items()
               if now - ts > IDEMPOTENCY_TTL]
    for k in expired:
        del _idempotency_cache[k]

@router.post("/create")
async def create_environment(
    request: CreateEnvironmentRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    lang: str = Query("en", description="Language code"),
) -> dict:
    """
    创建环境 (支持幂等性)

    客户端应该为每个创建请求生成唯一的 idempotency_key。
    如果使用相同的 key 重复请求,将返回首次请求的结果。
    """
    # 清理过期密钥
    cleanup_expired_keys()

    # 检查幂等性
    if idempotency_key:
        if idempotency_key in _idempotency_cache:
            cached_result, _ = _idempotency_cache[idempotency_key]
            logger.info(f"Returning cached result for idempotency key: {idempotency_key}")
            return cached_result

    try:
        # 执行实际的创建逻辑
        config_service, i18n_service, _ = get_services()
        executor = get_installation_executor()

        # ... 现有的创建逻辑 ...

        result = {
            "installation_id": installation.id,
            "env_id": installation.env_config.id,
            "status": installation.status,
            # ...
        }

        # 缓存结果
        if idempotency_key:
            _idempotency_cache[idempotency_key] = (result, datetime.now())

        return result

    except Exception as e:
        logger.error(f"Failed to create environment: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
```

### 2. 数据库唯一约束 (Database Unique Constraints)

对于环境创建,使用环境 ID 作为主键:

```python
# src/leropilot/core/environment_service.py

def create_environment(self, env_config: EnvironmentConfig) -> bool:
    """创建环境,如果已存在则返回 False"""
    env_dir = self.config.paths.get_environment_path(env_config.id)

    # 检查是否已存在
    if env_dir.exists():
        logger.warning(f"Environment {env_config.id} already exists")
        return False  # 幂等性: 已存在不重复创建

    # 创建环境目录
    env_dir.mkdir(parents=True, exist_ok=True)

    # 保存配置
    config_file = env_dir / "config.json"
    with open(config_file, "w") as f:
        f.write(env_config.model_dump_json(indent=2))

    return True
```

### 3. 状态机保护 (State Machine Protection)

对于安装过程,使用状态机防止重复执行:

```python
# src/leropilot/core/environment_service.py

class InstallationExecutor:
    def create_installation(
        self,
        env_config: EnvironmentConfig,
        plan: InstallationPlan
    ) -> Installation:
        """创建安装实例,防止重复创建"""

        # 检查是否已有活动安装
        for inst_id, inst in self.active_installations.items():
            if inst.env_config.id == env_config.id:
                if inst.status in ["pending", "running"]:
                    logger.warning(
                        f"Installation already active for env {env_config.id}"
                    )
                    return inst  # 返回现有安装

        # 创建新安装
        installation_id = str(uuid.uuid4())
        installation = Installation(
            id=installation_id,
            env_config=env_config,
            plan=plan,
            status="pending",
            created_at=datetime.now(),
        )

        self.active_installations[installation_id] = installation
        return installation
```

### 4. 乐观锁 (Optimistic Locking)

对于配置更新,使用版本号:

```python
# src/leropilot/models/config.py

class AppConfig(BaseModel):
    version: int = 1  # 添加版本字段
    # ... 其他字段

# src/leropilot/core/config.py

async def update_config_business_logic(new_config: AppConfig) -> AppConfig:
    """更新配置,使用乐观锁"""
    current_config = get_config()

    # 检查版本
    if new_config.version != current_config.version:
        raise HTTPException(
            status_code=409,
            detail="Config has been modified by another process. Please reload and try again."
        )

    # 更新版本号
    new_config.version += 1

    # 保存配置
    save_config(new_config)

    return new_config
```

---

## 具体修改方案 (Specific Implementation Plan)

### 前端修改 (Frontend Changes)

#### 1. 修改 `settings-page.tsx`

**问题**: 多个 useEffect 可能导致重复 API 调用

**解决方案**:

```typescript
// frontend/src/pages/settings-page.tsx

// 1. 使用 AbortController 取消重复请求
useEffect(() => {
  const abortController = new AbortController();

  const loadData = async () => {
    try {
      await loadConfig();
      await checkEnvironments();
    } catch (error) {
      if (error.name === "AbortError") return;
      console.error("Failed to load:", error);
    }
  };

  loadData();

  return () => {
    abortController.abort();
  };
}, [loadConfig, checkEnvironments]);

// 2. 修改 bundled git 状态检查
useEffect(() => {
  if (config?.tools.git.type !== "bundled") {
    setBundledGitStatus(null);
    return;
  }

  const abortController = new AbortController();

  fetch("/api/config/tools/git/bundled/status", {
    signal: abortController.signal,
  })
    .then((res) => res.json())
    .then((data) => setBundledGitStatus(data))
    .catch((err) => {
      if (err.name !== "AbortError") {
        console.error("Failed to check bundled git:", err);
      }
    });

  return () => {
    abortController.abort();
  };
}, [config?.tools.git.type]);
```

#### 2. 修改 `repository-status-button.tsx`

**问题**: checkStatus 在每次渲染时都可能被调用

**解决方案**:

```typescript
// frontend/src/components/repository-status-button.tsx

const checkStatus = useCallback(
  async (signal?: AbortSignal) => {
    if (!repoId) return;
    setIsChecking(true);
    try {
      const normalizedId = repoId.toLowerCase().replace(/ /g, "_");
      const response = await fetch(
        `/api/config/repositories/${normalizedId}/status`,
        { signal } // 传递 signal
      );
      if (response.ok) {
        const data: RepositoryStatus = await response.json();
        setIsDownloaded(data.is_downloaded);
        setLastUpdatedTime(data.last_updated);
        setHasUpdates(data.has_updates || false);
        onStatusChange?.(data);
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("Failed to check repository status:", err);
      }
    } finally {
      setIsChecking(false);
    }
  },
  [repoId, onStatusChange]
);

useEffect(() => {
  const abortController = new AbortController();
  checkStatus(abortController.signal);

  return () => {
    abortController.abort();
  };
}, [checkStatus]);
```

#### 3. 修改 `environment-list-page.tsx`

**解决方案**:

```typescript
// frontend/src/pages/environment-list-page.tsx

useEffect(() => {
  const abortController = new AbortController();

  const fetchEnvironments = async () => {
    try {
      const response = await fetch("/api/environments", {
        signal: abortController.signal,
      });
      if (response.ok) {
        const data = await response.json();
        setEnvironments(data);
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        console.error("Failed to fetch environments:", error);
      }
    } finally {
      setLoading(false);
    }
  };

  fetchEnvironments();

  return () => {
    abortController.abort();
  };
}, []);
```

#### 4. 创建环境时添加幂等性密钥

```typescript
// frontend/src/pages/environment-wizard.tsx

import { v4 as uuidv4 } from "uuid";

const handleCreateEnvironment = async () => {
  // 生成幂等性密钥
  const idempotencyKey = uuidv4();

  try {
    const response = await fetch("/api/environments/create", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey, // 添加幂等性密钥
      },
      body: JSON.stringify({
        env_config: wizardStore.getEnvironmentConfig(),
        custom_steps: wizardStore.customSteps,
      }),
    });

    const data = await response.json();
    // ...
  } catch (error) {
    console.error("Failed to create environment:", error);
  }
};
```

### 后端修改 (Backend Changes)

#### 1. 添加幂等性中间件

```python
# src/leropilot/middleware/idempotency.py

from datetime import datetime, timedelta
from typing import Dict, Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import json

class IdempotencyMiddleware(BaseHTTPMiddleware):
    """幂等性中间件,缓存 POST 请求的响应"""

    def __init__(self, app, ttl_hours: int = 24):
        super().__init__(app)
        self.cache: Dict[str, Tuple[dict, datetime]] = {}
        self.ttl = timedelta(hours=ttl_hours)

    def cleanup_expired(self):
        """清理过期的缓存"""
        now = datetime.now()
        expired = [k for k, (_, ts) in self.cache.items()
                   if now - ts > self.ttl]
        for k in expired:
            del self.cache[k]

    async def dispatch(self, request: Request, call_next):
        # 只处理 POST/PUT/DELETE 请求
        if request.method not in ["POST", "PUT", "DELETE"]:
            return await call_next(request)

        # 获取幂等性密钥
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        # 清理过期缓存
        self.cleanup_expired()

        # 检查缓存
        cache_key = f"{request.method}:{request.url.path}:{idempotency_key}"
        if cache_key in self.cache:
            cached_response, _ = self.cache[cache_key]
            return Response(
                content=json.dumps(cached_response),
                media_type="application/json",
                status_code=200,
                headers={"X-Idempotency-Cache": "HIT"}
            )

        # 执行请求
        response = await call_next(request)

        # 缓存成功的响应
        if 200 <= response.status_code < 300:
            # 读取响应体
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            try:
                response_data = json.loads(body)
                self.cache[cache_key] = (response_data, datetime.now())
            except json.JSONDecodeError:
                pass

            # 重新创建响应
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        return response
```

#### 2. 在主应用中注册中间件

```python
# src/leropilot/main.py

from leropilot.middleware.idempotency import IdempotencyMiddleware

app = FastAPI(title="LeRoPilot")

# 添加幂等性中间件
app.add_middleware(IdempotencyMiddleware, ttl_hours=24)
```

#### 3. 修改环境创建端点

```python
# src/leropilot/routers/environments.py

from fastapi import Header

@router.post("/create")
async def create_environment(
    request: CreateEnvironmentRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    lang: str = Query("en", description="Language code"),
) -> dict:
    """
    创建环境 (支持幂等性)

    Args:
        request: 环境配置
        idempotency_key: 幂等性密钥 (可选,建议提供)
        lang: 语言代码

    Returns:
        安装 ID 和状态
    """
    try:
        executor = get_installation_executor()

        # 检查是否已有活动安装
        existing_installation = None
        for inst_id, inst in executor.active_installations.items():
            if inst.env_config.id == request.env_config.id:
                if inst.status in ["pending", "running"]:
                    logger.info(
                        f"Returning existing installation for env {request.env_config.id}"
                    )
                    existing_installation = inst
                    break

        if existing_installation:
            # 返回现有安装
            return {
                "installation_id": existing_installation.id,
                "env_id": existing_installation.env_config.id,
                "status": existing_installation.status,
                "message": "Installation already in progress",
            }

        # 创建新安装
        config_service, i18n_service, _ = get_services()

        # ... 现有的创建逻辑 ...

    except Exception as e:
        logger.error(f"Failed to create environment: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
```

#### 4. 修改配置更新端点

```python
# src/leropilot/routers/config.py

@router.put("", response_model=AppConfig)
async def update_config(
    config: AppConfig,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> AppConfig:
    """
    更新配置 (支持幂等性)

    Args:
        config: 新配置
        idempotency_key: 幂等性密钥

    Returns:
        更新后的配置
    """
    try:
        # 幂等性检查由中间件处理
        return await update_config_business_logic(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
```

---

## 测试验证 (Testing & Verification)

### 前端测试

1. **React Strict Mode 测试**

   ```bash
   # 确保 main.tsx 中启用了 StrictMode
   cd frontend
   npm run dev
   ```

   打开浏览器控制台,验证:

   - API 请求只发送一次(检查 Network 标签)
   - 没有重复的控制台日志

2. **幂等性测试**
   - 快速点击"创建环境"按钮多次
   - 验证只创建一个环境
   - 检查后端日志确认幂等性密钥生效

### 后端测试

1. **幂等性密钥测试**

   ```bash
   # 使用相同的幂等性密钥发送两次请求
   curl -X POST http://localhost:8000/api/environments/create \
     -H "Content-Type: application/json" \
     -H "Idempotency-Key: test-key-123" \
     -d '{"env_config": {...}}'

   # 第二次请求应该返回缓存的结果
   curl -X POST http://localhost:8000/api/environments/create \
     -H "Content-Type: application/json" \
     -H "Idempotency-Key: test-key-123" \
     -d '{"env_config": {...}}'
   ```

2. **并发测试**

   ```python
   # tests/test_idempotency.py
   import asyncio
   import httpx

   async def test_concurrent_create():
       """测试并发创建环境的幂等性"""
       async with httpx.AsyncClient() as client:
           tasks = []
           idempotency_key = "test-concurrent-123"

           for _ in range(5):
               task = client.post(
                   "http://localhost:8000/api/environments/create",
                   json={"env_config": {...}},
                   headers={"Idempotency-Key": idempotency_key}
               )
               tasks.append(task)

           responses = await asyncio.gather(*tasks)

           # 验证所有响应相同
           assert all(r.status_code == 200 for r in responses)
           assert len(set(r.json()["installation_id"] for r in responses)) == 1
   ```

---

## 最佳实践总结 (Best Practices Summary)

### 前端 (Frontend)

1. ✅ **总是使用 AbortController** 取消未完成的请求
2. ✅ **避免使用 useRef 跳过 useEffect** (除非绝对必要)
3. ✅ **为数据修改操作生成幂等性密钥** (使用 UUID)
4. ✅ **正确设置 useEffect 依赖数组**
5. ✅ **使用 useCallback 稳定函数引用**
6. ❌ **不要忽略 React Strict Mode 警告**

### 后端 (Backend)

1. ✅ **为所有 POST/PUT/DELETE 端点支持幂等性密钥**
2. ✅ **使用状态机防止重复操作**
3. ✅ **在数据库层面添加唯一约束**
4. ✅ **记录幂等性密钥使用情况** (用于调试)
5. ✅ **定期清理过期的幂等性缓存**
6. ✅ **返回明确的错误信息** (如"操作已在进行中")

---

## 参考资源 (References)

- [React 18 Strict Mode](https://react.dev/reference/react/StrictMode)
- [AbortController API](https://developer.mozilla.org/en-US/docs/Web/API/AbortController)
- [Idempotency Keys (Stripe)](https://stripe.com/docs/api/idempotent_requests)
- [FastAPI Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
