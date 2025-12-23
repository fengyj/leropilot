import platform

import pytest
from fastapi.testclient import TestClient

from leropilot.main import app

client = TestClient(app)


def create_device(device_id: str, model: str | None = None) -> dict:
    payload = {"id": device_id, "category": "robot", "name": device_id}
    if model:
        payload["config"] = {"custom": {"model": model}}
    r = client.post("/api/hardware/devices", json=payload)
    if r.status_code == 409:
        # Device existed from previous runs; remove and retry to ensure test idempotency
        client.delete(f"/api/hardware/devices/{device_id}?delete_data=true")
        r = client.post("/api/hardware/devices", json=payload)
    assert r.status_code == 200
    return r.json()


def test_get_builtin_resource() -> None:
    device_id = "RES_DEV"
    create_device(device_id)
    # patch device to reference built-in model
    r = client.patch(f"/api/hardware/devices/{device_id}", json={"config": {"custom": {"model": "koch_follower"}}})
    assert r.status_code == 200

    # Request a known urdf resource under that model (canonical hardware route)
    r = client.get(f"/api/hardware/resources/{device_id}/koch.urdf")
    assert r.status_code == 200
    assert b"<robot" in r.content


def test_udev_endpoint_on_non_linux() -> None:
    r = client.post("/api/hardware/udev/install", json={"install": False})
    if platform.system() != "Linux":
        assert r.status_code == 400
    else:
        # On linux, should return rule dict
        assert r.status_code == 200
        assert "rule" in r.json()


def test_udev_video_rule_generation_and_install(monkeypatch: "pytest.MonkeyPatch") -> None:
    # Simulate Linux environment
    monkeypatch.setattr(platform, "system", lambda: "Linux")

    # 1) Generation (no install)
    r = client.post(
        "/api/hardware/udev/install",
        json={"install": False, "subsystem": "video4linux", "vendor": "1234", "product": "abcd"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "rule" in body
    rule = body["rule"]
    assert "SUBSYSTEM==\"video4linux\"" in rule
    assert "GROUP=\"video\"" in rule
    assert "ATTRS{idVendor}==\"1234\"" in rule
    assert "ATTRS{idProduct}==\"abcd\"" in rule

    # 2) Install path (monkeypatch SubprocessExecutor.run_sync to capture cmd)
    called: dict = {}

    def fake_run_sync(*args: object, **kwargs: object) -> int:
        called["cmd"] = args
        return 0

    monkeypatch.setattr("leropilot.routers.hardwares_api.SubprocessExecutor.run_sync", fake_run_sync)

    r2 = client.post(
        "/api/hardware/udev/install",
        json={"install": True, "subsystem": "video4linux", "vendor": "1234", "product": "abcd"},
    )
    assert r2.status_code == 200
    assert r2.json().get("installed") is True
    assert "/etc/udev/rules.d/99-leropilot.rules" in r2.json().get("path")
    assert "cmd" in called and called["cmd"]
    # Ensure pkexec is part of the command tuple
    assert any("pkexec" in str(x) for x in called["cmd"])
