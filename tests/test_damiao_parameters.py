"""Test Damiao parameter read/write functionality"""

import pytest
from unittest.mock import Mock, patch

from leropilot.services.hardware.motor_drivers.damiao.drivers import DamiaoCAN_Driver
from leropilot.services.hardware.motor_drivers.damiao.tables import DamiaoConstants


class TestDamiaoParameterAccess:
    """Test parameter read/write functionality"""

    @pytest.fixture
    def driver(self):
        """Create a mock driver for testing"""
        return DamiaoCAN_Driver("pcan:PCAN_USBBUS1")

    def test_constants_defined(self):
        """Test that parameter access constants are properly defined"""
        assert DamiaoConstants.CAN_CMD_QUERY_PARAM == 0x33
        assert DamiaoConstants.CAN_CMD_WRITE_PARAM == 0x55
        assert DamiaoConstants.CAN_CMD_SAVE_PARAM == 0xAA
        assert DamiaoConstants.PARAM_ID == 0x7FF

    def test_read_parameter_format(self, driver):
        """Test parameter read command format"""
        motor_id = 1
        id_tuple = (motor_id, motor_id)
        param_addr = 0x100

        expected_data = bytes([
            motor_id & 0xFF,          # motor_id_low
            (motor_id >> 8) & 0xFF,   # motor_id_high
            DamiaoConstants.CAN_CMD_QUERY_PARAM,  # command
            param_addr & 0xFF,        # param_addr_low
            (param_addr >> 8) & 0xFF, # param_addr_high
            0, 0, 0                   # padding
        ])

        with patch.object(driver, '_send_can_frame') as mock_send, \
             patch.object(driver, '_recv_motor_response') as mock_recv:

            mock_send.return_value = True
            # Mock response: [motor_id_low, motor_id_high, CMD_QUERY_PARAM, param_addr_low, param_addr_high, value_low, value_high, 0]
            mock_response = Mock()
            mock_response.data = bytes([1, 0, 0x33, 0x00, 0x01, 0x34, 0x12, 0])  # value = 0x1234
            mock_recv.return_value = mock_response

            result = driver.read_parameter(id_tuple, param_addr)

            # Verify send was called with correct data to PARAM_ID
            mock_send.assert_called_once_with(DamiaoConstants.PARAM_ID, expected_data)
            # Verify response parsing
            assert result == 0x1234

    def test_write_parameter_format(self, driver):
        """Test parameter write command format"""
        motor_id = 2
        id_tuple = (motor_id, motor_id)
        param_addr = 0x200
        value = 0x5678

        expected_data = bytes([
            motor_id & 0xFF,          # motor_id_low
            (motor_id >> 8) & 0xFF,   # motor_id_high
            DamiaoConstants.CAN_CMD_WRITE_PARAM,  # command
            param_addr & 0xFF,        # param_addr_low
            (param_addr >> 8) & 0xFF, # param_addr_high
            value & 0xFF,             # value_low
            (value >> 8) & 0xFF,      # value_high
            0                         # padding
        ])

        with patch.object(driver, '_send_can_frame') as mock_send, \
             patch.object(driver, '_recv_motor_response') as mock_recv:

            mock_send.return_value = True
            # Mock acknowledgment response
            mock_response = Mock()
            mock_response.data = bytes([2, 0, 0x55, 0x00, 0x02, 0x78, 0x56, 0])
            mock_recv.return_value = mock_response

            result = driver.write_parameter(id_tuple, param_addr, value)

            # Verify send was called with correct data to PARAM_ID
            mock_send.assert_called_once_with(DamiaoConstants.PARAM_ID, expected_data)
            assert result is True

    def test_save_parameters_format(self, driver):
        """Test parameter save command format"""
        motor_id = 3
        id_tuple = (motor_id, motor_id)

        expected_data = bytes([
            motor_id & 0xFF,          # motor_id_low
            (motor_id >> 8) & 0xFF,   # motor_id_high
            DamiaoConstants.CAN_CMD_SAVE_PARAM,  # command
            0, 0, 0, 0, 0             # padding
        ])

        with patch.object(driver, '_send_can_frame') as mock_send, \
             patch.object(driver, '_recv_motor_response') as mock_recv:

            mock_send.return_value = True
            # Mock acknowledgment response
            mock_response = Mock()
            mock_response.data = bytes([3, 0, 0xAA, 0, 0, 0, 0, 0])
            mock_recv.return_value = mock_response

            result = driver.save_parameters(id_tuple)

            # Verify send was called with correct data to PARAM_ID
            mock_send.assert_called_once_with(DamiaoConstants.PARAM_ID, expected_data)
            assert result is True

    def test_read_parameter_no_response(self, driver):
        """Test parameter read when no response is received"""
        with patch.object(driver, '_send_can_frame') as mock_send, \
             patch.object(driver, '_recv_motor_response') as mock_recv:

            mock_send.return_value = True
            mock_recv.return_value = None  # No response

            result = driver.read_parameter((1, 1), 0x100)
            assert result is None

    def test_write_parameter_send_failure(self, driver):
        """Test parameter write when send fails"""
        with patch.object(driver, '_send_can_frame') as mock_send:
            mock_send.return_value = False

            result = driver.write_parameter((1, 1), 0x100, 0x1234)
            assert result is False

    def test_identify_model_with_parameter_read(self, driver):
        """Test model identification using parameter reading"""
        motor_id = (1, 1)
        model_number = 17168  # DM4310

        with patch.object(driver, 'read_parameter') as mock_read:
            # Mock reading model number from parameter address 0x01
            mock_read.return_value = model_number

            result = driver.identify_model(motor_id)

            assert result is not None
            assert result.model == "DM4310"
            mock_read.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])