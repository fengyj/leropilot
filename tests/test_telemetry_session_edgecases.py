# ruff: noqa
import asyncio
from types import SimpleNamespace

import pytest

from leropilot.models.hardware import MotorTelemetry, ProtectionStatus
from leropilot.services.hardware.telemetry import TelemetrySession


class FakeDriverDisconnect:
    def __init__(self):
        self.torque_calls = []
        self.disconnected = False

    def write_torque_enable(self, motor_id, enabled):
        # Simulate driver that raises when asked to disable torque
        raise RuntimeError("driver disconnected")

    def disconnect(self):
        self.disconnected = True


class FakeDriverNormal:
    def __init__(self):
        self.torque_calls = []

    def write_torque_enable(self, motor_id, enabled):
        self.torque_calls.append((motor_id, enabled))

    def disconnect(self):
        pass


class FakeMotorServiceRepeated:
    def __init__(self):
        self._count = 0

    def read_telemetry_with_protection(self, driver, motor_id, brand, model, overrides=None):
        # Always return critical to test repeated critical handling
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


class FakeMotorServiceNormal:
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
async def test_repeated_critical_only_one_disable():
    driver = FakeDriverNormal()
    motor_service = FakeMotorServiceRepeated()
    device = SimpleNamespace(labels={})

    session = TelemetrySession(device_id="SNR", driver=driver, motor_service=motor_service, device=device, brand="dynamixel", target_ids=[1], poll_interval_ms=10)

    await session.start()
    q = session.subscribe()

    # Wait a short time
    await asyncio.sleep(0.2)

    await session.stop()

    # Should only have one disable call despite repeated critical
    disables = [c for c in driver.torque_calls if c == (1, False)]
    assert len(disables) == 1


@pytest.mark.asyncio
async def test_driver_disconnect_does_not_crash_session():
    driver = FakeDriverDisconnect()
    motor_service = FakeMotorServiceNormal()
    device = SimpleNamespace(labels={})

    session = TelemetrySession(device_id="SND", driver=driver, motor_service=motor_service, device=device, brand="dynamixel", target_ids=[1], poll_interval_ms=10)

    await session.start()
    q = session.subscribe()

    # Wait for an event to occur
    await asyncio.sleep(0.2)

    # Stop should not raise even if driver errors occur
    await session.stop()

    # Ensure queue received an event (EMERGENCY_PROTECTION) even though driver threw
    found = False
    while not q.empty():
        m = q.get_nowait()
        if m.get("type") == "event":
            found = True
            break
    assert found


@pytest.mark.asyncio
async def test_start_stop_restart():
    driver = FakeDriverNormal()
    motor_service = FakeMotorServiceNormal()
    device = SimpleNamespace(labels={})

    session = TelemetrySession(device_id="SNRR", driver=driver, motor_service=motor_service, device=device, brand="dynamixel", target_ids=[1], poll_interval_ms=10)

    # Start once
    await session.start()
    await asyncio.sleep(0.05)
    await session.stop()

    # Start again
    await session.start()
    await asyncio.sleep(0.05)
    await session.stop()

    # Ensure we did call torque disable on first critical
    assert (1, False) in driver.torque_calls
