import os
import shutil
from pathlib import Path

import pytest

from leropilot.utils.subprocess_executor import SubprocessExecutor
from leropilot.utils.unix import PrivilegeHelper, UdevManager


def test_generate_and_install_rule_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    um = UdevManager(rules_dir=rules_dir)

    rule = um.generate_rule(subsystem="video4linux", kernel="video0", group="video", mode="0660")
    fname = "99-leropilot.rules"
    path = rules_dir / fname

    assert not um.rule_exists(rule, filename=fname)

    # If owner can write, install should write directly
    um.install_rule_atomic(rule, filename=fname, use_pkexec=False)
    assert path.exists()
    assert rule in path.read_text(encoding="utf-8")
    assert um.rule_exists(rule, filename=fname)


def test_install_rule_atomic_privileged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    um = UdevManager(rules_dir=rules_dir)

    rule = um.generate_rule(subsystem="tty", group="dialout", mode="0666")
    fname = "99-leropilot.rules"

    # Simulate that direct write is not allowed by forcing os.access to return False
    monkeypatch.setattr(os, "access", lambda p, m: False)

    called = {}

    def fake_run(cmd: str | list[str], *args: object, **kwargs: object) -> object:
        called["cmd"] = cmd
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(SubprocessExecutor, "run_sync", staticmethod(fake_run))
    # Make pkexec available for the test environment
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pkexec" if name == "pkexec" else None)

    # Should use privileged move path (which calls run_with_privilege via PrivilegeHelper)
    um.install_rule_atomic(rule, filename=fname, use_pkexec=True)
    # Ensure SubprocessExecutor.run_sync was called (via PrivilegeHelper)
    assert called.get("cmd") is not None


def test_privilege_helper_message_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate pkexec and zenity present
    def which_mock(name: str) -> str | None:
        if name == "zenity":
            return "/usr/bin/zenity"
        if name == "pkexec":
            return "/usr/bin/pkexec"
        return None

    monkeypatch.setattr(shutil, "which", which_mock)

    recorded = {}

    def fake_run_sync(*args: object, **kwargs: object) -> object:
        recorded["args"] = args
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(SubprocessExecutor, "run_sync", staticmethod(fake_run_sync))

    PrivilegeHelper.run_with_privilege("echo hello", message="Please allow this for device access")

    assert recorded.get("args") is not None
    # Ensure the zenity command appears in the wrapped shell invocation
    joined = " ".join(map(str, recorded["args"]))
    assert "zenity" in joined or "kdialog" in joined
