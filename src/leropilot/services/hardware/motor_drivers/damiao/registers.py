"""Damiao register access utilities.

Provides a synchronous `DamiaoRegister` helper which wraps lower-level
parameter read/write operations from :class:`DamiaoCAN_Driver` and exposes
convenience helpers for commonly used registers (KP, KI, control mode,
PMAX/VMAX/TMAX, etc.).

Notes:
- This module operates on 4-byte Damiao parameter semantics where parameter
  queries (CAN CMD 0x33) and writes (0x55) return/accept 4-byte values in
  bytes 4..7 of the CAN payload (little-endian).
- Read/write methods raise :class:`leropilot.exceptions.OperationalError` on
  bus-level errors or timeouts.
"""

from __future__ import annotations

import struct

from leropilot.exceptions import OperationalError

from .drivers import DamiaoCAN_Driver
from .tables import DamiaoRegisters


class DamiaoRegister:
    """Helper for reading and writing Damiao motor parameter registers.

    Args:
        driver: An instance of :class:`DamiaoCAN_Driver` used to access the
            motor parameter read/write APIs.

    Behavior:
    - All methods are synchronous and will raise :class:`OperationalError`
      on failures (no response or negative acknowledgement).
    - `motor_id` must be a tuple `(send_id, recv_id)` as expected by the
      Damiao driver (no automatic validation is performed).
    """

    def __init__(self, driver: DamiaoCAN_Driver) -> None:
        self.driver = driver
        # No local read-only cache; use DamiaoRegisters.get_register_info() on demand.

    def is_read_only(self, param_addr: int) -> bool:
        """Return True if `param_addr` is read-only.

        Falls back to conservative True for unknown addresses.
        """
        try:
            _, is_rw, _ = DamiaoRegisters.get_register_info(param_addr)
            return not is_rw
        except Exception:
            # Unknown register -> treat as read-only conservatively
            return True

    def read_uint32(self, motor_id: tuple[int, int], param_addr: int) -> int:
        """Read an unsigned 32-bit integer from parameter `param_addr` (little-endian)."""
        b = self.driver.read_parameter(motor_id, param_addr)
        return int.from_bytes(b, byteorder="little", signed=False)

    def read_float32(self, motor_id: tuple[int, int], param_addr: int) -> float:
        """Read a 32-bit IEEE754 float from parameter `param_addr` (little-endian)."""
        b = self.driver.read_parameter(motor_id, param_addr)
        return struct.unpack("<f", b)[0]

    def write_uint32(self, motor_id: tuple[int, int], param_addr: int, value: int) -> None:
        """Write an unsigned 32-bit integer to `param_addr` (little-endian)."""
        if self.is_read_only(param_addr):
            raise OperationalError(i18n_key="hardware.motor_device.write_ro_register", retriable=False)
        b = int(value).to_bytes(4, byteorder="little", signed=False)
        self.driver.write_parameter(motor_id, param_addr, b)

    def write_float32(self, motor_id: tuple[int, int], param_addr: int, value: float) -> None:
        """Write a 32-bit IEEE754 float to `param_addr` (little-endian)."""
        if self.is_read_only(param_addr):
            raise OperationalError(i18n_key="hardware.motor_device.write_ro_register", retriable=False)
        b = struct.pack("<f", float(value))
        self.driver.write_parameter(motor_id, param_addr, b)

    def read_number(self, motor_id: tuple[int, int], param_addr: int, max_age: float | None = None) -> float:
        """Read a parameter and return it as a Python float.

        The method inspects `DamiaoRegisters` to determine whether the parameter
        is stored as a 32-bit IEEE754 float or an unsigned 32-bit integer and
        converts accordingly.
        """
        try:
            b = self.driver.read_parameter(motor_id, param_addr, max_age=max_age)
            if len(b) < 4:
                raise OperationalError(
                    i18n_key="hardware.motor_device.malformed_response",
                    retriable=True,
                    motor_id=motor_id,
                    param_addr=param_addr,
                )

            _, _, is_float = DamiaoRegisters.get_register_info(param_addr)
            if is_float:
                return struct.unpack("<f", b)[0]
            return float(int.from_bytes(b, byteorder="little", signed=False))
        except OperationalError:
            raise
        except Exception as e:
            raise OperationalError(
                i18n_key="hardware.motor_device.read_param_failed",
                retriable=True,
                motor_id=motor_id,
                param_addr=param_addr,
            ) from e

    def write_number(self, motor_id: tuple[int, int], param_addr: int, value: float) -> None:
        """Write `value` (as float) to `param_addr`.

        The register type (float vs integer) is looked up from `DamiaoRegisters`.
        """
        # Enforce read-only checks
        if self.is_read_only(param_addr):
            raise OperationalError(i18n_key="hardware.motor_device.write_ro_register", retriable=False)

        try:
            _, is_rw, is_float = DamiaoRegisters.get_register_info(param_addr)
            if not is_rw:
                raise OperationalError(i18n_key="hardware.motor_device.write_ro_register", retriable=False)

            if is_float:
                b = struct.pack("<f", float(value))
            else:
                b = int(value).to_bytes(4, byteorder="little", signed=False)

            self.driver.write_parameter(motor_id, param_addr, b)
        except OperationalError:
            raise
        except Exception as e:
            raise OperationalError(
                i18n_key="hardware.motor_device.write_param_failed",
                retriable=True,
                motor_id=motor_id,
                param_addr=param_addr,
            ) from e

    def bulk_read_numbers(
        self, requests: list[tuple[tuple[int, int], int]], max_age: float | None = None
    ) -> dict[tuple[tuple[int, int], int], float]:
        """Bulk read multiple parameters and return converted float values.

        Args:
            requests: list of (motor_id, param_addr) tuples
            max_age: optional max_age passed to underlying bulk read

        Returns:
            Dict mapping (motor_id, param_addr) -> float
        """
        # Ask driver to perform bulk parameter reads (may populate cache)
        self.driver.bulk_read_parameters(requests, max_age=max_age)

        results: dict[tuple[tuple[int, int], int], float] = {}
        for motor_id, param_addr in requests:
            results[(motor_id, param_addr)] = self.read_number(motor_id, param_addr, max_age=None)
        return results

    def bulk_write_numbers(self, writes: list[tuple[tuple[int, int], int, float]], base_timeout: float = 0.1) -> None:
        """Bulk write multiple parameters efficiently.

        Args:
            writes: list of (motor_id, param_addr, value)
            base_timeout: timeout passed to underlying bulk write
        """
        # Preflight: verify all destinations are writable and prepare bytes
        items: list[tuple[tuple[int, int], int, bytes]] = []
        for motor_id, param_addr, value in writes:
            if self.is_read_only(param_addr):
                raise OperationalError(i18n_key="hardware.motor_device.write_ro_register", retriable=False)
            _, is_rw, is_float = DamiaoRegisters.get_register_info(param_addr)
            if not is_rw:
                raise OperationalError(i18n_key="hardware.motor_device.write_ro_register", retriable=False)
            if is_float:
                b = struct.pack("<f", float(value))
            else:
                b = int(value).to_bytes(4, byteorder="little", signed=False)
            items.append((motor_id, param_addr, b))

        # Delegate to driver bulk write (sends all frames then waits for confirmations)
        self.driver.bulk_write_parameters(items, base_timeout=base_timeout)

    # Convenience helpers for common registers (addresses from tables/Datasheet)
    def get_control_mode(self, motor_id: tuple[int, int]) -> int:
        """
        Return the control mode as an integer.
        1=MIT, 2=Position and Velocity, 3=Velocity, 4=Torque and Position
        """
        return self.read_uint32(motor_id, DamiaoRegisters.CTRL_MODE[0])

    def set_control_mode(self, motor_id: tuple[int, int], mode: int) -> None:
        """Set the control mode.
        1=MIT, 2=Position and Velocity, 3=Velocity, 4=Torque and Position
        """
        self.write_uint32(motor_id, DamiaoRegisters.CTRL_MODE[0], int(mode))

    def get_max_velocity(self, motor_id: tuple[int, int]) -> float:
        return self.read_float32(motor_id, DamiaoRegisters.MAX_SPD[0])

    def set_max_velocity(self, motor_id: tuple[int, int], velocity: float) -> None:
        self.write_float32(motor_id, DamiaoRegisters.MAX_SPD[0], float(velocity))

    def get_pmax_vmax_tmax(self, motor_id: tuple[int, int]) -> tuple[float, float, float]:
        # read all three in a bulk read for efficiency
        self.driver.bulk_read_parameters(
            [
                (motor_id, DamiaoRegisters.PMAX[0]),
                (motor_id, DamiaoRegisters.VMAX[0]),
                (motor_id, DamiaoRegisters.TMAX[0]),
            ]
        )
        # then parse individually
        p = self.read_float32(motor_id, DamiaoRegisters.PMAX[0])
        v = self.read_float32(motor_id, DamiaoRegisters.VMAX[0])
        t = self.read_float32(motor_id, DamiaoRegisters.TMAX[0])
        return (p, v, t)

    def set_pmax_vmax_tmax(self, motor_id: tuple[int, int], p: float, v: float, t: float) -> None:
        for addr in (DamiaoRegisters.PMAX[0], DamiaoRegisters.VMAX[0], DamiaoRegisters.TMAX[0]):
            if self.is_read_only(addr):
                raise OperationalError(i18n_key="hardware.motor_device.write_ro_register", retriable=False)

        self.write_float32(motor_id, DamiaoRegisters.PMAX[0], float(p))
        self.write_float32(motor_id, DamiaoRegisters.VMAX[0], float(v))
        self.write_float32(motor_id, DamiaoRegisters.TMAX[0], float(t))

    def get_kp_ki_kd(self, motor_id: tuple[int, int]) -> tuple[float, float, float, float]:
        # read all four in a bulk read for efficiency
        self.driver.bulk_read_parameters(
            [
                (motor_id, DamiaoRegisters.KP_ASR[0]),
                (motor_id, DamiaoRegisters.KI_ASR[0]),
                (motor_id, DamiaoRegisters.KP_APR[0]),
                (motor_id, DamiaoRegisters.KI_APR[0]),
            ]
        )
        # then parse individually
        return (
            self.read_float32(motor_id, DamiaoRegisters.KP_ASR[0]),
            self.read_float32(motor_id, DamiaoRegisters.KI_ASR[0]),
            self.read_float32(motor_id, DamiaoRegisters.KP_APR[0]),
            self.read_float32(motor_id, DamiaoRegisters.KI_APR[0]),
        )

    def set_kp_ki(
        self,
        motor_id: tuple[int, int],
        kp_asr: float | None = None,
        ki_asr: float | None = None,
        kp_apr: float | None = None,
        ki_apr: float | None = None,
    ) -> None:
        # enforce read-only checks
        for addr in (
            DamiaoRegisters.KP_ASR[0],
            DamiaoRegisters.KI_ASR[0],
            DamiaoRegisters.KP_APR[0],
            DamiaoRegisters.KI_APR[0],
        ):
            if self.is_read_only(addr):
                raise OperationalError(i18n_key="hardware.motor_device.write_ro_register", retriable=False)

        if kp_asr is not None:
            self.write_float32(motor_id, DamiaoRegisters.KP_ASR[0], float(kp_asr))
        if ki_asr is not None:
            self.write_float32(motor_id, DamiaoRegisters.KI_ASR[0], float(ki_asr))
        if kp_apr is not None:
            self.write_float32(motor_id, DamiaoRegisters.KP_APR[0], float(kp_apr))
        if ki_apr is not None:
            self.write_float32(motor_id, DamiaoRegisters.KI_APR[0], float(ki_apr))

    def get_current_position(self, motor_id: tuple[int, int], max_age: float = 0.1) -> float:
        """Return the current motor position in radians."""
        return self.read_number(motor_id, DamiaoRegisters.P_M[0], max_age=max_age)

    def bulk_get_current_position(
        self, motor_ids: list[tuple[int, int]], max_age: float = 0.1
    ) -> dict[tuple[int, int], float]:
        """Return the current motor positions in radians for multiple motors."""
        # prepare bulk read requests
        requests = [(mid, DamiaoRegisters.P_M[0]) for mid in motor_ids]
        self.driver.bulk_read_parameters(requests, max_age=max_age)

        results : dict[tuple[int, int], float] = {}
        for mid in motor_ids:
            pos = self.read_number(mid, DamiaoRegisters.P_M[0])
            results[mid] = pos
        return results

    def get_current_state(self, motor_id: tuple[int, int], max_age: float = 0.1) -> tuple[float, float, float]:
        """Return the current motor state as a dict with keys:
        - position (rad)
        - temp_mos (°C)
        - temp_rotor (°C)
        """
        # prepare bulk read requests
        requests = [
            (motor_id, DamiaoRegisters.XOUT[0]),
            (motor_id, DamiaoRegisters.TPCB[0]),
            (motor_id, DamiaoRegisters.TMTR[0]),
        ]
        self.driver.bulk_read_parameters(requests, max_age=max_age)

        position = self.read_float32(motor_id, DamiaoRegisters.XOUT[0])
        temp_mos = self.read_float32(motor_id, DamiaoRegisters.TPCB[0])
        temp_rotor = self.read_float32(motor_id, DamiaoRegisters.TMTR[0])
        return (position, temp_mos, temp_rotor)

    def bulk_get_current_state(
        self, motor_ids: list[tuple[int, int]], max_age: float = 0.1
    ) -> dict[tuple[int, int], tuple[float, float, float]]:
        """Return the current motor states for multiple motors.

        Each state is a tuple:
        - position (rad)
        - temp_mos (°C)
        - temp_rotor (°C)
        """
        # prepare bulk read requests
        requests: list[tuple[tuple[int, int], int]] = []
        for mid in motor_ids:
            requests.extend(
                [
                    (mid, DamiaoRegisters.XOUT[0]),
                    (mid, DamiaoRegisters.TPCB[0]),
                    (mid, DamiaoRegisters.TMTR[0]),
                ]
            )
        self.driver.bulk_read_parameters(requests, max_age=max_age)

        results: dict[tuple[int, int], tuple[float, float, float]] = {}
        for mid in motor_ids:
            position = self.read_float32(mid, DamiaoRegisters.XOUT[0])
            temp_mos = self.read_float32(mid, DamiaoRegisters.TPCB[0])
            temp_rotor = self.read_float32(mid, DamiaoRegisters.TMTR[0])
            results[mid] = (position, temp_mos, temp_rotor)
        return results
