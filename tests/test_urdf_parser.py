# ruff: noqa
import importlib.resources

from leropilot.services.hardware.urdf import get_joint_chain, validate_file, validate_motor_count

resource_files = importlib.resources.files("leropilot.resources")
GOOD_URDF = resource_files.joinpath("robots").joinpath("koch_follower").joinpath("koch.urdf")


def test_validate_good_urdf():
    r = validate_file(str(GOOD_URDF))
    assert r["valid"] is True
    assert r["joints"] > 0
    assert r["links"] > 0


def test_get_joint_chain():
    # We don't know exact link names for every robot, but ensure function returns list or None
    chain = get_joint_chain(str(GOOD_URDF), "base_link", "end_link")
    # Either None or list (no exception)
    assert chain is None or isinstance(chain, list)


def test_validate_motor_count_mismatch():
    ok, msg = validate_motor_count(str(GOOD_URDF), motor_count=999)
    assert ok is False
    assert "mismatch" in msg or "Motor count" in msg
