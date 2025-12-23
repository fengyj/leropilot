# ruff: noqa: ANN201
from fastapi.testclient import TestClient

from leropilot.main import app

client = TestClient(app)


def test_list_cameras():
    r = client.get("/api/hardware/cameras")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_camera_snapshot_invalid():
    # invalid camera id
    r = client.get("/api/hardware/cameras/invalid/snapshot")
    assert r.status_code == 400


# We cannot reliably open a real camera in CI; this test mainly ensures route behavior
