# ruff: noqa: ANN201
from fastapi.testclient import TestClient

from leropilot.main import app

client = TestClient(app)


def test_add_device_rejects_empty_device_id():
    payload = {
        "id": "",
        "category": "robot",
        "name": "NoSerial",
    }

    resp = client.post("/api/hardware/devices", json=payload)
    assert resp.status_code == 409
    assert "device_id" in resp.json().get("detail", "").lower()


def test_add_device_rejects_camera_category():
    payload = {
        "id": "CAM123",
        "category": "camera",
        "name": "MyCamera",
    }

    resp = client.post("/api/hardware/devices", json=payload)
    assert resp.status_code == 409
    assert "camera" in resp.json().get("detail", "").lower()
