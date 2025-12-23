# ruff: noqa
from types import SimpleNamespace

import pytest

from leropilot.services.hardware.telemetry import TelemetrySession


class DummyMotorService:
    def read_telemetry_with_protection(self, driver, motor_id, brand, robot_type_id, overrides):
        # Return a simple telemetry object-like with model_dump
        class T:
            def __init__(self, mid):
                self._d = {"id": mid}

            def model_dump(self):
                return self._d

        return T(motor_id)


@pytest.mark.asyncio
async def test_enable_disable_polling_and_interval():
    device = SimpleNamespace(labels={}, connection_settings={})
    motor_service = DummyMotorService()
    # Start session but polling should be disabled by default
    session = TelemetrySession(device_id="SNP", driver=None, motor_service=motor_service, device=device, brand="dynamixel", target_ids=[1], poll_interval_ms=50)

    assert not getattr(session, "_polling_enabled", False)

    await session.set_poll_interval_ms(30)
    await session.enable_polling()
    assert session.poll_interval_ms == 30
    assert session._polling_enabled

    await session.disable_polling()
    assert not session._polling_enabled

    # Cleanup
    await session.stop()
