# LeRoPilot

[![Build Matrix](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml) [![Publish Release](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml) ![license](https://img.shields.io/badge/license-AGPLv3-blue)

LeRoPilot is designed to provide a graphical user interface for LeRobot, simplifying the installation process and improving the usability of data recording.

## Key Features

- **Environment Management**: Create and manage different LeRobot environments by selecting specific LeRobot and PyTorch versions, utilizing Python virtual environments.
- **Device Management**: Conveniently manage devices (robots, cameras) to reduce the effort required for device setup.
- **Data Recording**: Provides handy data recording tools to facilitate the recording and management of datasets.

LeRoPilot is a desktop/web hybrid application that serves a local UI and provides functionality via a Python backend and a TypeScript frontend. It ships as prebuilt native binaries for macOS, Linux and Windows.

For Mandarin (中文) instructions, see `README_zh.md`.

The application supports two modes:

- **Desktop Mode (Recommended)**: Native Electron application.
- **Browser Mode**: Opens a browser window, suitable for WSL or remote servers.

Quick start (Linux / macOS):

```bash
# Run portable version
chmod +x ./LeRoPilot-*-portable
./LeRoPilot-*-portable
```

On Windows: double-click `LeRoPilot-*-portable.exe` or run the installer.

**Contents**

- **Overview**: short project description and license
- **Quick Start**: run prebuilt binaries
- **Build from Source**: requirements and build steps
- **Development**: run backend and frontend locally
- **Configuration**: where config and data live, env overrides
- **CI & Releases**: GitHub Actions workflows summary
- **Contributing & CLA**: how to contribute and sign CLA
- **Troubleshooting**: common issues and fixes

## Quick Start

1. Download a matching prebuilt binary from the Releases page.
2. **Desktop Mode**: Run the portable executable or installer.
3. **Browser Mode** (for WSL/Server):
   Run the Python backend directly:
   ```bash
   python -m leropilot.main --no-browser
   ```
   Then visit `http://127.0.0.1:8000`.

## Downloads

Release assets are published on GitHub Releases. Typical names include `leropilot-vX.Y.Z-linux`, `leropilot-vX.Y.Z-win.exe`, and `leropilot-vX.Y.Z-mac`.

## Build from Source

### Requirements

- Python 3.10+
- Node.js 16+

Notes: PyInstaller cannot reliably cross-compile between OSes. Build Windows executables on Windows, and macOS executables on macOS.

### Build steps

```bash
# Install Python dev dependencies
pip install -e ".[dev]"

# Build everything (Frontend + Backend + Electron)
python scripts/build-electron.py
```

The produced artifacts are placed under `dist/electron/`:

- Windows: `LeRoPilot-*-portable.exe` and `LeRoPilot-Setup-*.exe`
- macOS: `LeRoPilot-*.dmg` and `LeRoPilot-*.zip`
- Linux: `LeRoPilot-*.AppImage` and `LeRoPilot-*.tar.gz`

To publish a release (example):

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Development

### Browser Mode (Default)

Run the backend (FastAPI) and frontend separately:

```bash
# Terminal 1: Backend
python -m leropilot.main

# Terminal 2: Frontend
cd frontend
npm run dev
```

### Electron Mode

```bash
# Terminal 1: Backend (no browser)
python -m leropilot.main --no-browser

# Terminal 2: Frontend
cd frontend
npm run dev

# Terminal 3: Electron
cd electron
npm start
```

### Troubleshooting

#### WSL / Linux Issues

1. **Missing Dependencies (Ubuntu)**:
   Electron requires certain Linux GUI libraries that may not be installed by default in WSL.

   **For Ubuntu 22.04**:

   ```bash
   sudo apt-get update
   sudo apt-get install -y libnss3 libatk-bridge2.0-0 libgtk-3-0 libasound2 libgbm1 libxss1
   ```

   **For Ubuntu 24.04** (library names have `t64` suffix):

   ```bash
   sudo apt-get update
   sudo apt-get install -y libnss3 libatk-bridge2.0-0t64 libgtk-3-0t64 libasound2t64 libgbm1 libxss1
   ```

2. **White Screen / Crash on Startup**:
   If you see a white screen or the app crashes with `FATAL: This is frequently caused by incorrect permissions on /dev/shm`, it's a known issue with Electron in some WSL environments.

   **Fix**: Run the following command to fix shared memory permissions:

   ```bash
   sudo chmod 1777 /dev/shm
   ```

   **Note**: After running this command, you may need to restart WSL:

   ```bash
   wsl --shutdown
   ```

   Then reopen your WSL terminal and try again.

3. **Window Not Visible**:
   If the app is running but the window is not visible, try checking the logs for any errors. The app is configured to auto-disable hardware acceleration in WSL to prevent rendering issues.

### VS Code Debugging

- **Python: FastAPI**: Starts backend + browser (Recommended for WSL)
- **Electron: All**: Starts backend + Electron (Requires GUI environment)

## Configuration

Application data and configuration are stored in `~/.leropilot/` by default:

- `~/.leropilot/config.yaml` — configuration file
- `~/.leropilot/logs/` — application logs

Example `config.yaml`:

```yaml
port: 8000
data_dir: ~/.leropilot
```

Environment variables with the `LEROPILOT_` prefix override configuration values. Example:

```bash
export LEROPILOT_PORT=9000
```

## CI & Releases

LeRoPilot uses GitHub Actions for CI, packaging and releases. Key workflows:

- `build-matrix.yml`: builds frontend, runs lint/tests, and packages artifacts for Linux, Windows, and macOS.
- `publish-release.yml`: builds and publishes release artifacts when a tag is pushed.
- `cla.yml`: verifies that contributors have accepted the CLA in PR descriptions.
- `auto-merge-label.yml`: applies review labels to new PRs to streamline the review process.

Temporary artifacts can be downloaded from workflow runs in the Actions tab; official, versioned binaries are published on the Releases page.

## Contributing & CLA

We welcome contributions. Before submitting a PR, read `CONTRIBUTING.md` and sign the Contributor License Agreement (CLA) described in `cla/CLA.md`.

Include the following line in your PR description to accept the CLA:

```
I accept the CLA (Contributor License Agreement). Name: <Your Full Name>, Email: <your-email>
```

## Troubleshooting

- Headless or WSL environments: automatic browser opening may fail (xdg-open); visit `http://127.0.0.1:8000` manually.
- Permission errors: on macOS/Linux run `chmod +x ./leropilot` before executing.
- Port in use: change the port in `config.yaml` or set `LEROPILOT_PORT`.
- Cross-platform build failures: build on the target platform (see PyInstaller notes).

## Commercial

Commercial licensing and enterprise support are available. See `COMMERCIAL.md` for details.

## Contact

- Author: Feng Yu Jian
- Email: fengyj@live.com

## License

This project is distributed under the GNU AGPLv3. See the `LICENSE` file for full terms.

Thank you for using LeRoPilot — contributions and feedback are appreciated.
