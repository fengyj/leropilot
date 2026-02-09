# RobotTelecontrolService 快速参考指南

## API 概览

### RobotTelecontrolService

主要类用于控制和监控机器人。

```python
from leropilot.services.hardware.robots import RobotTelecontrolService

# 使用 async context manager
async with RobotTelecontrolService(robot) as service:
    await service.start(callback=telemetry_handler, fps=30)
    
    # 发送命令 - 使用 motor name（逻辑名称）
    await service.set_positions({
        "motor_bus_1": {"joint_1": 0.5, "joint_2": -0.3}
    })
    await service.set_torques({
        "motor_bus_1": {"joint_1": True, "joint_2": False}
    })
    await service.set_velocities({
        "motor_bus_1": {"joint_1": 1.0, "joint_2": -0.5}
    })
    
    # 校准
    await service.set_homing_offsets({
        "motor_bus_1": {
            "joint_1": {"range_min": -100, "range_max": 100},
            "joint_2": {"range_min": -50, "range_max": 50}
        }
    })
    await service.set_ranges({
        "motor_bus_1": {
            "joint_1": {"range_min": -100, "range_max": 100}
        }
    })
    
    # 控制
    await service.polling(False)  # 暂停数据读取
    await service.emergency_stop()  # 紧急停止
```

### RobotTelecontrolSession

WebSocket 会话处理器。

```python
from leropilot.services.hardware.robots import RobotTelecontrolSession
from fastapi import WebSocket

@app.websocket("/robots/{robot_id}/telecontrol")
async def robot_ws(websocket: WebSocket, robot_id: str):
    session = RobotTelecontrolSession(robot_id, normalized=True)
    await session.accept(websocket)
```

## WebSocket 协议

### 数据结构说明

所有电机相关命令采用统一的分层结构：
```
{
  bus_name: {              # 电机总线名称
    motor_name: value      # 电机逻辑名称 -> 值
  }
}
```

- **bus_name**: 来自 robot definition（如 "motor_bus_1"）
- **motor_name**: 电机逻辑名称，来自 robot definition（如 "joint_1"）

### 客户端 → 服务器

所有命令都是 JSON 格式，必须包含 `type` 字段。

#### 设置位置
```json
{
  "type": "set_positions",
  "motor_positions": {
    "motor_bus_1": {
      "joint_1": 0.5,
      "joint_2": -0.3
    }
  }
}
```

#### 设置扭矩
```json
{
  "type": "set_torques",
  "motor_enabled": {
    "motor_bus_1": {
      "joint_1": true,
      "joint_2": false
    }
  }
}
```

#### 设置速度
```json
{
  "type": "set_velocities",
  "motor_velocities": {
    "motor_bus_1": {
      "joint_1": 1.0,
      "joint_2": -0.5
    }
  }
}
```

#### 紧急停止
```json
{
  "type": "emergency_stop"
}
```

#### 控制数据读取
```json
{
  "type": "polling",
  "enabled": false
}
```

#### 设置零点偏移
```json
{
  "type": "set_homing_offsets",
  "motor_offsets": {
    "motor_bus_1": {
      "joint_1": {"range_min": -100, "range_max": 100},
      "joint_2": {"range_min": -50, "range_max": 50}
    }
  }
}
```

#### 设置范围
```json
{
  "type": "set_ranges",
  "motor_ranges": {
    "motor_bus_1": {
      "joint_1": {"range_min": -100, "range_max": 100},
      "joint_2": {"range_min": -50, "range_max": 50}
    }
  }
}
```

#### 心跳
```json
{
  "type": "heartbeat"
}
```

### 服务器 → 客户端

#### 会话初始化
```json
{
  "type": "session_init",
  "robot_id": "robot_123",
  "normalized": true,
  "fps": 30
}
```

#### 遥测数据
```json
{
  "type": "telemetry",
  "frame": {
    "timestamp": 1234567890.123,
    "actual_fps": 30,
    "motor_buses": {
      "bus_1": {
        "bus_name": "bus_1",
        "motors": {
          "joint_1": {
            "id": 1,
            "position": 0.5,
            "velocity": 0.0,
            "current": 100,
            "load": 50,
            "temperature": 35,
            "voltage": 12.0,
            "moving": false,
            "goal_position": 0.5,
            "error": 0,
            "protection_status": {
              "status": "ok",
              "violations": []
            }
          }
        }
      }
    },
    "actual_fps": 30,
    "normalized": true
  }
}
```

#### 命令确认
```json
{
  "type": "command_ack",
  "command_type": "set_positions",
  "success": true,
  "message": "Set positions for 2 motor(s)"
}
```

#### 错误
```json
{
  "type": "error",
  "code": "DEVICE_NOT_AVAILABLE",
  "message": "Robot is offline",
  "details": {
    "robot_id": "robot_123"
  }
}
```

## 类型参考

### MotorID
```python
MotorID = int | tuple[int, int]
```
- `int`: 串口电机（Dynamixel, Feetech）
- `tuple[int, int]`: CAN 电机（Damiao）(send_id, recv_id)

### 位置值
- 如果 `normalized=True`: [-1.0, 1.0]
- 如果 `normalized=False`: 原始编码器单位（通常是 int）

### 速度值
通常为 rad/s 或 rpm（取决于电机类型）

## 错误码

- `DEVICE_NOT_AVAILABLE` - 设备离线或不可用
- `SESSION_INIT_FAILED` - 会话初始化失败
- `UNKNOWN_COMMAND` - 未知命令类型
- `INVALID_JSON` - JSON 解析失败
- `COMMAND_FAILED` - 命令执行失败

## 最佳实践

### 1. 连接管理
```javascript
// 自动心跳
const heartbeatInterval = setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "heartbeat" }));
  }
}, 2000);  // 每 2 秒一次

// 清理
window.addEventListener('beforeunload', () => {
  clearInterval(heartbeatInterval);
  ws.close();
});
```

### 2. 错误处理
```javascript
ws.onerror = (event) => {
  console.error("WebSocket error:", event);
  // 重新连接逻辑
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "error") {
    console.error(`Error [${msg.code}]:`, msg.message);
    // 显示用户提示
  }
};
```

### 3. 数据处理
```javascript
// 缓冲遥测数据
const telemetryBuffer = [];
const MAX_BUFFER_SIZE = 100;  // 保留最近的 100 帧

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "telemetry") {
    telemetryBuffer.push(msg.frame);
    if (telemetryBuffer.length > MAX_BUFFER_SIZE) {
      telemetryBuffer.shift();
    }
    updateUI(msg.frame);
  }
};
```

### 4. 命令发送
```javascript
// 限流 - 避免过度发送命令
const commandQueue = [];
let isProcessing = false;

async function sendCommand(command) {
  commandQueue.push(command);
  if (!isProcessing) {
    processQueue();
  }
}

async function processQueue() {
  isProcessing = true;
  while (commandQueue.length > 0) {
    const cmd = commandQueue.shift();
    ws.send(JSON.stringify(cmd));
    await new Promise(resolve => setTimeout(resolve, 20));  // 50Hz 限制
  }
  isProcessing = false;
}
```

## 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `fps` | int | 30 | 目标帧率 |
| `normalized` | bool | False | 是否规范化位置 |
| `heartbeat_timeout` | float | 5.0 | 心跳超时（秒） |

## 性能指标

- 目标 FPS: 30（可配置）
- 心跳超时: 5 秒
- 最多电机总线: 8-16（取决于硬件）
- 单总线电机数: 254（Dynamixel）

## 故障排除

### 连接超时
- 检查 robot 状态（必须为 AVAILABLE）
- 检查 motor bus 接口配置
- 验证硬件连接

### 电机不响应
- 检查心跳是否正常（2 秒）
- 确认 polling 已启用
- 检查电机启用状态

### 数据不准确
- 验证规范化设置
- 检查校准数据
- 查看 FPS 是否稳定

## 示例应用

完整的 React 应用示例：

```tsx
import { useState, useEffect, useRef } from 'react';

export function RobotControl({ robotId }) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [telemetry, setTelemetry] = useState(null);
  const [fps, setFps] = useState(0);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/robots/${robotId}/telecontrol?normalized=true`);
    
    ws.onopen = () => {
      setConnected(true);
      // 启动心跳
      const interval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "heartbeat" }));
        }
      }, 2000);
      return () => clearInterval(interval);
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "telemetry") {
        setTelemetry(msg.frame);
        setFps(msg.frame.actual_fps);
      }
    };

    ws.onclose = () => setConnected(false);
    wsRef.current = ws;

    return () => ws.close();
  }, [robotId]);

  const setPosition = (motorId, position) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "set_positions",
        motor_positions: { [motorId]: position }
      }));
    }
  };

  return (
    <div className="control-panel">
      <div>状态: {connected ? "✓ 已连接" : "✗ 离线"}</div>
      <div>FPS: {fps.toFixed(1)}</div>
      {telemetry && (
        <div>
          {Object.entries(telemetry.motor_buses).map(([busName, busData]) => (
            <div key={busName}>
              {Object.entries(busData.motors).map(([motorId, telemetry]) => (
                <MotorWidget
                  key={motorId}
                  motorId={motorId}
                  telemetry={telemetry}
                  onSetPosition={setPosition}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

## 更多帮助

- 查看 `IMPLEMENTATION_TELECONTROL.md` 了解实现细节
- 查看 `tests/` 目录中的单元测试了解用法示例
- 查看源代码中的 docstring 了解详细 API
