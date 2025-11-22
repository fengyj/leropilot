# LeRoPilot

[![Build Matrix](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml) [![Publish Release](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml) [![Sync Wiki](https://github.com/fengyj/leropilot/actions/workflows/sync-wiki.yml/badge.svg)](https://github.com/fengyj/leropilot/actions/workflows/sync-wiki.yml) ![license](https://img.shields.io/badge/license-AGPLv3-blue)

为 [LeRobot](https://github.com/huggingface/lerobot) 提供的图形化界面，简化机器人项目的环境管理、设备配置和数据录制。

## 🚀 快速开始

**[📖 阅读文档](docs/wiki/Home_zh.md)** | **[⬇️ 下载最新版本](https://github.com/fengyj/leropilot/releases)**

```bash
# 桌面模式（推荐）
# 下载并运行适合您平台的安装程序或便携版可执行文件

# 浏览器模式（WSL/服务器）
python -m leropilot.main --no-browser
# 然后在浏览器中打开 http://localhost:8000
```

详细安装说明请参见 **[安装指南](docs/wiki/Installation-Guide_zh.md)**。

## ✨ 主要功能

- **环境管理**：使用虚拟环境创建和管理不同 Python、LeRobot 和 PyTorch 版本的 LeRobot 环境
- **设备管理**：通过直观的界面配置和管理机器人和摄像头
- **数据录制**：通过简化的工作流程录制和管理机器人学习数据集
- **跨平台**：支持 Windows、macOS 和 Linux 的原生桌面应用，以及用于远程服务器的浏览器模式

## 📚 文档

- **[安装指南](docs/wiki/Installation-Guide_zh.md)** - 安装和运行 LeRoPilot
- **[快速入门](docs/wiki/Quick-Start_zh.md)** - 5 分钟创建您的第一个环境
- **[常见问题](docs/wiki/FAQ_zh.md)** - 常见问题解答
- **[English Documentation](docs/wiki/Home.md)** - 英文文档

## 🛠️ 开发

### 前置要求

- Python 3.10 或 3.11
- Node.js 20+
- Git

### 搭建开发环境

```bash
# 克隆仓库
git clone https://github.com/fengyj/leropilot.git
cd leropilot

# 安装 Python 依赖
pip install uv
uv sync --extra dev

# 安装前端依赖
cd frontend
npm install
cd ..
```

### 本地运行

**终端 1 - 后端：**

```bash
python -m leropilot.main --no-browser
```

**终端 2 - 前端：**

```bash
cd frontend
npm run dev
```

在浏览器中打开 `http://localhost:5173`。

### 构建

**构建前端：**

```bash
cd frontend
npm run build
```

**构建 Python 后端：**

```bash
python -m PyInstaller --noconfirm --clean build-backend.spec
```

**构建 Electron 应用：**

```bash
cd electron
npm install
npm run build
```

### 测试

```bash
# 运行 Python 测试
pytest

# 运行前端测试
cd frontend
npm test

# 运行代码检查
./scripts/run-lint.sh
```

## 🤝 贡献

我们欢迎贡献！请参见我们的[贡献指南](CONTRIBUTING.md)了解以下详情：

- 行为准则
- 开发工作流程
- 拉取请求流程
- 编码标准

在贡献之前，请签署我们的[贡献者许可协议 (CLA)](cla/CLA.md)。

## 📄 许可证

LeRoPilot 采用 **GNU Affero 通用公共许可证 v3.0 (AGPLv3)** 授权。

这意味着：

- ✅ 您可以使用、修改和分发本软件
- ✅ 分发时必须公开源代码
- ✅ 衍生作品必须采用 AGPLv3 许可
- ✅ 网络使用视为分发（AGPL 要求）

如需不受 AGPLv3 限制的商业使用，可获得商业许可。详见 [COMMERCIAL.md](COMMERCIAL.md)。

## 🙏 致谢

LeRoPilot 基于以下项目构建：

- [LeRobot](https://github.com/huggingface/lerobot) - 机器人学习框架
- [Electron](https://www.electronjs.org/) - 跨平台桌面框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Python Web 框架
- [React](https://react.dev/) - UI 库
- [Vite](https://vitejs.dev/) - 前端构建工具

## 📞 联系方式

- **问题反馈**: [GitHub Issues](https://github.com/fengyj/leropilot/issues)
- **讨论**: [GitHub Discussions](https://github.com/fengyj/leropilot/discussions)
- **邮箱**: fengyj@live.com

---

**[文档](docs/wiki/Home_zh.md)** • **[发布版本](https://github.com/fengyj/leropilot/releases)** • **[贡献](CONTRIBUTING.md)** • **[许可证](LICENSE)**
