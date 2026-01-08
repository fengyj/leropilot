from leropilot.services.hardware.robots import RobotSpecService


def test_lekiwi_wheel_motors_not_need_calibration():
    spec = RobotSpecService()
    r = spec.get_robot_definition("lekiwi-base-3wheel")
    assert r is not None
    mb = r.motor_buses.get("motorbus")
    assert mb is not None

    # First three motors (ids 17,18,19) are wheels and should have need_calibration False
    motors = list(mb.motors.values())
    assert len(motors) >= 3
    wheel_ids = [17, 18, 19]
    for wid in wheel_ids:
        # find motor entry by id
        found = None
        for m in motors:
            if getattr(m, "key", None) == wid or getattr(m, "raw_id", None) == wid:
                found = m
                break
        assert found is not None, f"Wheel motor {wid} not found in definition"
        assert found.need_calibration is False, f"Wheel motor {wid} should have need_calibration False"