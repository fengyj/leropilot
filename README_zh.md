
# LeRoPilot


[![Build Matrix](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml) [![Publish Release](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/publish-release.yml) ![license](https://img.shields.io/badge/license-AGPLv3-blue)

**许可：** AGPLv3 — 版权 © 2025 冯裕坚 (Feng Yu Jian) <fengyj@live.com>。

一句快速开始：下载对应平台的二进制后运行（Linux/macOS）:

```bash
chmod +x ./leropilot && ./leropilot
```

Windows 上双击 `leropilot.exe`。

## 目录

- [快速开始](#快速开始)
- [下载并运行](#下载并运行)
- [从源码构建](#从源码构建)
- [开发模式](#开发模式)
- [配置](#配置)
- [CI / 发布](#ci--发布)
- [许可与 CLA](#许可与-cla)
- [商业授权](#商业授权)
- [故障排查](#故障排查)
- [联系方式](#联系方式)

## 快速开始

1. 在 Releases 页面下载对应平台的资产（`leropilot-<tag>-<os>`）。
2. 在 macOS / Linux 上：

```bash
chmod +x ./leropilot
./leropilot
```

Windows：双击 `leropilot.exe`。

默认打开浏览器并访问 `http://127.0.0.1:8000`。

## 下载并运行

预编译二进制可在 Releases 页面获取，文件格式示例：`leropilot-v0.1.0-linux`、`leropilot-v0.1.0-win.exe`、`leropilot-v0.1.0-mac`。

## 从源码构建

### 要求

- Python 3.10+
- Node.js 16+

> 注意：PyInstaller 不能跨平台交叉编译。要生成 Windows 可执行文件，请在 Windows 环境或 `windows-latest` runner 上构建；要生成 macOS 可执行文件，请在 macOS 环境或 `macos-latest` runner 上构建。

### 构建步骤

```bash
# 安装 Python 依赖
pip install -e "[dev]"

# 构建前端
cd frontend
npm ci
npm run build
cd ..

# 使用脚本打包（会执行前端构建并通过 PyInstaller 打包）
python scripts/build.py
```

生成的可执行文件位于 `dist/` 目录。

### 触发发布（示例）

在仓库中打标签并推送：

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

## 配置

应用数据存放在 `~/.leropilot/`：

- 配置：`~/.leropilot/config.yaml`
- 日志：`~/.leropilot/logs/`

可通过环境变量（`LEROPILOT_` 前缀）覆盖配置，例如：

```bash
export LEROPILOT_PORT=9000
```

## CI / 发布

项目的 CI/CD 由 GitHub Actions 驱动，核心工作流如下：

- **`build-matrix.yml`**：每次向任意分支推送代码时都会运行。该流程会构建前端、安装依赖、执行 lint 与单元测试，并分别在 Linux、Windows、macOS 上打包可执行文件，构建产物会以 artifacts 形式保存备用。
- **`publish-release.yml`**：当推送形如 `v*` 的标签或手动触发时运行，用于生成正式发布版本并把多平台产物附加到 GitHub Release。
- **`cla.yml`**：在 Pull Request 中检查是否包含 CLA 签署声明，确保合规性。
- **`auto-merge-label.yml`**：自动为新的或更新的 Pull Request 添加 `needs-review` 标签，以便快速分配审核。

你可以在仓库的 “Actions” 标签页查看每次构建的状态与日志。

## 许可与 CLA

本项目采用 GNU AGPLv3。外部贡献者需要签署 CLA（见 `cla/CLA.md` 与 `CONTRIBUTING.md`）。在 PR 描述中包含：

```
I accept the CLA (Contributor License Agreement). Name: <Your Full Name>, Email: <your-email>
```

## 商业授权

如需商业许可或企业支持，请参见 `COMMERCIAL.md`。

## 故障排查

- WSL/无 GUI：自动打开浏览器可能失败（xdg-open 错误），可手动访问 `http://127.0.0.1:8000`。
- 权限：请为 macOS/Linux 二进制执行 `chmod +x ./leropilot`。
- 端口占用：若 8000 被占用，可通过 `config.yaml` 或 `LEROPILOT_PORT` 环境变量修改。
- 构建跨平台失败：请在对应平台上构建（参见 PyInstaller 注意）。

## 联系方式

- 作者：冯裕坚 (Feng Yu Jian)
- 邮箱：fengyj@live.com

---

感谢使用与关注 LeRoPilot！欢迎按 `CONTRIBUTING.md` 指引参与贡献。

## CI / 发布说明

- **CI 构建产物**：`build-matrix.yml` 在每次推送后都会上传名为 `leropilot-<os>-<run_id>` 的临时 artifacts，可在 Actions 标签页对应的运行记录中下载。
- **正式发布资产**：在 Releases 页面可以获取 `publish-release.yml` 生成的长期保存二进制文件，命名格式为 `leropilot-<tag>-<os>`。

推荐的发布步骤：

1. 推送一个版本标签（例如 `v0.1.0`），触发 `publish-release.yml`。
2. GitHub Actions 会在三个平台上构建最新可执行文件并附加到对应 Release。
3. 从 Release 页面下载目标平台的资产对外发布。

注意事项：

- workflow artifacts 只临时保存，适合内部测试；Release 资产会长期可用。
- 平台签名（如 macOS notarization、Windows Authenticode）需要额外凭据，默认流程不会自动完成。

