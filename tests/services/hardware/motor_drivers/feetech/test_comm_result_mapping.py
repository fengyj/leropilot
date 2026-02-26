import scservo_sdk as scs
import pytest

from leropilot.services.hardware.motor_drivers.feetech.drivers import FeetechDriver
from leropilot.exceptions import OperationalError


def test_check_sdk_result_logs_constant_name(caplog):
    drv = FeetechDriver(interface="/dev/null", baud_rate=115200)
    drv.serial_port = None
    drv.connected = True

    # Monkeypatch packet_handler.read2ByteTxRx to simulate RX timeout
    drv.packet_handler.read2ByteTxRx = lambda port_handler, motor_id, addr: (0, scs.COMM_RX_TIMEOUT, 0)

    with pytest.raises(OperationalError):
        drv._feetech_read_word(249, 3)

    # Ensure the log contains the friendly constant name
    found = any("COMM_RX_TIMEOUT" in rec.getMessage() for rec in caplog.records)
    assert found, "Expected log to include 'COMM_RX_TIMEOUT'"
