# Installation Guide

## System Requirements

- **Operating System**: Windows 10/11, macOS 10.15+, or Linux (Ubuntu 20.04+)
- **Memory**: 4GB RAM minimum (8GB recommended)
- **Disk Space**: 2GB free space
- **Git**: Optional (LeRoPilot can download a bundled version), or pre-installed system Git
- **Python**: 3.10 or 3.11 (for browser mode only)

## Installation Methods

### Method 1: Desktop Application (Recommended)

Download the latest release for your platform:

#### Windows

1. Download `LeRoPilot-Setup-*.exe` (installer) or `LeRoPilot-Portable-*.exe` (portable)
2. **Installer**: Run the setup and follow the wizard
3. **Portable**: Double-click the executable to run directly

#### macOS

1. Download `LeRoPilot-*.dmg`
2. Open the DMG file
3. Drag LeRoPilot to Applications folder
4. Launch from Applications

#### Linux

**Option A: tar.gz Archive (Recommended - No Dependencies)**

1. Download `leropilot-linux-*.tar.gz`
2. Extract the archive:
   ```bash
   tar -xzf leropilot-linux-*.tar.gz
   ```
3. Run the application:
   ```bash
   cd leropilot-linux-*
   ./leropilot
   ```
4. (Optional) Install to `/opt` for system-wide access:
   ```bash
   sudo mv leropilot-linux-* /opt/leropilot
   sudo ln -s /opt/leropilot/leropilot /usr/local/bin/leropilot
   ```

**Option B: AppImage**

1. Download `LeRoPilot-*.AppImage`
2. Make it executable:
   ```bash
   chmod +x LeRoPilot-*.AppImage
   ```
3. Run the AppImage:
   ```bash
   ./LeRoPilot-*.AppImage
   ```

> **Note**: On Ubuntu 22.04+ and other newer distributions, you may need to install `libfuse2`:
>
> ```bash
> sudo apt install libfuse2
> ```
>
> Alternatively, you can run AppImage without FUSE:
>
> ```bash
> ./LeRoPilot-*.AppImage --appimage-extract-and-run
> ```

### Method 2: Browser Mode (WSL/Server)

For WSL or remote server environments:

1. **Install via pip** (coming soon):

   ```bash
   pip install leropilot
   leropilot --no-browser
   ```

2. **Or run from source**:

   ```bash
   git clone https://github.com/fengyj/leropilot.git
   cd leropilot
   pip install -e .
   python -m leropilot.main --no-browser
   ```

3. Open your browser and navigate to `http://localhost:8000`

> **Note for WSL Users**: For the best experience with the integrated terminal feature, we recommend installing [Windows Terminal](https://apps.microsoft.com/detail/9n0dx20hk701) (`wt.exe`). LeRoPilot will automatically use it to open terminals.

## First Launch

1. **Desktop Mode**: The application window will open automatically
2. **Browser Mode**: Open `http://localhost:8000` in your browser

On first launch, LeRoPilot will:

- Create a configuration directory at `~/.leropilot/`
- Set up default settings
- Display the welcome screen

## Next Steps

- [Quick Start Guide](Quick-Start.md) - Get started with your first environment
- [Configuration](Configuration.md) - Customize your settings
- [Troubleshooting](Troubleshooting.md) - Common installation issues

## Updating

### Desktop Application

Download and install the latest version from the [Releases page](https://github.com/fengyj/leropilot/releases).

### Browser Mode

```bash
pip install --upgrade leropilot
```

## Uninstallation

### Windows

- **Installer**: Use "Add or Remove Programs"
- **Portable**: Simply delete the executable

### macOS

Drag LeRoPilot from Applications to Trash

### Linux

Delete the AppImage file

### Remove Configuration

To completely remove all data:

```bash
rm -rf ~/.leropilot
```
