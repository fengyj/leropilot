# 安装指南

## 系统要求

- **操作系统**: Windows 10/11、macOS 10.15+ 或 Linux (Ubuntu 20.04+)
- **内存**: 最低 4GB RAM（推荐 8GB）
- **磁盘空间**: 2GB 可用空间
- **Git**: 可选 (LeRoPilot 可下载内置版本)，或使用预装的系统 Git
- **Python**: 3.10 或 3.11（仅浏览器模式需要）

## 安装方式

### 方式 1：桌面应用（推荐）

下载适合您平台的最新版本：

#### Windows

1. 下载 `LeRoPilot-Setup-*.exe`（安装版）或 `LeRoPilot-Portable-*.exe`（便携版）
2. **安装版**：运行安装程序并按照向导操作
3. **便携版**：双击可执行文件直接运行

#### macOS

1. 下载 `LeRoPilot-*.dmg`
2. 打开 DMG 文件
3. 将 LeRoPilot 拖到应用程序文件夹
4. 从应用程序启动

#### Linux

**选项 A：tar.gz 压缩包（推荐 - 无需额外依赖）**

1. 下载 `leropilot-linux-*.tar.gz`
2. 解压压缩包：
   ```bash
   tar -xzf leropilot-linux-*.tar.gz
   ```
3. 运行应用程序：
   ```bash
   cd leropilot-linux-*
   ./leropilot
   ```
4. （可选）安装到 `/opt` 以便全局访问：
   ```bash
   sudo mv leropilot-linux-* /opt/leropilot
   sudo ln -s /opt/leropilot/leropilot /usr/local/bin/leropilot
   ```

**选项 B：AppImage**

1. 下载 `LeRoPilot-*.AppImage`
2. 添加执行权限：
   ```bash
   chmod +x LeRoPilot-*.AppImage
   ```
3. 运行 AppImage：
   ```bash
   ./LeRoPilot-*.AppImage
   ```

> **注意**：在 Ubuntu 22.04+ 及其他较新的发行版上，可能需要安装 `libfuse2`：
>
> ```bash
> sudo apt install libfuse2
> ```
>
> 或者，可以在不依赖 FUSE 的情况下运行 AppImage：
>
> ```bash
> ./LeRoPilot-*.AppImage --appimage-extract-and-run
> ```

### 方式 2：浏览器模式（WSL/服务器）

适用于 WSL 或远程服务器环境：

1. **通过 pip 安装**（即将推出）：

   ```bash
   pip install leropilot
   leropilot --no-browser
   ```

2. **或从源码运行**：

   ```bash
   git clone https://github.com/fengyj/leropilot.git
   cd leropilot
   pip install -e .
   python -m leropilot.main --no-browser
   ```

3. 打开浏览器访问 `http://localhost:8000`

> **WSL 用户注意**：为了获得最佳的集成终端体验，我们建议安装 [Windows Terminal](https://apps.microsoft.com/detail/9n0dx20hk701) (`wt.exe`)。LeRoPilot 将自动使用它来打开终端。

## 首次启动

1. **桌面模式**：应用程序窗口将自动打开
2. **浏览器模式**：在浏览器中打开 `http://localhost:8000`

首次启动时，LeRoPilot 将：

- 在 `~/.leropilot/` 创建配置目录
- 设置默认配置
- 显示欢迎界面

## 下一步

- [快速入门](Quick-Start_zh.md) - 创建您的第一个环境
- [配置说明](Configuration_zh.md) - 自定义设置
- [故障排除](Troubleshooting_zh.md) - 常见安装问题

## 更新

### 桌面应用

从 [Releases 页面](https://github.com/fengyj/leropilot/releases) 下载并安装最新版本。

### 浏览器模式

```bash
pip install --upgrade leropilot
```

## 卸载

### Windows

- **安装版**：使用"添加或删除程序"
- **便携版**：直接删除可执行文件

### macOS

将 LeRoPilot 从应用程序拖到废纸篓

### Linux

删除 AppImage 文件

### 删除配置

完全删除所有数据：

```bash
rm -rf ~/.leropilot
```
