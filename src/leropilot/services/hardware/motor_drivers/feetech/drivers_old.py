"""
Feetech SCS servo driver implementation.

Supports Feetech STS3215 and SCS0009 servos using Feetech SDK.
"""

import logging

import scservo_sdk as scs

from leropilot.exceptions import MotorIdentificationError, OperationalError
from leropilot.models.hardware import MotorModelInfo, MotorTelemetry, PositionType

from ..base import BaseMotorDriver
from .tables import SCS_STS_MODELS_LIST, SIGNED_REGISTERS, SCS_STS_Registers, feetech_supports_register, models_for_id

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
        self.protocol = self.packet_handler
        self.protocol_id: int = PROTOCOL_END
        self.registers = SCS_STS_Registers

    def _ensure_connected(self, motor_id: int | None = None, register: int | None = None) -> None:
        """Raise OperationalError if driver is not connected.

        Args:
            motor_id: Optional motor id for context
            register: Optional register address for context
        """
        if not self.connected or not self.port_handler or not self.packet_handler:
            raise OperationalError(
                i18n_key="hardware.motor_device.not_connected",
                retriable=False,
                interface=self.interface,
                motor_id=motor_id,
                register=register,
            )

    def _decode_signed_register(self, value: int, addr: int) -> int:
        """Decode register value using sign-magnitude encoding if in SIGNED_REGISTERS table.

        Feetech motors use sign-magnitude encoding, not two's complement.

        Args:
            value: Raw unsigned register value
            addr: Register address

        Returns:
            Signed value if register uses sign-magnitude, otherwise unchanged
        """
        if addr in SIGNED_REGISTERS:
            sign_bit = SIGNED_REGISTERS[addr]
            sign_mask = 1 << sign_bit
            magnitude_mask = sign_mask - 1
            if value & sign_mask:  # Negative
                return -(value & magnitude_mask)
            return value & magnitude_mask
        return value

    def _encode_signed_register(self, value: float, addr: int) -> int:
        """Encode value using sign-magnitude encoding if in SIGNED_REGISTERS table.

        Feetech motors use sign-magnitude encoding, not two's complement.

        Args:
            value: Signed value to encode
            addr: Register address

        Returns:
            Unsigned register value
        """
        int_value = int(value)
        if addr in SIGNED_REGISTERS:
            sign_bit = SIGNED_REGISTERS[addr]
            sign_mask = 1 << sign_bit
            magnitude_mask = sign_mask - 1
            if int_value < 0:
                return sign_mask | (abs(int_value) & magnitude_mask)
            return int_value & magnitude_mask
        return int_value

    def _check_sdk_result(
        self, result: int, error: int, operation: str, motor_id: int, addr: int | None = None
    ) -> None:
        """Check SDK operation result and raise OperationalError if failed.

        Args:
            result: SDK result code
            error: SDK error code
            operation: Operation name for logging
            motor_id: Motor ID for error context
            addr: Optional register address for error context
        """
        if result != scs.COMM_SUCCESS or error != 0:
            addr_info = f" addr={addr}" if addr is not None else ""
            logger.debug(f"SDK {operation} failed for motor {motor_id}{addr_info}: result={result}, error={error}")
            raise OperationalError(
                i18n_key="hardware.motor_device.operation_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
                register=addr,
                operation=operation,
            )

    def connect(self) -> None:
        """Connect to motor bus via serial port.

        Raises:
            OperationalError: If connection fails.
        """
        if self.connected:
            return

        try:
            if not self.port_handler.openPort():
                logger.error(f"Failed to open port {self.interface}")
                raise OperationalError(
                    i18n_key="hardware.motor_device.connect_failed",
                    retriable=True,
                    interface=self.interface,
                )

            # Use a default baud rate if none provided
            baud_to_set = int(self.baud_rate or 1000000)
            if not self.port_handler.setBaudRate(baud_to_set):
                logger.error(f"Failed to set baud rate {baud_to_set}")
                self.port_handler.closePort()
                raise OperationalError(
                    i18n_key="hardware.motor_device.connect_failed",
                    retriable=True,
                    interface=self.interface,
                )

            self.connected = True
            logger.info(f"Connected to Feetech motor bus (SDK) on {self.interface} at {baud_to_set} baud")
        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Error connecting with SDK: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.connect_failed",
                retriable=True,
                interface=self.interface,
            ) from e

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

    def _feetech_read_byte(self, motor_id: int, addr: int) -> int:
        """Read a single byte register and return as int.

        Directly calls PacketHandler.read1ByteTxRx().
        Raises OperationalError on communication failure.
        """
        self._ensure_connected(motor_id=motor_id, register=addr)
        try:
            data, result, error = self.packet_handler.read1ByteTxRx(self.port_handler, motor_id, addr)
            self._check_sdk_result(result, error, "read1ByteTxRx", motor_id, addr)
            return self._decode_signed_register(int(data), addr)
        except OperationalError:
            raise
        except Exception as e:
            logger.debug(f"SDK read1ByteTxRx exception for motor {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.read_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
                register=addr,
            ) from e

    def _feetech_read_word(self, motor_id: int, addr: int) -> int:
        """Read a 2-byte register and return as int (little-endian).

        Directly calls PacketHandler.read2ByteTxRx().
        Raises OperationalError on communication failure.
        """
        self._ensure_connected(motor_id=motor_id, register=addr)
        try:
            data, result, error = self.packet_handler.read2ByteTxRx(self.port_handler, motor_id, addr)
            self._check_sdk_result(result, error, "read2ByteTxRx", motor_id, addr)
            return self._decode_signed_register(int(data), addr)
        except OperationalError:
            raise
        except Exception as e:
            logger.debug(f"SDK read2ByteTxRx exception for motor {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.read_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
                register=addr,
            ) from e

    def _feetech_read_dword(self, motor_id: int, addr: int) -> int:
        """Read a 4-byte register and return as int (little-endian).

        Directly calls PacketHandler.read4ByteTxRx().
        Raises OperationalError on communication failure.
        """
        self._ensure_connected(motor_id=motor_id, register=addr)
        try:
            data, result, error = self.packet_handler.read4ByteTxRx(self.port_handler, motor_id, addr)
            self._check_sdk_result(result, error, "read4ByteTxRx", motor_id, addr)
            return self._decode_signed_register(int(data), addr)
        except OperationalError:
            raise
        except Exception as e:
            logger.debug(f"SDK read4ByteTxRx exception for motor {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.read_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
                register=addr,
            ) from e

    def _read_model_and_fw(self, motor_id: int) -> tuple[int, int | None, int | None]:
        """Read model number (int) and firmware major/minor (ints or None).

        Uses _feetech_read_word() for deterministic int results.
        Returns (model_number, fw_major, fw_minor).
        Raises OperationalError if model read fails; gracefully returns None for fw if read fails.
        """
        # Model number (2 bytes)
        addr, _ = SCS_STS_Registers.MODEL_NUMBER
        model_number = self._feetech_read_word(motor_id, addr)

        # Firmware (2 bytes) �?may fail; return None for fw parts if unreadable
        fw_major = None
        fw_minor = None
        try:
            fw_addr, _ = SCS_STS_Registers.FIRMWARE_MAJOR
            fw_val = self._feetech_read_word(motor_id, fw_addr)
            if fw_val is not None:
                fw_major = (fw_val >> 8) & 0xFF
                fw_minor = fw_val & 0xFF
        except OperationalError:
            fw_major = None
            fw_minor = None

        return model_number, fw_major, fw_minor

    def identify_model(
        self,
        motor_id: int,
        model_number: int | None = None,
        fw_major: int | None = None,
        fw_minor: int | None = None,
        raise_on_ambiguous: bool = False,
    ) -> MotorModelInfo:
        """Identify a motor and return a `MotorModelInfo` instance (best-effort).

        Uses cached results when available to avoid repeated register reads.

        If `model_number`/`fw_*` are provided, identification will use those values
        and avoid additional register reads (useful for `scan_motors`).

        Raises:
            OperationalError: if driver is not connected.
            ValueError: if model number is unknown.
        """
        if not self.connected:
            raise OperationalError(
                i18n_key="hardware.motor_device.not_connected",
                retriable=False,
                interface=self.interface,
                motor_id=motor_id,
            )

        # If caller didn't provide model/fw data, read them deterministically
        if model_number is None or fw_major is None or fw_minor is None:
            try:
                m_num, m_fw_major, m_fw_minor = self._read_model_and_fw(motor_id)
                if model_number is None:
                    model_number = m_num
                if fw_major is None:
                    fw_major = m_fw_major
                if fw_minor is None:
                    fw_minor = m_fw_minor
            except OperationalError as e:
                # Raise a domain-specific identification error so callers can
                # distinguish identification failures from other ValueError uses.
                raise MotorIdentificationError(
                    i18n_key="hardware.motor_device.identification_failed",
                    retriable=True,
                    interface=self.interface,
                    motor_id=motor_id,
                ) from e

        # Use table-based selection logic
        candidates = models_for_id(model_number)

        if not candidates:
            # Unable to identify model from tables
            raise MotorIdentificationError(
                i18n_key="hardware.motor_device.unknown_model",
                retriable=False,
                interface=self.interface,
                motor_id=motor_id,
                data={"model_number": model_number},
            )

        # Firmware-derived variant detection (SO-101 family) - try this first if firmware available
        if fw_major == 0xC0 and fw_minor is not None:
            variant_code = f"C{fw_minor:03X}"
            # Prefer candidate entries that include the explicit variant suffix
            for c in candidates:
                if c.model == "STS3215" and (c.variant or "").endswith(variant_code):
                    return c

        # Prefer an un-variant candidate (base model) when available
        for c in candidates:
            if c.variant is None:
                return c

        # Ambiguous: either raise or return base-like fallback
        if raise_on_ambiguous:
            raise MotorIdentificationError(
                i18n_key="hardware.motor_device.ambiguous_model",
                retriable=False,
                interface=self.interface,
                motor_id=motor_id,
                data={"candidates": [c.model for c in candidates]},
            )

        result = candidates[0].model_copy()
        result.variant = None
        return result

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
            self._check_sdk_result(result, error, "writeTxRx", motor_id, addr)
            return True
        except OperationalError:
            raise
        except Exception as e:
            logger.debug(f"SDK write exception for motor {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.write_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
                register=addr,
            ) from e

    def read_telemetry(self, motor_id: int, model_info: MotorModelInfo) -> MotorTelemetry:
        """Read real-time telemetry from a single motor.

        Uses individual register reads since Feetech SDK's readTxRx returns int for small reads.
        While less efficient than block reads, this ensures compatibility with the SDK.

        Args:
            motor_id: Motor ID
            model_info: `MotorModelInfo` (required)

        Returns:
            Motor telemetry data or None if critical read fails
        """

        try:
            # Position is critical and should be returned in SI (radians) via the value-level API
            position = self.read_position(motor_id, model_info)
            if position is None:
                logger.error(f"Position not supported or failed to read for motor {motor_id}")
                return None

            # Read other telemetry data (value-level helpers return SI units where applicable)
            velocity = self.read_velocity(motor_id, model_info) or 0
            load_val = self._read_load(motor_id, model_info)
            temperature_raw = self.read_temperature(motor_id, model_info)
            voltage_raw = self.read_voltage(motor_id, model_info)
            current_ma = self.read_current(motor_id, model_info)
            goal_position = self.read_goal_position(motor_id, model_info)

            # Determine if motor is moving
            moving = abs(velocity) > 0

            return MotorTelemetry(
                id=motor_id,
                position=position,
                position_type=PositionType.RAW,
                goal_position=goal_position if goal_position is not None else None,
                velocity=velocity,
                current=current_ma if current_ma is not None else None,
                load=int(load_val) if load_val is not None else None,
                temperature=temperature_raw if temperature_raw is not None else None,
                voltage=voltage_raw if voltage_raw is not None else None,
                moving=moving,
                error=0,
            )

        except ValueError:
            raise
        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to read telemetry from motor {motor_id}: {e}")
            return None

    def bulk_read_telemetry(self, motors: dict[int, MotorModelInfo]) -> dict[int, MotorTelemetry]:
        """Read telemetry from multiple motors efficiently using GroupSyncRead.

        Creates separate GroupSyncRead instances for each register address to enable
        efficient batch reading. This follows lerobot best practices.

        Args:
            motors: Mapping of motor_id -> MotorModelInfo

        Returns:
            Dict mapping motor_id -> telemetry
        """
        if not self.connected or not motors:
            return {}

        result: dict[int, MotorTelemetry] = {}

        try:
            # Define registers to read with their byte lengths
            # Extract (addr, length) from register tuples
            registers_to_read = [
                (*SCS_STS_Registers.PRESENT_POSITION, "position"),
                (*SCS_STS_Registers.PRESENT_VELOCITY, "velocity"),
                (*SCS_STS_Registers.PRESENT_LOAD, "load"),
                (*SCS_STS_Registers.PRESENT_VOLTAGE, "voltage"),
                (*SCS_STS_Registers.PRESENT_TEMPERATURE, "temperature"),
                (*SCS_STS_Registers.PRESENT_CURRENT, "current"),
                (*SCS_STS_Registers.GOAL_POSITION, "goal_position"),
            ]

            # Store raw telemetry data: motor_id -> {field_name: raw_value}
            raw_data: dict[int, dict[str, int | None]] = {motor_id: {} for motor_id in motors}

            # Read each register using GroupSyncRead
            for addr, byte_length, field_name in registers_to_read:
                # Create new GroupSyncRead instance for this register
                group_sync_read = scs.GroupSyncRead(self.port_handler, self.packet_handler, addr, byte_length)

                # Add all motors that support this register
                motors_added = []
                for motor_id, model_info in motors.items():
                    if feetech_supports_register(model_info.model, addr):
                        if group_sync_read.addParam(motor_id):
                            motors_added.append(motor_id)

                if not motors_added:
                    # No motors support this register, skip
                    for motor_id in motors:
                        raw_data[motor_id][field_name] = None
                    continue

                # Perform sync read
                comm_result = group_sync_read.txRxPacket()
                if comm_result != scs.COMM_SUCCESS:
                    logger.warning(
                        f"GroupSyncRead failed for register {addr}: {self.packet_handler.getTxRxResult(comm_result)}"
                    )
                    for motor_id in motors_added:
                        raw_data[motor_id][field_name] = None
                    continue

                # Extract data for each motor
                for motor_id in motors_added:
                    if not group_sync_read.isAvailable(motor_id, addr, byte_length):
                        logger.debug(f"Data not available for motor {motor_id} register {addr}")
                        raw_data[motor_id][field_name] = None
                        continue

                    # Get data and apply signed conversion if needed
                    value = group_sync_read.getData(motor_id, addr, byte_length)
                    value = self._decode_signed_register(value, addr)
                    raw_data[motor_id][field_name] = value

            # Convert raw data to MotorTelemetry objects (convert to SI units where applicable)
            for motor_id, model_info in motors.items():
                data = raw_data[motor_id]

                # Position is critical - skip motor if unavailable
                position = data.get("position")
                if position is None:
                    logger.debug(f"Skipping motor {motor_id}: position unavailable")
                    continue

                velocity = data.get("velocity") or 0
                load_val = data.get("load")
                temperature_raw = data.get("temperature")
                voltage_raw_val = data.get("voltage")
                current_raw = data.get("current")
                goal_position = data.get("goal_position") or position

                # Convert position and velocity to SI units (radians, rad/s)
                conv_pos = self._get_conversion_factor(model_info, "position")  # type: ignore[arg-type]
                pos_si = position * conv_pos

                conv_vel = self._get_conversion_factor(model_info, "velocity")  # type: ignore[arg-type]
                vel_si = (velocity * conv_vel) if velocity is not None else 0.0

                # Convert voltage (requires per-model conversion factor)
                conv_v = self._get_conversion_factor(model_info, "voltage")  # type: ignore[arg-type]
                voltage = (voltage_raw_val * conv_v) if voltage_raw_val is not None else None

                # Convert current (requires per-model conversion factor)
                conv_c = self._get_conversion_factor(model_info, "current")  # type: ignore[arg-type]
                current_ma = (current_raw * conv_c) if current_raw is not None else None

                # Determine if moving
                moving = abs(vel_si) > 0

                result[motor_id] = MotorTelemetry(
                    id=motor_id,
                    position=pos_si,
                    position_type=PositionType.RAW_IN_RADIAN,
                    goal_position=(goal_position * conv_pos) if goal_position is not None else None,
                    velocity=vel_si,
                    current=current_ma,
                    load=int(load_val) if load_val is not None else None,
                    temperature=temperature_raw if temperature_raw is not None else None,
                    voltage=voltage,
                    moving=moving,
                    error=0,
                )

        except ValueError:
            # Missing model metadata — do not swallow; let caller fix model_info
            raise
        except OperationalError:
            # I/O level failure — re-raise so caller can handle or retry
            raise
        except Exception as e:
            logger.error(f"Failed to bulk read telemetry: {e}")
            # Fallback to individual reads
            for motor_id, model_info in motors.items():
                telemetry = self.read_telemetry(motor_id, model_info)
                if telemetry:
                    result[motor_id] = telemetry

        return result

    def _get_position_max(self, model_info: MotorModelInfo | None = None) -> int:
        """Get the maximum position value for a motor model.

        Uses encoder_resolution - 1 if available, otherwise DEFAULT_POSITION_MAX.
        """
        return int(model_info.encoder_resolution - 1)

    def _get_velocity_max(self, model_info: MotorModelInfo | None = None) -> int:
        """Get the maximum velocity value for a motor model.

        Currently uses DEFAULT_VELOCITY_MAX, but could be made model-specific in the future.
        """
        return DEFAULT_VELOCITY_MAX

    def supported_models(self) -> list[MotorModelInfo]:
        """Return list of MotorModelInfo supported by this driver (all series)."""
        return list(SCS_STS_MODELS_LIST)

    def scan_motors(self, scan_range: list[int] | None = None) -> dict[int, MotorModelInfo]:
        """
        Scan motor bus and discover all motors using optimized batch ping.

        Performance: Scans in batches of 20 with reduced timeouts for ~2-3x speedup.

        Args:
            scan_range: List of motor IDs to scan (default: 1-253)

        Returns:
            Mapping of motor id -> MotorModelInfo for discovered motors
        """
        if scan_range is None:
            scan_range = list(range(1, 254))

        discovered: dict[int, MotorModelInfo] = {}
        logger.info(f"Scanning {len(scan_range)} motor IDs on Feetech bus")

        if not self.connected:
            logger.error("Not connected to Feetech motor bus")
            return discovered

        # Scan in batches to reduce per-motor overhead
        batch_size = 20
        for i in range(0, len(scan_range), batch_size):
            batch = scan_range[i : i + batch_size]
            logger.debug(f"Scanning batch: motor IDs {batch[0]}-{batch[-1]}")

            for motor_id in batch:
                try:
                    # Use SDK ping with reduced timeout (implicit in SDK)
                    result, error = self.packet_handler.ping(self.port_handler, motor_id)
                    if result != scs.COMM_SUCCESS:
                        continue
                except Exception as e:
                    logger.debug(f"SDK ping failed for motor {motor_id}: {e}")
                    continue

                # Read model number and firmware deterministically
                try:
                    model_number, fw_major, fw_minor = self._read_model_and_fw(motor_id)
                except OperationalError as e:
                    logger.debug(f"Failed to read model/firmware for motor {motor_id}: {e}")
                    continue

                # Try to identify the motor model; skip if unknown
                try:
                    model_info = self.identify_model(
                        motor_id, model_number=model_number, fw_major=fw_major, fw_minor=fw_minor
                    )
                except (MotorIdentificationError, RuntimeError) as e:
                    logger.debug(f"Failed to identify model for motor {motor_id}: {e}")
                    continue

                if not model_info:
                    logger.debug(f"Skipping unknown model for motor {motor_id} (model_number={model_number})")
                    continue

                discovered[motor_id] = model_info
                logger.info(f"Found motor {motor_id}: {model_info.model} (model_number={model_number})")

        logger.info(f"Scan complete: found {len(discovered)} motors")
        return discovered

    def bulk_read_registers(
        self,
        motor_ids: list[int],
        register_addr: int,
    ) -> dict[int, float]:
        """Read the same register from multiple motors using SyncRead.

        Args:
            motor_ids: List of motor IDs to read from
            register_addr: Register address to read

        Returns:
            Dict mapping motor_id -> register value (signed, as float)
        """
        if not motor_ids:
            return {}

        # Determine register length
        reg_len = 2  # Default
        for reg_name, reg_val in vars(SCS_STS_Registers).items():
            if reg_name.startswith("_"):
                continue
            if not isinstance(reg_val, tuple) or len(reg_val) != 2:
                continue
            reg_addr, length = reg_val
            if reg_addr == register_addr:
                reg_len = length
                break

        # Use SyncRead
        group_sync_read = scs.GroupSyncRead(self.port_handler, self.packet_handler, register_addr, reg_len)

        for motor_id in motor_ids:
            group_sync_read.addParam(motor_id)

        result = group_sync_read.txRxPacket()
        if result != scs.COMM_SUCCESS:
            logger.warning(f"Sync read failed for register {register_addr}, using individual reads")
            # Fallback to base class implementation
            return super().bulk_read_registers(motor_ids, register_addr)

        # Parse results
        results: dict[int, float] = {}
        for motor_id in motor_ids:
            if group_sync_read.isAvailable(motor_id, register_addr, reg_len):
                raw_value = group_sync_read.getData(motor_id, register_addr, reg_len)
                signed_value = self._decode_signed_register(raw_value, register_addr)
                results[motor_id] = float(signed_value)
            else:
                logger.warning(f"No data for motor {motor_id} at register {register_addr}")

        group_sync_read.clearParam()
        return results

    def bulk_write_registers(
        self,
        register_addr: int,
        motor_values: dict[int, float],
    ) -> None:
        """Write the same register to multiple motors using SyncWrite.

        Args:
            register_addr: Register address to write
            motor_values: Dict mapping motor_id -> value to write
        """
        if not motor_values:
            return

        # Determine register length
        reg_len = 2  # Default
        for reg_name, reg_val in vars(SCS_STS_Registers).items():
            if reg_name.startswith("_"):
                continue
            if not isinstance(reg_val, tuple) or len(reg_val) != 2:
                continue
            reg_addr, length = reg_val
            if reg_addr == register_addr:
                reg_len = length
                break

        # Use SyncWrite
        group_sync_write = scs.GroupSyncWrite(self.port_handler, self.packet_handler, register_addr, reg_len)

        for motor_id, value in motor_values.items():
            # Encode with sign-magnitude if applicable
            encoded_value = self._encode_signed_register(value, register_addr)

            # Convert to byte array
            if reg_len == 1:
                data = [encoded_value & 0xFF]
            elif reg_len == 2:
                data = [
                    encoded_value & 0xFF,
                    (encoded_value >> 8) & 0xFF,
                ]
            elif reg_len == 4:
                data = [
                    encoded_value & 0xFF,
                    (encoded_value >> 8) & 0xFF,
                    (encoded_value >> 16) & 0xFF,
                    (encoded_value >> 24) & 0xFF,
                ]
            else:
                raise ValueError(f"Unsupported register length {reg_len}")

            if not group_sync_write.addParam(motor_id, data):
                logger.warning(f"Failed to add motor {motor_id} to sync write")

        result = group_sync_write.txPacket()
        if result != scs.COMM_SUCCESS:
            logger.error(f"Sync write failed for register {register_addr}")
            raise OperationalError(f"Sync write failed: {result}")

        group_sync_write.clearParam()

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
        return self._feetech_write(motor_id, SCS_STS_Registers.TORQUE_ENABLE, 1 if enabled else 0, 1)

    def bulk_set_torque(self, motor_ids: list[int], enabled: bool) -> dict[int, bool]:
        """
        Set torque for multiple motors at once using Sync Write.

        Args:
            motor_ids: List of motor IDs
            enabled: True to enable, False to disable

        Returns:
            Dict mapping motor_id -> success (bool)
        """
        val = 1 if enabled else 0

        # Try to use Sync Write for efficiency
        try:
            # Sync Write command is 0x82 (Standard for SCS/STS)
            # data is just 1 byte per motor
            success = self.packet_handler.syncWrite(
                self.port_handler, SCS_STS_Registers.TORQUE_ENABLE, 1, motor_ids, [[val]] * len(motor_ids)
            )
            # status is usually 0 (COMM_SUCCESS) or 1
            is_ok = success == 0
            return {motor_id: is_ok for motor_id in motor_ids}
        except Exception as e:
            logger.debug(f"Sync write failed for torque: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.write_failed",
                retriable=True,
                interface=self.interface,
            ) from e

    def bulk_set_position(self, positions: dict[int, float], velocity: float | None = None) -> dict[int, bool]:
        """Set target positions for multiple motors efficiently using Sync Write.

        If `velocity` is provided, uses 6-byte sync write to set [Position, Time=0, Velocity].
        Handles motors of different models by using appropriate limits for each.

        Args:
            positions: Dict mapping motor_id -> target position
            velocity: Optional movement velocity (applied to all motors)

        Returns:
            Dict mapping motor_id -> success (bool)
        """
        try:
            addr, _ = SCS_STS_Registers.GOAL_POSITION
            id_list = list(positions.keys())
            data_list = []

            # 44 is Goal Time, usually 0. 46 is Goal Velocity.
            # We write from 42 (Goal Position) to 47 (Goal Velocity) = 6 bytes
            data_len = 2 if velocity is None else 6

            for _motor_id, pos in positions.items():
                p = max(0, int(round(pos)))
                payload = [p & 0xFF, (p >> 8) & 0xFF]  # Little-endian

                if velocity is not None:
                    v = max(0, int(round(velocity)))
                    # Append 2 bytes for time (0) and 2 bytes for velocity
                    payload.extend([0, 0, v & 0xFF, (v >> 8) & 0xFF])

                data_list.append(payload)

            result_code = self.packet_handler.syncWrite(self.port_handler, addr, data_len, id_list, data_list)

            is_ok = result_code == 0  # COMM_SUCCESS is 0
            return {motor_id: is_ok for motor_id in id_list}

        except Exception as e:
            # Identification errors should surface to the caller so they can
            # decide how to handle unknown motors (we re-raise MotorIdentificationError).
            if isinstance(e, (ValueError, MotorIdentificationError)):
                raise
            logger.error(f"Bulk set position failed: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.write_failed",
                retriable=True,
                interface=self.interface,
            ) from e

    def bulk_write_register(
        self,
        motor_values: dict[int, int],
        register_addr: int,
        register_len: int,
    ) -> dict[int, bool]:
        """Write the same register to multiple motors using syncWrite.

        Optimized for batch initialization (operating mode, current limits, etc.).
        Supports both signed and unsigned values - negative values are automatically
        encoded using two's complement.

        Args:
            motor_values: Dict mapping motor_id -> value to write (supports negative values)
            register_addr: Register address to write
            register_len: Register length in bytes (1, 2, or 4)

        Returns:
            Dict mapping motor_id -> success (bool)

        Example:
            # Supports negative values
            driver.bulk_write_register(
                {1: 1000, 2: -100, 3: 500},  # Negative values OK
                register_addr=38,
                register_len=2
            )
        """
        if not self.connected or not motor_values:
            return {mid: False for mid in motor_values.keys()}

        try:
            id_list = list(motor_values.keys())
            data_list = []

            # Encode values as little-endian bytes (handles negative via two's complement)
            for motor_id in id_list:
                value = motor_values[motor_id]
                # Convert to unsigned using two's complement for negative values
                if register_len == 1:
                    unsigned = value & 0xFF
                    payload = [unsigned]
                elif register_len == 2:
                    unsigned = value & 0xFFFF
                    payload = [unsigned & 0xFF, (unsigned >> 8) & 0xFF]
                elif register_len == 4:
                    unsigned = value & 0xFFFFFFFF
                    payload = [
                        unsigned & 0xFF,
                        (unsigned >> 8) & 0xFF,
                        (unsigned >> 16) & 0xFF,
                        (unsigned >> 24) & 0xFF,
                    ]
                else:
                    logger.error(f"Unsupported register length: {register_len}")
                    return {mid: False for mid in motor_values.keys()}
                data_list.append(payload)

            # Use scservo_sdk syncWrite
            result_code = self.packet_handler.syncWrite(
                self.port_handler, register_addr, register_len, id_list, data_list
            )

            is_ok = result_code == 0  # COMM_SUCCESS
            return {motor_id: is_ok for motor_id in id_list}

        except Exception as e:
            logger.error(f"Bulk write register failed: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.write_failed",
                retriable=True,
                interface=self.interface,
            ) from e

    # ========== High-level API: Physical Units ==========
    # These methods accept physical units (mA, rad/s, etc.) and convert internally

    def bulk_write_current_limit(
        self,
        motor_currents: dict[int, float],
        current_unit_ma: float | None = None,
    ) -> dict[int, bool]:
        """Set current limit for multiple motors (high-level API).

        Args:
            motor_currents: Dict mapping motor_id -> current limit in mA
            current_unit_ma: Optional custom unit (default: ~6.5mA/unit for STS3215)

        Returns:
            Dict mapping motor_id -> success (bool)

        Example:
            # Set 500mA limit for motors 1, 2, 3
            driver.bulk_write_current_limit({1: 500, 2: 500, 3: 400})
        """
        from .tables import FeetechUnits, SCS_STS_Registers

        unit = current_unit_ma or FeetechUnits.CURRENT_MA_PER_UNIT
        register_values = {mid: int(current_ma / unit) for mid, current_ma in motor_currents.items()}

        return self.bulk_write_register(
            register_values,
            SCS_STS_Registers.CURRENT_LIMIT[0],
            SCS_STS_Registers.CURRENT_LIMIT[1],
        )

    def bulk_write_velocity_limit(
        self,
        motor_velocities: dict[int, float],
        velocity_unit_rad_s: float | None = None,
    ) -> dict[int, bool]:
        """Set velocity limit for multiple motors (high-level API).

        Args:
            motor_velocities: Dict mapping motor_id -> velocity limit in rad/s
            velocity_unit_rad_s: Optional custom unit (default: 2π/4096 rad/s/unit)

        Returns:
            Dict mapping motor_id -> success (bool)

        Example:
            # Set 1.5 rad/s limit for motors
            driver.bulk_write_velocity_limit({1: 1.5, 2: 1.0, 3: 2.0})
        """
        from .tables import FeetechUnits, SCS_STS_Registers

        unit = velocity_unit_rad_s or FeetechUnits.VELOCITY_RAD_S_PER_UNIT
        register_values = {mid: int(vel_rad_s / unit) for mid, vel_rad_s in motor_velocities.items()}

        return self.bulk_write_register(
            register_values,
            SCS_STS_Registers.VELOCITY_LIMIT[0],
            SCS_STS_Registers.VELOCITY_LIMIT[1],
        )

    def bulk_write_temperature_limit(
        self,
        motor_temperatures: dict[int, float],
    ) -> dict[int, bool]:
        """Set temperature limit for multiple motors (high-level API).

        Args:
            motor_temperatures: Dict mapping motor_id -> temperature limit in °C

        Returns:
            Dict mapping motor_id -> success (bool)

        Example:
            # Set 65°C limit
            driver.bulk_write_temperature_limit({1: 65, 2: 65, 3: 60})
        """
        from .tables import FeetechUnits, SCS_STS_Registers

        # Temperature has 1:1 mapping
        register_values = {
            mid: int(temp_c / FeetechUnits.TEMPERATURE_C_PER_UNIT) for mid, temp_c in motor_temperatures.items()
        }

        return self.bulk_write_register(
            register_values,
            SCS_STS_Registers.TEMPERATURE_LIMIT[0],
            SCS_STS_Registers.TEMPERATURE_LIMIT[1],
        )

    def bulk_write_operating_mode(
        self,
        motor_modes: dict[int, int],
    ) -> dict[int, bool]:
        """Set operating mode for multiple motors (high-level API).

        Args:
            motor_modes: Dict mapping motor_id -> operating mode
                         0: Position servo mode
                         1: Velocity servo mode
                         3: Step servo mode

        Returns:
            Dict mapping motor_id -> success (bool)

        Example:
            # Set position mode
            driver.bulk_write_operating_mode({1: 0, 2: 0, 3: 0})
        """
        from .tables import SCS_STS_Registers

        return self.bulk_write_register(
            motor_modes,
            SCS_STS_Registers.OPERATING_MODE[0],
            SCS_STS_Registers.OPERATING_MODE[1],
        )

    def write_register(self, motor_id: int, address: int, value: int, length: int) -> bool:
        """Write a register value to a motor.

        Args:
            motor_id: Motor ID
            address: Register address
            value: Value to write
            length: Register length in bytes (1, 2, or 4)

        Returns:
            True if write successful
        """
        return self._feetech_write(motor_id, address, value, length)

    def read_register(self, motor_id: int, address: int, length: int) -> int | None:
        """Read a register value from a motor (unified interface).

        Args:
            motor_id: Motor ID
            address: Register address
            length: Register length in bytes (1, 2, or 4)

        Returns:
            Raw register value (unsigned) or None if read failed
        """
        try:
            if length == 1:
                return self._feetech_read_byte(motor_id, address)
            elif length == 2:
                return self._feetech_read_word(motor_id, address)
            elif length == 4:
                return self._feetech_read_dword(motor_id, address)
            else:
                logger.error(f"Unsupported register length: {length}")
                return None
        except Exception as e:
            logger.debug(f"Failed to read register {address} from motor {motor_id}: {e}")
            return None

    # -------------------- Feetech value-level overrides --------------------
    def read_value(
        self, motor_id: int, model_info: MotorModelInfo, address: int, length: int, unit_type: str, signed: bool = False
    ) -> float | None:
        """Read physical value from a register and convert to standard units.

        Feetech uses sign-magnitude encoding for some registers; its low-level
        read_register() and _feetech_read_* helpers already apply that decoding.
        Therefore, we override the base behaviour which assumes two's-complement
        signed interpretation.
        """
        raw = self.read_register(motor_id, address, length)
        if raw is None:
            return None
        # No two's-complement conversion here: low level already returned signed
        conv = self._get_conversion_factor(model_info, unit_type)  # type: ignore[arg-type]
        return float(raw) * conv

    def bulk_read_register(self, motor_ids: list[int], register_addr: int, register_len: int) -> dict[int, int | None]:
        """Protocol-optimized bulk register read using GroupSyncRead.

        Returns mapping motor_id -> raw register value (unsigned) or None if read failed.
        Raises RuntimeError on GroupSyncRead comm failure so callers may fallback.
        """
        if not self.connected or not motor_ids:
            return {mid: None for mid in motor_ids}

        results: dict[int, int | None] = {mid: None for mid in motor_ids}

        group = scs.GroupSyncRead(self.port_handler, self.packet_handler, register_addr, register_len)
        motors_added: list[int] = []
        for mid in motor_ids:
            # Attempt to add all provided ids; caller is responsible for filtering unsupported models
            try:
                if group.addParam(mid):
                    motors_added.append(mid)
            except Exception:
                # If SDK addParam fails, leave as None and continue
                results[mid] = None

        if not motors_added:
            return results

        comm_result = group.txRxPacket()
        if comm_result != scs.COMM_SUCCESS:
            logger.warning(
                f"GroupSyncRead failed for register {register_addr}: {self.packet_handler.getTxRxResult(comm_result)}"
            )
            # Signal failure to callers so they can choose fallback semantics
            raise RuntimeError("GroupSyncRead failed")

        for mid in motors_added:
            try:
                if not group.isAvailable(mid, register_addr, register_len):
                    results[mid] = None
                    continue
                raw = group.getData(mid, register_addr, register_len)
                results[mid] = int(raw)
            except Exception:
                results[mid] = None

        return results

    def bulk_read_values(
        self,
        motor_models: dict[int, MotorModelInfo],
        register_addr: int,
        register_len: int,
        unit_type: str,
        signed: bool = False,
    ) -> dict[int, float | None]:
        """Bulk-read values using the protocol-optimized `bulk_read_register`.

        Converts raw register values into standardized physical units. If the
        underlying register bulk read fails (communication error), falls back to
        sequential `read_value` calls per motor. Missing conversion metadata
        (ValueError) is propagated.
        """
        if not self.connected or not motor_models:
            return {mid: None for mid in motor_models.keys()}

        # Prepare results and list of motors that support this register
        results: dict[int, float | None] = {mid: None for mid in motor_models.keys()}
        supported_ids: list[int] = []
        for mid, model_info in motor_models.items():
            if feetech_supports_register(model_info.model, register_addr):
                supported_ids.append(mid)
            else:
                results[mid] = None

        try:
            raw_values = self.bulk_read_register(supported_ids, register_addr, register_len)

            for mid, raw in raw_values.items():
                if raw is None:
                    results[mid] = None
                    continue
                model_info = motor_models[mid]

                # For signed values, Feetech uses sign-magnitude encoding
                raw_signed = self._decode_signed_register(raw, register_addr) if signed else raw

                conv = self._get_conversion_factor(model_info, unit_type)  # type: ignore[arg-type]
                results[mid] = raw_signed * conv

            return results

        except ValueError:
            # Missing model metadata — propagate
            raise
        except RuntimeError:
            # GroupSyncRead failed — fall back to sequential reads
            logger.debug(f"GroupSyncRead failed for register {register_addr}, falling back to sequential reads")
            for mid, model_info in motor_models.items():
                try:
                    results[mid] = self.read_value(
                        mid, model_info, register_addr, register_len, unit_type, signed=signed
                    )
                except Exception:
                    results[mid] = None
            return results
        except OperationalError:
            # I/O level failure — propagate
            raise
        except Exception as e:
            logger.debug(f"Bulk read values failed for register {register_addr}: {e}, falling back to sequential reads")
            for mid, model_info in motor_models.items():
                try:
                    results[mid] = self.read_value(
                        mid, model_info, register_addr, register_len, unit_type, signed=signed
                    )
                except Exception:
                    results[mid] = None
            return results

    # ========== Position/Velocity/Current (standard units API) ==========
    def read_position(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        """Read motor position in radians using the generic value-level helper."""
        addr, length = SCS_STS_Registers.PRESENT_POSITION
        return self.read_value(motor_id, model_info, addr, length, "position")

    def write_position(
        self, motor_id: int, model_info: MotorModelInfo, position: float, velocity: float | None = None
    ) -> bool:
        """Write target position in radians using `write_value`. Velocity is optional (rad/s)."""

        addr_pos, len_pos = SCS_STS_Registers.GOAL_POSITION
        addr_vel, len_vel = SCS_STS_Registers.GOAL_VELOCITY

        try:
            ok = self.write_value(motor_id, model_info, position, addr_pos, len_pos, "position")
            if not ok:
                return False
            if velocity is not None:
                vel_ok = self.write_value(motor_id, model_info, velocity, addr_vel, len_vel, "velocity")
                return ok and vel_ok
            return True
        except OperationalError:
            raise
        except ValueError:
            # Missing conversion metadata - propagate so caller can fix model_info
            raise
        except Exception as e:
            logger.error(f"Failed to write position for motor {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.write_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
            ) from e

    def bulk_read_position(self, motors: dict[int, MotorModelInfo]) -> dict[int, float | None]:
        return self.bulk_read_values(motors, *SCS_STS_Registers.PRESENT_POSITION, "position")

    def bulk_write_position(
        self,
        positions: dict[int, float],
        motor_info: dict[int, MotorModelInfo],
        velocities: dict[int, float] | None = None,
    ) -> dict[int, bool]:
        """Bulk-write positions (radians) using `bulk_write_values` and then
        (optionally) write velocities for the subset that succeeded.

        This mirrors the Dynamixel implementation: write positions first via the
        value-level helper, then attempt velocity writes only for motors where
        position writes succeeded. Merge results so velocity failures do not
        hide position failures.
        """
        if not self.connected or not positions:
            return {mid: False for mid in positions.keys()}

        addr_pos, len_pos = SCS_STS_Registers.GOAL_POSITION
        addr_vel, len_vel = SCS_STS_Registers.GOAL_VELOCITY

        try:
            results_pos = self.bulk_write_values(positions, motor_info, addr_pos, len_pos, "position")

            # Start with position results
            combined: dict[int, bool] = {mid: bool(ok) for mid, ok in results_pos.items()}

            if velocities:
                # Only attempt velocity writes for motors where position write succeeded
                vel_subset = {mid: v for mid, v in velocities.items() if results_pos.get(mid)}
                if vel_subset:
                    results_vel = self.bulk_write_velocity(vel_subset, motor_info)
                    for mid, pos_ok in results_pos.items():
                        if not pos_ok:
                            combined[mid] = False
                        else:
                            vel_ok = results_vel.get(mid, True)
                            combined[mid] = pos_ok and vel_ok

            # Ensure returned dict includes all requested motors
            for mid in positions.keys():
                combined.setdefault(mid, False)

            return combined

        except ValueError:
            # Missing model metadata — propagate
            raise
        except OperationalError:
            # I/O failure — propagate
            raise
        except Exception as e:
            logger.error(f"Bulk write position failed: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.write_failed", retriable=True, interface=self.interface
            ) from e

    def read_velocity(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        addr, length = SCS_STS_Registers.PRESENT_VELOCITY
        return self.read_value(motor_id, model_info, addr, length, "velocity", signed=True)

    def write_velocity(self, motor_id: int, model_info: MotorModelInfo, velocity: float) -> bool:
        """Write target velocity in rad/s using `write_value`."""
        addr, length = SCS_STS_Registers.GOAL_VELOCITY
        try:
            return self.write_value(motor_id, model_info, velocity, addr, length, "velocity")
        except OperationalError:
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to write velocity for motor {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.write_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
            ) from e

    def bulk_read_velocity(self, motors: dict[int, MotorModelInfo]) -> dict[int, float | None]:
        return self.bulk_read_values(motors, *SCS_STS_Registers.PRESENT_VELOCITY, "velocity", signed=True)

    def bulk_write_velocity(
        self, velocities: dict[int, float], motor_info: dict[int, MotorModelInfo]
    ) -> dict[int, bool]:
        """Bulk-write velocities (rad/s) using the value-level helper."""
        return self.bulk_write_values(velocities, motor_info, *SCS_STS_Registers.GOAL_VELOCITY, "velocity")

    def read_current(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        addr, length = SCS_STS_Registers.PRESENT_CURRENT
        return self.read_value(motor_id, model_info, addr, length, "current", signed=True)

    def write_current(self, motor_id: int, model_info: MotorModelInfo, current_ma: float) -> bool:
        """Write current limit in mA using `write_value`."""
        addr, length = SCS_STS_Registers.CURRENT_LIMIT
        try:
            return self.write_value(motor_id, model_info, current_ma, addr, length, "current")
        except OperationalError:
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to write current for motor {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.write_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
            ) from e

    def bulk_read_current(self, motors: dict[int, MotorModelInfo]) -> dict[int, float | None]:
        return self.bulk_read_values(motors, *SCS_STS_Registers.PRESENT_CURRENT, "current", signed=True)

    def bulk_write_current(self, currents: dict[int, float], motor_info: dict[int, MotorModelInfo]) -> dict[int, bool]:
        # Delegate to bulk_write_values for conversion
        return self.bulk_write_values(
            currents, motor_info, SCS_STS_Registers.CURRENT_LIMIT[0], SCS_STS_Registers.CURRENT_LIMIT[1], "current"
        )

    def read_goal_position(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        addr, length = SCS_STS_Registers.GOAL_POSITION
        return self.read_value(motor_id, model_info, addr, length, "position")

    def read_voltage(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        """Read voltage in volts."""
        # Let underlying errors (ValueError/OperationalError) propagate to the caller
        return self._read_voltage(motor_id, model_info)

    def bulk_read_voltage(self, motors: dict[int, MotorModelInfo]) -> dict[int, float | None]:
        """Read per-motor voltages efficiently using the protocol-optimized bulk reader.

        Reads only the `PRESENT_VOLTAGE` register via `bulk_read_values` to avoid
        constructing full telemetry objects when only voltage is needed.
        """
        return self.bulk_read_values(motors, *SCS_STS_Registers.PRESENT_VOLTAGE, "voltage")

    def read_temperature(self, motor_id: int, model_info: MotorModelInfo) -> float | None:
        """Read temperature in Celsius."""
        try:
            return self._read_temperature(motor_id, model_info)
        except Exception as e:
            logger.debug(f"Failed to read temperature for motor {motor_id}: {e}")
            return None

    def bulk_read_temperature(self, motors: dict[int, MotorModelInfo]) -> dict[int, float | None]:
        """Read per-motor temperatures efficiently using `bulk_read_values` (temperature register only)."""
        return self.bulk_read_values(motors, *SCS_STS_Registers.PRESENT_TEMPERATURE, "temperature")

    # ------------------------------------------------------------------

    def set_velocity(self, motor_id: int, velocity: int, model_info: MotorModelInfo | None = None) -> bool:
        """Set motor target velocity in raw hardware units.

        Args:
            motor_id: Motor ID
            velocity: Target velocity in raw hardware units (int)
            model_info: Optional MotorModelInfo (used to get velocity_max)

        Returns:
            True if command sent successfully
        """
        try:
            velocity_max = self._get_velocity_max(model_info)

            # Clamp to valid range
            velocity = max(-velocity_max, min(velocity_max, int(round(velocity))))

            # Write to goal velocity register
            addr, length = SCS_STS_Registers.GOAL_VELOCITY
            return self._feetech_write(motor_id, addr, velocity, length)

        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to set velocity for motor {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.write_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
            ) from e

    def set_position(self, motor_id: int, position: float, velocity: float | None = None) -> bool:
        """Set motor target position.

        Args:
            motor_id: Motor ID
            position: Target position (counts)
            velocity: Optional movement velocity (counts/s)

        Returns:
            True if command sent successfully
        """

        try:
            # Get model info for position/velocity limits (fail-fast on unknown model)
            model_info = self.identify_model(motor_id)

            position_max = self._get_position_max(model_info)
            velocity_max = self._get_velocity_max(model_info)

            # Multi-Register Write if velocity is provided
            if velocity is not None:
                # Write both position(2b) and velocity(2b).
                p = max(0, min(position_max, int(round(position))))
                v = max(0, min(velocity_max, int(round(velocity))))
                # Write position and velocity via two writes for compatibility
                res1 = self._feetech_write(motor_id, SCS_STS_Registers.GOAL_POSITION, p, 2)
                res2 = self._feetech_write(motor_id, SCS_STS_Registers.GOAL_VELOCITY, v, 2)
                return res1 and res2
            else:
                return self._feetech_write(motor_id, SCS_STS_Registers.GOAL_POSITION, int(round(position)), 2)
        except OperationalError:
            raise
        except Exception as e:
            logger.error(f"Failed to set position for motor {motor_id}: {e}")
            raise OperationalError(
                i18n_key="hardware.motor_device.write_failed",
                retriable=True,
                interface=self.interface,
                motor_id=motor_id,
            ) from e

    # ------------------------------------------------------------------
    # Homing and range (calibration) helpers
    # ------------------------------------------------------------------

    def supports_homing_offset(self, motor_id: int, model_info: MotorModelInfo) -> bool:
        """Return True if the model defines a homing offset register."""
        addr, _ = SCS_STS_Registers.HOMING_OFFSET
        return feetech_supports_register(model_info.model, addr)

    def read_homing_offset(self, motor_id: int, model_info: MotorModelInfo) -> float:
        """Read homing offset; return 0.0 if unsupported."""
        addr, _ = SCS_STS_Registers.HOMING_OFFSET
        if not feetech_supports_register(model_info.model, addr):
            return 0.0
        return float(self._feetech_read_word(motor_id, addr))

    def write_homing_offset(self, motor_id: int, model_info: MotorModelInfo, offset: float | None = None) -> bool:
        """Write homing offset. If unsupported, return False. Raises on communication failures."""
        addr, length = SCS_STS_Registers.HOMING_OFFSET
        if not feetech_supports_register(model_info.model, addr):
            return False

        if offset is None:
            pos = self._read_position(motor_id, model_info)
            if pos is None:
                raise ValueError(f"Cannot determine current position for homing offset on motor {motor_id}")
            offset = float(pos)

        return self._feetech_write(motor_id, addr, int(round(offset)), length)

    def read_range(self, motor_id: int, model_info: MotorModelInfo) -> tuple[float, float]:
        """Read (range_min, range_max). If unsupported, return (0.0, float(encoder_res - 1))."""
        default_res = model_info.encoder_resolution
        fallback = (0.0, float(default_res - 1))

        addr_min, _ = SCS_STS_Registers.RANGE_MIN
        addr_max, _ = SCS_STS_Registers.RANGE_MAX
        if not (
            feetech_supports_register(model_info.model, addr_min)
            and feetech_supports_register(model_info.model, addr_max)
        ):
            return fallback

        try:
            rmin = self._feetech_read_word(motor_id, addr_min)
            rmax = self._feetech_read_word(motor_id, addr_max)
            return (float(rmin), float(rmax))
        except Exception as e:
            logger.warning(f"Failed to read range for motor {motor_id}: {e}")
            return fallback

    def write_range(self, motor_id: int, model_info: MotorModelInfo, range_min: float, range_max: float) -> bool:
        """Write range limits to motor. Returns False if unsupported or failed."""
        addr_min, len_min = SCS_STS_Registers.RANGE_MIN
        addr_max, len_max = SCS_STS_Registers.RANGE_MAX
        if not (
            feetech_supports_register(model_info.model, addr_min)
            and feetech_supports_register(model_info.model, addr_max)
        ):
            return False

        try:
            ok1 = self._feetech_write(motor_id, addr_min, int(round(range_min)), len_min)
            ok2 = self._feetech_write(motor_id, addr_max, int(round(range_max)), len_max)
            return ok1 and ok2
        except Exception as e:
            logger.error(f"Failed to write range for motor {motor_id}: {e}")
            return False
