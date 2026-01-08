"""
Feetech SCS servo driver implementation.

Supports Feetech STS3215 and SCS0009 servos using Feetech SDK.
"""

import logging
import time

import scservo_sdk as scs

from leropilot.models.hardware import MotorModelInfo, MotorTelemetry

from ..base import BaseMotorDriver
from .tables import SCS_STS_MODELS_LIST, SCS_STS_Registers, models_for_id

logger = logging.getLogger(__name__)

# Protocol settings
PROTOCOL_END = 0  # Little-endian


class FeetechDriver(BaseMotorDriver[int]):
    """Driver for Feetech SCS servo motors using Feetech SDK"""

    def __init__(self, interface: str, baud_rate: int | None = None) -> None:
        """
        Initialize Feetech driver.

        Args:
            interface: Serial port (e.g., "COM11", "/dev/ttyUSB0")
            baud_rate: Serial baud rate (default: 1000000)
        """
        super().__init__(interface, baud_rate)
        self.port_handler = scs.PortHandler(self.interface)
        self.packet_handler = scs.PacketHandler(PROTOCOL_END)
        self.connected = False
        # Protocol metadata for higher-level code that inspects drivers
        # Keep a reference to packet handler as `protocol` for compatibility
        self.protocol = self.packet_handler
        # Protocol id
        self.protocol_id: int = PROTOCOL_END
        self.registers = SCS_STS_Registers

    def connect(self) -> bool:
        """Connect to motor bus via serial port"""
        try:
            if self.port_handler.openPort():
                if self.port_handler.setBaudRate(self.baud_rate):
                    self.connected = True
                    logger.info(f"Connected to Feetech motor bus (SDK) on {self.interface} @ {self.baud_rate} baud")
                    return True
                else:
                    logger.error(f"Failed to set baud rate {self.baud_rate} with SDK")
                    self.port_handler.closePort()
            else:
                logger.error(f"Failed to open port {self.interface} with SDK")
        except Exception as e:
            logger.error(f"Failed to connect using SDK: {e}")
        return False

    def disconnect(self) -> bool:
        """Disconnect from motor bus"""
        try:
            self.port_handler.closePort()
            self.connected = False
            logger.info("Disconnected from Feetech motor bus (SDK)")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting with SDK: {e}")
            return False

    def ping_motor(self, motor_id: int) -> bool:
        """
        Ping motor to check if it exists.

        Args:
            motor_id: Motor ID (1-254)

        Returns:
            True if motor responds
        """
        if not self.connected:
            return False

        try:
            # Use SDK ping
            result, error = self.packet_handler.ping(self.port_handler, motor_id)
            return result == scs.COMM_SUCCESS
        except Exception as e:
            logger.debug(f"SDK ping failed for motor {motor_id}: {e}")
            return False

    def _feetech_read(self, motor_id: int, addr: int, length: int) -> int | None:
        """
        Send a Feetech READ command and return the data value.

        Args:
            motor_id: Motor ID (1-254)
            addr: Register address
            length: Number of bytes to read (1 or 2)

        Returns:
            Data value or None if failed
        """
        try:
            # Use SDK for reading
            data, result, error = self.packet_handler.readTxRx(self.port_handler, motor_id, addr, length)
            if result == scs.COMM_SUCCESS and error == 0:
                return data
            else:
                logger.debug(f"SDK read failed for motor {motor_id}: result={result}, error={error}")
                return None
        except Exception as e:
            logger.debug(f"SDK read exception for motor {motor_id}: {e}")
            return None

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
        try:
            # Use SDK for writing
            result, error = self.packet_handler.writeTxRx(self.port_handler, motor_id, addr, length, value)
            if result == scs.COMM_SUCCESS and error == 0:
                return True
            else:
                logger.debug(f"SDK write failed for motor {motor_id}: result={result}, error={error}")
                return False
        except Exception as e:
            logger.debug(f"SDK write exception for motor {motor_id}: {e}")
            return False

    def _ping_motor_direct(self, motor_id: int) -> bool:
        """
        Direct ping implementation for scanning.

        Args:
            motor_id: Motor ID to ping

        Returns:
            True if motor responds
        """
        return self.ping_motor(motor_id)

    def identify_model(
        self,
        motor_id: int,
        model_number: int | None = None,
        fw_major: int | None = None,
        fw_minor: int | None = None,
        raise_on_ambiguous: bool = False,
    ) -> MotorModelInfo:
        """Identify a motor and return a `MotorModelInfo` instance (best-effort).

        If `model_number`/`fw_*` are provided, identification will use those values
        and avoid additional register reads (useful for `scan_motors`).

        Raises:
            RuntimeError: if driver is not connected.
            ValueError: if model number is unknown.
        """
        if not self.connected:
            raise RuntimeError("Driver not connected for identify_model")

        # Ensure we have a model_number (read if not provided)
        if model_number is None:
            model_number = self._feetech_read(motor_id, SCS_STS_Registers.ADDR_MODEL_NUMBER, 2)
            if model_number is None:
                raise ValueError(f"Failed to read model number for motor {motor_id}")

        # Ensure firmware bytes are available when needed for variant resolution
        if fw_major is None or fw_minor is None:
            fw_data = self._feetech_read(motor_id, SCS_STS_Registers.ADDR_FIRMWARE_MAJOR, 2)
            if fw_data is not None:
                fw_major = (fw_data >> 8) & 0xFF  # High byte
                fw_minor = fw_data & 0xFF  # Low byte

        # Use table-based selection logic
        candidates = models_for_id(model_number)

        if not candidates:
            # Unable to identify model from tables
            raise ValueError(f"Unknown Feetech model number: {model_number}")

        # Firmware-derived variant detection (SO-101 family) - try this first if firmware available
        if fw_major == 0xC0 and fw_minor is not None:
            variant_code = f"C{fw_minor:03X}"
            for m in SCS_STS_MODELS_LIST:
                if m.model == "STS3215" and (m.variant or "").endswith(variant_code):
                    # Identified variant is already represented in the tables (brand set there)
                    pass
        for c in candidates:
            if c.variant is None:
                return c

        # Ambiguous: either raise or return base-like fallback
        if raise_on_ambiguous:
            from leropilot.models.hardware import AmbiguousModelError

            raise AmbiguousModelError(f"Model id {model_number} is ambiguous: {[c.model for c in candidates]}")

        result = candidates[0].model_copy()
        result.variant = None
        return result

    def supported_models(self) -> list[MotorModelInfo]:
        """Return list of MotorModelInfo supported by this driver (all series)."""
        return list(SCS_STS_MODELS_LIST)

    def read_telemetry(self, motor_id: int) -> MotorTelemetry | None:
        """
        Read real-time telemetry from a single motor (returns SI units).

        Args:
            motor_id: Motor ID

        Returns:
            Motor telemetry data or None if read fails
        """
        if not self.connected:
            return None

        try:
            # Try to get model info for conversion; fall back to defaults
            model_info = self.identify_model(motor_id)
            position_scale = None
            if model_info and model_info.position_scale:
                position_scale = model_info.position_scale

            # Read present position (2 bytes)
            position = self._feetech_read(motor_id, SCS_STS_Registers.ADDR_PRESENT_POSITION, 2)
            if position is None:
                logger.error(f"Failed to read position from motor {motor_id}")
                return None

            # Read present speed (2 bytes)
            speed = self._feetech_read(motor_id, SCS_STS_Registers.ADDR_PRESENT_SPEED, 2)
            if speed is None:
                logger.error(f"Failed to read speed from motor {motor_id}")
                return None
            if speed > 32767:
                speed = speed - 65536

            # Read present load (2 bytes)
            load = self._feetech_read(motor_id, SCS_STS_Registers.ADDR_PRESENT_LOAD, 2)
            if load is None:
                logger.error(f"Failed to read load from motor {motor_id}")
                return None
            if load > 32767:
                load = load - 65536

            # Read temperature (1 byte)
            temperature = self._feetech_read(motor_id, SCS_STS_Registers.ADDR_PRESENT_TEMPERATURE, 1)
            if temperature is None:
                logger.error(f"Failed to read temperature from motor {motor_id}")
                return None

            # Read voltage (1 byte)
            voltage_raw = self._feetech_read(motor_id, SCS_STS_Registers.ADDR_PRESENT_VOLTAGE, 1)
            if voltage_raw is None:
                logger.error(f"Failed to read voltage from motor {motor_id}")
                return None
            voltage = voltage_raw / 10.0

            # Read current (2 bytes)
            current_raw = self._feetech_read(motor_id, SCS_STS_Registers.ADDR_PRESENT_CURRENT, 2)
            if current_raw is None:
                logger.error(f"Failed to read current from motor {motor_id}")
                return None
            if current_raw > 32767:
                current_raw = current_raw - 65536
            current_ma = current_raw * 6.5  # Convert to mA

            # Read goal position (2 bytes)
            goal_position = self._feetech_read(motor_id, SCS_STS_Registers.ADDR_GOAL_POSITION, 2)
            if goal_position is None:
                logger.error(f"Failed to read goal position from motor {motor_id}")
                return None

            # Determine if motor is moving (speed != 0)
            moving = abs(speed) > 0

            # Convert position/speed to SI if position_scale available
            if position_scale:
                position_si = float(position) * position_scale
                velocity_si = float(speed) * position_scale
                goal_position_si = float(goal_position) * position_scale
            else:
                # Fall back to raw counts but warn
                logger.debug("No position_scale available for motor %s; returning raw counts", motor_id)
                position_si = float(position)
                velocity_si = float(speed)
                goal_position_si = float(goal_position)

            return MotorTelemetry(
                id=motor_id,
                position=position_si,
                velocity=velocity_si,
                current=int(current_ma),
                load=int(load),
                temperature=int(temperature),
                voltage=float(voltage),
                moving=moving,
                goal_position=goal_position_si,
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

    def scan_motors(self, scan_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """
        Scan motor bus and discover all motors.

        Args:
            scan_range: List of motor IDs to scan (default: 1-253)

        Returns:
            Mapping of motor id -> MotorModelInfo for discovered motors
        """
        if scan_range is None:
            scan_range = list(range(1, 254))

        discovered: dict[int, MotorModelInfo] = {}
        logger.info(f"Scanning {len(scan_range)} motor IDs on Feetech bus")

        for motor_id in scan_range:
            # Ping the motor directly
            if self._ping_motor_direct(motor_id):
                try:
                    # We already have model_number/firmware bytes; use identify_model to resolve
                    model_number = self._feetech_read(motor_id, SCS_STS_Registers.ADDR_MODEL_NUMBER, 2)
                    if model_number is None:
                        logger.warning(f"Motor {motor_id} responded to ping but failed to return model number")
                        continue

                    fw_data = self._feetech_read(motor_id, SCS_STS_Registers.ADDR_FIRMWARE_MAJOR, 2)
                    fw_major = None
                    fw_minor = None
                    if fw_data is not None:
                        fw_major = (fw_data >> 8) & 0xFF  # High byte
                        fw_minor = fw_data & 0xFF  # Low byte

                    try:
                        model_info = self.identify_model(
                            motor_id, model_number=model_number, fw_major=fw_major, fw_minor=fw_minor
                        )
                    except Exception as e:
                        logger.debug(f"identify_model raised for motor {motor_id}: {e}")
                        model_info = None

                    if not model_info:
                        logger.debug(f"Skipping unknown model for motor {motor_id} (model_number={model_number})")
                        continue

                    discovered[motor_id] = model_info
                    logger.info(f"Found motor {motor_id}: {model_info.model} (model_number={model_number})")
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
        return self._feetech_write(motor_id, SCS_STS_Registers.ADDR_TORQUE_ENABLE, 1 if enabled else 0, 1)

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
        try:
            success = self.protocol.reboot(motor_id)
            if success:
                time.sleep(0.5)  # Wait for reboot
            return success
        except Exception as e:
            logger.error(f"Reboot failed for motor {motor_id}: {e}")
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
        if not self.connected:
            return False

        try:
            # Clamp position to valid range
            position = max(0, min(4095, position))

            if speed is not None:
                # Write both position and speed
                speed = max(0, min(2047, speed))
                pos_result = self.protocol.write_register(
                    motor_id, self.registers.ADDR_GOAL_POSITION, position.to_bytes(2, byteorder="little")
                )
                speed_result = self.protocol.write_register(
                    motor_id, self.registers.ADDR_GOAL_SPEED, speed.to_bytes(2, byteorder="little")
                )
                return pos_result and speed_result
            else:
                # Write only position
                return self.protocol.write_register(
                    motor_id, self.registers.ADDR_GOAL_POSITION, position.to_bytes(2, byteorder="little")
                )
        except Exception as e:
            logger.error(f"Failed to set position for motor {motor_id}: {e}")
            return False
