
# LeRoPilot


[![Build Matrix](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml) ![license](https://img.shields.io/badge/license-AGPLv3-blue)

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

项目在 GitHub Actions 上构建跨平台二进制（Linux/Windows/macOS）。构建产物会以 artifacts 上传，tag 推送时会创建 Release 并把资产附到 Release：

- 在 Actions 页面选择对应 workflow 运行，下载名为 `leropilot-<os>-<run_id>` 的 artifact（临时）。
- 在 Releases 页面下载正式发布的资产，文件名类似 `leropilot-<tag>-<os>`（长期保存）。

注意：签名/签章（如 macOS notarization 或 Windows Authenticode）需要证书与私密凭据，不在默认 CI 中完成。

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

LeRoPilot 的跨平台可执行文件由 GitHub Actions 自动构建并作为 artifacts 或 Release 资产提供下载。

- 如果你想获取 CI 构建（临时保存）的产物：打开仓库的 Actions 标签页，选择对应的 workflow 运行，下载名为 `leropilot-<os>-<run_id>` 的 artifact。
- 要获取官方发布的二进制文件：打开仓库的 Releases 页面，下载对应 tag 下附带的资产（文件命名类似 `leropilot-<tag>-<os>`）。

推荐的发布流程：

1. 在仓库中推送一个 tag（例如 `v0.1.0`），这会触发 `publish-release.yml` workflow。
2. Actions 会在 Linux/Windows/macOS 上构建对应平台的二进制并将其上传为 artifacts，然后创建一个 GitHub Release 并把这些资产附到 Release 中。
3. 在 Release 页面下载对应平台的资产并分发给用户。

注意事项：
- Actions 上传的 workflow artifacts 会在一段时间后过期；Release 资产会长期保留，适合对外发布。
- 生成平台特定的签名/安装器（例如 macOS 的 notarization 或 Windows 的 Authenticode 签名）需要额外的证书与私密凭据，这些通常不在默认 CI 中完成，需要在拥有相应凭据的环境中执行额外步骤。

