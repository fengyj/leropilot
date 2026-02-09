"""Tests for DamiaoRegister caching behavior."""

import pytest


def test_pmax_vmax_tmax_cache_reads_once(monkeypatch):
    from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver

    drv = DamiaoCAN_Driver("pcan:PCAN_USBBUS1")
    reg = drv.register

    # First calls return values; subsequent calls should not be invoked (cache hit)
    calls = {"count": 0}

    def fake_read(motor_id, addr):
        # Return distinct values based on addr
        calls["count"] += 1
        if addr == 0x15:
            return 1.1
        if addr == 0x16:
            return 2.2
        if addr == 0x17:
            return 3.3
        return None

    monkeypatch.setattr(reg, "read_float32", fake_read)

    a = reg.get_pmax_vmax_tmax((1, 1))
    assert a == (1.1, 2.2, 3.3)

    # Replace read_float32 with one that would raise if called (shouldn't be called due to cache)
    def bad_read(*args, **kwargs):
        raise AssertionError("read_float32 should not be called on cache hit")

    monkeypatch.setattr(reg, "read_float32", bad_read)

    b = reg.get_pmax_vmax_tmax((1, 1))
    assert b == (1.1, 2.2, 3.3)


def test_set_updates_cache(monkeypatch):
    from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver

    drv = DamiaoCAN_Driver("pcan:PCAN_USBBUS1")
    reg = drv.register

    # Patch write methods to succeed
    monkeypatch.setattr(reg, "write_float32", lambda motor_id, addr, v: True)

    ok = reg.set_pmax_vmax_tmax((2, 2), 4.4, 5.5, 6.6)
    assert ok == (True, True, True)

    # After set, get should return cached values even if reads would fail
    monkeypatch.setattr(reg, "read_float32", lambda *_: (_ for _ in ()).throw(AssertionError("Should not be read")))
    assert reg.get_pmax_vmax_tmax((2, 2)) == (4.4, 5.5, 6.6)
