# LeRoPilot


[![Build Matrix](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml/badge.svg?branch=main)](https://github.com/fengyj/leropilot/actions/workflows/build-matrix.yml) ![license](https://img.shields.io/badge/license-AGPLv3-blue)

**License:** AGPLv3 — Copyright © 2025 冯裕坚 (Feng Yu Jian) <fengyj@live.com>.

中文说明：参见 `README_zh.md`。

一句快速开始：下载对应平台的二进制后运行（Linux/macOS）:

```bash
chmod +x ./leropilot && ./leropilot
```

或 Windows 上双击 `leropilot.exe`。

## 目录

- [快速开始 (Quick Start)](#快速开始-quick-start)
- [下载并运行 (Downloads)](#下载并运行-downloads)
- [从源码构建 (Build from Source)](#从源码构建-build-from-source)
- [开发模式 (Development)](#开发模式-development)
- [配置 (Configuration)](#配置-configuration)
- [CI / Releases](#ci--releases)
- [许可与贡献者协议 (License & CLA)](#许可与贡献者协议-license--cla)
- [商业授权 (Commercial)](#商业授权-commercial)
- [故障排查 (Troubleshooting)](#故障排查-troubleshooting)
- [联系方式 (Contact)](#联系方式-contact)

## 快速开始 (Quick Start)

1. 从 Releases 页下载与你的平台匹配的资产（`leropilot-<tag>-<os>`）。
2. 在 macOS / Linux 上：

```bash
chmod +x ./leropilot
./leropilot
```

Windows：双击 `leropilot.exe`。

默认打开浏览器并在 `http://127.0.0.1:8000` 提供 UI 界面。

## 下载并运行 (Downloads)

预编译的可执行文件可在 Releases 页面获取，文件命名格式示例：`leropilot-v0.1.0-linux`、`leropilot-v0.1.0-win.exe`、`leropilot-v0.1.0-mac`。

## 从源码构建 (Build from Source)

### 要求

- Python 3.10+
- Node.js 16+

> 注意：PyInstaller 不能可靠地跨平台交叉编译。要生成 Windows 可执行文件，请在 Windows runner（或本地 Windows）上构建；要生成 macOS 可执行，请在 macOS runner（或本地 macOS）上构建。

### 构建步骤

```bash
# 安装 Python 依赖
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

### 触发发布（示例）

在仓库中打标签并推送以触发 release 工作流：

```bash
git tag v0.1.0
git push origin v0.1.0
```

## 开发模式 (Development)

后端（FastAPI）运行：

```bash
python -m leropilot.main
```

前端开发服务器：

```bash
cd frontend
npm run dev
```

开发模式下前端地址为 `http://localhost:5173`，API 可通过代理访问后端。

## 配置 (Configuration)

应用数据存放在 `~/.leropilot/`：

- 配置：`~/.leropilot/config.yaml`
- 日志：`~/.leropilot/logs/`

示例 `config.yaml`：

```yaml
port: 8000
data_dir: ~/.leropilot
```

也可以通过环境变量（`LEROPILOT_` 前缀）覆盖配置：

```bash
export LEROPILOT_PORT=9000
```

## CI / Releases

LeRoPilot 在 GitHub Actions 上进行跨平台构建（Linux/Windows/macOS），构建产物会以 artifacts 形式上传，tag 推送时还会创建 Release 并把资产附到 Release。以下为常见操作：

- 在 Actions 标签页中选择对应的 workflow 运行，下载名为 `leropilot-<os>-<run_id>` 的 artifact（临时）。
- 在 Releases 页面下载正式发布的资产，文件名类似 `leropilot-<tag>-<os>`（长期保存）。

注意：签名/签章（macOS notarization 或 Windows Authenticode）需要额外凭据，不在默认 CI 中完成。

## 许可与贡献者协议 (License & CLA)

本项目采用 GNU AGPLv3 许可，详见 `LICENSE`。为保留商业许可选项，外部贡献者需要签署 CLA（参见 `cla/CLA.md` 和 `CONTRIBUTING.md`）。

在 PR 描述中包含以下行以接受 CLA：

```
I accept the CLA (Contributor License Agreement). Name: <Your Full Name>, Email: <your-email>
```

## 商业授权 (Commercial)

如需商业许可或企业支持，请参见 `COMMERCIAL.md`。

## 故障排查 (Troubleshooting)

- WSL/无 GUI 环境：自动打开浏览器可能失败（xdg-open 错误），你仍可手动访问 `http://127.0.0.1:8000`。
- 权限：在 macOS/Linux 上运行前执行 `chmod +x ./leropilot`。
- 端口占用：如果 8000 被占用，设置环境变量或 `config.yaml` 修改端口。
- 构建跨平台失败：请在对应平台上构建（参见 PyInstaller 注意）。

## 联系方式 (Contact)

- 作者：冯裕坚 (Feng Yu Jian)
- 邮箱：fengyj@live.com

---

感谢使用与关注 LeRoPilot！欢迎按 `CONTRIBUTING.md` 指引参与贡献。

## CI / Releases

Pre-built artifacts for Linux, Windows and macOS are produced by GitHub Actions and attached to Releases.

- To download CI-built artifacts (temporary): open the workflow run in the repository Actions tab and download the artifact named like `leropilot-<os>-<run_id>`.
- To download official release binaries: open the repository Releases page and download the assets attached to the desired tag (files are named `leropilot-<tag>-<os>`).

Recommended release workflow:

1. Push a tag (for example `v0.1.0`) to trigger the `publish-release.yml` workflow.
2. Actions will build binaries for all supported platforms and create a GitHub Release for that tag.
3. Download the platform-specific asset from the Release page and distribute it to users.

Notes:
- Artifacts uploaded by workflow runs are retained for a limited time; Releases are persistent and intended for distribution.
- Building platform-specific installers or signing (macOS notarization or Windows Authenticode) requires additional credentials and is not performed by default.

