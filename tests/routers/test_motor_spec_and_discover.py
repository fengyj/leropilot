from fastapi.testclient import TestClient

from leropilot.main import app

client = TestClient(app)


def test_motor_discover_bad_interface() -> None:
    r = client.post("/api/hardware/motor-discover", json={"interface": "NONEXISTENT", "baud_rates": [115200]})
    # Endpoint removed — expect 404
    assert r.status_code == 404
