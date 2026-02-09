# RobotTelecontrolService 和 RobotTelecontrolSession 实现说明

## 概述

本实现为 LeRoPilot 提供了完整的机器人遥操作（teleoperation）能力，包括：

1. **RobotTelecontrolService** - 后端服务，负责电机数据读取和控制
2. **RobotTelecontrolSession** - WebSocket 会话，处理客户端连接和消息分发
3. **WebSocket API 模型** - 定义了客户端与服务器之间的通信协议

## 核心文件

### 模型定义

**文件**: `src/leropilot/models/hardware.py`

核心数据模型：
- `RobotTelemetryFrame` - 机器人完整遥测数据帧（包含 actual_fps: int）
- `MotorBusData` - 单个电机总线的数据（motors: dict[str, MotorTelemetry]）
- `MotorTelemetry` - 单个电机的遥测数据

**文件**: `src/leropilot/models/api/web_socket.py`

定义了所有 WebSocket 相关的 API 模型：

客户端命令：
- `SetPositionsCommand` - 设置电机位置
- `SetTorquesCommand` - 启用/禁用电机扭矩
- `SetVelocitiesCommand` - 设置电机速度
- `EmergencyStopCommand` - 紧急停止
- `PollingCommand` - 暂停/恢复数据读取
- `SetHomingOffsetsCommand` - 设置零点偏移
- `SetRangesCommand` - 设置位置范围
- `HeartbeatCommand` - 心跳信号

服务器响应：
- `SessionInitMessage` - 会话初始化消息
- `TelemetryMessage` - 遥测数据消息
- `CommandAckMessage` - 命令确认
- `ErrorMessage` - 错误消息

### 服务实现

**文件**: `src/leropilot/services/hardware/robots/telecontrol.py`

`RobotTelecontrolService` 类：

#### 初始化
- 验证 robot 状态为 AVAILABLE
- 验证所有 motor_bus_connections 都有 interface 配置
- 支持异步上下文管理器（`async with`）

#### 核心方法

**start(callback, fps)**
- 初始化所有电机总线（create → connect → scan → register）
- 启动异步读取循环
- 参数：
  - `callback`: 异步回调函数，接收 `RobotTelemetryFrame`
  - `fps`: 目标帧率（整数）

**stop()**
- 停止读取循环
- 断开所有电机总线连接
- 自动清理资源

**_read_loop()**
- 主异步循环，按目标 FPS 读取数据
- 并行读取所有电机总线（使用 `asyncio.gather`）
- 计算实际 FPS
- 调用回调函数

**FPS 计算**
- 使用 deque 存储最近 2 秒的时间戳
- 当样本数 >= 2*fps 时计算实际 FPS
- 每秒更新一次
- 结果为整数（通过 round() 舍入）

#### 电机操作方法

**emergency_stop()**
- 并发禁用所有电机

**set_positions(motor_positions: dict[str, dict[str, float]])**
- 并发设置多个电机位置
- 参数结构：{bus_name: {motor_name: position}}
- motor_name 为逻辑名称，service 内部转换为 MotorID
- 支持规范化位置 [-1, 1]

**set_torques(motor_enabled: dict[str, dict[str, bool]])**
- 并发启用/禁用多个电机
- 参数结构：{bus_name: {motor_name: enabled}}

**set_velocities(motor_velocities: dict[str, dict[str, float]])**
- 并发设置多个电机速度
- 参数结构：{bus_name: {motor_name: velocity}}

#### 校准方法

**set_homing_offsets(motor_offsets: dict[str, dict[str, dict[str, int]]])**
- 读取当前电机位置
- 计算并设置零点偏移
- 更新范围限制
- 注册校准数据到电机总线
- 参数结构：{bus_name: {motor_name: {range_min, range_max}}}

**set_ranges(motor_ranges: dict[str, dict[str, dict[str, int]]])**
- 设置电机位置范围（最小/最大）
- 更新校准数据
- 参数结构：{bus_name: {motor_name: {range_min, range_max}}}

#### 控制方法

**polling(enabled: bool)**
- 暂停/恢复电机数据读取
- 使用 `asyncio.Event` 实现

### WebSocket 会话实现

**文件**: `src/leropilot/services/hardware/robots/session.py`

`RobotTelecontrolSession` 类：

#### 初始化
- 验证 robot 存在（从 RobotManager 获取）
- 初始化时不启动服务（在 accept 时启动）

#### 接收连接

**accept(websocket)**
- 初始化 WebSocket 连接
- 创建并启动 RobotTelecontrolService
- 发送 `SessionInitMessage`
- 启动心跳监控任务
- 进入消息循环

#### 消息处理

**_message_loop()**
- 接收并解析 JSON 消息
- 根据 `type` 字段分发到对应的处理函数

支持的命令处理：
- `_handle_heartbeat()` - 更新最后心跳时间
- `_handle_emergency_stop()` - 调用 service.emergency_stop()
- `_handle_set_positions()` - 调用 service.set_positions()
- `_handle_set_torques()` - 调用 service.set_torques()
- `_handle_set_velocities()` - 调用 service.set_velocities()
- `_handle_polling()` - 调用 service.polling()
- `_handle_set_homing_offsets()` - 调用 service.set_homing_offsets()
- `_handle_set_ranges()` - 调用 service.set_ranges()

#### 心跳监控

**_monitor_heartbeat()**
- 监控客户端心跳
- 超时阈值：5 秒
- 超时时自动调用 stop()

#### 清理

**stop()**
- 停止消息循环
- 取消心跳监控任务
- 停止 RobotTelecontrolService
- 关闭 WebSocket 连接

#### 遥测发送

**_send_telemetry_frame(frame)**
- 将 RobotTelemetryFrame 转换为 TelemetryMessage
- 发送 JSON 到客户端
- motor 索引已映射为逻辑名称（来自 RobotDefinition）

## 关键设计决策

### 1. 完全异步架构
- 使用 `asyncio` 而非线程
- 支持多个电机总线的并发读取
- 更好地与 FastAPI 集成

### 2. 并发电机总线读取
- 使用 `asyncio.gather()` 并行读取所有 motorbus
- 提高吞吐量，充分利用 I/O 等待时间

### 3. FPS 计算
- 基于实际读取时间戳计算
- 使用 deque 维护时间历史
- 每秒更新一次

### 4. 资源管理
- 异步上下文管理器确保清理
- 连接断开时自动停止服务
- 异常情况下的错误恢复

### 5. 基于 MotorBus 的分层数据结构
- WebSocket 命令使用 motor name（逻辑名称）作为顶级键
- 组织结构：{bus_name: {motor_name: value}}
- Service 层负责将 motor name 转换为 MotorID
- 提高代码清晰度，避免 ID 混淆
- Motor name 来自 robot definition，便于调试

### 6. 名称到 ID 的转换
- 通过 `_names_to_ids()` 方法进行转换
- 支持整数和元组 ID（Damiao CAN）
- 简化对外 API（基于逻辑名称），简化内部调用（基于 ID）
- 防止僵死连接
- 自动检测客户端离线
- 5 秒超时配置

## 类型系统

所有类型注解使用严格的类型系统：
- `MotorID = int | tuple[int, int]` - 支持串口电机和 CAN 电机（内部使用）
- `fps: int` - 帧率为整数
- WebSocket API 使用 motor name（str）作为键（外部 API）
- 所有函数参数和返回值都有完整的类型注解

## 错误处理

- 构造函数中进行状态验证
- 操作中的异常被捕获并记录
- 向客户端返回 `ErrorMessage`
- 优雅降级（例如部分电机失败不影响整体）

## 单元测试

### test_robot_telecontrol_service.py
- 初始化验证
- 异步上下文管理
- 电机总线初始化
- 电机操作（位置、扭矩、速度）
- FPS 计算
- 校准方法

### test_robot_telecontrol_session.py
- 会话初始化
- WebSocket 连接和接收
- 消息处理（所有命令类型）
- 心跳超时
- 错误处理
- 资源清理

## 使用示例

### 后端集成（在 FastAPI 路由中）

```python
from fastapi import WebSocket
from leropilot.services.hardware.robots import RobotTelecontrolSession

@app.websocket("/hardware/robots/{robot_id}/telecontrol")
async def robot_websocket(websocket: WebSocket, robot_id: str):
    """WebSocket endpoint for robot teleoperation."""
    normalized = websocket.query_params.get("normalized", "false").lower() == "true"
    session = RobotTelecontrolSession(robot_id, normalized=normalized)
    await session.accept(websocket)
```

### 前端使用

```typescript
// 连接到 WebSocket
const ws = new WebSocket(`ws://localhost:8000/hardware/robots/${robotId}/telecontrol?normalized=true`);

// 发送命令 - 注意 motor_positions 使用电机 ID（整数或元组字符串形式）
ws.send(JSON.stringify({
  type: "set_positions",
  motor_positions: { 1: 0.5, 2: -0.3 }
}));

// 接收遥测
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "telemetry") {
    // 处理遥测数据
    updateRobotState(msg.frame);
  }
};

// 心跳
setInterval(() => {
  ws.send(JSON.stringify({ type: "heartbeat" }));
}, 2000);
```

## 性能考虑

- 目标 30 FPS（可配置）
- 所有电机总线并发读取
- 内存高效的 deque 用于 FPS 计算
- 异步 I/O 避免阻塞

## 未来改进方向

1. 支持更复杂的 motor bus 控制算法
2. 添加录制/回放功能
3. 支持多客户端连接管理
4. 实现客户端间数据同步
5. 添加更详细的性能指标
