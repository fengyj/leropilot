# LeRoPilot

[![Build Matrix](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml) [![Publish Release](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml) [![Sync Wiki](https://github.com/fengyj/leropilot/actions/workflows/sync-wiki.yml/badge.svg)](https://github.com/fengyj/leropilot/actions/workflows/sync-wiki.yml) ![license](https://img.shields.io/badge/license-AGPLv3-blue)

A graphical user interface for [LeRobot](https://github.com/huggingface/lerobot) that simplifies environment management, device configuration, and data recording for robotics projects.

## 🚀 Quick Start

**[📖 Read the Documentation](docs/wiki/Home.md)** | **[⬇️ Download Latest Release](https://github.com/fengyj/leropilot/releases)**

```bash
# Desktop Mode (Recommended)
# Download and run the installer or portable executable for your platform

# Browser Mode (WSL/Server)
python -m leropilot.main --no-browser
# Then open http://localhost:8000 in your browser
```

For detailed installation instructions, see the **[Installation Guide](docs/wiki/Installation-Guide.md)**.

## ✨ Key Features

- **Environment Management**: Create and manage LeRobot environments with different Python, LeRobot, and PyTorch versions using virtual environments
- **Device Management**: Configure and manage robots and cameras with an intuitive interface
- **Data Recording**: Record and manage datasets for robot learning with streamlined workflows
- **Cross-Platform**: Native desktop applications for Windows, macOS, and Linux, plus browser mode for remote servers

## 📚 Documentation

- **[Installation Guide](docs/wiki/Installation-Guide.md)** - Get LeRoPilot up and running
- **[Quick Start](docs/wiki/Quick-Start.md)** - Create your first environment in 5 minutes
- **[FAQ](docs/wiki/FAQ.md)** - Frequently asked questions
- **[中文文档](docs/wiki/Home_zh.md)** - Chinese documentation

## 🛠️ Development

### Prerequisites

- Python 3.10 or 3.11
- Node.js 20+
- Git

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/fengyj/leropilot.git
cd leropilot

# Install Python dependencies
pip install uv
uv sync --extra dev

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### Run Locally

**Terminal 1 - Backend:**

```bash
python -m leropilot.main --no-browser
```

**Terminal 2 - Frontend:**

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

### Build

**Build Frontend:**

```bash
cd frontend
npm run build
```

**Build Python Backend:**

```bash
python -m PyInstaller --noconfirm --clean build-backend.spec
```

**Build Electron App:**

```bash
cd electron
npm install
npm run build
```

### Testing

```bash
# Run Python tests
pytest

# Run frontend tests
cd frontend
npm test

# Run linting
./scripts/run-lint.sh
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:

- Code of Conduct
- Development workflow
- Pull request process
- Coding standards

Before contributing, please sign our [Contributor License Agreement (CLA)](cla/CLA.md).

## 📄 License

LeRoPilot is licensed under the **GNU Affero General Public License v3.0 (AGPLv3)**.

This means:

- ✅ You can use, modify, and distribute this software
- ✅ You must disclose source code when distributing
- ✅ You must license derivative works under AGPLv3
- ✅ Network use counts as distribution (AGPL requirement)

For commercial use without AGPLv3 restrictions, a commercial license is available. See [COMMERCIAL.md](COMMERCIAL.md) for details.

## 🙏 Acknowledgments

LeRoPilot is built on top of:

- [LeRobot](https://github.com/huggingface/lerobot) - The robotics learning framework
- [Electron](https://www.electronjs.org/) - Cross-platform desktop framework
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [React](https://react.dev/) - UI library
- [Vite](https://vitejs.dev/) - Frontend build tool

## 📞 Contact

- **Issues**: [GitHub Issues](https://github.com/fengyj/leropilot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/fengyj/leropilot/discussions)
- **Email**: fengyj@live.com

---

**[Documentation](docs/wiki/Home.md)** • **[Releases](https://github.com/fengyj/leropilot/releases)** • **[Contributing](CONTRIBUTING.md)** • **[License](LICENSE)**
