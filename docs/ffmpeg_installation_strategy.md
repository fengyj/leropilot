# FFmpeg 安装策略（最终版）

## 设计原则

1. **仅安装到程序目录** - 避免系统版本冲突
2. **不检测系统 FFmpeg** - 简化逻辑，保证一致性
3. **不需要 sudo 权限** - 适配 Electron + Python Backend 架构
4. **所有平台一致** - 统一的安装和管理方式

## 架构考虑

本项目架构：

```
Frontend (Electron/Web UI)
    ↓ HTTP API
Backend (Python FastAPI)
    ↓ 执行命令
System
```

**关键约束**:

- Python backend 执行命令时无法直接与用户交互
- 需要 sudo 的操作难以处理密码输入
- **解决方案**: 完全避免 sudo，所有工具安装到程序目录

## 版本要求

根据 LeRobot 官方文档：

- **推荐版本**: FFmpeg 7.x (7.0.x, 7.1.x, 7.2.x)
- **关键要求**: 支持 libsvtav1 编码器
- **兼容版本**: FFmpeg 8.x 也支持

## 安装流程

### 1. 检测阶段

```python
async def check_ffmpeg() -> Optional[Path]:
    """检查程序目录中的 FFmpeg"""
    tools_dir = config.paths.data_dir / "tools"

    # 查找所有 ffmpeg-* 目录，按版本降序
    ffmpeg_dirs = sorted(
        tools_dir.glob("ffmpeg-*"),
        key=lambda p: parse_version(p.name),
        reverse=True
    )

    for ffmpeg_dir in ffmpeg_dirs:
        ffmpeg_bin = ffmpeg_dir / "bin" / "ffmpeg"
        if platform.system() == "Windows":
            ffmpeg_bin = ffmpeg_bin.with_suffix(".exe")

        if ffmpeg_bin.exists():
            # 验证版本和 libsvtav1 支持
            if await verify_ffmpeg(ffmpeg_bin):
                return ffmpeg_bin

    return None  # 需要安装
```

### 2. 下载源

| 平台        | 下载源                                         | 格式    |
| ----------- | ---------------------------------------------- | ------- |
| **Windows** | https://github.com/BtbN/FFmpeg-Builds/releases | .zip    |
| **macOS**   | https://evermeet.cx/ffmpeg/                    | .7z     |
| **Linux**   | https://github.com/BtbN/FFmpeg-Builds/releases | .tar.xz |

**版本选择**:

- 优先下载 7.1.x 系列（稳定且支持 libsvtav1）
- 备选 7.0.x 或 8.0.x

### 3. 安装步骤

```python
async def install_ffmpeg(version: str = "7.1.3") -> Path:
    """安装 FFmpeg 到程序目录"""
    platform_name = platform.system().lower()
    target_dir = config.paths.data_dir / "tools" / f"ffmpeg-{version}"

    if target_dir.exists():
        logger.info(f"FFmpeg {version} already installed")
        return target_dir / "bin" / "ffmpeg"

    # 1. 下载
    download_url = get_download_url(platform_name, version)
    archive_file = await download_file(download_url, target_dir.parent)

    # 2. 解压
    await extract_archive(archive_file, target_dir)

    # 3. 验证
    ffmpeg_bin = target_dir / "bin" / "ffmpeg"
    if not await verify_ffmpeg(ffmpeg_bin):
        raise InstallationError("FFmpeg installation failed verification")

    # 4. 清理
    archive_file.unlink()

    return ffmpeg_bin
```

### 4. 验证安装

```python
async def verify_ffmpeg(ffmpeg_path: Path) -> bool:
    """验证 FFmpeg 安装"""
    try:
        # 检查版本
        version_output = await run_command(
            [str(ffmpeg_path), "-version"],
            capture_output=True
        )
        version = parse_ffmpeg_version(version_output)

        if version[0] not in [7, 8]:  # 主版本必须是 7 或 8
            logger.warning(f"FFmpeg version {version} not supported")
            return False

        # 检查 libsvtav1
        encoders_output = await run_command(
            [str(ffmpeg_path), "-encoders"],
            capture_output=True
        )

        if "libsvtav1" not in encoders_output:
            logger.warning("FFmpeg does not support libsvtav1")
            return False

        return True
    except Exception as e:
        logger.error(f"FFmpeg verification failed: {e}")
        return False
```

## 目录结构

```
{data_dir}/
  └── tools/
      ├── ffmpeg-7.1.3/          ← 当前使用
      │   ├── bin/
      │   │   ├── ffmpeg(.exe)
      │   │   ├── ffplay(.exe)
      │   │   └── ffprobe(.exe)
      │   ├── doc/
      │   ├── presets/
      │   └── version.txt
      ├── ffmpeg-7.0.3/          ← 旧版本（可选保留）
      └── uv/
          └── uv(.exe)
```

## 版本管理

### 配置文件

```yaml
# config.yaml
tools:
  ffmpeg:
    current_version: "7.1.3"
    path: "/home/user/.leropilot/tools/ffmpeg-7.1.3/bin/ffmpeg"
```

### 多版本共存

- 允许保留多个版本
- 配置文件指定当前使用的版本
- 用户可以在设置中切换版本

### 升级策略

```python
async def upgrade_ffmpeg(new_version: str) -> None:
    """升级 FFmpeg"""
    # 1. 下载新版本
    new_path = await install_ffmpeg(new_version)

    # 2. 更新配置
    config.tools.ffmpeg.current_version = new_version
    config.tools.ffmpeg.path = str(new_path)
    save_config(config)

    # 3. (可选) 删除旧版本
    # 保留最近 2 个版本
    cleanup_old_ffmpeg_versions(keep=2)
```

## UI 流程

### 安装提示

```
┌─────────────────────────────────────────┐
│ 需要安装 FFmpeg                         │
├─────────────────────────────────────────┤
│                                         │
│ LeRobot 需要 FFmpeg 7.x 进行视频处理    │
│                                         │
│ 安装位置:                               │
│ ~/.leropilot/tools/ffmpeg-7.1.3/        │
│                                         │
│ 下载大小: ~80 MB                        │
│ 预计耗时: 2-5 分钟                      │
│                                         │
│ ✓ 无需管理员权限                        │
│ ✓ 不影响系统 FFmpeg                     │
│                                         │
│     [开始安装]  [取消]                  │
└─────────────────────────────────────────┘
```

### 安装进度

```
┌─────────────────────────────────────────┐
│ 正在安装 FFmpeg 7.1.3                   │
├─────────────────────────────────────────┤
│                                         │
│ ✓ 下载 FFmpeg                           │
│   ffmpeg-7.1.3-linux64-gpl.tar.xz       │
│   80.5 MB / 80.5 MB                     │
│                                         │
│ ⏳ 解压文件...                          │
│   Extracting to ~/.leropilot/tools/...  │
│   [████████████░░░░░░░░] 65%            │
│                                         │
│ ⏸ 验证安装                             │
│                                         │
└─────────────────────────────────────────┘
```

### 安装完成

```
┌─────────────────────────────────────────┐
│ ✓ FFmpeg 安装成功                       │
├─────────────────────────────────────────┤
│                                         │
│ 版本: FFmpeg 7.1.3                      │
│ 路径: ~/.leropilot/tools/ffmpeg-7.1.3/  │
│ libsvtav1: ✓ 支持                       │
│                                         │
│              [继续]                      │
└─────────────────────────────────────────┘
```

## 高级模式支持

虽然不检测系统 FFmpeg，但高级用户仍可以使用系统版本：

### 方式 1: 编辑安装命令

在高级安装模式中，用户可以编辑命令中的 FFmpeg 路径：

```bash
# 默认（程序目录）
~/.leropilot/tools/ffmpeg-7.1.3/bin/ffmpeg -i input.mp4 ...

# 用户可以修改为系统路径
/usr/local/bin/ffmpeg -i input.mp4 ...
```

### 方式 2: 配置文件

用户可以手动编辑配置文件：

```yaml
# config.yaml
tools:
  ffmpeg:
    type: "custom" # 改为 custom
    path: "/usr/local/bin/ffmpeg" # 指定系统路径
```

## 下载镜像（国内网络）

### GitHub Releases 镜像

```python
GITHUB_MIRRORS = [
    "https://github.com",  # 官方
    "https://ghproxy.com/https://github.com",  # 镜像 1
    "https://mirror.ghproxy.com/https://github.com",  # 镜像 2
]

async def download_with_mirrors(url: str, target: Path) -> Path:
    """使用镜像下载"""
    for mirror in GITHUB_MIRRORS:
        try:
            mirrored_url = url.replace("https://github.com", mirror)
            return await download_file(mirrored_url, target)
        except Exception as e:
            logger.warning(f"Failed to download from {mirror}: {e}")
            continue

    raise DownloadError("All mirrors failed")
```

## 实现代码示例

### FFmpegManager

```python
class FFmpegManager:
    """FFmpeg 安装和管理"""

    SUPPORTED_VERSIONS = ["7.0.3", "7.1.3", "8.0.1"]
    DEFAULT_VERSION = "7.1.3"

    async def ensure_ffmpeg(self) -> Path:
        """确保 FFmpeg 可用"""
        # 检查是否已安装
        ffmpeg_path = await self.check_ffmpeg()
        if ffmpeg_path:
            return ffmpeg_path

        # 安装
        return await self.install_ffmpeg(self.DEFAULT_VERSION)

    async def check_ffmpeg(self) -> Optional[Path]:
        """检查程序目录中的 FFmpeg"""
        tools_dir = self.config.paths.data_dir / "tools"

        # 查找所有 ffmpeg-* 目录
        for ffmpeg_dir in sorted(tools_dir.glob("ffmpeg-*"), reverse=True):
            ffmpeg_bin = ffmpeg_dir / "bin" / "ffmpeg"
            if platform.system() == "Windows":
                ffmpeg_bin = ffmpeg_bin.with_suffix(".exe")

            if ffmpeg_bin.exists() and await self.verify_ffmpeg(ffmpeg_bin):
                return ffmpeg_bin

        return None

    async def install_ffmpeg(self, version: str) -> Path:
        """安装 FFmpeg 到程序目录"""
        target_dir = self.config.paths.data_dir / "tools" / f"ffmpeg-{version}"

        if target_dir.exists():
            ffmpeg_bin = target_dir / "bin" / "ffmpeg"
            if platform.system() == "Windows":
                ffmpeg_bin = ffmpeg_bin.with_suffix(".exe")
            return ffmpeg_bin

        # 下载并安装
        platform_name = platform.system().lower()

        if platform_name == "windows":
            return await self._install_windows(target_dir, version)
        elif platform_name == "darwin":
            return await self._install_macos(target_dir, version)
        else:
            return await self._install_linux(target_dir, version)

    async def verify_ffmpeg(self, ffmpeg_path: Path) -> bool:
        """验证 FFmpeg"""
        try:
            version_output = await run_command(
                [str(ffmpeg_path), "-version"],
                capture_output=True
            )
            version = self._parse_version(version_output)

            if version[0] not in [7, 8]:
                return False

            encoders_output = await run_command(
                [str(ffmpeg_path), "-encoders"],
                capture_output=True
            )

            return "libsvtav1" in encoders_output
        except Exception:
            return False
```

## 总结

### 核心优势

- ✅ **无需 sudo**: 适配 Electron + Python Backend 架构
- ✅ **不检测系统**: 简化逻辑，避免冲突
- ✅ **版本控制**: 程序完全控制 FFmpeg 版本
- ✅ **多版本共存**: 支持保留多个版本
- ✅ **高级支持**: 通过编辑命令或配置使用系统版本
- ✅ **所有平台一致**: 统一的安装和管理方式

### 与其他工具一致

- Git: 程序目录（Windows）或系统（macOS/Linux）
- UV: 程序目录（所有平台）
- **FFmpeg: 程序目录（所有平台）** ← 新策略
