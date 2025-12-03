# 配置说明

LeRoPilot 提供了全面的设置界面，供您自定义使用体验。您可以点击侧边栏的 **设置** 图标进入设置页面。

## 通用设置

### 外观 (Appearance)

- **主题**: 选择 **跟随系统**、**浅色** 或 **深色** 模式。
- 更改会立即生效。

### 语言 (Language)

- **界面语言**: 在 **English** 和 **中文 (简体中文)** 之间切换。
- 选择后界面会立即更新。

## 路径 (Paths)

### 数据目录

- **位置**: 指定 LeRoPilot 存储环境、数据集和日志的位置。
- **默认**: `~/.leropilot/data` (Linux/macOS) 或 `%USERPROFILE%\.leropilot\data` (Windows)。
- 如果系统盘空间有限，您可以将其更改为自定义位置。

### 只读路径

- 添加 LeRoPilot 可以读取但不能修改的外部目录。
- 用于访问现有的数据集而无需导入。

## 工具 (Tools)

### Git 配置

LeRoPilot 需要 Git 来进行环境管理。您可以选择：

1.  **内置 Git (推荐)**:

    - LeRoPilot 可以下载并管理一个便携版 Git。
    - 与系统 Git 隔离。
    - 确保兼容性。
    - 点击 **"下载并安装"** 即可自动设置。

2.  **自定义 Git**:
    - 使用系统中已安装的 Git。
    - 提供 git 可执行文件的路径（例如 `/usr/bin/git`）。
    - LeRoPilot 会验证版本和路径。

## 仓库源 (Repositories)

配置 LeRoPilot 获取资源的来源。

- **LeRobot 源**: 管理 LeRobot 的上游仓库。
- **HuggingFace**: 配置 HuggingFace Hub 令牌和端点（适用于受限网络）。

## PyPI 镜像 (PyPI Mirrors)

配置 Python 包索引镜像以加速环境创建。

- **镜像**: 添加或删除 PyPI 镜像（例如 TUNA、Aliyun）。
- **首选**: 选择用于安装的首选镜像。
