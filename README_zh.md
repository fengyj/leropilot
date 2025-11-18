# LeRoPilot

**许可：** AGPLv3 — 版权 © 2025 冯裕坚 (Feng Yu Jian) <fengyj@live.com>。个人使用免费；商业使用请参见 `COMMERCIAL.md` 联系授权。

## 简介

LeRoPilot 是一个本地开发环境管理工具，提供基于浏览器的界面来创建与管理 Python 环境。项目已打包为单文件可执行程序，用户无需依赖即可运行。

## 快速开始

### 系统要求（构建时）
- Python 3.10+
- Node.js 16+

运行已打包的可执行文件无需任何依赖。

### 下载并运行（已编译的可执行文件）
- Windows: 双击 `leropilot.exe` 即可启动，默认打开浏览器访问 `http://127.0.0.1:8000`
- macOS / Linux: 给文件执行权限后运行：

```bash
chmod +x leropilot
./leropilot
```

浏览器打开 `http://127.0.0.1:8000` 即可访问 UI。

### 从源码构建（可选）

1. 安装 Python 依赖：

```bash
pip install -e ".[dev]"
```

2. 安装前端依赖并构建静态文件：

```bash
cd frontend
npm install
npm run build
cd ..
```

3. 使用 PyInstaller 打包：

```bash
python scripts/build.py
```

生成的可执行文件位于 `dist/` 目录。

## 开发模式

- 后端（FastAPI）

```bash
python -m leropilot.main
```

- 前端（开发服务器）

```bash
cd frontend
npm run dev
```

前端开发服务器默认在 `http://localhost:5173`，并配置了 `/api` 代理到后端。

## 配置

应用数据存放在 `~/.leropilot/`：
- 配置文件：`~/.leropilot/config.yaml`
- 日志：`~/.leropilot/logs/`

可通过 `LEROPILOT_` 前缀的环境变量覆盖配置，例如：

```bash
export LEROPILOT_PORT=9000
```

## 许可与贡献者协议（CLA）

本项目采用 **GNU AGPLv3** 开源许可，详细条款见 `LICENSE` 文件。为了保留未来对商业用户提供闭源/商业许可证的能力，所有外部贡献者需要签署贡献者许可协议（CLA），详见 `cla/CLA.md` 与 `CONTRIBUTING.md`。

当提交 Pull Request 时，请在 PR 描述中包含以下行以接受 CLA（否则 PR 可能不会被合并）：

```
I accept the CLA (Contributor License Agreement). Name: <Your Full Name>, Email: <your-email>
```

## 商业授权

如需商业许可、企业支持或闭源授权，请参见 `COMMERCIAL.md` 中的联系方式并与作者联系。

## 联系方式

- 作者：冯裕坚 (Feng Yu Jian)
- 邮箱：fengyj@live.com

---

感谢使用与关注 LeRoPilot！欢迎按 `CONTRIBUTING.md` 指引参与贡献。
