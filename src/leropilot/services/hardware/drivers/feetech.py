"""
Feetech SCS servo driver implementation.

Supports Feetech STS3215 and SCS0009 servos using raw serial communication.
Directly implements SCS protocol without external SDK dependencies.
"""

import logging
import time

import serial

from leropilot.models.hardware import MotorInfo, MotorTelemetry
from leropilot.services.hardware.drivers.base import BaseMotorDriver

logger = logging.getLogger(__name__)

# Feetech SCS protocol register addresses (STS3215)
ADDR_FIRMWARE_MAJOR = 0
ADDR_FIRMWARE_MINOR = 1
ADDR_MODEL_NUMBER = 3
ADDR_ID = 5
ADDR_BAUD_RATE = 6
ADDR_TORQUE_ENABLE = 40
ADDR_GOAL_POSITION = 42
ADDR_GOAL_SPEED = 46
ADDR_PRESENT_POSITION = 56
ADDR_PRESENT_SPEED = 58
ADDR_PRESENT_LOAD = 60
ADDR_PRESENT_VOLTAGE = 62
ADDR_PRESENT_TEMPERATURE = 63
ADDR_PRESENT_CURRENT = 69

# Protocol settings
PROTOCOL_END = 0  # Little-endian

# Model number mappings
# Format: model_number: (base_model, variant)
MODEL_NAMES = {
    # Standard models (mappings from LeRobot and Feetech docs)
    0x0309: ("STS3215", None),  # 777
    0x0504: ("SCS0009", None),  # 1284
    0x0600: ("SCS09", None),  # 1536
    0x0700: ("SCS15", None),  # 1792
    0x0800: ("SCS20", None),  # 2048
    0x0A00: ("SCS25", None),  # 2560
    0x0C00: ("SCS30", None),  # 3072
    0x0E00: ("SCS35", None),  # 3584
    0x1000: ("SCS40", None),  # 4096
    0x0609: ("STS3215", None),  # 1545
    0x0C8F: ("STS3215", None),  # 3215
    0x0909: ("STS3250", None),  # 2313
    0x0B09: ("STS3250", None),  # 2825
    0x2C08: ("SM8512BL", None),  # 11272
    # SO-101 specific variants (C001, C044, C046)
    0xC001: ("STS3215", "C001"),
    0xC044: ("STS3215", "C044"),
    0xC046: ("STS3215", "C046"),
    # Legacy/Other mappings
    0x0E: ("SCS0009", None),
    0x00: ("STS3215", None),
}


class FeetechDriver(BaseMotorDriver):
    """Driver for Feetech SCS servo motors using raw serial communication"""

    def __init__(self, interface: str, baud_rate: int = 1000000) -> None:
        """
        Initialize Feetech driver.

        Args:
            interface: Serial port (e.g., "COM11", "/dev/ttyUSB0")
            baud_rate: Serial baud rate (default: 1000000)
        """
        super().__init__(interface, baud_rate)
        self.serial_port: serial.Serial | None = None
        self.connected = False

    def connect(self) -> bool:
        """Connect to motor bus via serial port"""
        try:
            self.serial_port = serial.Serial(self.interface, self.baud_rate, timeout=0.05)
            self.connected = True
            logger.info(f"Connected to Feetech motor bus on {self.interface} @ {self.baud_rate} baud")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to {self.interface}: {e}")
            self.connected = False
            return False

    def disconnect(self) -> bool:
        """Disconnect from motor bus"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.connected = False
            logger.info("Disconnected from Feetech motor bus")
            return True
        return False

    def _read_packet(self, motor_id: int, expected_data_len: int) -> bytes | None:
        """
        Read and validate a Feetech response packet.

        Args:
            motor_id: Expected motor ID
            expected_data_len: Expected number of data bytes (excluding Error byte)

        Returns:
            Validated packet bytes or None
        """
        if not self.serial_port:
            return None

        # Read a chunk of data
        resp = self.serial_port.read(64)
        if not resp:
            return None

        # Find header 0xFF 0xFF ID
        header_idx = -1
        for i in range(len(resp) - 5):
            if resp[i] == 0xFF and resp[i + 1] == 0xFF and resp[i + 2] == motor_id:
                header_idx = i
                break

        if header_idx == -1:
            return None

        resp = resp[header_idx:]

        # Expected total length: Header(2) + ID(1) + Length(1) + Error(1) + Data(N) + Checksum(1)
        # Total = 6 + N
        expected_total_len = 6 + expected_data_len

        if len(resp) < expected_total_len:
            # Try to read more if needed
            remaining = expected_total_len - len(resp)
            resp += self.serial_port.read(remaining)

        if len(resp) < expected_total_len:
            return None

        packet = resp[:expected_total_len]

        # Validate Checksum
        # Checksum = ~(ID + Length + Error + Params...) & 0xFF
        cs_sum = sum(packet[2:-1])
        calculated_cs = (~cs_sum) & 0xFF
        if packet[-1] != calculated_cs:
            logger.debug(f"Checksum mismatch for motor {motor_id}: expected {calculated_cs:02X}, got {packet[-1]:02X}")
            return None

        return packet

    def _feetech_read(self, motor_id: int, addr: int, length: int) -> bytes | None:
        """
        Send a Feetech READ command and return raw response bytes.

        Args:
            motor_id: Motor ID (1-254)
            addr: Register address
            length: Number of bytes to read

        Returns:
            Raw response bytes or None if failed
        """
        if not self.serial_port or not self.connected:
            return None

        # Construct READ packet
        packet_length = 4
        instruction = 0x02  # READ instruction
        checksum = (~(motor_id + packet_length + instruction + addr + length)) & 0xFF
        packet = bytes(
            [
                0xFF,
                0xFF,  # Header
                motor_id,  # Motor ID
                packet_length,  # Packet length
                instruction,  # Instruction
                addr,  # Address
                length,  # Length
                checksum,  # Checksum
            ]
        )

        try:
            self.serial_port.reset_input_buffer()
            self.serial_port.write(packet)
            time.sleep(0.02)  # Wait for response

            return self._read_packet(motor_id, length)
        except Exception as e:
            logger.debug(f"Read failed for motor {motor_id}: {e}")
            return None

    def ping_motor(self, motor_id: int) -> bool:
        """
        Ping motor to check if it exists.

        Args:
            motor_id: Motor ID (1-254)

        Returns:
            True if motor responds
        """
        return self._ping_motor_direct(motor_id)

    def read_telemetry(self, motor_id: int) -> MotorTelemetry | None:
        """
        Read real-time telemetry from a single motor.

        Args:
            motor_id: Motor ID

        Returns:
            Motor telemetry data or None if read fails
        """
        if not self.serial_port or not self.connected:
            return None

        try:
            # Read present position (2 bytes)
            resp = self._feetech_read(motor_id, ADDR_PRESENT_POSITION, 2)
            if not resp or len(resp) < 8:
                logger.error(f"Failed to read position from motor {motor_id}")
                return None
            position = resp[5] | (resp[6] << 8)

            # Read present speed (2 bytes)
            resp = self._feetech_read(motor_id, ADDR_PRESENT_SPEED, 2)
            if not resp or len(resp) < 8:
                logger.error(f"Failed to read speed from motor {motor_id}")
                return None
            speed = resp[5] | (resp[6] << 8)
            if speed > 32767:
                speed = speed - 65536

            # Read present load (2 bytes)
            resp = self._feetech_read(motor_id, ADDR_PRESENT_LOAD, 2)
            if not resp or len(resp) < 8:
                logger.error(f"Failed to read load from motor {motor_id}")
                return None
            load = resp[5] | (resp[6] << 8)
            if load > 32767:
                load = load - 65536

            # Read temperature (1 byte)
            resp = self._feetech_read(motor_id, ADDR_PRESENT_TEMPERATURE, 1)
            if not resp or len(resp) < 7:
                logger.error(f"Failed to read temperature from motor {motor_id}")
                return None
            temperature = resp[5]

            # Read voltage (1 byte)
            resp = self._feetech_read(motor_id, ADDR_PRESENT_VOLTAGE, 1)
            if not resp or len(resp) < 7:
                logger.error(f"Failed to read voltage from motor {motor_id}")
                return None
            voltage = resp[5] / 10.0

            # Read current (2 bytes)
            resp = self._feetech_read(motor_id, ADDR_PRESENT_CURRENT, 2)
            if not resp or len(resp) < 8:
                logger.error(f"Failed to read current from motor {motor_id}")
                return None
            current_raw = resp[5] | (resp[6] << 8)
            if current_raw > 32767:
                current_raw = current_raw - 65536
            current_ma = current_raw * 6.5  # Convert to mA

            # Read goal position (2 bytes)
            resp = self._feetech_read(motor_id, ADDR_GOAL_POSITION, 2)
            if not resp or len(resp) < 8:
                logger.error(f"Failed to read goal position from motor {motor_id}")
                return None
            goal_position = resp[5] | (resp[6] << 8)

            # Determine if motor is moving (speed != 0)
            moving = abs(speed) > 0

            return MotorTelemetry(
                id=motor_id,
                position=float(position),
                velocity=float(speed),
                current=int(current_ma),
                load=int(load),
                temperature=int(temperature),
                voltage=float(voltage),
                moving=moving,
                goal_position=float(goal_position),
                error=0,
            )

        except Exception as e:
            logger.error(f"Failed to read telemetry from motor {motor_id}: {e}")
            return None

    def read_bulk_telemetry(self, motor_ids: list[int]) -> dict[int, MotorTelemetry]:
        """
        Read telemetry from multiple motors efficiently.

        Args:
            motor_ids: List of motor IDs

        Returns:
            Dict mapping motor_id -> telemetry
        """
        result = {}
        for motor_id in motor_ids:
            telemetry = self.read_telemetry(motor_id)
            if telemetry:
                result[motor_id] = telemetry
        return result

    def scan_motors(self, scan_range: list[int] | None = None) -> list[MotorInfo]:
        """
        Scan motor bus and discover all motors.

        Args:
            scan_range: List of motor IDs to scan (default: 1-253)

        Returns:
            List of discovered motors
        """
        if scan_range is None:
            scan_range = list(range(1, 254))

        discovered = []
        logger.info(f"Scanning {len(scan_range)} motor IDs on Feetech bus")

        for motor_id in scan_range:
            # Ping the motor directly
            if self._ping_motor_direct(motor_id):
                try:
                    # Read model number (2 bytes at ADDR_MODEL_NUMBER)
                    resp = self._feetech_read(motor_id, ADDR_MODEL_NUMBER, 2)
                    model_number = 0
                    if resp and len(resp) >= 7:
                        # Feetech uses little-endian for model number
                        model_number = resp[5] | (resp[6] << 8)
                        logger.debug(f"Motor {motor_id} reported model number: {model_number} (0x{model_number:04X})")
                    else:
                        logger.warning(f"Motor {motor_id} responded to ping but failed to return model number")
                        continue

                    # Read firmware version (2 bytes at ADDR_FIRMWARE_MAJOR)
                    fw_resp = self._feetech_read(motor_id, ADDR_FIRMWARE_MAJOR, 2)
                    fw_version = "unknown"
                    fw_major = 0
                    fw_minor = 0
                    if fw_resp and len(fw_resp) >= 7:
                        fw_major = fw_resp[5]
                        fw_minor = fw_resp[6]
                        fw_version = f"{fw_major}.{fw_minor}"

                    model_info_tuple = MODEL_NAMES.get(model_number, (f"Unknown-{model_number}", None))
                    base_model, variant = model_info_tuple

                    # Special handling for SO-101 variants based on firmware version
                    # Many SO-101 motors report standard model 777 but use firmware version
                    # to distinguish variants (e.g., Major 0xC0, Minor 0x01 -> C001)
                    if base_model == "STS3215" and fw_major == 0xC0:
                        variant = f"C{fw_minor:03X}"
                        logger.debug(f"Detected SO-101 variant {variant} from firmware {fw_major:02X}.{fw_minor:02X}")

                    motor_info = MotorInfo(
                        id=motor_id,
                        model=base_model,
                        variant=variant,
                        model_number=model_number,
                        firmware_version=fw_version,
                    )
                    discovered.append(motor_info)
                    logger.info(f"Found motor {motor_id}: {motor_info.full_name} (FW: {fw_version})")
                except Exception as e:
                    logger.warning(f"Failed to read info for motor {motor_id}: {e}")

        logger.info(f"Scan complete: found {len(discovered)} motors")
        return discovered

    def set_torque(self, motor_id: int, enabled: bool) -> bool:
        """
        Enable or disable motor torque.

        Args:
            motor_id: Motor ID
            enabled: True to enable torque, False to disable

        Returns:
            True if command sent successfully
        """
        # STS3032 Torque Enable address is 40 (0x28)
        return self._feetech_write(motor_id, ADDR_TORQUE_ENABLE, 1 if enabled else 0, 1)

    def bulk_set_torque(self, motor_ids: list[int], enabled: bool) -> bool:
        """
        Set torque for multiple motors at once.

        Args:
            motor_ids: List of motor IDs
            enabled: True to enable, False to disable

        Returns:
            True if all commands sent successfully
        """
        success = True
        for motor_id in motor_ids:
            if not self.set_torque(motor_id, enabled):
                success = False
        return success

    def reboot_motor(self, motor_id: int) -> bool:
        """
        Reboot a single motor.

        Args:
            motor_id: Motor ID

        Returns:
            True if reboot command sent
        """
        if not self.serial_port or not self.connected:
            return False

        # Feetech reboot instruction is 0x08
        packet = [0xFF, 0xFF, motor_id, 0x02, 0x08]
        checksum = ~(sum(packet[2:]) & 0xFF) & 0xFF
        packet.append(checksum)

        try:
            self.serial_port.write(bytearray(packet))
            time.sleep(0.5)  # Wait for reboot
            return True
        except Exception as e:
            logger.error(f"Error rebooting motor {motor_id}: {e}")
            return False

    def set_position(self, motor_id: int, position: int, speed: int | None = None) -> bool:
        """
        Set motor target position.

        Args:
            motor_id: Motor ID
            position: Target position (raw servo value, typically 0-4095)
            speed: Optional movement speed (0-2047)

        Returns:
            True if command sent successfully
        """
        if not self.serial_port or not self.connected:
            return False

        try:
            # Clamp position to valid range
            position = max(0, min(4095, position))

            if speed is not None:
                # Write both position and speed (4 bytes starting at ADDR_GOAL_POSITION)
                speed = max(0, min(2047, speed))
                packet_length = 7
                instruction = 0x03
                data = [ADDR_GOAL_POSITION, position & 0xFF, position >> 8, speed & 0xFF, speed >> 8]
                checksum = (~(motor_id + packet_length + instruction + sum(data))) & 0xFF
                packet = [0xFF, 0xFF, motor_id, packet_length, instruction] + data + [checksum]
                self.serial_port.write(bytearray(packet))
            else:
                # Write only position (2 bytes)
                self._feetech_write(motor_id, ADDR_GOAL_POSITION, position, 2)

            return True
        except Exception as e:
            logger.error(f"Failed to set position for motor {motor_id}: {e}")
            return False

    def _feetech_write(self, motor_id: int, addr: int, value: int, length: int) -> bool:
        """
        Send a Feetech WRITE command.

        Args:
            motor_id: Motor ID
            addr: Register address
            value: Value to write
            length: Number of bytes (1 or 2)

        Returns:
            True if successful
        """
        if not self.serial_port or not self.connected:
            return False

        # Construct WRITE packet
        packet_length = 3 + length
        instruction = 0x03  # WRITE instruction

        params = []
        params.append(addr)
        if length == 1:
            params.append(value & 0xFF)
        else:
            params.append(value & 0xFF)
            params.append((value >> 8) & 0xFF)

        checksum = (~(motor_id + packet_length + instruction + sum(params))) & 0xFF

        packet = [0xFF, 0xFF, motor_id, packet_length, instruction] + params + [checksum]

        try:
            self.serial_port.write(bytearray(packet))
            time.sleep(0.01)
            return True
        except Exception as e:
            logger.debug(f"Write failed for motor {motor_id}: {e}")
            return False

    def _ping_motor_direct(self, motor_id: int) -> bool:
        """
        Ping motor directly using raw serial (like in PoC).

        Args:
            motor_id: Motor ID (1-254)

        Returns:
            True if motor responds
        """
        if not self.serial_port or not self.connected:
            return False

        # Construct PING packet (same as PoC)
        length = 2
        instruction = 0x01  # PING instruction
        checksum = (~(motor_id + length + instruction)) & 0xFF
        packet = bytes(
            [
                0xFF,
                0xFF,  # Header
                motor_id,  # Motor ID
                length,  # Packet length
                instruction,  # Instruction
                checksum,  # Checksum
            ]
        )

        try:
            self.serial_port.reset_input_buffer()
            self.serial_port.write(packet)
            time.sleep(0.02)  # Wait for response

            # PING response has 0 data bytes
            resp = self._read_packet(motor_id, 0)
            return resp is not None
        except Exception as e:
            logger.debug(f"Ping failed for motor {motor_id}: {e}")
            return False
