# LeRoPilot

[![Build Matrix](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml) [![Publish Release](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml) ![license](https://img.shields.io/badge/license-AGPLv3-blue)

LeRoPilot is designed to provide a graphical user interface for LeRobot, simplifying the installation process and improving the usability of data recording.

## Key Features

- **Environment Management**: Create and manage different LeRobot environments by selecting specific LeRobot and PyTorch versions, utilizing Python virtual environments.
- **Device Management**: Conveniently manage devices (robots, cameras) to reduce the effort required for device setup.
- **Data Recording**: Provides handy data recording tools to facilitate the recording and management of datasets.

LeRoPilot is a desktop/web hybrid application that serves a local UI and provides functionality via a Python backend and a TypeScript frontend. It ships as prebuilt native binaries for macOS, Linux and Windows.

For Mandarin (中文) instructions, see `README_zh.md`.

Quick start (Linux / macOS):

```bash
chmod +x ./leropilot
./leropilot
```

On Windows: double-click `leropilot.exe`.

The application opens a browser window by default and serves the UI at `http://127.0.0.1:8000`.

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

1. Download a matching prebuilt binary from the Releases page (`leropilot-<tag>-<os>`).
2. On macOS / Linux:

```bash
chmod +x ./leropilot
./leropilot
```

3. On Windows: run `leropilot.exe` by double-clicking it.

By default the UI will be available at `http://127.0.0.1:8000` in your browser.

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

# Build frontend
cd frontend
npm ci
npm run build
cd ..

# Package the application (this runs the frontend build and PyInstaller)
python scripts/build.py
```

The produced binaries are placed under `dist/`.

To publish a release (example):

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Development

Run the backend (FastAPI):

```bash
python -m leropilot.main
```

Run the frontend development server:

```bash
cd frontend
npm run dev
```

During development the frontend runs at `http://localhost:5173` and the frontend dev server proxies API requests to the backend for local testing.

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
