import math

import scservo_sdk as scs

from leropilot.exceptions import MotorIdentificationError
from leropilot.models.hardware import MotorBrand, MotorModelInfo
from leropilot.services.hardware.motor_drivers.feetech.drivers import FeetechDriver


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
    def fake_read_word(motor_id, addr, signed=False):
        if addr == 3:  # ADDR_MODEL_NUMBER
            return 0x0C8F  # Return integer value directly
        if addr == 0:  # ADDR_FIRMWARE_MAJOR
            return 0x0201  # Return integer value directly (high=0x02, low=0x01)
        return None

    drv._feetech_read_word = fake_read_word

    info = drv.identify_model(1)
    assert isinstance(info, MotorModelInfo)
    assert info.model == "STS3215"


def test_identify_model_sts3215_variant_from_firmware():
    drv = FeetechDriver("/dev/null", 115200)
    drv.serial_port = DummySerial()
    drv.connected = True

    # model_id 49153 corresponds to STS3215-C001 variant in tables
    # firmware major 0xC0, minor 0x01 indicates the same variant
    def fake_read_word(motor_id, addr, signed=False):
        if addr == 3:  # ADDR_MODEL_NUMBER
            return 49153  # C001 variant uses this model_id
        if addr == 0:  # ADDR_FIRMWARE_MAJOR
            return 0xC001  # firmware indicates C001 (high=0xC0, low=0x01)
        return None

    drv._feetech_read_word = fake_read_word

    info = drv.identify_model(1)
    assert isinstance(info, MotorModelInfo)
    assert info.model == "STS3215"
    # Should detect C001 variant from the model_id
    assert info.variant == "STS3215-C001"


def test_scan_motors_uses_identify_model_and_skips_unknown():
    drv = FeetechDriver("/dev/null", 115200)
    drv.serial_port = DummySerial()
    drv.connected = True

    # For motor 1, model number 3215 and firmware C001
    def fake_read_word(motor_id, addr, signed=False):
        if addr == 3:  # ADDR_MODEL_NUMBER
            return 0x0C8F  # Return integer value directly (STS3215)
        if addr == 0:  # ADDR_FIRMWARE_MAJOR
            return 0xC001  # Return integer value directly (high=0xC0, low=0x01)
        return None

    drv._feetech_read_word = fake_read_word

    # Also mock _feetech_read for the fallback block read in scan_motors
    def fake_read(motor_id, addr, length):
        if addr == 3 and length == 2:  # ADDR_MODEL_NUMBER
            return (0x0C8F).to_bytes(2, "little")
        if addr == 0 and length == 2:  # ADDR_FIRMWARE_MAJOR
            return (0xC001).to_bytes(2, "little")
        return bytes([0xFF] * length)

    drv._feetech_read = fake_read
    # Mock packet_handler.ping to succeed for id 1
    drv.packet_handler.ping = (
        lambda port_handler, motor_id: (scs.COMM_SUCCESS, 0) if motor_id == 1 else (scs.COMM_TX_FAIL, 1)
    )

    discovered = drv.scan_motors(scan_range=[1])
    assert len(discovered) == 1
    info = discovered[1]  # dictionary lookup
    assert info.model == "STS3215"


def test_scan_motors_skips_unknown_model_number():
    drv = FeetechDriver("/dev/null", 115200)
    drv.serial_port = DummySerial()
    drv.connected = True

    # model_number not present in FEETECH tables -> identify_model returns None
    def fake_read_word(motor_id, addr, signed=False):
        if addr == 3:  # ADDR_MODEL_NUMBER
            return 0xFFFF  # Unknown model number
        return None

    drv._feetech_read_word = fake_read_word
    drv._feetech_read = lambda motor_id, addr, length: bytes([0xFF, 0xFF])  # dummy fallback
    drv.packet_handler.ping = lambda port_handler, motor_id: (scs.COMM_SUCCESS, 0)

    discovered = drv.scan_motors(scan_range=[1])
    assert len(discovered) == 0


def test_read_telemetry_si_conversion():
    drv = FeetechDriver("/dev/null", 115200)
    drv.serial_port = DummySerial()
    drv.connected = True

    # Provide identify_model that returns known position_scale
    drv.identify_model = lambda mid: MotorModelInfo(
        model="STS3215", model_ids=[3215], limits={}, position_scale=(2 * math.pi) / 4096, brand=MotorBrand.FEETECH
    )

    # Setup mocks for read_word and read_byte
    def fake_read_word(motor_id, addr, signed=False):
        if addr == 56:  # ADDR_PRESENT_POSITION
            return 1000
        if addr == 58:  # ADDR_PRESENT_SPEED
            return 20
        if addr == 60:  # ADDR_PRESENT_LOAD
            return 5
        if addr == 69:  # ADDR_PRESENT_CURRENT
            return 10
        if addr == 42:  # ADDR_GOAL_POSITION
            return 2000
        return 0

    def fake_read_byte(motor_id, addr):
        if addr == 63:  # ADDR_PRESENT_TEMPERATURE
            return 30
        if addr == 62:  # ADDR_PRESENT_VOLTAGE
            return 75  # raw -> 7.5V
        return 0

    drv._feetech_read_word = fake_read_word
    drv._feetech_read_byte = fake_read_byte

    telemetry = drv.read_telemetry(1, drv.identify_model(1))
    assert telemetry is not None
    # Check position converted to radians
    expected_pos = 1000 * ((2 * math.pi) / 4096)
    assert abs(telemetry.raw_position - expected_pos) < 1e-6
    # Check velocity converted
    expected_vel = 20 * ((2 * math.pi) / 4096)
    assert abs(telemetry.velocity - expected_vel) < 1e-6
    assert telemetry.voltage == 7.5
    assert telemetry.temperature == 30


def test_set_position_raises_on_unknown_model():
    drv = FeetechDriver("/dev/null", 115200)
    drv.serial_port = DummySerial()
    drv.connected = True

    # Force identify_model to fail
    def fake_identify(motor_id, *_args, **_kwargs):
        raise MotorIdentificationError("hardware.motor_device.unknown_model")

    drv.identify_model = fake_identify

    import pytest

    with pytest.raises(MotorIdentificationError):
        drv.set_position(1, 100)


def test_bulk_set_position_raises_on_unknown_model():
    drv = FeetechDriver("/dev/null", 115200)
    drv.serial_port = DummySerial()
    drv.connected = True

    # For motor 1 return a valid model info, for 2 raise
    from leropilot.models.hardware import MotorBrand, MotorModelInfo

    valid_model = MotorModelInfo(model="STS3215", model_ids=[3215], limits={}, variant=None, brand=MotorBrand.FEETECH)

    def fake_identify(motor_id, *_args, **_kwargs):
        if motor_id == 2:
            raise MotorIdentificationError("hardware.motor_device.unknown_model")

    drv.identify_model = fake_identify

    import pytest

    with pytest.raises(MotorIdentificationError):
        drv.bulk_set_position({1: 100.0, 2: 200.0}, speed=None)
