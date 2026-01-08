# ruff: noqa
import io
import zipfile

from fastapi.testclient import TestClient

from leropilot.main import app

client = TestClient(app)


from leropilot.services.hardware.robots import get_robot_manager


def create_device(device_id: str):
    manager = get_robot_manager()
    manager._robots.pop(device_id, None)
    from leropilot.models.hardware import Robot

    r = Robot(id=device_id, name=device_id)
    manager._robots[device_id] = r
    return r.model_dump()


def _make_zip_with_root_urdf(urdf_name: str, urdf_content: bytes) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        zf.writestr(urdf_name, urdf_content)
        zf.writestr("meshes/dummy.stl", b"solid dummy")
    return bio.getvalue()


def test_upload_zip_with_root_urdf():
    device_id = "ZIP_URDF_DEV"
    create_device(device_id)

    urdf_content = b"<robot name=\"z\">\n</robot>"
    z = _make_zip_with_root_urdf("custom.urdf", urdf_content)

    files = {"file": ("archive.zip", z, "application/zip")}
    r = client.post(f"/api/hardware/robots/{device_id}/urdf", files=files)
    assert r.status_code == 200, r.text

    # GET should return the uploaded (renamed) robot.urdf
    r = client.get(f"/api/hardware/robots/{device_id}/urdf")
    assert r.status_code == 200
    assert b"<robot" in r.content


def test_upload_zip_with_multiple_root_urdfs_fails():
    device_id = "ZIP_URDF_FAIL"
    create_device(device_id)

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        zf.writestr("a.urdf", b"<robot></robot>")
        zf.writestr("b.urdf", b"<robot></robot>")
    z = bio.getvalue()

    files = {"file": ("archive.zip", z, "application/zip")}
    r = client.post(f"/api/hardware/robots/{device_id}/urdf", files=files)
    assert r.status_code == 400
