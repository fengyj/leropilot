import math

import pytest

from leropilot.services.hardware.motor_drivers.feetech.drivers import FeetechDriver
from leropilot.models.hardware import MotorModelInfo, MotorBrand


class DummySerial:
    def __init__(self):
        self.is_open = True

    def read(self, n):
        return b""

    def reset_input_buffer(self):
        pass

    def write(self, data):
        pass

    def close(self):
        self.is_open = False


def make_resp_for_two_bytes(low: int, high: int, hdr_id: int = 1):
    # Build a minimal valid packet with header, id, length, error, data(low,high), checksum
    # Header 0xFF 0xFF, id, length, error(0), data low, data high, checksum
    packet = bytearray([0xFF, 0xFF, hdr_id, 0x04, 0x00, low & 0xFF, high & 0xFF, 0x00])
    # Calculate checksum = ~(sum(packet[2:-1])) & 0xFF
    cs = (~(sum(packet[2:-1]))) & 0xFF
    packet[-1] = cs
    return bytes(packet)


def test_identify_model_sts3215():
    drv = FeetechDriver("/dev/null", 115200)
    drv.serial_port = DummySerial()
    drv.connected = True

    # model_number 0x0C8F (3215) -> STS3215
    def fake_read(motor_id, addr, length):
        if addr == 3:  # ADDR_MODEL_NUMBER
            return 0x0C8F  # Return integer value directly
        if addr == 0:  # ADDR_FIRMWARE_MAJOR
            return 0x0201  # Return integer value directly (high=0x02, low=0x01)
        return None

    drv._feetech_read = fake_read

    info = drv.identify_model(1)
    assert isinstance(info, MotorModelInfo)
    assert info.model == "STS3215"


def test_identify_model_sts3215_variant_from_firmware():
    drv = FeetechDriver("/dev/null", 115200)
    drv.serial_port = DummySerial()
    drv.connected = True

    # model_number 3215, firmware major indicates SO-101 variant family (0xC0), minor 1 -> C001
    def fake_read(motor_id, addr, length):
        if addr == 3:  # ADDR_MODEL_NUMBER
            return 0x0C8F  # Return integer value directly
        if addr == 0:  # ADDR_FIRMWARE_MAJOR
            return 0xC001  # Return integer value directly (high=0xC0, low=0x01)
        return None

    drv._feetech_read = fake_read

    info = drv.identify_model(1)
    assert isinstance(info, MotorModelInfo)
    assert info.model == "STS3215"
    # variant should be full model name as per preference
    assert info.variant == "STS3215-C001"


def test_scan_motors_uses_identify_model_and_skips_unknown():
    drv = FeetechDriver("/dev/null", 115200)
    drv.serial_port = DummySerial()
    drv.connected = True

    # For motor 1, model number 3215 and firmware C001
    def fake_read(motor_id, addr, length):
        if addr == 3:  # ADDR_MODEL_NUMBER
            return 0x0C8F  # Return integer value directly
        if addr == 0:  # ADDR_FIRMWARE_MAJOR
            return 0xC001  # Return integer value directly (high=0xC0, low=0x01)
        return None

    drv._feetech_read = fake_read
    # make ping succeed for id 1
    drv._ping_motor_direct = lambda mid: True

    discovered = drv.scan_motors(scan_range=[1])
    assert len(discovered) == 1
    info = discovered[0]
    assert info.model == "STS3215"
    assert info.variant == "STS3215-C001"


def test_scan_motors_skips_unknown_model_number():
    drv = FeetechDriver("/dev/null", 115200)
    drv.serial_port = DummySerial()
    drv.connected = True

    # model_number not present in FEETECH tables -> identify_model returns None
    def fake_read(motor_id, addr, length):
        if addr == 3:  # ADDR_MODEL_NUMBER
            return make_resp_for_two_bytes(0xFF, 0xFF, hdr_id=motor_id)  # 0xFFFF
        return None

    drv._feetech_read = fake_read
    drv._ping_motor_direct = lambda mid: True

    discovered = drv.scan_motors(scan_range=[1])
    assert len(discovered) == 0

def test_read_telemetry_si_conversion():
    drv = FeetechDriver("/dev/null", 115200)
    drv.serial_port = DummySerial()
    drv.connected = True

    # Provide identify_model that returns known position_scale
    drv.identify_model = lambda mid: MotorModelInfo(
        model="STS3215",
        model_ids=[3215],
        limits={},
        position_scale=(2 * math.pi) / 4096,
        brand=MotorBrand.FEETECH
    )

    # Prepare read responses for addresses used in read_telemetry
    # present position = 1000 -> low=1000 & 0xFF, high=1000>>8
    pos_low = 1000 & 0xFF
    pos_high = (1000 >> 8) & 0xFF
    speed_low = 20 & 0xFF
    speed_high = (20 >> 8) & 0xFF
    load_low = 5 & 0xFF
    load_high = 0
    temp = 30
    volt = 75  # raw -> 7.5V
    cur_low = 10 & 0xFF
    cur_high = 0
    goal_low = 2000 & 0xFF
    goal_high = (2000 >> 8) & 0xFF

    def fake_read(motor_id, addr, length):
        if addr == 56:  # ADDR_PRESENT_POSITION
            return (pos_high << 8) | pos_low  # Return integer value
        if addr == 58:  # ADDR_PRESENT_SPEED
            return (speed_high << 8) | speed_low  # Return integer value
        if addr == 60:  # ADDR_PRESENT_LOAD
            return (load_high << 8) | load_low  # Return integer value
        if addr == 63:  # ADDR_PRESENT_TEMPERATURE
            return temp  # Return integer value
        if addr == 62:  # ADDR_PRESENT_VOLTAGE
            return volt  # Return integer value
        if addr == 69:  # ADDR_PRESENT_CURRENT
            return (cur_high << 8) | cur_low  # Return integer value
        if addr == 42:  # ADDR_GOAL_POSITION
            return (goal_high << 8) | goal_low  # Return integer value
        return None

    drv._feetech_read = fake_read

    telemetry = drv.read_telemetry(1)
    assert telemetry is not None
    # Check position converted to radians
    expected_pos = 1000 * ((2 * math.pi) / 4096)
    assert abs(telemetry.position - expected_pos) < 1e-6
    # Check velocity converted
    expected_vel = 20 * ((2 * math.pi) / 4096)
    assert abs(telemetry.velocity - expected_vel) < 1e-6
    assert telemetry.voltage == 7.5
    assert telemetry.temperature == temp
