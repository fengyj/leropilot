from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from leropilot.main import app


def test_patch_robot_name_without_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Use TestClient app that uses real config; assume robots exist from fixture
    client = TestClient(app)
    res = client.get('/api/hardware/robots')
    assert res.status_code == 200
    robots = res.json()
    assert len(robots) > 0
    robot = robots[0]
    rid = robot['id']

    new_name = robot['name'] + '-patched'
    payload = {'name': new_name}
    r = client.patch(f'/api/hardware/robots/{rid}?verify=false', json=payload)
    assert r.status_code == 200
    updated = r.json()
    assert updated['name'] == new_name

