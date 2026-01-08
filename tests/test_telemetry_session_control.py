# ruff: noqa
import asyncio
from types import SimpleNamespace

import pytest

from leropilot.services.hardware.telemetry import TelemetrySession


class FakeDriver:
    def __init__(self):
        self.torque_calls = []
        self.position_calls = []
        self.disconnected = False

    def write_torque_enable(self, motor_id, enabled):
        self.torque_calls.append((motor_id, enabled))

    def write_goal_position(self, motor_id, position):
        self.position_calls.append((motor_id, position))

    def disconnect(self):
        self.disconnected = True


class FakeMotorService:
    def create_driver(self, interface, brand, interface_type, baud_rate):
        return FakeDriver()


@pytest.mark.asyncio
async def test_open_and_control():
    device = SimpleNamespace(labels={}, connection_settings={})
    motor_service = FakeMotorService()
    session = TelemetrySession(device_id="SNCTL", driver=None, motor_service=motor_service, device=device, brand="dynamixel", target_ids=[1,2], poll_interval_ms=10)

    opened = await session.open_driver(interface="COM3", baud_rate=1000000)
    assert opened
    assert session.driver is not None

    # Without calibration, control should be blocked
    ack = await session.set_torque(False)
    assert ack.get("success") is False

    # Add fake calibration data
    # Use `calibration_settings` instead of deprecated `config` structure
    device.calibration_settings = {"motor_bus": [SimpleNamespace(homing_offset=0)]}

    ack = await session.set_position(1, 123)
    assert ack.get("success") is True

    ack = await session.set_positions([{"id":1, "position":100}, {"id":2, "position":200}])
    assert ack.get("success") is True

    ack = await session.set_torque(False)
    assert ack.get("success") is True

    # emergency_stop should emit event into queue
    q = session.subscribe()
    ack = await session.emergency_stop()
    assert ack.get("success") is True

    found = False
    # Drain queue
    for _ in range(10):
        if not q.empty():
            m = q.get_nowait()
            if m.get("type") == "event" and m.get("event", {}).get("code") == "EMERGENCY_STOP":
                found = True
                break
        await asyncio.sleep(0.01)

    assert found

    # Close driver and verify underlying driver disconnect was called
    drv = session.driver
    await session.close_driver()
    assert session.driver is None
    assert isinstance(drv, FakeDriver)
    assert drv.disconnected
