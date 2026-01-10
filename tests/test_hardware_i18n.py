from fastapi.testclient import TestClient

from leropilot.main import app

client = TestClient(app)


def test_get_nonexistent_robot_returns_localized_message_zh():
    resp = client.get("/api/hardware/robots/nonexistent?lang=zh")
    assert resp.status_code == 404
    assert resp.json().get("detail") == "未找到机器人"


def test_get_nonexistent_definition_image_returns_localized_message_zh():
    resp = client.get("/api/hardware/robots/definitions/def_not_exist/image?lang=zh")
    assert resp.status_code == 404
    assert resp.json().get("detail") == "未找到定义"


def test_upload_urdf_to_nonexistent_robot_returns_localized_message_zh():
    # No file content required; endpoint will check robot existence first
    resp = client.post("/api/hardware/robots/nonexistent/urdf?lang=zh", files={"file": ("robot.urdf", b"<robot></robot>", "text/xml")})
    assert resp.status_code == 404
    assert resp.json().get("detail") == "未找到机器人"
