from pathlib import Path

from leropilot.utils.unix import UdevManager


def ensure_rule_present(**kwargs: object) -> dict[str, object]:
    """Wrapper for backwards compatibility in tests."""
    manager = UdevManager()
    return manager.ensure_rule_present(**kwargs)


def generate_rule(**kwargs: object) -> str:
    """Wrapper for backwards compatibility in tests."""
    manager = UdevManager()
    return manager.generate_rule(**kwargs)


def test_generate_rule_video_default() -> None:
    r = generate_rule(subsystem="video4linux")
    assert 'SUBSYSTEM=="video4linux"' in r
    assert 'GROUP="video"' in r


def test_generate_rule_with_vendor_product() -> None:
    r = generate_rule(subsystem="video4linux", vendor="1234", product="abcd")
    assert 'ATTRS{idVendor}=="1234"' in r
    assert 'ATTRS{idProduct}=="abcd"' in r


def test_ensure_rule_present_idempotent(tmp_path: Path) -> None:
    # use a temporary file to emulate /etc/udev/rules.d/99-leropilot.rules
    rule_file = tmp_path / "99-leropilot.rules"

    res1 = ensure_rule_present(
        subsystem="video4linux",
        vendor="1234",
        product="abcd",
        install_with_pkexec=False,
        rule_file=rule_file,
    )
    assert res1["installed"] is True or res1["skipped"] is False
    # second call should be idempotent
    res2 = ensure_rule_present(
        subsystem="video4linux",
        vendor="1234",
        product="abcd",
        install_with_pkexec=False,
        rule_file=rule_file,
    )
    assert res2["skipped"] is True
