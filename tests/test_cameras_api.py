# ruff: noqa: ANN201
import pytest
from fastapi.testclient import TestClient

from leropilot.main import app

client = TestClient(app)


def test_list_cameras():
    r = client.get("/api/hardware/cameras")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_camera_snapshot_invalid() -> None:
    # invalid camera id
    r = client.get("/api/hardware/cameras/invalid/snapshot")
    assert r.status_code == 400


def test_camera_snapshot_permission_attempts_udev_install(monkeypatch: "pytest.MonkeyPatch") -> None:
    # Simulate VideoCapture behavior: first instance not opened, second instance opened and returns frame
    import numpy as np
    state: dict = {"created": 0}

    class FakeCap:
        def __init__(self, index: int) -> None:
            state["created"] += 1
            self._created = state["created"]

        def isOpened(self) -> bool:
            return self._created > 1

        def read(self) -> tuple[bool, object]:
            if self._created == 1:
                return False, None
            return True, np.zeros((10, 10, 3), dtype=np.uint8)

        def set(self, *args: object, **kwargs: object) -> bool:
            return True

        def release(self) -> None:
            return None

    monkeypatch.setattr("cv2.VideoCapture", FakeCap)

    # Patch ensure_rule_present to record being called
    called: dict = {}

    def fake_ensure(*args: object, **kwargs: object) -> dict:
        called["udev"] = True
        return {"installed": True, "skipped": False, "rule": "", "path": "/tmp/99-leropilot.rules"}

    monkeypatch.setattr("leropilot.utils.unix.UdevManager.ensure_rule_present", lambda self, **kw: fake_ensure(**kw))
    # Ensure platform looks like Linux so the udev auto-fix path is exercised on Windows CI
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Linux")

    r = client.get("/api/hardware/cameras/cam_0/snapshot")
    assert r.status_code == 200
    assert called.get("udev") is True
