# 常见问题解答 (FAQ)

## 一般问题

### LeRoPilot 是什么？

LeRoPilot 是 LeRobot 的图形化界面，简化了机器人项目的环境管理、设备配置和数据录制。

### LeRoPilot 免费吗？

是的，LeRoPilot 是开源软件，采用 AGPLv3 许可证免费使用。也提供商业许可。

### 支持哪些平台？

LeRoPilot 支持 Windows 10/11、macOS 10.15+ 和 Linux (Ubuntu 20.04+)。

## 安装

### 需要安装 Python 吗？

- **桌面模式**：不需要，Python 已打包在应用程序中
- **浏览器模式**：需要，需要 Python 3.10 或 3.11

### 需要多少磁盘空间？

- 应用程序：约 200MB
- 每个 LeRobot 环境：2-5GB（取决于包）
- 数据集：根据录制大小而定

### 可以安装多个版本吗？

可以，您可以并行安装多个版本。每个版本维护自己的配置。

## 环境管理

### 可以创建多少个环境？

没有硬性限制。每个环境都是独立的，存储在 `~/.leropilot/environments/` 中。

### 可以使用现有的 Python 环境吗？

不能直接使用。LeRoPilot 创建和管理自己的虚拟环境以确保兼容性。

### 如何删除环境？

转到环境 → 选择环境 → 点击"删除"。这将删除虚拟环境但保留您的数据。

### 可以在不同机器间共享环境吗？

由于二进制依赖性，环境是特定于机器的。但是，您可以导出环境规范并在另一台机器上重新创建。

## 设备管理

### 支持哪些设备？

LeRoPilot 支持与 LeRobot 兼容的设备，包括：

- 机械臂（Koch、SO100 等）
- 摄像头（USB、网络摄像头）
- 通过配置的自定义设备

### 我的摄像头未被检测到，怎么办？

1. 检查摄像头是否在其他应用程序中工作
2. 验证 USB 连接和权限
3. 参见[故障排除 - 摄像头问题](Troubleshooting_zh.md#摄像头问题)

### 可以同时使用多个摄像头吗？

可以，您可以配置和使用多个摄像头进行多视角录制。

## 数据录制

### 数据集存储在哪里？

默认情况下，数据集存储在 `~/.leropilot/data/` 中。您可以在设置 → 路径 → 数据目录中更改。

### 录制以什么格式保存？

录制以 LeRobot 的标准格式保存（HDF5 或 Parquet，取决于配置）。

### 可以暂停和恢复录制吗？

目前，每个录制会话创建一个单独的片段。暂停/恢复功能尚未支持。

## 配置

### 配置文件在哪里？

配置存储在 `~/.leropilot/config.json` 中。

### 可以更改默认端口吗？

可以，在设置 → 服务器 → 端口中，或通过命令行：

```bash
leropilot --port 8080
```

### 如何重置为默认设置？

删除 `~/.leropilot/config.json` 并重启 LeRoPilot。将使用默认值创建新配置。

## 故障排除

### 应用程序无法启动

1. 检查系统要求
2. 查看 `~/.leropilot/logs/` 中的日志
3. 参见[故障排除指南](Troubleshooting_zh.md)

### 环境创建失败

常见原因：

- 网络问题（无法下载包）
- 磁盘空间不足
- Python 版本不兼容

参见[故障排除 - 环境创建](Troubleshooting_zh.md#环境创建)

### UI 空白或无响应

1. 清除浏览器缓存（浏览器模式）
2. 重启应用程序
3. 检查后端是否运行（查找端口 8000）

## 开发

### 如何贡献？

参见我们的[贡献指南](../CONTRIBUTING.md)了解提交拉取请求的指南。

### 在哪里报告 Bug？

在我们的 [GitHub Issues](https://github.com/fengyj/leropilot/issues) 页面报告 Bug。

### 有开发路线图吗？

有的，参见我们的 [GitHub Projects](https://github.com/fengyj/leropilot/projects) 了解计划的功能。

## 商业使用

### 可以商业使用 LeRoPilot 吗？

可以，在 AGPLv3 下（需要公开源代码）或通过商业许可。详见 [COMMERCIAL.md](../COMMERCIAL.md)。

### 如何获得商业许可？

请联系 fengyj@live.com 咨询商业许可。

## 还有问题？

- [GitHub Discussions](https://github.com/fengyj/leropilot/discussions) - 向社区提问
- [GitHub Issues](https://github.com/fengyj/leropilot/issues) - 报告 Bug
- 邮箱：fengyj@live.com
