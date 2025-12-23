# ruff: noqa
import importlib.resources

from fastapi.testclient import TestClient

from leropilot.main import app

client = TestClient(app)


def create_device(device_id: str, model: str | None = None):
    payload = {"id": device_id, "category": "robot", "name": device_id}
    if model:
        payload["config"] = {"custom": {"model": model}}
    r = client.post("/api/hardware/devices", json=payload)
    assert r.status_code == 200
    return r.json()


def test_builtin_urdf_fallback():
    device_id = "URDF_BUILTIN_DEV"
    create_device(device_id)

    # Patch device to set custom model to existing built-in robot
    r = client.patch(f"/api/hardware/devices/{device_id}", json={"config": {"custom": {"model": "koch_follower"}}})
    assert r.status_code == 200

    # GET URDF should return built-in file
    r = client.get(f"/api/hardware/devices/{device_id}/urdf")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/xml")
    assert b"<robot" in r.content


def test_upload_get_delete_urdf_valid():
    device_id = "URDF_UPLOAD_DEV"
    create_device(device_id)

    # Load existing built-in urdf to use as upload content
    resource_files = importlib.resources.files("leropilot.resources")
    urdf_file = resource_files.joinpath("robots").joinpath("koch_follower").joinpath("koch.urdf")
    content = urdf_file.read_bytes()

    files = {"file": ("koch.urdf", content, "application/xml")}
    r = client.post(f"/api/hardware/devices/{device_id}/urdf", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("validation")
    assert body["validation"].get("valid") is True

    # GET should return the uploaded file
    r = client.get(f"/api/hardware/devices/{device_id}/urdf")
    assert r.status_code == 200
    assert b"<robot" in r.content

    # DELETE
    r = client.delete(f"/api/hardware/devices/{device_id}/urdf")
    assert r.status_code == 204

    # Now GET should 404
    r = client.get(f"/api/hardware/devices/{device_id}/urdf")
    assert r.status_code == 404


def test_upload_invalid_urdf():
    device_id = "URDF_INVALID_DEV"
    create_device(device_id)

    files = {"file": ("bad.urdf", b"not a urdf content", "application/xml")}
    r = client.post(f"/api/hardware/devices/{device_id}/urdf", files=files)
    assert r.status_code == 400
    body = r.json()
    assert "URDF" in str(body.get("detail"))
