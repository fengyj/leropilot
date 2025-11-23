# Installation Guide

## System Requirements

- **Operating System**: Windows 10/11, macOS 10.15+, or Linux (Ubuntu 20.04+)
- **Memory**: 4GB RAM minimum (8GB recommended)
- **Disk Space**: 2GB free space
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

1. Download `LeRoPilot-*.AppImage`
2. Make it executable:
   ```bash
   chmod +x LeRoPilot-*.AppImage
   ```
3. Run the AppImage:
   ```bash
   ./LeRoPilot-*.AppImage
   ```

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
