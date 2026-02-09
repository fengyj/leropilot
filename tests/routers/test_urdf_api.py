# ruff: noqa
import importlib.resources

from fastapi.testclient import TestClient

from leropilot.main import app

client = TestClient(app)


from leropilot.services.hardware.robots import get_robot_manager


def create_device(device_id: str, model: str | None = None):
    # Add device directly into manager to avoid reliance on add_robot verification
    # If `model` provided, try to resolve to a built-in RobotDefinition and set
    # `definition` directly (tests should not exercise the PATCH API to set definition).
    manager = get_robot_manager()
    manager._robots.pop(device_id, None)
    from leropilot.models.hardware import Robot

    r = Robot(id=device_id, name=device_id, is_calibrated=False)
    if model:
        # Prefer explicit RobotDefinition when available
        try:
            from leropilot.services.hardware.robots.spec_service import RobotSpecService

            spec = RobotSpecService()
            defn = spec.get_robot_definition(model)
            if defn:
                r.definition = defn
            else:
                # Fallback to label when definition not found
                r.labels["leropilot.ai/robot_type_id"] = model
        except Exception:
            r.labels["leropilot.ai/robot_type_id"] = model
    manager._robots[device_id] = r
    return r.model_dump()


def test_builtin_urdf_fallback():
    device_id = "URDF_BUILTIN_DEV"
    create_device(device_id)

    # Patch device to set custom model to existing built-in robot (use label)
    # Create device with explicit built-in model set via helper
    create_device(device_id, model="koch-follower")

    # GET URDF should return built-in file
    r = client.get(f"/api/hardware/robots/{device_id}/urdf")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/xml")
    assert b"<robot" in r.content


def test_upload_get_delete_urdf_valid():
    device_id = "URDF_UPLOAD_DEV"
    create_device(device_id)

    # Load existing built-in urdf to use as upload content
    resource_files = importlib.resources.files("leropilot.resources")
    urdf_file = resource_files.joinpath("robots").joinpath("koch-follower").joinpath("robot.urdf")
    content = urdf_file.read_bytes()

    files = {"file": ("robot.urdf", content, "application/xml")}
    r = client.post(f"/api/hardware/robots/{device_id}/urdf", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("validation")
    assert body["validation"].get("valid") is True

    # GET should return the uploaded file
    r = client.get(f"/api/hardware/robots/{device_id}/urdf")
    assert r.status_code == 200
    assert b"<robot" in r.content

    # DELETE
    r = client.delete(f"/api/hardware/robots/{device_id}/urdf")
    assert r.status_code == 204

    # Now GET should 404
    r = client.get(f"/api/hardware/robots/{device_id}/urdf")
    assert r.status_code == 404


def test_upload_invalid_urdf():
    device_id = "URDF_INVALID_DEV"
    create_device(device_id)

    files = {"file": ("bad.urdf", b"not a urdf content", "application/xml")}
    r = client.post(f"/api/hardware/robots/{device_id}/urdf", files=files)
    assert r.status_code == 400
    body = r.json()
    assert "URDF" in str(body.get("detail"))
