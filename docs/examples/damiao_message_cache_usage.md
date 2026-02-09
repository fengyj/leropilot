# Damiao Message Cache Usage Guide

## Overview

The Damiao driver now includes automatic message caching through a background receive thread. This reduces CAN bus traffic and improves performance by:

1. **Continuous reception**: Messages are collected in the background without blocking
2. **Smart caching**: Status and parameters cached separately with timestamps
3. **Deferred parsing**: Raw bytes stored, parsed only when needed with current parameter values

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   DamiaoCAN_Driver                      │
│                                                         │
│  ┌─────────────────┐       ┌──────────────────┐       │
│  │  Receive Thread │──────>│  MessageCache    │       │
│  │  (_receive_loop)│       │                  │       │
│  └─────────────────┘       │  - status_cache  │       │
│                             │  - param_cache   │       │
│  ┌─────────────────┐       │  - param_events  │       │
│  │  Main Thread    │<──────│                  │       │
│  │  (your code)    │       └──────────────────┘       │
│  └─────────────────┘                                   │
└─────────────────────────────────────────────────────────┘
```

## Message Types Cached

### 1. Status Feedback (MST_ID)
- **Triggered by**: All control commands (MIT, position, velocity, torque)
- **CAN ID**: Motor's recv_id
- **Data**: Position, velocity, torque, temperatures, error state
- **Cache key**: `motor_id`
- **Typical max_age**: 0.1 - 1.0 seconds (needs fresh data)

### 2. Parameter Responses (0x7FF)
- **Types**:
  - Read response (0x33): Returns 4-byte parameter value
  - Write confirmation (0x55): Confirms parameter written
  - Store confirmation (0xAA): Confirms saved to flash
- **Data**: Register ID + value (int or float, depends on register)
- **Cache key**: `(motor_id, register_id)`
- **Typical max_age**: 60+ seconds (parameters change rarely)

## Basic Usage

### 1. Register Motors on Connect

```python
driver = DamiaoCAN_Driver(interface="pcan:PCAN_USBBUS1")
driver.connect()

# Register each motor so receive thread can route messages
for motor_id in [(0x01, 0x11), (0x02, 0x12)]:
    driver.register_motor_id(motor_id)
```

### 2. Read Status from Cache

```python
# Option A: Read from cache (fast, may be None if no recent data)
raw_status = driver.cache.get_status_raw(motor_id, max_age=0.1)
if raw_status:
    # Parse with current parameter values
    pmax, vmax, tmax = driver.register.get_pmax_vmax_tmax(motor_id)
    state = (raw_status[1] >> 4) & 0x0F
    pos_u = (raw_status[1] << 8) | raw_status[2]
    vel_u = (raw_status[3] << 4) | (raw_status[4] >> 4)
    torq_u = ((raw_status[4] & 0x0F) << 8) | raw_status[5]
    
    position = uint_to_float(pos_u, -pmax, pmax, 16)
    velocity = uint_to_float(vel_u, -vmax, vmax, 12)
    torque = uint_to_float(torq_u, -tmax, tmax, 12)
    temp_mos = raw_status[6]
    temp_rotor = raw_status[7]
else:
    # No recent status, need to trigger refresh
    driver.refresh_status(motor_id)
    time.sleep(0.01)
    raw_status = driver.cache.get_status_raw(motor_id, max_age=0.1)
```

### 3. Read Parameter with Smart Caching

```python
# Try cache first (allows 60s old data for stable parameters)
raw_param = driver.cache.get_parameter_raw(motor_id, register_id, max_age=60.0)

if raw_param:
    # Parse from cache (instant, no CAN traffic)
    if register_type == "float":
        # data[4:8] contains 4-byte float
        value = struct.unpack('<f', raw_param[4:8])[0]
    else:
        # data[4:8] contains 4-byte int
        value = struct.unpack('<I', raw_param[4:8])[0]
else:
    # Not cached, send read command
    driver.register._send_read_command(motor_id, register_id)
    
    # Wait for response with event (better than sleep)
    if driver.cache.wait_for_parameter(motor_id, register_id, timeout=0.5):
        raw_param = driver.cache.get_parameter_raw(motor_id, register_id)
        # Parse as above
    else:
        raise TimeoutError("Parameter read timeout")
```

### 4. Write Parameter

```python
# Write triggers automatic caching of confirmation
driver.register.write_parameter(motor_id, register_id, value)

# Confirmation automatically cached by receive thread
# You can verify with:
raw_confirm = driver.cache.get_parameter_raw(motor_id, register_id, max_age=1.0)
if raw_confirm and raw_confirm[2] == 0x55:
    print("Write confirmed")
```

## Advanced: Deferred Parsing Pattern

The cache stores **raw bytes only** to avoid blocking the receive thread. This means:

### ❌ Old approach (parse in receive thread - BLOCKS)
```python
def _classify_and_cache(self, msg):
    # BAD: Reading pmax/vmax/tmax here blocks receive thread
    pmax, vmax, tmax = self.register.get_pmax_vmax_tmax(motor_id)
    position = uint_to_float(pos_u, -pmax, pmax, 16)  # Parse now
    self.cache.update_status(motor_id, position=position, ...)
```

### ✅ New approach (parse at read time - NON-BLOCKING)
```python
def _classify_and_cache(self, msg):
    # GOOD: Just store raw bytes, no I/O or complex logic
    self.cache.update_status(motor_id, msg.data, msg.arbitration_id)

# Later, when reading:
def read_position(self, motor_id):
    raw = self.cache.get_status_raw(motor_id)
    if raw:
        # NOW parse, when we're not in the receive thread
        pmax, vmax, tmax = self.register.get_pmax_vmax_tmax(motor_id)
        pos_u = (raw[1] << 8) | raw[2]
        return uint_to_float(pos_u, -pmax, pmax, 16)
```

**Why this matters**:
- Receive thread stays fast and responsive
- pmax/vmax/tmax may change (user updates limits), parsing uses latest values
- Register type (int vs float) determined by caller who knows what they're reading

## Thread Safety

All cache operations are thread-safe with internal locks:

```python
# Safe to call from multiple threads
position_thread_1 = driver.cache.get_status_raw(motor_id)
param_thread_2 = driver.cache.get_parameter_raw(motor_id, reg_id)
```

## Cleanup on Disconnect

```python
driver.disconnect()
# Automatically:
# 1. Stops receive thread
# 2. Clears all caches
# 3. Wakes waiting threads (no deadlock)
```

## Performance Tips

### 1. Batch Status Reads
```python
# Instead of individual reads:
for mid in motor_ids:
    driver.refresh_status(mid)
    
time.sleep(0.01)  # Short delay for responses

positions = {}
for mid in motor_ids:
    raw = driver.cache.get_status_raw(mid)
    if raw:
        positions[mid] = parse_position(raw)
```

### 2. Long Cache for Stable Parameters
```python
# Motor model unlikely to change, cache for hours
raw_model = driver.cache.get_parameter_raw(
    motor_id, 
    DamiaoRegisters.MOTOR_MODEL,
    max_age=3600.0  # 1 hour
)
```

### 3. Event-Based Waiting
```python
# ❌ Bad: Fixed sleep (too short = fail, too long = slow)
driver.register._send_read_command(motor_id, reg_id)
time.sleep(0.1)  # Hope it arrives in time?

# ✅ Good: Wait exactly as long as needed
driver.register._send_read_command(motor_id, reg_id)
if driver.cache.wait_for_parameter(motor_id, reg_id, timeout=0.5):
    # Returns immediately when message arrives
    raw = driver.cache.get_parameter_raw(motor_id, reg_id)
```

## Debugging

Enable debug logging to see message classification:

```python
import logging
logging.getLogger('leropilot.services.hardware.motor_drivers.damiao').setLevel(logging.DEBUG)

# You'll see:
# DEBUG: Cached parameter read: motor=(1, 17), reg=0x7005
# DEBUG: Received status from unregistered motor: recv_id=0x13
```

## Migration from Old Code

### Before (blocking reads)
```python
driver.send_mit_control(motor_id, p, v, t, kp, kd)
response = driver.recv_motor_response(motor_id, timeout=0.1)
position = parse_response(response)
```

### After (cached reads)
```python
driver.send_mit_control(motor_id, p, v, t, kp, kd)
# Response automatically cached by receive thread
time.sleep(0.005)  # Minimal delay for message to arrive
raw = driver.cache.get_status_raw(motor_id, max_age=0.1)
if raw:
    position = parse_status(raw)
```

**Or even better**: Don't wait at all, just read cache on next control cycle!

```python
# Control loop
while True:
    # Read last known position from cache
    raw = driver.cache.get_status_raw(motor_id, max_age=0.05)
    position = parse_status(raw) if raw else last_position
    
    # Compute control
    new_cmd = controller.update(position)
    
    # Send command (will trigger status response that gets cached)
    driver.send_mit_control(motor_id, new_cmd)
```
