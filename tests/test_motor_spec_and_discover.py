from fastapi.testclient import TestClient

from leropilot.main import app

client = TestClient(app)


def test_get_motor_specs_not_found() -> None:
    r = client.get("/api/hardware/motor-specs/unknown/xx")
    assert r.status_code == 404


def test_get_motor_specs_known() -> None:
    r = client.get("/api/hardware/motor-specs/dynamixel/XL330-M077")
    assert r.status_code == 200
    body = r.json()
    assert body.get("model_ids") is not None


def test_motor_discover_bad_interface() -> None:
    r = client.post("/api/hardware/motor-discover", json={"interface": "NONEXISTENT", "baud_rates": [115200]})
    # Probe may return 404 or 500 depending on platform; assert it's not 200
    assert r.status_code != 200
