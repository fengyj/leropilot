import platform

from fastapi.testclient import TestClient

from leropilot.main import app

client = TestClient(app)


def create_device(device_id: str, model: str | None = None) -> dict:
    payload = {"id": device_id, "category": "robot", "name": device_id}
    if model:
        payload["labels"] = {"leropilot.ai/robot_type_id": model}
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
    r = client.patch(f"/api/hardware/devices/{device_id}", json={"labels": {"leropilot.ai/robot_type_id": "koch_follower"}})
    assert r.status_code == 200

    # Request a known urdf resource under that model (canonical hardware route)
    r = client.get(f"/api/hardware/resources/{device_id}/robot.urdf")
    assert r.status_code == 200
    assert b"<robot" in r.content


def test_udev_endpoint_not_exposed() -> None:
    r = client.post("/api/hardware/udev/install", json={"install": False})
    # The public udev install API is intentionally not exposed; service utilities
    # handle udev installation automatically when required.
    assert r.status_code == 404


# The explicit udev install API was removed in favor of a service util.
# The behavior is tested in `tests/test_udev_service.py` and camera integration tests.
