# LeRoPilot

[![Build Matrix](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml) [![Publish Release](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml) ![license](https://img.shields.io/badge/license-AGPLv3-blue)

LeRoPilot 的开发初衷是为 LeRobot 提供一个图形化界面，旨在简化安装过程并提升数据录制的易操作性。

## 主要功能

- **环境管理**：通过 Python 虚拟环境，允许用户选择 LeRobot 和 PyTorch 的版本，从而创建和管理不同版本的 LeRobot 环境。
- **设备管理**：提供便捷的设备（机器人、摄像头）管理功能，减少用户在设备设置上的工作量。
- **数据录制**：提供趁手的数据录制工具，方便用户录制和管理数据集（DataSet）。

LeRoPilot 是一个桌面/网页混合应用：使用 Python 后端（FastAPI）提供功能，前端使用 TypeScript（Vite）构建本地 UI。项目提供 macOS、Linux 和 Windows 的预编译二进制。

快速开始（中文说明）请参阅下文。英文说明见 `README.md`。

## 快速开始

1. 在 GitHub Releases 页面下载与你的平台匹配的二进制（例如 `leropilot-vX.Y.Z-linux` 或 `leropilot-vX.Y.Z-win.exe`）。
2. 在 macOS / Linux 上：

```bash
chmod +x ./leropilot
./leropilot
```

3. 在 Windows 上：双击 `leropilot.exe` 运行。

应用默认会打开浏览器并在 `http://127.0.0.1:8000` 提供 UI 界面。

## 下载与发布资产

预编译的发布资产位于 GitHub Releases 页面。Actions 临时 artifacts 可以从相应的 workflow 运行中下载（适合内部测试）；正式发布的二进制会附加到 Release 页面并长期保存。

## 从源码构建

### 要求

- Python 3.10+
- Node.js 16+

注意：PyInstaller 无法可靠地跨平台交叉编译。请在目标平台（或对应 runner）上构建目标平台的可执行文件。

### 构建步骤

```bash
# 安装 Python 开发依赖
pip install -e ".[dev]"

# 构建前端
cd frontend
npm ci
npm run build
cd ..

# 使用打包脚本（会执行前端构建并通过 PyInstaller 打包）
python scripts/build.py
```

生成的可执行文件位于 `dist/` 目录。

触发发布（示例）：

```bash
git tag v0.1.0
git push origin v0.1.0
```

## 开发模式

后端（FastAPI）运行：

```bash
python -m leropilot.main
```

前端开发服务器：

```bash
cd frontend
npm run dev
```

开发模式下前端在 `http://localhost:5173` 运行，dev server 会将 API 请求代理到后端以便联调。

## 配置

应用数据与日志默认位于 `~/.leropilot/`：

- `~/.leropilot/config.yaml` — 配置
- `~/.leropilot/logs/` — 日志

示例 `config.yaml`：

```yaml
port: 8000
data_dir: ~/.leropilot
```

可以通过环境变量（`LEROPILOT_` 前缀）覆盖配置。例如：

```bash
export LEROPILOT_PORT=9000
```

## CI / 发布工作流

本项目使用 GitHub Actions 实现 CI、构建与发布。关键工作流：

- `build-matrix.yml`：在每次 push 时运行，负责构建前端、安装依赖、运行 lint/tests，并在 Linux/Windows/macOS 上打包可执行文件，产物以 artifacts 上传。
- `publish-release.yml`：当推送 tag（例如 `v0.1.0`）时触发，构建并发布 Release 资产。
- `cla.yml`：在 PR 中验证是否包含 CLA 签署声明，确保合规。
- `auto-merge-label.yml`：自动为新建或更新的 PR 添加 `needs-review` 标签以便审查。

临时 artifacts 可在 Actions 标签页对应运行中下载；正式的 Release 资产请在 Releases 页面获取。

## 贡献与 CLA

欢迎贡献。提交 PR 前请阅读 `CONTRIBUTING.md` 并签署 CLA（见 `cla/CLA.md`）。在 PR 描述中包含以下行以接受 CLA：

```
I accept the CLA (Contributor License Agreement). Name: <Your Full Name>, Email: <your-email>
```

## 故障排查

- 无头环境 / WSL：自动打开浏览器可能失败（xdg-open），请手动访问 `http://127.0.0.1:8000`。
- 权限问题：在 macOS/Linux 上请先运行 `chmod +x ./leropilot`。
- 端口占用：如果 8000 被占用，请修改 `config.yaml` 或设置 `LEROPILOT_PORT`。
- 跨平台构建失败：请在目标平台或相应 runner 上构建（参见 PyInstaller 注意）。

## 商业授权

如需商业许可或企业支持，请参考 `COMMERCIAL.md`。

## 联系方式

- 作者：冯裕坚 (Feng Yu Jian)
- 邮箱：fengyj@live.com

## 许可

本项目采用 GNU AGPLv3 许可。详见仓库根目录的 `LICENSE` 文件。

感谢使用 LeRoPilot，欢迎报告问题或提交改进建议。
