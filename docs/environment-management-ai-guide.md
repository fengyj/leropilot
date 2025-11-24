# LeRobot 环境管理功能 - AI 维护指引

> **目标读者**: 未来的 AI 助手或开发者，需要维护或扩展 LeRobot 环境管理功能
>
> **文档目的**: 提供完整的上下文、设计理念、实现细节和维护指导

---

## 1. 功能概述

### 1.1 核心功能

LeRoPilot 的环境管理功能允许用户：

- 创建和管理多个 LeRobot 开发环境
- 自动安装所有必需的工具和依赖
- 支持不同版本的 LeRobot、PyTorch 和 CUDA
- 提供图形化界面和高级命令行模式

### 1.2 关键设计理念

**零依赖、无 sudo、跨平台**

1. **零依赖**: 用户无需预装任何工具（Git、Python、FFmpeg 等）
2. **无 sudo**: 整个安装过程不需要管理员权限
3. **跨平台**: Windows、macOS、Linux 使用一致的逻辑
4. **版本隔离**: 每个环境独立，互不影响
5. **可恢复**: 安装失败后可以从中断点继续

### 1.3 架构约束

- **前端**: Electron (Web UI) + React + TypeScript
- **后端**: Python FastAPI
- **通信**: HTTP REST API + WebSocket (实时进度)
- **限制**: Python backend 无法直接与用户交互（无终端）

---

## 2. 工具管理策略

### 2.1 工具列表和策略

| 工具       | 用途              | 安装策略                    | 存储位置                             |
| ---------- | ----------------- | --------------------------- | ------------------------------------ |
| **UV**     | Python 包管理     | 打包内置                    | `{app_dir}/tools/uv/`                |
| **Git**    | 克隆 LeRobot 仓库 | 检测系统 → 下载预编译二进制 | `{data_dir}/tools/git-{version}/`    |
| **FFmpeg** | 视频处理          | 下载预编译二进制            | `{data_dir}/tools/ffmpeg-{version}/` |
| **Python** | 运行环境          | UV 自动下载                 | UV 管理                              |

### 2.2 为什么不检测系统 FFmpeg？

**设计决策**: 只检测系统 Git，不检测系统 FFmpeg

**原因**:

1. **版本冲突**: 用户升级系统 FFmpeg 可能导致 LeRobot 不兼容
2. **版本控制**: 程序完全控制 FFmpeg 版本，保证一致性
3. **libsvtav1 要求**: LeRobot 需要特定编码器支持
4. **高级模式**: 用户仍可通过编辑命令使用系统 FFmpeg

### 2.3 为什么检测系统 Git？

**设计决策**: 优先使用系统 Git

**原因**:

1. **常见工具**: Git 是开发者常用工具，大多数系统已安装
2. **节省空间**: 避免重复下载
3. **系统集成**: 系统 Git 可能配置了 SSH keys、credentials 等
4. **备选方案**: 如果系统没有，自动下载到程序目录

---

## 3. 版本管理

### 3.1 LeRobot 版本支持

**最低支持版本**: v0.3.3

**维护的版本元数据**:

- `docs/lerobot_versions.yaml`: 版本要求（Python、PyTorch、FFmpeg）
- `docs/lerobot_extras.yaml`: 可选依赖的中英文说明

**版本映射规则**:

- Release tags (v0.4.1, v0.4.0, v0.3.3) → 使用对应版本元数据
- 其他 tags/branches → 使用 main 分支元数据

### 3.2 如何添加新版本支持

**步骤**:

1. **查阅官方文档**

   - README: https://github.com/huggingface/lerobot/blob/v{version}/README.md
   - pyproject.toml: https://github.com/huggingface/lerobot/blob/v{version}/pyproject.toml

2. **更新版本元数据** (`docs/lerobot_versions.yaml`)

   ```yaml
   v0.5.0:
     release_date: "2025-xx-xx"
     python_version: "3.10+"
     pytorch_version: "2.3+"
     ffmpeg_version: "7.x"
     requires_libsvtav1: true
   ```

3. **更新 extras 元数据** (`docs/lerobot_extras.yaml`)

   - 检查 pyproject.toml 的 `[project.optional-dependencies]`
   - 添加新的 extras 或更新现有的
   - 提供中英文说明

4. **测试新版本**
   - 创建环境
   - 验证安装
   - 测试基本功能

### 3.3 FFmpeg 版本更新

**当 LeRobot 要求新的 FFmpeg 版本时**:

1. **更新版本元数据**

   ```yaml
   v0.5.0:
     ffmpeg_version: "8.x"
     ffmpeg_fallback: "8.0.1"
   ```

2. **更新 FFmpegManager**

   ```python
   SUPPORTED_VERSIONS = ["7.0.3", "7.1.3", "8.0.1"]
   DEFAULT_VERSION = "8.0.1"  # 更新默认版本
   ```

3. **测试下载和验证**

---

## 4. 关键实现细节

### 4.1 环境创建流程

```
1. 前置检查
   ├─ 配置文件存在？
   ├─ Repository 已下载？
   └─ 工具可用？(Git, UV, FFmpeg)

2. 用户输入
   ├─ 选择 Repository
   ├─ 选择版本 (Tags/Branches)
   ├─ 选择 CUDA 版本
   ├─ 选择 Extras
   └─ 配置环境名称

3. 安装步骤 (可恢复)
   ├─ Git checkout 版本
   ├─ 创建虚拟环境 (uv venv)
   ├─ 安装 PyTorch
   ├─ 安装 LeRobot (uv pip install -e .)
   ├─ 安装 Extras
   └─ 验证安装

4. 完成
   └─ 保存环境元数据到 environments.json
```

### 4.2 安装状态持久化

**文件**: `{data_dir}/environments/{env_id}/install_state.json`

**目的**: 支持安装失败后恢复

**结构**:

```json
{
  "environment_id": "uuid",
  "steps": [
    {
      "name": "checkout",
      "command": ["git", "checkout", "v0.4.1"],
      "status": "success",
      "output": "...",
      "retry_count": 0
    },
    {
      "name": "create_venv",
      "command": ["uv", "venv", "--python", "3.10", "..."],
      "status": "running",
      "output": "...",
      "retry_count": 1
    }
  ],
  "current_step": 1
}
```

**逻辑**:

- 每步开始前检查状态
- 如果已成功，跳过
- 如果失败，允许重试（最多 3 次）

### 4.3 高级模式实现

**设计**: Jupyter Notebook 风格的命令编辑界面

**UI**:

```
[1] 切换到版本 v0.4.1
┌─────────────────────────────────────┐
│ git checkout v0.4.1                 │
└─────────────────────────────────────┘
[执行]

[2] 创建虚拟环境
┌─────────────────────────────────────┐
│ uv venv --python 3.10 \             │
│   ~/.leropilot/environments/...     │
└─────────────────────────────────────┘
[执行]
```

**实现**:

- 前端: 可编辑的文本框
- 后端: 接收编辑后的命令并执行
- 安全: 用户对编辑负责，无限制

**用例**: 高级用户可以修改 FFmpeg 路径为系统版本

---

## 5. 常见维护任务

### 5.1 添加新的 Extras 分类

**场景**: LeRobot 添加了新的可选依赖类型

**步骤**:

1. **更新 extras 元数据** (`docs/lerobot_extras.yaml`)

   ```yaml
   v0.5.x:
     categories:
       new_category:
         title_zh: "新分类"
         title_en: "New Category"
         items:
           new_extra:
             name_zh: "新组件"
             name_en: "New Component"
             description_zh: "..."
             description_en: "..."
   ```

2. **更新前端 UI**

   - `frontend/src/components/environment-wizard.tsx`
   - 添加新分类的显示

3. **测试**
   - 创建环境时选择新 extra
   - 验证安装成功

### 5.2 支持新的 CUDA 版本

**场景**: PyTorch 发布了新的 CUDA 版本支持

**步骤**:

1. **更新 CUDA 检测逻辑** (`src/leropilot/managers/cuda_manager.py`)

   ```python
   if driver_ver >= "535.0":
       result["recommendation"] = "cu122"  # 新版本
   ```

2. **更新 UI 选项** (`frontend/src/components/cuda-selector.tsx`)

   ```tsx
   <option value="cu122">CUDA 12.2</option>
   ```

3. **更新 PyTorch 安装命令**
   ```python
   if cuda_version == "cu122":
       index_url = "https://download.pytorch.org/whl/cu122"
   ```

### 5.3 修复工具下载链接失效

**场景**: Git/FFmpeg 的下载链接变更

**步骤**:

1. **查找新的下载源**

   - Git: https://github.com/git-for-windows/git/releases
   - FFmpeg: https://github.com/BtbN/FFmpeg-Builds/releases

2. **更新下载 URL**

   - `src/leropilot/managers/git_manager.py`
   - `src/leropilot/managers/ffmpeg_manager.py`

3. **添加镜像源**

   ```python
   DOWNLOAD_MIRRORS = [
       "https://github.com/...",
       "https://ghproxy.com/https://github.com/...",
   ]
   ```

4. **测试下载**

---

## 6. 故障排查指南

### 6.1 环境创建失败

**症状**: 安装过程中断或失败

**排查步骤**:

1. **检查日志**

   - 位置: `{data_dir}/logs/environment_creation.log`
   - 查找错误信息

2. **检查安装状态**

   - 文件: `{data_dir}/environments/{env_id}/install_state.json`
   - 查看哪一步失败

3. **常见原因**:

   - 网络问题（下载超时）
   - 磁盘空间不足
   - Python 版本不兼容
   - PyTorch 下载失败

4. **解决方案**:
   - 重试安装（会从失败的步骤继续）
   - 更换 PyPI 镜像源
   - 检查磁盘空间
   - 检查网络连接

### 6.2 FFmpeg 验证失败

**症状**: FFmpeg 安装成功但验证失败

**排查步骤**:

1. **检查版本**

   ```bash
   ~/.leropilot/tools/ffmpeg-7.1.3/bin/ffmpeg -version
   ```

2. **检查 libsvtav1**

   ```bash
   ~/.leropilot/tools/ffmpeg-7.1.3/bin/ffmpeg -encoders | grep libsvtav1
   ```

3. **常见原因**:

   - 下载的 FFmpeg 版本不对
   - 缺少 libsvtav1 编码器
   - 二进制文件损坏

4. **解决方案**:
   - 删除并重新下载 FFmpeg
   - 使用备选版本（7.1.1）
   - 检查下载源

### 6.3 UV 创建虚拟环境失败

**症状**: `uv venv` 命令失败

**排查步骤**:

1. **检查 UV 版本**

   ```bash
   ~/.leropilot/tools/uv/uv --version
   ```

2. **检查 Python 可用性**

   ```bash
   uv python list
   ```

3. **常见原因**:

   - UV 版本过旧
   - Python 版本不可用
   - 磁盘空间不足

4. **解决方案**:
   - 更新 UV 版本
   - 手动安装 Python
   - 清理磁盘空间

---

## 7. 测试策略

### 7.1 单元测试

**覆盖范围**:

- 工具管理器（GitManager, FFmpegManager, UVManager）
- 环境管理器（EnvironmentManager）
- 版本解析和验证
- 配置管理

**示例**:

```python
# tests/managers/test_ffmpeg_manager.py
async def test_check_ffmpeg():
    manager = FFmpegManager(config)
    ffmpeg_path = await manager.check_ffmpeg()
    assert ffmpeg_path is not None
    assert ffmpeg_path.exists()

async def test_verify_ffmpeg():
    manager = FFmpegManager(config)
    is_valid = await manager.verify_ffmpeg(ffmpeg_path)
    assert is_valid is True
```

### 7.2 集成测试

**测试场景**:

- 完整的环境创建流程
- 安装失败后恢复
- 多个环境并存
- 环境删除和清理

**示例**:

```python
# tests/integration/test_environment_creation.py
async def test_create_environment_full_flow():
    config = EnvironmentCreateConfig(
        repository_id="official",
        lerobot_version="v0.4.1",
        cuda_version="cu121",
        extras=["aloha", "pusht"]
    )

    env = await environment_manager.create_environment(config)
    assert env.installation_status == "completed"
    assert env.path.exists()
```

### 7.3 手动测试清单

**每次发布前测试**:

- [ ] Windows 10/11: 创建环境（v0.4.1, CUDA 12.1, aloha）
- [ ] macOS (Intel): 创建环境（v0.4.0, CPU, pusht）
- [ ] macOS (Apple Silicon): 创建环境（v0.4.1, CPU, all）
- [ ] Linux (Ubuntu 22.04): 创建环境（v0.3.3, CUDA 11.8, smolvla）
- [ ] 中断安装后恢复
- [ ] 高级模式编辑命令
- [ ] 删除环境
- [ ] 多个环境切换

---

## 8. 性能优化建议

### 8.1 下载优化

**问题**: 大文件下载慢

**优化**:

1. **并行下载**: 同时下载多个工具
2. **断点续传**: 支持下载中断后继续
3. **镜像源**: 提供多个下载源
4. **缓存**: 缓存已下载的文件

### 8.2 安装优化

**问题**: PyTorch 安装慢

**优化**:

1. **PyPI 镜像**: 使用国内镜像（清华、阿里云）
2. **预下载**: 后台预下载常用版本
3. **进度显示**: 实时显示下载进度

### 8.3 UI 优化

**问题**: 长时间等待无反馈

**优化**:

1. **WebSocket**: 实时推送安装进度
2. **日志流**: 实时显示命令输出
3. **进度条**: 显示整体进度百分比

---

## 9. 安全考虑

### 9.1 下载验证

**建议**: 验证下载文件的完整性

**实现**:

```python
async def download_and_verify(url: str, target: Path, checksum: str) -> Path:
    """下载并验证文件"""
    await download_file(url, target)

    # 计算 SHA256
    sha256 = hashlib.sha256()
    with open(target, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)

    if sha256.hexdigest() != checksum:
        raise DownloadError("Checksum mismatch")

    return target
```

### 9.2 命令注入防护

**问题**: 高级模式允许用户编辑命令

**防护**:

1. **参数验证**: 验证命令参数格式
2. **路径检查**: 确保路径在允许的范围内
3. **日志记录**: 记录所有执行的命令

---

## 10. 未来扩展方向

### 10.1 环境模板

**功能**: 预定义的环境配置模板

**示例**:

```yaml
templates:
  - name: "ALOHA 开发环境"
    lerobot_version: "v0.4.1"
    cuda_version: "cu121"
    extras: ["aloha", "dynamixel", "intelrealsense"]

  - name: "PushT 仿真环境"
    lerobot_version: "v0.4.0"
    cuda_version: "cpu"
    extras: ["pusht"]
```

### 10.2 环境导出/导入

**功能**: 导出环境配置，在其他机器上重现

**格式**:

```json
{
  "name": "my-lerobot-env",
  "lerobot_version": "v0.4.1",
  "python_version": "3.10.12",
  "pytorch_version": "2.2.0",
  "cuda_version": "cu121",
  "extras": ["aloha", "pusht"],
  "custom_packages": ["numpy==1.24.0", "opencv-python==4.8.0"]
}
```

### 10.3 环境快照

**功能**: 保存环境状态，支持回滚

**实现**: 使用符号链接或虚拟环境克隆

---

## 11. 相关文档索引

### 11.1 设计文档

- `environment-creation-final-design.md`: 最终设计文档
- `environment-creation-implementation-plan.md`: 实现计划
- `ffmpeg_installation_strategy.md`: FFmpeg 安装策略
- `git_installation_strategy.md`: Git 安装策略

### 11.2 元数据文件

- `docs/lerobot_versions.yaml`: LeRobot 版本要求
- `docs/lerobot_extras.yaml`: Extras 中英文说明
- `docs/lerobot_version_research.md`: 版本研究总结

### 11.3 代码文件

**数据模型**:

- `src/leropilot/models/environment.py`

**管理器**:

- `src/leropilot/managers/git_manager.py`
- `src/leropilot/managers/uv_manager.py`
- `src/leropilot/managers/ffmpeg_manager.py`
- `src/leropilot/managers/environment_manager.py`

**API**:

- `src/leropilot/routers/environments.py`

**前端**:

- `frontend/src/pages/environments-page.tsx`
- `frontend/src/components/environment-wizard.tsx`
- `frontend/src/components/environment-installation.tsx`

---

## 12. 联系和支持

### 12.1 报告问题

**GitHub Issues**: https://github.com/yourusername/leropilot/issues

**问题模板**:

```markdown
**环境信息**:

- OS: Windows 11 / macOS 14 / Ubuntu 22.04
- LeRoPilot 版本: v1.0.0
- LeRobot 版本: v0.4.1

**问题描述**:
[详细描述问题]

**重现步骤**:

1. ...
2. ...

**日志**:
[粘贴相关日志]
```

### 12.2 贡献指南

**Pull Request 流程**:

1. Fork 项目
2. 创建功能分支
3. 实现功能并测试
4. 提交 PR 并描述变更

---

**文档版本**: v1.0
**创建日期**: 2024-11-24
**最后更新**: 2024-11-24
**维护者**: LeRoPilot Team
