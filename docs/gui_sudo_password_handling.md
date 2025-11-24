# GUI 应用中的 Sudo 密码处理

## 问题

在 GUI 应用（如 Electron）中执行需要 sudo 权限的命令时，无法直接在终端提示用户输入密码。

## 解决方案

### macOS

使用 `osascript` 调用 AppleScript，弹出系统密码对话框：

```python
async def install_with_sudo_macos(command: list[str]) -> None:
    """macOS: 使用图形化 sudo 提示"""
    # 构建命令字符串
    cmd_str = " ".join(shlex.quote(arg) for arg in command)

    # 使用 osascript 执行，会弹出密码对话框
    applescript = f'do shell script "{cmd_str}" with administrator privileges'

    await run_command([
        "osascript",
        "-e",
        applescript
    ])
```

**示例**:

```python
# 安装 Homebrew
await install_with_sudo_macos([
    "/bin/bash",
    "-c",
    "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
])

# 使用 Homebrew 安装 FFmpeg (通常不需要 sudo)
await run_command(["brew", "install", "ffmpeg"])
```

**效果**:

- 弹出系统密码对话框
- 用户输入管理员密码
- 命令以 root 权限执行

### Linux

#### 方案 1: pkexec (推荐)

`pkexec` 是 PolicyKit 的一部分，大多数现代 Linux 发行版都预装：

```python
async def install_with_sudo_linux(command: list[str]) -> None:
    """Linux: 使用 pkexec 弹出密码对话框"""
    # pkexec 会弹出图形化密码对话框
    await run_command(["pkexec"] + command)
```

**示例**:

```python
# Ubuntu/Debian
await install_with_sudo_linux(["apt", "install", "-y", "ffmpeg"])

# Fedora
await install_with_sudo_linux(["dnf", "install", "-y", "ffmpeg"])
```

**效果**:

- 弹出图形化密码对话框（取决于桌面环境）
- GNOME: polkit-gnome-authentication-agent
- KDE: polkit-kde-authentication-agent
- 用户输入密码后执行命令

#### 方案 2: gksudo/kdesudo (较老)

```python
async def install_with_sudo_linux_legacy(command: list[str]) -> None:
    """Linux: 使用 gksudo (GNOME) 或 kdesudo (KDE)"""
    # 检测桌面环境
    desktop = os.getenv("XDG_CURRENT_DESKTOP", "").lower()

    if "gnome" in desktop or "unity" in desktop:
        sudo_cmd = "gksudo"
    elif "kde" in desktop:
        sudo_cmd = "kdesudo"
    else:
        sudo_cmd = "pkexec"  # 备选

    cmd_str = " ".join(shlex.quote(arg) for arg in command)
    await run_command([sudo_cmd, cmd_str])
```

**注意**: gksudo 和 kdesudo 在新版本中已被弃用，推荐使用 pkexec。

### Windows

Windows 使用 UAC (User Account Control) 提升权限：

```python
import ctypes
import sys

def is_admin() -> bool:
    """检查是否有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

async def install_with_admin_windows(command: list[str]) -> None:
    """Windows: 请求 UAC 提升权限"""
    if is_admin():
        # 已有管理员权限，直接执行
        await run_command(command)
    else:
        # 请求 UAC 提升
        # 方案 1: 重启程序并请求提升
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",  # 请求管理员权限
            sys.executable,  # Python 解释器
            " ".join(command),  # 参数
            None,
            1  # SW_SHOWNORMAL
        )
```

**更好的方案**: 使用 PowerShell 的 `Start-Process -Verb RunAs`

```python
async def install_with_admin_windows_ps(command: list[str]) -> None:
    """Windows: 使用 PowerShell 请求 UAC"""
    cmd_str = " ".join(shlex.quote(arg) for arg in command)

    ps_script = f'''
    Start-Process -FilePath "{command[0]}" -ArgumentList "{' '.join(command[1:])}" -Verb RunAs -Wait
    '''

    await run_command([
        "powershell",
        "-Command",
        ps_script
    ])
```

**注意**: Windows 下安装 FFmpeg 通常不需要管理员权限（下载到程序目录）。

## 实现示例

### FFmpegManager 中的使用

```python
class FFmpegManager:
    async def install_system_ffmpeg(self, platform: str) -> None:
        """安装系统级 FFmpeg（需要 sudo/admin）"""

        if platform == "darwin":
            # macOS: 使用 Homebrew
            # 先检查 Homebrew
            try:
                await run_command(["brew", "--version"])
            except FileNotFoundError:
                # 安装 Homebrew (需要密码)
                await self._install_homebrew_macos()

            # 安装 FFmpeg (通常不需要 sudo)
            await run_command(["brew", "install", "ffmpeg"])

        elif platform.startswith("linux"):
            # Linux: 使用包管理器
            distro = detect_linux_distro()

            if distro in ["ubuntu", "debian"]:
                # 使用 pkexec 弹出密码对话框
                await run_command([
                    "pkexec",
                    "apt", "update"
                ])
                await run_command([
                    "pkexec",
                    "apt", "install", "-y", "ffmpeg"
                ])
            elif distro == "fedora":
                await run_command([
                    "pkexec",
                    "dnf", "install", "-y", "ffmpeg"
                ])

        elif platform == "win32":
            # Windows: 不需要管理员权限
            # 直接下载到程序目录
            await self.install_to_program_dir(platform)

    async def _install_homebrew_macos(self) -> None:
        """macOS: 安装 Homebrew"""
        install_script = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'

        # 使用 osascript 弹出密码对话框
        applescript = f'do shell script "{install_script}" with administrator privileges'

        await run_command([
            "osascript",
            "-e",
            applescript
        ])
```

## UI 流程

### 安装提示

```
┌─────────────────────────────────────────┐
│ 安装 FFmpeg                             │
├─────────────────────────────────────────┤
│                                         │
│ 选择安装方式:                           │
│                                         │
│ ● 程序目录 (推荐)                       │
│   无需管理员权限                        │
│   独立管理，避免冲突                    │
│                                         │
│ ○ 系统级安装                            │
│   需要管理员密码                        │
│   系统统一管理                          │
│                                         │
│     [开始安装]  [取消]                  │
└─────────────────────────────────────────┘
```

### 密码提示（系统级安装）

**macOS**:

```
┌─────────────────────────────────────────┐
│ 🔐 需要管理员权限                       │
├─────────────────────────────────────────┤
│                                         │
│ 安装 FFmpeg 需要管理员权限              │
│                                         │
│ 点击"继续"后，系统会提示您输入密码      │
│                                         │
│     [继续]  [取消]                      │
└─────────────────────────────────────────┘
```

点击"继续"后，系统弹出密码对话框：

```
┌─────────────────────────────────────────┐
│ "LeRoPilot" 想要进行更改。              │
│ 请输入密码以允许此操作。                │
├─────────────────────────────────────────┤
│ 用户名: yourname                        │
│ 密码: [**********]                      │
│                                         │
│     [取消]  [好]                        │
└─────────────────────────────────────────┘
```

**Linux (pkexec)**:

```
┌─────────────────────────────────────────┐
│ 需要认证                                │
├─────────────────────────────────────────┤
│ 需要认证以安装软件包                    │
│                                         │
│ 密码: [**********]                      │
│                                         │
│     [取消]  [认证]                      │
└─────────────────────────────────────────┘
```

## 总结

| 平台        | 工具                        | 密码对话框   | 说明             |
| ----------- | --------------------------- | ------------ | ---------------- |
| **macOS**   | `osascript`                 | 系统对话框   | 使用 AppleScript |
| **Linux**   | `pkexec`                    | 图形化对话框 | PolicyKit        |
| **Windows** | `Start-Process -Verb RunAs` | UAC 对话框   | PowerShell       |

**推荐策略**:

- **默认**: 安装到程序目录（无需 sudo）
- **可选**: 系统级安装（使用上述方法处理密码）
- **用户选择**: 让用户决定安装方式
