# Environment Management Reference (for AI)

> This document is the authoritative guide for AI-driven maintenance, upgrade, and extension of the LeRoPilot environment management subsystem. It covers architecture, data flow, metadata, upgrade strategies, and code generation principles. Any code or metadata changes must conform to this specification.

---

## 1. Core Principles & Architecture

### 1.1 Goals
- Enable users to create, manage, and upgrade multiple isolated LeRobot environments.
- Support zero system dependencies, cross-platform (Windows/macOS/Linux), and no sudo required.
- Ensure version isolation, reproducibility, and robust error recovery.

### 1.2 System Structure
- **Backend**: Python (FastAPI), modular managers/services/models.
- **Frontend**: Electron + React + TypeScript, wizard UI for environment creation/management.
- **Communication**: REST API + WebSocket/SSE for real-time progress/log streaming.


### 1.3 Key Modules (Backend)
- `models/environment.py`: 环境配置与安装状态数据模型。
- `core/environment_service.py`: 环境目录、配置、生命周期管理、安装执行、计划生成。
- `core/environment_installer.py`: 安装计划生成、模板变量解析、平台适配。
- `core/config_loader.py`: 加载和解析安装步骤模板、依赖、版本配置（environment_installation_config.json）。
- `core/repo.py`: 仓库元数据提取、extras解析。
- `core/command_executor.py`: 命令执行、实时输出流、错误处理。
- `core/git_manager.py`: 仓库克隆、分支/标签管理。


## 2. Metadata Files & Auto-Generation



### 2.1 lerobot_versions.yaml
- 本文件是 AI 生成和维护环境管理相关代码的元数据参考，不直接被业务代码读取。
- 用于指导 AI 在 LeRobot 版本升级、依赖变更时如何自动生成/更新后端和前端代码。
- 内容包括支持的 LeRobot 版本、所需 Python/PyTorch/FFmpeg 版本、回退规则和安装说明。
- 映射 tags/branches 到基础版本以保证兼容性。

**自动生成流程**：
   1. 使用 `core/git_manager.py` 拉取所有 tags/branches。
   2. 用 `core/repo.py` 解析每个版本的 pyproject.toml，提取 requires-python、dependencies。
   3. 结合每个版本的 README 文档和 release notes，补充安装说明和特殊依赖。
   4. 自动生成/更新 lerobot_versions.yaml。
   5. 若 main 分支有更新，自动同步。

AI 后续维护和升级时，需优先从 lerobot_versions.yaml 获取各版本依赖和安装要求，再据此自动更新后端/前端相关代码（如依赖校验、安装流程、兼容性提示等）。


### 2.2 lerobot_extras.yaml
- 本文件是 AI 生成和维护环境管理相关代码的元数据参考，不直接被业务代码读取。
- 用于指导 AI 在 LeRobot extras 变更时如何自动生成/更新后端和前端代码（如前端选项、安装逻辑等）。
- 内容包括可选依赖（extras）分类及多语言描述。
- **自动生成流程**：
   1. 用 `core/repo.py` 解析 pyproject.toml 的 [project.optional-dependencies]，过滤掉 dev/test/doc/quality。
   2. 用 i18n_service 或官方文档补充多语言描述。
   3. 自动生成/更新 lerobot_extras.yaml，随 LeRobot release 同步。

### 2.3 environment_installation_config.json 结构与自动提取

`environment_installation_config.json` 定义了每个 LeRobot 版本在不同平台（darwin/linux/windows）下的安装步骤序列。

**文件结构**：
```json
{
  "repositories": {
    "official": {
      "versions": {
        "v0.4.1": {
          "python_version": ">=3.10",
          "torch_version": ">=2.2.1,<2.8.0",
          "compatibility_matrix": [
            { "torch": "2.7.1", "cuda": ["11.8", "12.6", "12.8"], "rocm": ["6.3"], "cpu": true, "is_recommended": true },
            { "torch": "2.7.0", "cuda": ["11.8", "12.6", "12.8"], "rocm": ["6.3"], "cpu": true, "is_recommended": false },
            { "torch": "2.6.0", "cuda": ["11.8", "12.4", "12.6"], "rocm": ["6.1", "6.2.4"], "cpu": true, "is_recommended": false }
          ],
          "darwin": [ /* 步骤数组 */ ],
          "linux": [ /* 步骤数组 */ ],
          "windows": [ /* 步骤数组 */ ]
        }
      }
    }
  }
}
```

**步骤定义（InstallStepTemplate）**：
- `id`: 步骤唯一标识符（如 `checkout_version`, `create_venv`, `ensure_ffmpeg`, `install_pytorch`, `install_lerobot`）
- `commands`: 命令数组（支持模板变量如 `{ref}`, `{venv_path}`, `{cache_dir}`, `{cuda_tag}` 等）

**自动生成流程**：
   1. 从 PyTorch 官方文档（https://pytorch.org/get-started/previous-versions/）获取准确的 CUDA/ROCm 版本兼容性矩阵
   2. 从 LeRobot upstream pyproject.toml 提取 `requires-python` 和 `torch` 版本约束：
      - **提取 torch_version**：在 `dependencies` 数组中查找以 `torch` 开头的条目
      - 使用正则表达式提取版本约束：`torch(>=[\d.]+),(<[\d.]+)`
      - **关键**：忽略分号后的平台条件（如 `;platform_machine==...`），只提取版本范围
      - 示例：从 `"torch>=2.2.1,<2.8.0"` 提取 `>=2.2.1,<2.8.0`
   3. 生成 `compatibility_matrix` 数组：
      - 覆盖 `torch_version` 约束范围内的**所有** PyTorch 版本（不能遗漏任何版本）
      - 每个条目包含：`torch`（版本号）、`cuda`（兼容版本数组）、`rocm`（兼容版本数组）、`cpu`（布尔值）、`is_recommended`（布尔值）
      - **推荐逻辑**：只有最新的 PyTorch 版本设置 `is_recommended: true`，其他所有版本必须为 `false`
      - 示例：若 torch_version 为 `>=2.2.1,<2.8.0`，则必须包含 2.2.1, 2.2.2, 2.3.0, 2.3.1, 2.4.0, 2.4.1, 2.5.0, 2.5.1, 2.6.0, 2.7.0, 2.7.1（共 11 个版本）
   4. 根据平台差异生成不同的命令序列：
      - **FFmpeg 安装**：缓存解压后的文件到 `{cache_dir}/tools/ffmpeg-{version}`，复制可执行文件到虚拟环境的 bin（macOS/Linux）或 Scripts（Windows）目录
      - **PyTorch 安装**：macOS 使用默认源，Linux/Windows 使用 `--index-url` 指定 CUDA/ROCm 标签
   5. **一致性要求**：所有版本配置（v0.4.1、v0.4.0、v0.3.3、main）必须使用相同的推荐逻辑和完整的版本覆盖
   6. 新版本或 main 分支有更新时，自动同步

**关键约束**：
- **compatibility_matrix 完整性**：必须覆盖 `torch_version` 约束范围内的所有 PyTorch 版本，不能遗漏任何版本
- **推荐逻辑一致性**：在所有版本配置（v0.4.1、v0.4.0、v0.3.3、main）中，只有最新的 PyTorch 版本（如 2.7.1）设置 `is_recommended: true`
- **版本数据来源**：CUDA/ROCm 兼容性必须从 PyTorch 官方文档获取，不能臆造或猜测
- 每个平台（darwin/linux/windows）的步骤独立定义，不使用"common"共享节
- FFmpeg 采用三级缓存策略：下载缓存 → 全局解压 → 环境特定复制


## 3. Environment Lifecycle & Data Flow


### 3.1 Creation Flow
1. 预检查：配置文件存在、仓库已下载（FFmpeg、Python 可按需自动下载，无需提前准备）。
2. 用户输入：选择仓库、版本、extras、环境名称。CUDA 版本由后台检测并推荐（见下文"CUDA 检测与推荐策略"），用户可选择覆盖但会收到兼容性提示。
3. 安装步骤（可恢复）：
   - 步骤定义由 `environment_installation_config.json` 的平台特定节（darwin/linux/windows）决定
   - 典型步骤序列：
     1. **checkout_version**: 切换到指定的 git ref（tag/branch/commit）
     2. **create_venv**: 使用 uv 创建虚拟环境（指定 Python 版本）
     3. **ensure_ffmpeg**:
        - 检查 `{cache_dir}/tools/ffmpeg-{version}` 是否存在
        - 不存在则下载到临时位置并解压到缓存
        - 复制 ffmpeg/ffprobe 可执行文件到虚拟环境的 bin/Scripts 目录
        - 设置可执行权限（Unix）
     4. **install_pytorch**: 安装 PyTorch 和 torchvision（带 CUDA/ROCm 标签）
     5. **install_lerobot**: 安装 LeRobot 本体及选定的 extras
4. 持久化环境配置和安装状态到 `{data_dir}/environments/{env_id}/`。

**FFmpeg 三级缓存策略**：
- **下载缓存**：`{cache_dir}/tools/ffmpeg-{version}/` - 解压后的完整目录（只解压一次）
- **虚拟环境**：`{venv_path}/bin/` 或 `{venv_path}/Scripts/` - 仅复制 ffmpeg/ffprobe 可执行文件
- 优势：避免重复下载和解压，每个环境独立隔离，删除环境时一并删除

### 3.1.1 安装步骤更新与新版本适配

本节描述的是 AI 代码维护/升级阶段的自动化流程（即开发者或 AI 发现 LeRobot 有新发布时，自动抓取和更新相关代码），而非程序运行时的用户操作。

当 LeRobot 仓库有新版本发布或 main 分支有更新时，AI需：
   1. AI 无需本地拉取仓库，可直接访问 GitHub，抓取各版本的 README、pyproject.toml、release notes 等文件，自动更新元数据和相关代码。
   2. 解析 pyproject.toml，提取依赖和 extras。
   3. 更新 lerobot_versions.yaml、lerobot_extras.yaml。
   4. 生成/更新 environment_installation_config.json，定义新版本的安装步骤。
   5. 自动更新后端/前端相关代码（如依赖校验、安装流程、兼容性提示等）。
   6. 校验和测试新流程。

   ### 3.1.2 CUDA 检测与推荐策略

   说明：CUDA 版本不应由用户随意选择。安装 PyTorch 时关键是宿主机 GPU 驱动与 PyTorch wheel 的兼容性（driver >= wheel 要求），而非本机是否安装完整的 CUDA Toolkit。AI 在维护/升级阶段应生成并记录推荐策略，运行时代码负责实际检测与提示。

   检测与决策流程（维护文档指导）:
   - 后端运行时检测（由运行时代码在用户机器上执行）：
     1. 尝试使用 `nvidia-smi` 读取 GPU 与 driver 版本；若失败，可尝试 `py3nvml` 或系统检测方法。
     2. 根据 driver 版本映射到支持的 CUDA runtime（使用项目维护的 driver→CUDA 映射表）。
     3. 决策：若 driver 满足 GPU 模式则推荐对应 `cuXXX`；否则推荐 `cpu`（CPU-only）。

   伪码（供 AI 参考并纳入文档或工具实现）：
   ```
   def detect_cuda_recommendation():
      if run('nvidia-smi') succeeds:
         driver = parse_driver_version()
         cuda_candidate = map_driver_to_cuda(driver)
         if cuda_candidate:
            return {'mode':'gpu','cuda':cuda_candidate,'driver':driver}
      return {'mode':'cpu','cuda':None,'driver':None}

   rec = detect_cuda_recommendation()
   if rec['mode']=='gpu':
      torch_pkg = select_torch_pkg_for_cuda(rec['cuda'])
   else:
      torch_pkg = select_cpu_torch_pkg()
   ```

   UI 文案建议（在环境创建/向导中显示）:
   - 自动推荐: “检测到 NVIDIA GPU (driver {ver})，推荐使用 PyTorch + CUDA {cuda}。若需手动覆盖，选择“自定义”，但请注意可能不兼容。”
   - 不支持 GPU: “未检测到可用 GPU 或驱动版本不足，建议安装 CPU-only 版本或升级驱动。”

   何时提示用户/何时要求人工操作:
   - 若检测到驱动版本低于推荐值：提示“驱动过旧，需升级或选择 CPU-only”；不要在 AI 自动流程内尝试安装或升级宿主机驱动。
   - 若用户强制覆盖 CUDA 选择：记录覆盖理由并在安装日志/PR 中标注风险说明。

   Metadata 与文档要求：
   - 在 `docs/lerobot_versions.yaml` 为每个 LeRobot 版本记录推荐的 PyTorch + 最低 driver 要求或兼容的 CUDA runtime，便于 AI 自动匹配。
   - 在 `environment-management-reference.md` 和前端文档明确“系统检测 + 推荐”原则，避免误导用户以为可以随意选择 CUDA。


### 3.2 Install State Persistence
- `{data_dir}/environments/{env_id}/install_state.json` records each step, status, output, and retry count.
- Enables recovery from failed/partial installations.

### 3.3 Version Management
- Always support minimum version (see lerobot_versions.yaml).
- When LeRobot releases new versions/tags, update metadata and validate compatibility.
- Fallback to main branch config for unknown tags/branches.

---

## 4. Tool Management Strategy

### 4.0 工具管理概览
- **FFmpeg**：从官方源下载，缓存解压后的文件，复制到虚拟环境
- **Python**：由 UV 自动管理（根据 `python_version` 约束）
- **PyTorch**：根据检测到的 CUDA/ROCm 版本选择合适的 wheel index
- **依赖包**：按 `environment_installation_config.json` 的 `commands` 数组自动安装
- **UV、Git**：系统工具，安装和配置见 config 文档

### 4.0.1 FFmpeg 安装策略详解

**版本管理**：
- 当前使用版本：7.1.3（支持 libsvtav1）
- 版本信息存储在 `environment_installation_config.json` 的 `ensure_ffmpeg` 步骤的命令中

**平台特定下载源**：
- **macOS**: https://evermeet.cx/ffmpeg/getrelease/ffmpeg/7z (.7z 格式)
- **Linux**: https://github.com/BtbN/FFmpeg-Builds/releases (.tar.xz 格式)
- **Windows**: https://github.com/BtbN/FFmpeg-Builds/releases (.zip 格式)

**安装流程（三步缓存）**：
1. **检查并下载**：
   - 检查 `{cache_dir}/tools/ffmpeg-7.1.3` 是否存在
   - 不存在则下载压缩包到 `/tmp/ffmpeg.*`
   - 解压到 `{cache_dir}/tools/ffmpeg-7.1.3`
   - 删除临时压缩包

2. **复制到虚拟环境**：
   - **macOS/Linux**: 复制 `ffmpeg` 和 `ffprobe` 到 `{venv_path}/bin/`
   - **Windows**: 复制 `ffmpeg.exe` 和 `ffprobe.exe` 到 `{venv_path}\Scripts\`
   - **Unix**: 执行 `chmod +x` 设置可执行权限

3. **验证**：
   - 运行 `ffmpeg -version` 验证安装
   - 运行 `ffmpeg -encoders` 检查 libsvtav1 支持

**目录结构**：
```
{data_dir}/
├── cache/
│   └── ffmpeg-7.1.3/        # 解压后的完整目录
│       ├── ffmpeg           # macOS: 直接
│       ├── ffprobe
│       └── bin/             # Linux/Windows: bin子目录
│           ├── ffmpeg
│           └── ffprobe
└── environments/
    └── {env_id}/
        └── .venv/
            ├── bin/         # macOS/Linux
            │   ├── ffmpeg   # 从cache复制
            │   └── ffprobe
            └── Scripts/     # Windows
                ├── ffmpeg.exe
                └── ffprobe.exe
```

#### 4.1 `environment_extra_dependencies.json` 格式与 AI 更新流程

- 目标：为运行时代码提供稳定、可验证的外部二进制（如 FFmpeg）来源；为 AI 提供维护时更新这些来源的明确流程。
- 文件位置：`src/leropilot/resources/environment_extra_dependencies.json`。

- 推荐的数据结构（概念）：

   - 顶层键按工具名（例如 `ffmpeg`）划分。
   - 每个工具按操作系统/平台组织：`windows` / `linux` / `darwin`。
   - 每个平台按架构或通用标签组织（例如 `amd64`、`x86_64`、`universal`）。
   - 每个架构下以版本为键，值包含至少 `{ "url", "filename" (可选), "source", "sha256" (可选), "notes" }`。

   示例（简化）：

   ```json
   {
      "ffmpeg": {
         "linux": {
            "x86_64": {
               "7.1.1": {
                  "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/<tag>/ffmpeg-7.1.1-linux64-gpl.tar.xz",
                  "filename": "ffmpeg-7.1.1-linux64-gpl.tar.xz",
                  "source": "BtbN/FFmpeg-Builds",
                  "sha256": "..."
               },
               "latest": { "url": "https://.../latest/ffmpeg-master-latest-linux64-gpl.tar.xz" }
            }
         },
         "darwin": {
            "universal": {
               "7.1.3": { "url": "https://evermeet.cx/pub/ffmpeg/7.1.3/ffmpeg.zip", "sha256": "..." }
            }
         }
      }
   }
   ```

- 维护（AI/开发者）责任与步骤：

   1. 从 `docs/lerobot_versions.yaml` 读取目标 LeRobot 版本的 `ffmpeg_version` 与 `ffmpeg_fallback`（维护阶段的事实来源）。
   2. 对于 BtbN（Windows/Linux）：使用 GitHub Releases API 检索目标 release tag 与 asset 列表，匹配 `asset_name`（或使用 `checksums.sha256` 文件匹配），获取 `browser_download_url` 与 `sha256`（若可得）。
   3. 对于 macOS（Evermeet）：抓取 `https://evermeet.cx/pub/ffmpeg/` 列表或使用已知 `pub_pattern`（`https://evermeet.cx/pub/ffmpeg/{version}/ffmpeg.zip`）构建 URL，下载并计算 `sha256`。
   4. 将解析到的具体版本条目写入 `src/leropilot/resources/environment_extra_dependencies.json`，字段至少包含 `url`、`filename`、`source`（例如 `BtbN/FFmpeg-Builds` 或 `evermeet.cx`）、以及可选的 `sha256`。保持 `latest` 指向 release 的示例或 API 路径以便快速回滚/调试。
   5. 运行仓库内的 FFmpeg 相关单元测试（如 `tests/managers/test_ffmpeg_manager.py`），并本地验证下载/校验/解压流程。若测试通过，提交 PR（包含更改的 JSON、更新的测试或解析脚本），并在 PR 描述中标注来源与校验信息（tag、asset 名、sha256）。

- 运行时（后端）责任：

   - FFmpeg 的安装现在完全通过 `environment_installation_config.json` 中的平台特定命令处理（`ensure_ffmpeg` 步骤）：
      - 检查缓存目录 `{cache_dir}/tools/ffmpeg-7.1.3` 是否存在
      - 若不存在，下载并解压到缓存目录（从 BtbN/FFmpeg-Builds 或 evermeet.cx）
      - 从缓存目录复制 `ffmpeg` 和 `ffprobe` 到虚拟环境的 `bin/` 或 `Scripts/` 目录
      - 设置可执行权限
   - 所有操作通过 shell 命令执行，由 `InstallationExecutor` 统一处理，无需专门的 FFmpeg 管理类

- 额外要点：

   - 保持 `environment_extra_dependencies.json` 为可审计、可回滚的单一事实源（AI 提交时应包含 tag/asset/sha），避免运行时代码去直接解析 upstream 的非确定性页面。
   - 对于自动解析 GitHub Releases，优先使用 GitHub API（带 `If-Modified-Since` / ETag）以减少频繁请求；解析后再将确定的 asset URL 和 sha 固化到 JSON 并提交 PR。若无法取得 sha，则在 PR 中列出校验策略并在 CI 中增加下载并校验步骤。
   - 对于镜像策略，运行时代码应支持 `GITHUB_MIRRORS` 或替代域名（参见 `docs/ffmpeg_installation_strategy.md` 的下载镜像段落）。

此节旨在把 `environment_extra_dependencies.json` 的格式与维护流程写入 AI 参考文档，使 AI 在发现 LeRobot 新版本或 FFmpeg 要求变化时，能按照步骤解析 upstream、选择合适二进制、校验并安全地更新资源清单和安装逻辑。


## 5. Error Handling & Recovery
- All install steps are atomic and recoverable; failed steps can be retried up to 3 times.
- All command outputs (stdout/stderr) are logged and streamed to frontend.
- Common failure causes: network, disk space, version incompatibility.
- Recovery: retry, switch mirrors, clean disk, update drivers.

---

## 6. Upgrade & Maintenance Workflow


### 6.1 LeRobot 升级/新版本适配
1. **获取版本信息**：
   - 直接访问 GitHub API 获取 LeRobot 仓库的所有 tags 和 branches
   - 示例：`https://api.github.com/repos/huggingface/lerobot/tags`

2. **解析依赖**：
   - 获取各版本的 pyproject.toml：`https://raw.githubusercontent.com/huggingface/lerobot/{ref}/pyproject.toml`
   - 提取 `requires-python`（如 `>=3.10`）
   - **提取 torch 版本约束**：
     - 在 `dependencies` 数组中查找以 `torch` 开头的条目（可能包含平台条件，如 `torch>=2.2.1,<2.8.0 ; ...`）
     - 使用正则表达式提取版本约束部分：`torch(>=[\d.]+),(<[\d.]+)`
     - **关键**：忽略分号后的平台条件（如 `;platform_machine==...`），只提取版本范围
     - 示例：从 `"torch>=2.2.1,<2.8.0"` 提取 `>=2.2.1,<2.8.0`
     - **验证**：解析后与原始文件内容对比，确保准确性；记录来源 commit SHA
   - 提取 `torchvision` 版本约束（用于验证兼容性）
   - 提取 `[project.optional-dependencies]` 中的所有 extras

3. **确定 CUDA/ROCm 兼容性**：
   - 访问 PyTorch 官方版本页面：`https://pytorch.org/get-started/previous-versions/`
   - 根据 torch 版本约束，确定支持的 CUDA 和 ROCm 精确版本列表
   - 示例：torch 2.2.x 支持 CUDA ["11.8", "12.1"]，ROCm ["5.6", "5.7"]

4. **更新 environment_installation_config.json**：
   - 为新版本添加配置节，包含：
     - `python_version`：从 pyproject.toml 提取（如 `>=3.10`）
     - `torch_version`：从 pyproject.toml 提取（如 `>=2.2.1,<2.8.0`）
       - **提取方法**：在 `dependencies` 数组中查找 `torch` 条目，提取版本约束，忽略平台条件
     - `compatibility_matrix`：完整的 PyTorch 版本兼容性矩阵
       - **覆盖范围**：必须包含 `torch_version` 约束范围内的所有版本（如 2.2.1 到 2.7.1）
       - **数据来源**：从 PyTorch 官方文档获取每个版本支持的 CUDA/ROCm 版本
       - **推荐标记**：只有最新版本（如 2.7.1）设置 `is_recommended: true`
       - **一致性检查**：确保所有版本配置（v0.4.1、v0.4.0、v0.3.3、main）使用相同的推荐逻辑
     - `darwin`/`linux`/`windows`：平台特定的安装步骤数组
   - **验证步骤**：
     - 使用 `grep` 搜索 `"is_recommended": true`，确保只有目标版本被标记
     - 统计每个配置节的 `compatibility_matrix` 长度，确保覆盖完整
     - 对比 torch_version 范围与 compatibility_matrix 内容，确保无遗漏

5. **更新 i18n.json**：
   - 检查新增/移除的 extras
   - 为新 extras 添加英文和中文名称、描述
   - 分配合适的 category（motors/robots/policies/features/simulation）

6. **更新元数据文件**：
   - 更新 `docs/lerobot_versions.yaml`（AI 参考）
   - 更新 `docs/lerobot_extras.yaml`（AI 参考）

7. **验证和测试**：
   - 运行单元测试确保配置解析正确
   - 在各平台测试新版本的环境创建流程
   - 验证 FFmpeg、PyTorch、LeRobot 安装成功

### 6.2 Extras 变更处理

**检测变更**：
1. 对比新旧版本 pyproject.toml 的 `[project.optional-dependencies]`
2. 识别新增、移除、修改的 extras

**更新 i18n.json**：
1. 为新增 extras 添加条目：
   ```json
   "extra_name": {
     "name": { "en": "Name", "zh": "名称" },
     "description": { "en": "Description", "zh": "描述" },
     "category": "motors|robots|policies|features|simulation"
   }
   ```

2. 分类参考：
   - **motors**: 电机驱动（dynamixel, feetech）
   - **robots**: 机器人平台和硬件（gamepad, hopejr, lekiwi, reachy2, kinematics, intelrealsense, phone）
   - **policies**: 策略和模型（pi, smolvla, groot, hilserl）
   - **features**: 功能特性（async）
   - **simulation**: 仿真环境（aloha, pusht, xarm, libero, metaworld）

**验证**：
- 检查 extras 在前端是否正确显示
- 测试安装包含新 extras 的环境
- 验证错误处理（不存在的 extras）

### 6.3 工具版本升级

**FFmpeg 版本升级**：
1. 确定新版本号（如从 7.1.3 升级到 7.2.0）
2. 更新 `environment_installation_config.json` 中所有平台的 `ensure_ffmpeg` 步骤：
   - 修改下载 URL 中的版本号
   - 修改缓存目录名称
   - 更新解压后的目录名称
3. 验证新版本在各平台的可用性：
   - macOS: https://evermeet.cx/ffmpeg/
   - Linux/Windows: https://github.com/BtbN/FFmpeg-Builds/releases
4. 测试下载、解压、安装、验证流程

**Python 版本支持**：
- Python 版本由 LeRobot 的 `requires-python` 决定
- UV 自动管理 Python 安装
- 只需更新 `python_version` 字段


## 7. Data Models & API Contracts
- All environment configs must include: repo_url, ref, python_version, torch_version, cuda_version, extras, display_name, created_at, status.
- API endpoints must conform to: create/list/delete environment, stream install logs, query status.
- All error responses must include code, message, and details.

---

## 8. Security & Compliance
- Never hardcode secrets; always use env vars or config files.
- Validate and sanitize all user inputs.
- Never log sensitive data.
- Use parameterized commands for all shell/script execution.

---

## 9. Testing & Validation
- All new/changed code must have unit and integration tests.
- Test environment creation, upgrade, recovery, and error scenarios on all platforms.
- Validate metadata auto-generation against upstream LeRobot repo.

---

## 10. Key Files and Their Roles

### 10.1 配置和元数据文件

| 文件 | 位置 | 用途 | 维护方式 |
|------|------|------|----------|
| `environment_installation_config.json` | `src/leropilot/resources/` | 定义每个 LeRobot 版本在各平台的安装步骤序列 | AI 自动生成/更新，基于 upstream pyproject.toml |
| `i18n.json` | `src/leropilot/resources/` | 安装步骤和 extras 的多语言显示名称和描述 | AI 根据 pyproject.toml extras 更新 |
| `lerobot_versions.yaml` | `docs/` | AI 参考：各版本的依赖要求、安装说明（不被运行时代码读取） | AI 维护 |
| `lerobot_extras.yaml` | `docs/` | AI 参考：extras 的分类和描述（不被运行时代码读取） | AI 维护 |
| `environment_extra_dependencies.json` | `src/leropilot/resources/` | 外部二进制（如 FFmpeg）的下载源和校验信息 | AI 解析 upstream releases 更新 |

### 10.2 运行时数据文件

| 文件 | 位置 | 内容 |
|------|------|------|
| `environment.json` | `{data_dir}/environments/{env_id}/` | 环境配置（版本、extras、路径等） |
| `install_state.json` | `{data_dir}/environments/{env_id}/` | 安装步骤状态、输出、重试次数 |
| `.venv/` | `{data_dir}/environments/{env_id}/` | 虚拟环境目录 |

### 10.3 缓存目录结构

```
{data_dir}/
├── cache/
│   └── ffmpeg-7.1.3/        # 解压后的 FFmpeg（共享）
├── tools/                    # （已废弃，使用 cache）
└── environments/
    └── {env_id}/
        ├── environment.json
        ├── install_state.json
        └── .venv/
            ├── bin/         # macOS/Linux
            │   ├── python
            │   ├── ffmpeg   # 从 cache 复制
            │   └── ffprobe
            └── Scripts/     # Windows
                ├── python.exe
                ├── ffmpeg.exe
                └── ffprobe.exe
```

## 11. References

- [lerobot_versions.yaml](./lerobot_versions.yaml) - AI 参考：版本依赖和安装要求（基于真实仓库数据）
- [lerobot_extras.yaml](./lerobot_extras.yaml) - AI 参考：Extras 分类和描述（基于真实仓库数据）
- [ffmpeg_installation_strategy.md](../ffmpeg_installation_strategy.md) - FFmpeg 安装策略详解
- [system-design.md](../spec/system-design.md) - 系统架构设计
- [environment-management.md](../spec/environment-management.md) - 环境管理详细规范

## 12. Changelog

### 2025-11-26
- 添加 `compatibility_matrix` 字段，替代简单的 `cuda_versions` 和 `rocm_versions` 数组
- 明确推荐逻辑：只有最新 PyTorch 版本设置 `is_recommended: true`
- 添加完整性要求：`compatibility_matrix` 必须覆盖 `torch_version` 约束范围内的所有版本
- 添加一致性要求：所有版本配置（v0.4.1、v0.4.0、v0.3.3、main）必须使用相同的推荐逻辑
- 详细说明 `torch_version` 提取方法：忽略平台条件，只提取版本范围
- 添加验证步骤：使用 grep 和长度统计确保配置正确性

### 2025-11-25
- 更新 FFmpeg 安装策略为三级缓存（下载缓存 → 虚拟环境复制）
- 明确 `environment_installation_config.json` 使用平台特定步骤（无 common 节）
- 更新 `cuda_versions` 和 `rocm_versions` 为精确版本数组
- 扩展 `i18n.json` extras 列表，覆盖所有 LeRobot 支持的可选依赖
- 添加详细的版本升级和 extras 变更处理流程

---

**Version:** 2025-11-26
**Maintainer:** LeRoPilot Team
