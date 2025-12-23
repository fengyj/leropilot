# ruff: noqa: ANN201, ANN001, ANN204, ANN401
import asyncio
from types import SimpleNamespace

import pytest

from leropilot.models.hardware import MotorTelemetry, ProtectionStatus
from leropilot.services.hardware.telemetry import TelemetrySession


class FakeDriver:
    def __init__(self):
        self.torque_calls = []

    def write_torque_enable(self, motor_id, enabled):
        self.torque_calls.append((motor_id, enabled))


class FakeMotorService:
    def __init__(self):
        self._count = 0

    def read_telemetry_with_protection(self, driver, motor_id, brand, model, overrides=None):
        self._count += 1
        if self._count == 1:
            return MotorTelemetry(
                id=motor_id,
                position=0.0,
                velocity=0.0,
                current=0,
                load=0,
                temperature=100,
                voltage=12.0,
                moving=False,
                goal_position=0.0,
                error=0,
                protection_status=ProtectionStatus(status="critical", violations=[]),
            )
        return MotorTelemetry(
            id=motor_id,
            position=0.0,
            velocity=0.0,
            current=0,
            load=0,
            temperature=30,
            voltage=12.0,
            moving=False,
            goal_position=0.0,
            error=0,
            protection_status=ProtectionStatus(status="ok", violations=[]),
        )


@pytest.mark.asyncio
async def test_telemetry_session_auto_disable():
    driver = FakeDriver()
    motor_service = FakeMotorService()
    device = SimpleNamespace(labels={})

    session = TelemetrySession(
        device_id="SN",
        driver=driver,
        motor_service=motor_service,
        device=device,
        brand="dynamixel",
        target_ids=[1],
        poll_interval_ms=10,
    )

    await session.start()
    q = session.subscribe()

    # Wait for the EMERGENCY_PROTECTION event to show up
    found = False
    for _ in range(100):
        await asyncio.sleep(0.02)
        while not q.empty():
            msg = q.get_nowait()
            if msg.get("type") == "event" and msg.get("event", {}).get("code") == "EMERGENCY_PROTECTION":
                found = True
                break
        if found:
            break

    await session.stop()

    assert found, "Expected EMERGENCY_PROTECTION event"
    assert (1, False) in driver.torque_calls
