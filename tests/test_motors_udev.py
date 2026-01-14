import pytest

from leropilot.models.hardware import MotorBrand, MotorModelInfo
from leropilot.services.hardware.motors import MotorService


def test_probe_serial_permission_triggers_udev_install(monkeypatch: "pytest.MonkeyPatch") -> None:
    # Simulate a driver that fails to connect first time (permission), then succeeds
    class FakeDriver:
        def __init__(self, interface: str, rate: int) -> None:
            self.interface = interface
            self.rate = rate
            self._connect_calls = 0

        def connect(self) -> bool:
            self._connect_calls += 1
            return self._connect_calls > 1

        def scan_motors(self, scan_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
            return {
                1: MotorModelInfo(
                    model="XL",
                    model_ids=[1190],
                    limits={},
                    variant=None,
                    brand=MotorBrand.DYNAMIXEL,
                )
            }

        def disconnect(self) -> None:
            pass

    called: dict = {}

    def fake_ensure(*args: object, **kwargs: object) -> dict:
        called["udev"] = True
        return {"installed": True, "skipped": False, "rule": "", "path": "/tmp/99-leropilot.rules"}

    # Patch DynamixelDriver used in MotorService._try_driver
    monkeypatch.setattr("leropilot.services.hardware.motors.DynamixelDriver", FakeDriver)
    monkeypatch.setattr("leropilot.utils.unix.UdevManager.ensure_rule_present", lambda self, **kw: fake_ensure(**kw))
    # Ensure platform appears as Linux so udev auto-fix path is exercised
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Linux")

    svc = MotorService()
    # Probe the serial port; should trigger ensure_rule_present and succeed
    res = svc.probe_connection(interface="/dev/ttyUSB0", interface_type="serial", probe_baud_list=[115200])
    assert res is not None
    assert called.get("udev") is True
