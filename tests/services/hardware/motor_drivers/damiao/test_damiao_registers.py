"""Tests for Damiao register/table definitions."""

from leropilot.services.hardware.motor_drivers.damiao.tables import DamiaoRegisters, DamiaoConstants, damiao_supports_register


def test_damiao_registers_present() -> None:
    # Basic sanity checks for commonly used registers (values taken from DM-J4310 manual)
    # Ensure KT_VALUE is correctly defined at address 0x01 (per DM-J4310 tables)
    assert isinstance(DamiaoRegisters.KT_VALUE, tuple)
    assert DamiaoRegisters.KT_VALUE[0] == 0x01

    # Control and speed
    assert DamiaoRegisters.MAX_SPD[0] == 0x06
    assert DamiaoRegisters.CTRL_MODE[0] == 0x0A

    # Mapping limits (position/velocity/torque)
    assert DamiaoRegisters.PMAX[0] == 0x15
    assert DamiaoRegisters.VMAX[0] == 0x16
    assert DamiaoRegisters.TMAX[0] == 0x17

    # Ensure UV_VALUE and KT_VALUE are correctly marked as writable floats
    _, is_rw, is_float = DamiaoRegisters.get_register_info(DamiaoRegisters.UV_VALUE[0])
    assert is_rw is True and is_float is True
    _, is_rw, is_float = DamiaoRegisters.get_register_info(DamiaoRegisters.KT_VALUE[0])
    assert is_rw is True and is_float is True

    # PID gains (speed & position loops)
    assert DamiaoRegisters.KP_ASR[0] == 0x19
    assert DamiaoRegisters.KI_ASR[0] == 0x1A
    assert DamiaoRegisters.KP_APR[0] == 0x1B
    assert DamiaoRegisters.KI_APR[0] == 0x1C


def test_damiao_register_support_lookup() -> None:
    # Known model should report support for a known register address
    assert damiao_supports_register("DM4310", DamiaoRegisters.CTRL_MODE[0]) is True
    assert damiao_supports_register("DM4310", DamiaoRegisters.KP_ASR[0]) is True

    # Unknown model should return False
    assert damiao_supports_register("UNKNOWN_MODEL", DamiaoRegisters.CTRL_MODE[0]) is False


def test_read_only_flags_and_reject_write() -> None:
    # Ensure read-only flags are accessible via get_register_info and write attempts are rejected
    _, is_rw, _ = DamiaoRegisters.get_register_info(DamiaoRegisters.HW_VER[0])
    assert is_rw is False

    class _DummyDriver:
        pass

    reg = __import__("leropilot.services.hardware.motor_drivers.damiao.registers", fromlist=["DamiaoRegister"]).DamiaoRegister(_DummyDriver())

    # Writing to a read-only register should raise OperationalError
    import pytest
    from leropilot.exceptions import OperationalError

    with pytest.raises(OperationalError):
        reg.write_uint32((1, 1), DamiaoRegisters.HW_VER[0], 0x1234)


def test_uv_and_kt_marked_writable_floats() -> None:
    # Ensure UV_VALUE and KT_VALUE are correctly marked as writable floats
    _, is_rw, is_float = DamiaoRegisters.get_register_info(DamiaoRegisters.UV_VALUE[0])
    assert is_rw is True and is_float is True

    _, is_rw, is_float = DamiaoRegisters.get_register_info(DamiaoRegisters.KT_VALUE[0])
    assert is_rw is True and is_float is True


def test_read_number_and_bulk_read_numbers(monkeypatch) -> None:
    # Create a dummy driver where read_parameter returns known values
    class DummyDriver:
        def __init__(self):
            self.read_calls = []
        def read_parameter(self, motor_id, param_addr, max_age=None):
            self.read_calls.append((motor_id, param_addr))
            # Return float 3.5 for float params, uint32 7 for int params
            _, _, is_float = DamiaoRegisters.get_register_info(param_addr)
            if is_float:
                import struct
                return struct.pack('<f', 3.5)
            return (7).to_bytes(4, byteorder='little', signed=False)
        def bulk_read_parameters(self, requests, base_timeout=0.1, max_age=None):
            # simulate bulk read success
            return {(mid, addr): self.read_parameter(mid, addr) for (mid, addr) in requests}

    dummy = DummyDriver()
    reg = __import__("leropilot.services.hardware.motor_drivers.damiao.registers", fromlist=["DamiaoRegister"]).DamiaoRegister(dummy)

    # Single read
    v = reg.read_number((1,1), DamiaoRegisters.PMAX[0])
    assert abs(v - 3.5) < 1e-6

    # Bulk read
    reqs = [((1,1), DamiaoRegisters.PMAX[0]), ((2,2), DamiaoRegisters.CTRL_MODE[0])]
    vals = reg.bulk_read_numbers(reqs)
    assert isinstance(vals, dict)
    assert abs(vals[(1,1), DamiaoRegisters.PMAX[0]] - 3.5) < 1e-6
    assert vals[(2,2), DamiaoRegisters.CTRL_MODE[0]] == 7


def test_bulk_write_numbers_prepares_correct_bytes(monkeypatch) -> None:
    # Ensure bulk_write_numbers creates correctly encoded bytes and delegates to driver.bulk_write_parameters
    recorded = []
    class DummyDriver:
        def bulk_write_parameters(self, items, base_timeout=0.1):
            # capture items for assertion
            recorded.extend(items)

    dummy = DummyDriver()
    reg = __import__("leropilot.services.hardware.motor_drivers.damiao.registers", fromlist=["DamiaoRegister"]).DamiaoRegister(dummy)

    writes = [((1,1), DamiaoRegisters.PMAX[0], 1.5), ((2,2), DamiaoRegisters.CTRL_MODE[0], 3)]
    reg.bulk_write_numbers(writes)

    # Two items recorded
    assert len(recorded) == 2
    # First should be float 1.5
    import struct
    assert struct.unpack('<f', recorded[0][2])[0] == 1.5
    # Second should be uint32 3
    assert int.from_bytes(recorded[1][2], byteorder='little', signed=False) == 3)


def test_get_control_mode_reads_value(monkeypatch) -> None:
    # CTRL_MODE register present and at expected address
    assert DamiaoRegisters.CTRL_MODE[0] == 0x0A

    # Create a dummy driver and DamiaoRegister instance and monkeypatch read_uint32
    class _DummyDriver:
        pass

    reg = __import__("leropilot.services.hardware.motor_drivers.damiao.registers", fromlist=["DamiaoRegister"]).DamiaoRegister(_DummyDriver())

    # Simulate underlying read_uint32 returning a small value
    monkeypatch.setattr(reg, "read_uint32", lambda motor_id, addr: 3)

    assert reg.get_control_mode((1, 1)) == 3


def test_read_number_and_bulk(monkeypatch) -> None:
    import struct

    class _DummyDriver:
        pass

    drv = _DummyDriver()
    # Simulate individual read returning float 3.14
    def fake_read_parameter(motor_id, addr, max_age=None):
        return struct.pack("<f", 3.14)

    drv.read_parameter = fake_read_parameter
    drv.bulk_read_parameters = lambda requests, max_age=None: None

    reg = __import__("leropilot.services.hardware.motor_drivers.damiao.registers", fromlist=["DamiaoRegister"]).DamiaoRegister(drv)

    v = reg.read_number((1, 1), DamiaoRegisters.PMAX[0])
    assert abs(v - 3.14) < 1e-6

    # Test bulk_read_numbers
    requests = [((1, 1), DamiaoRegisters.PMAX[0]), ((2, 2), DamiaoRegisters.VMAX[0])]
    results = reg.bulk_read_numbers(requests, max_age=0.1)
    assert ( (1,1), DamiaoRegisters.PMAX[0]) in results
    assert ( (2,2), DamiaoRegisters.VMAX[0]) in results
    assert abs(results[((1,1), DamiaoRegisters.PMAX[0])] - 3.14) < 1e-6
