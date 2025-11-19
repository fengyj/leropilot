# LeRoPilot-AI-SRS v0.1

**AI-Executable Specification**
`single-file → copilot → shipped`

```markdown
# 强制上下文（LLM 必须逐字阅读）

1. 本项目 = 本地 Web 服务（FastAPI + React 18）+ PyInstaller 单文件可执行。
2. 用户零依赖：双击打开浏览器即可用。
3. 代码必须一次通过 CI（ruff + mypy + pytest + build-size-gate）。
4. 禁止升级任何依赖版本，除非同步修改本文件里的版本号。
5. 禁止在生成后再“回头打补丁”——所有逻辑在本文件一次性描述完毕。
```

---

## 1. 仓库结构（必须 1:1 生成）

```
leropilot/
├── src/leropilot/          ← Python 根包，禁止再嵌套
│   ├── __init__.py         ← 仅导出版本 __version__ = "0.1.0"
│   ├── config.py           ← BaseSettings，支持 yaml 文件覆盖
│   ├── logger.py           ← structlog 单例，JSON 输出
│   ├── storage.py          ← Path 操作 + json 读写，必须 Result[_, Exception]
│   ├── models/             ← Pydantic 模型，全部 frozen=True
│   ├── api/                ← FastAPI 路由，依赖注入统一用 deps.py
│   ├── services/           ← 业务逻辑，必须线程安全
│   ├── repository/         ← Git 操作，必须加 asyncio.Lock
│   ├── environment/        ← venv + pip + 源码安装，必须生成进度流
│   └── cli.py              ← Typer 入口，仅用于 dev
├── frontend/               ← Vite + React 18 + TypeScript + TailwindCSS
│   └── src/
│       ├── api/            ← openapi-typescript 自动生成，禁止手写
│       ├── components/     ← UI 组件，如 CreateEnvironmentDialog.tsx
│       ├── pages/          ← 页面级组件，如 EnvironmentListPage.tsx
│       ├── stores/         ← Zustand 全局状态管理
│       └── main.tsx        ← 必须 React.StrictMode
├── tests/
│   ├── backend/test_ai_*.py     ← 每个路由必须对应一条 happy-path 测试
│   └── frontend/test_ai.*.ts    ← 仅快照测试，防止 UI 漂移
├── scripts/
│   ├── build.py            ← 一键打包，产出 dist/leropilot(.exe)
│   └── ci_size_check.py    ← 体积门控：win ≤ 80 MB，mac ≤ 75 MB
├── build.spec               ← PyInstaller spec，excludes 已锁死
└── pyproject.toml           ← 依赖版本冻结，禁止升级
```

---

## 2. 依赖版本（冻结，LLM 禁止改）

```toml
[project]
dependencies = [
"fastapi==0.115.6",
"uvicorn[standard]==0.32.1",
"pydantic==2.10.3",
"pydantic-settings==2.6.1",
"gitpython==3.1.43",
"structlog==24.4.0",
"returns==0.22.0",          # Result 类型
"typer==0.12.5",            # CLI
"pyyaml==6.0.2",
"psutil==6.0.0",
]
```

---

## 3. 后端生成规则（按文件逐条执行）

### 3.1 config.py

- 类 `AppConfig(BaseSettings)`，env*prefix="LEROPILOT*"。
- **加载逻辑**：必须优先从 `~/.leropilot/config.yaml` 文件读取配置，然后用环境变量中的值进行覆盖。
- 字段：`data_dir`, `port`, `pypi_mirror`, `default_repo_url`, `max_concurrent_installations`。
- 全部 `@field_validator` 必须抛出 `ValueError` 且带 `code=<ErrorCode>.value`。

### 3.2 logger.py

- 函数 `get_logger(name: str) -> structlog.BoundLogger`。
- 输出格式 JSON，始终带 `{"env_id": "", "step": "", "elapsed_ms": 0}`。
- 文件轮转 10 MB × 5 份，路径 `~/.leropilot/logs/`。

### 3.3 storage.py

- 类 `StorageManager`。
- 所有方法返回 `Result[T, Exception]`（用 `returns` 包）。
- 提供 `save_env_config`, `load_env_config`, `delete_env` 三个原子操作。
- 禁止直接使用 `json.load`，必须 `with open(...) as f: json.loads(f.read())`。

### 3.4 models/

- 全部 `pydantic.BaseModel`，`frozen=True`。
- `CreateEnvironmentRequest` 字段：`ref`, `gpu`, `devices`, `display_name`。
- `EnvironmentStatus` 枚举：`pending`, `running`, `completed`, `failed`。
- `ErrorCode` IntEnum：见 3.10。

### 3.5 repository/manager.py

- 类 `RepositoryManager`。
- 所有 git 操作包裹 `asyncio.Lock`。
- `clone_from` 使用 `depth=1`。
- 方法签名：`checkout_version(ref: str) -> Result[bool, Exception]`。

### 3.6 environment/installer.py

- 类 `EnvironmentInstaller`。
- `start_installation` 立即返回，后台协程 `_run_installation`。
- 每步进度百分比写死：5/15/20/40/60/80/90/100。
- 日志实时推入 `asyncio.Queue[str]`，格式 `{"type": "log"|"complete"|"error", "msg": ""}`。
- **失败处理**：失败时自动 `shutil.rmtree(env_path)`。推送到队列的 `error` 消息**必须**包含 `subprocess` 的 `stdout` 和 `stderr` 以便调试。

### 3.7 services/environment_service.py

- 类 `EnvironmentService`。
- 内存 `_tasks: dict[str, CreateEnvironmentResponse]`。
- **并发安全**：所有修改 `_tasks` 字典或与 `StorageManager` 交互的方法，都**必须**被一个类实例级别的 `asyncio.Lock` 保护，防止竞态条件。
- `delete_environment` 必须同时删除磁盘目录 + json 记录 + 内存 task。

### 3.8 api/environments.py

- 路由前缀 `/environments`。
- `POST /` → 201 返回 `CreateEnvironmentResponse`。
- `GET /{env_id}/install_logs` → SSE `text/event-stream`，必须带 `retry: 2000`。
- 所有 `HTTPException` 使用 `ErrorCode` 表，`status_code=400` + `detail={"code": <ErrorCode>}`。

### 3.9 deps.py（统一依赖）

- `get_env_service() -> EnvironmentService` 单例。
- `get_repo_manager() -> RepositoryManager` 单例。
- 禁止直接 import 实例，必须通过 `deps`。

### 3.10 error.py

```python
from enum import IntEnum

class ErrorCode(IntEnum):
    GIT_CLONE_FAILED    = 4001
    PIP_INSTALL_TIMEOUT = 4002
    VENV_DIRTY          = 4003
    ENV_NOT_FOUND       = 4100
    CONCURRENT_OPERATION_LIMIT = 4009
```

---

## 4. 前端生成规则

### 4.1 依赖与架构

1.  `package.json` 锁定版本：
    `"react": "18.3.1", "react-dom": "18.3.1", "@tanstack/react-query": "5.0.5", "zustand": "4.5.0", "antd": "5.15.0"`
2.  `openapi-typescript` 自动生成 `api.ts` → 禁止手写 `any`。
3.  组件文件命名 `PascalCase.tsx`，样式文件命名 `kebab-case.module.css`。
4.  所有可交互元素（按钮、输入框）带 `data-testid`，方便 `test_ai.*.ts` 快照。

### 4.2 状态管理策略

- **服务器状态**：所有与后端 API 交互的数据（如环境列表）**必须**使用 `@tanstack/react-query` 管理。
- **全局客户端状态**：仅用于管理与 API 无关的全局 UI 状态（如“创建环境对话框是否可见”）。**必须**使用 `zustand` 在 `stores/` 目录下创建。

### 4.3 核心组件划分

- **`pages/EnvironmentListPage.tsx`**: 应用主页。
  - 使用 `useQuery` 获取并展示所有环境的列表（`GET /environments`）。
  - 列表使用 `antd` 的 `Table` 组件，展示 `displayName`, `ref`, `status` 和一个操作列。
  - 页面右上角有一个“创建新环境”的 `Button`。
- **`components/CreateEnvironmentDialog.tsx`**: 创建新环境的模态框。
  - 使用 `antd` 的 `Modal` 和 `Form` 组件。
  - 包含 `displayName`, `ref`, `gpu` 等字段的输入。
  - 使用 `useMutation` 提交表单 (`POST /environments`)。成功后，调用 `queryClient.invalidateQueries` 使主页列表自动刷新。
- **`components/InstallationLogViewer.tsx`**: 日志查看组件。
  - 接收 `envId: string` 作为 prop。
  - 内部使用 `useEffect` 创建 `new EventSource("/environments/{envId}/install_logs")`。
  - `onmessage` 时将日志追加到显示区域，并自动滚动到底部。
  - `onerror` 时，自动重连 3 次，若仍然失败，则在组件顶部显示一个 `antd` 的 `Alert` 组件，提示用户“日志流连接已断开，请检查网络或刷新页面”。
  - 组件销毁时，必须调用 `eventSource.close()`。

### 4.4 核心用户流程

1.  用户打开应用，看到 `EnvironmentListPage`。
2.  点击“创建新环境”按钮，`zustand` store 更新状态，`CreateEnvironmentDialog` 模态框弹出。
3.  用户填写信息并提交。`useMutation` 触发 API 调用。提交后，无论成功失败，模态框都将关闭。
4.  若创建成功，`EnvironmentListPage` 的 `Table` 会因 `react-query` 的缓存失效而自动重新获取数据，新环境以 `pending` 状态出现在列表中。
5.  用户点击列表中任一环境的操作列中的“查看日志”按钮，页面跳转到详情页，`InstallationLogViewer` 组件挂载并开始接收实时日志。

---

## 5. 测试生成规则

- **Backend**: 每个路由一条 `test_ai_<name>.py`。
  ```python
  async def test_ai_create_env(client: AsyncClient) -> None:
      payload = {"ref": "main", "gpu": False, "devices": [], "display_name": "Test Env"}
      r = await client.post("/environments", json=payload)
      assert r.status_code == 201
      assert r.json()["env_id"]
  ```
- **Frontend**: 仅快照测试。`test_ai.snapshot.ts` 对 `CreateEnvironmentDialog` 和 `EnvironmentListPage` 的初始渲染进行快照，防止 UI 漂移。

---

## 6. 打包与体积门控

- PyInstaller `build.spec` 已锁 excludes: `['torch', 'tensorflow', 'matplotlib', 'pytest']`。
- CI 脚本 `ci_size_check.py` 检查体积：Windows ≤ 80 MB, macOS ≤ 75 MB。

---

## 7. 禁止清单（LLM 必须遵守）

1.  禁止升级任何依赖版本。
2.  禁止生成 `console.log` 或 `print` 语句。
3.  禁止在代码里出现 `torch` 等大型库的顶级 `import`。
4.  禁止前端使用 React 19 的新语法（如 `use` hook）。
5.  禁止后端路由直接 `raise Exception`，必须 raise 封装好的 `HTTPException`。
6.  禁止在 `tests/` 之外使用 `pytest.skip` 或 `vi.skip`。
7.  禁止把 `~/.leropilot` 硬编码成别的路径。
8.  禁止把 git/pip 命令暴露在同步函数里。
9.  禁止把 `EnvironmentService` 做成多例。
10. 禁止在前端硬编码 API 路径，必须通过生成的 `api.ts` 客户端调用。
11. 禁止在生成后“再补一段”——全部逻辑必须在本文件一次性描述完毕。

---

## 8. 最终交付物

运行 `python scripts/build.py` 后必须生成：

```
dist/
├── leropilot.exe      (≤ 80 MB)
├── leropilot          (macOS executable, ≤ 75 MB)
└── version.txt        ← 仅一行：3.1.0
```

---
