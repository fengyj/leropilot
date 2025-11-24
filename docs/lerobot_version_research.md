# LeRobot 版本研究总结

## 研究日期

2024-11-23

## 研究来源

- v0.4.1 pyproject.toml
- v0.4.0 pyproject.toml
- v0.3.3 pyproject.toml
- main branch pyproject.toml

## 关键发现

### 1. 版本要求一致性

所有研究的版本（v0.3.3, v0.4.0, v0.4.1, main）都有相同的基础要求：

| 组件        | 要求                            |
| ----------- | ------------------------------- |
| Python      | `>=3.10`                        |
| PyTorch     | `>=2.2.1,<2.8.0`                |
| TorchVision | `>=0.21.0,<0.23.0`              |
| FFmpeg      | 通过 `imageio[ffmpeg]` 自动安装 |

### 2. FFmpeg 处理

- 所有版本都依赖 `imageio[ffmpeg]>=2.34.0,<3.0.0`
- `imageio[ffmpeg]` 会自动下载和管理 FFmpeg 二进制文件
- 用户不需要手动安装 FFmpeg（imageio 会处理）
- 但官方文档仍建议使用 conda 安装 FFmpeg 7.x 以获得 libsvtav1 支持

### 3. 版本差异

**v0.4.1 vs v0.4.0**:

- 几乎完全相同
- 只有版本号不同

**v0.4.x vs v0.3.3**:

- v0.4.x 使用 `datasets>=4.0.0,<4.2.0`
- v0.3.3 使用 `datasets>=2.19.0,<=3.6.0`
- v0.4.x 使用 `av>=15.0.0`
- v0.3.3 使用 `av>=14.2.0`
- 其他核心依赖基本一致

### 4. Extras 对比

**v0.4.x 新增**:

- `phone`: 手机遥控支持
- `reachy2`: Reachy2 机器人

**v0.3.3 独有**:

- `xarm`: xArm 仿真（v0.4.x 移除）
- `pi0`: PI0 模型（v0.4.x 改名为 `pi`）

**共同的 extras**:

- `feetech`, `dynamixel`: 电机
- `gamepad`, `hopejr`, `lekiwi`: 机器人
- `intelrealsense`, `kinematics`: 硬件/功能
- `smolvla`, `hilserl`: 策略模型
- `aloha`, `pusht`: 仿真
- `async`, `dev`, `test`: 功能/开发

### 5. 安装步骤

所有版本的安装步骤相同：

```bash
# 1. 创建虚拟环境
conda create -y -n lerobot python=3.10
conda activate lerobot

# 2. (可选) 安装 FFmpeg
conda install ffmpeg -c conda-forge

# 3. 安装 LeRobot
git clone https://github.com/huggingface/lerobot.git
cd lerobot
pip install -e .

# 4. (可选) 安装 extras
pip install -e ".[aloha,pusht]"
```

## 对设计的影响

### 1. 版本元数据文件准确性 ✅

`docs/lerobot_versions.yaml` 中的信息是准确的：

- Python 3.10+
- PyTorch 2.2+
- FFmpeg 7.x (推荐)

### 2. FFmpeg 安装策略

**更新建议**:

- imageio 会自动安装 FFmpeg，但可能不是最优版本
- 仍建议用户手动安装 FFmpeg 7.x 以获得 libsvtav1 支持
- 我们的程序应该：
  1. 检测 FFmpeg 是否可用
  2. 检测是否支持 libsvtav1
  3. 如果不支持，提示用户安装 FFmpeg 7.x

### 3. Extras 元数据需要更新

`docs/lerobot_extras.yaml` 需要调整：

- v0.3.3: 包含 `xarm` 和 `pi0`
- v0.4.x: 移除 `xarm`，`pi0` 改名为 `pi`，新增 `phone` 和 `reachy2`

### 4. 安装命令

使用 `uv` 的等价命令：

```bash
# 创建虚拟环境
uv venv --python 3.10 /path/to/env

# 安装 LeRobot
uv pip install --python /path/to/env/bin/python -e .

# 安装 extras
uv pip install --python /path/to/env/bin/python -e ".[aloha,pusht]"
```

## 结论

1. ✅ 所有版本的基础要求一致，简化了实现
2. ✅ 版本元数据文件基本准确
3. ⚠️ 需要更新 extras 元数据以反映版本差异
4. ✅ FFmpeg 策略合理（检测 + 提示安装）
5. ✅ 设计文档可以进入实现阶段

## 下一步

1. 更新 `docs/lerobot_extras.yaml` 以准确反映各版本的 extras
2. 开始实现数据模型和管理器
