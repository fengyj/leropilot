"""
Robot verification service.

This module handles verifying robot configurations against actual hardware
and checking robot status.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from leropilot.services.hardware.motor_buses.motor_bus import MotorBus

from leropilot.exceptions import ResourceConflictError, ValidationError
from leropilot.models.hardware import (
    DeviceStatus,
    MotorBusDefinition,
    MotorModelInfo,
    Robot,
)

logger = logging.getLogger(__name__)


class RobotVerificationService:
    """Service for verifying robot configurations against actual hardware."""

    def __init__(self) -> None:
        pass

    def verify_motor_bus(self, bus: "MotorBus", motorbus_def: MotorBusDefinition) -> bool:
        """Verify whether a MotorBus instance matches a given MotorBusDefinition.

        Checks performed:
          - bus class name equals motorbus_def.type
          - number of motors matches
          - for each motor in the definition, an entry exists on the bus with matching
            id, brand, model and (optionally) variant. If a definition's variant is None
            the variant is not compared.
        """
        try:
            # Type check on class name
            if bus.__class__.__name__ != motorbus_def.type:
                return False

            # Build definition dict keyed by the raw id values (coerce list ids to tuples for hashability)
            req_by_id: dict[object, Any] = {}
            # motorbus_def.motors is expected to be a dict[name -> RobotMotorDefinition]
            for req in motorbus_def.motors.values() if isinstance(motorbus_def.motors, dict) else motorbus_def.motors:
                # Use the motor definition's canonical key form (int or tuple).
                rid = getattr(req, "key", req.id)
                req_key = rid if not isinstance(rid, list) else tuple(rid)
                # Duplicate definition ids are ambiguous
                if req_key in req_by_id:
                    return False
                req_by_id[req_key] = req

            from typing import cast

            from leropilot.services.hardware.motor_drivers.base import BaseMotorDriver

            # Build bus dict keyed by the raw motor keys (coerce list keys to tuples)
            bus_by_id: dict[object, tuple[BaseMotorDriver[Any], MotorModelInfo | None]] = {}
            for k, entry in bus.motors.items():
                # Normalize list keys to tuples
                key_norm = tuple(k) if isinstance(k, list) else k
                if not entry:
                    return False
                _, minfo = entry
                if minfo is None:
                    return False
                # Duplicate keys are ambiguous
                if key_norm in bus_by_id:
                    return False
                bus_by_id[key_norm] = cast(tuple[BaseMotorDriver[Any], MotorModelInfo | None], entry)

            # Counts must match
            if len(bus_by_id) != len(req_by_id):
                return False

            # Compare each required motor against discovered motor info using exact-key matching
            for rk, req in req_by_id.items():
                req_key = cast(int | tuple[int, int], rk)
                entry_val = bus_by_id.get(req_key)
                if entry_val is None:
                    return False
                driver, minfo = cast(tuple[BaseMotorDriver[Any], MotorModelInfo | None], entry_val)
                if minfo is None:
                    return False

                # Brand check (case-insensitive)
                if str(minfo.brand.value).lower() != str(req.brand).lower():
                    return False

                # Model check (case-insensitive exact)
                if (getattr(minfo, "model", "") or "").lower() != str(req.model).lower():
                    return False

                # Variant check only when requirement specifies one
                if req.variant is not None:
                    if (getattr(minfo, "variant", "") or "").lower() != str(req.variant).lower():
                        return False

            return True
        except Exception:
            return False

    def check_robot_status(
        self, robot: Robot, discovered: list[tuple["MotorBus", str | None, str | None]]
    ) -> tuple[DeviceStatus, bool]:
        """Compare a persisted `robot` against `discovered` motorbuses and return
        the computed DeviceStatus and a boolean indicating whether the robot should
        be removed (transient and offline).

        Returns:
            (status, should_remove)
        """
        try:
            all_connections_ok = True
            any_mismatch = False

            # If robot has no motor_bus_connections, consider it offline/invalid
            if not robot.motor_bus_connections:
                return DeviceStatus.OFFLINE, robot.is_transient

            # For each connection, try to find a matching discovered bus
            for conn_key, conn in (robot.motor_bus_connections or {}).items():
                conn_found = False
                matched_bus = None
                for bus, serial_num, _mf in discovered:
                    # If conn has serial_number, prefer matching by serial
                    if conn.serial_number:
                        if conn.serial_number == serial_num:
                            conn_found = True
                            matched_bus = bus
                            conn.interface = getattr(bus, "interface", None)
                            break
                    else:
                        # Fall back to matching by interface (runtime info)
                        if conn.interface and getattr(bus, "interface", None) == conn.interface:
                            conn_found = True
                            matched_bus = bus
                            break

                if not conn_found:
                    # Could not find required motorbus -> offline
                    all_connections_ok = False
                    conn.interface = None
                    break

                # If we have a motorbus definition for this connection, verify it
                mb_def = self._get_motor_bus_definition(robot, conn_key)

                if mb_def is not None:
                    assert matched_bus is not None
                    ok = self.verify_motor_bus(matched_bus, mb_def)
                    if not ok:
                        any_mismatch = True

            # Apply status logic
            if not all_connections_ok:
                return DeviceStatus.OFFLINE, robot.is_transient
            if any_mismatch:
                return DeviceStatus.INVALID, False
            return DeviceStatus.AVAILABLE, False
        except Exception:
            # On unexpected error, degrade to OFFLINE and keep robot if not transient
            return DeviceStatus.OFFLINE, robot.is_transient

    def verify_robot(self, robot: Robot) -> bool:
        """Verify a persisted `robot` against the actual motorbuses present.

        Constructs MotorBus objects for each `RobotMotorBusConnection` in
        `robot.motor_bus_connections`, runs `scan_motors()` on each bus to
        discover attached motors, and then delegates to `check_robot_status`
        to compute the overall status.

        Raises:
            ResourceConflictError: when verification fails resulting in OFFLINE or INVALID status.
            ValidationError: when a required interface is missing or when the motorbus type cannot be resolved.

        Returns:
            True on successful verification (AVAILABLE).
        """
        from leropilot.services.hardware.motor_buses.motor_bus import MotorBus

        if not robot.motor_bus_connections:
            raise ValueError("Robot has no motor bus connections to verify")

        discovered: list[tuple[MotorBus, str | None, str | None]] = []
        buses_to_close: list[MotorBus] = []

        try:
            for conn_key, conn in (robot.motor_bus_connections or {}).items():
                # Interface must be present to construct the runtime motorbus
                if not conn.interface:
                    raise ValidationError("hardware.robot_device.missing_interface", id=conn_key)

                # Resolve bus class
                try:
                    cls = MotorBus.resolve_bus_class(conn.motor_bus_type)
                except Exception as e:
                    raise ValidationError("hardware.robot_device.unknown_bus_type", bus_type=conn.motor_bus_type) from e

                # Create and probe the motorbus
                try:
                    bus = MotorBus.create(cls, conn.interface, conn.baudrate or 0)
                    if not bus.connect():
                        try:
                            bus.disconnect()
                        except Exception:
                            pass
                        raise ValidationError("hardware.robot_device.connect_failed", interface=conn.interface)

                    buses_to_close.append(bus)
                    # scan_motors should populate bus.motors
                    bus.scan_motors()
                    discovered.append((bus, conn.serial_number, None))
                except ValueError:
                    # pass through ValueError for better user messages
                    raise
                except Exception as e:
                    try:
                        bus.disconnect()
                    except Exception:
                        pass
                    raise RuntimeError(f"Error probing motorbus '{conn_key}': {e}") from e

            # Use the helper to check computed status
            status, _should_remove = self.check_robot_status(robot, discovered)

            if status == DeviceStatus.OFFLINE:
                raise ResourceConflictError("hardware.robot_device.offline")
            if status == DeviceStatus.INVALID:
                raise ResourceConflictError("hardware.robot_device.invalid_mismatch")

            # AVAILABLE -> verification passed
            return True
        finally:
            # Ensure buses are disconnected
            for b in buses_to_close:
                try:
                    b.disconnect()
                except Exception:
                    pass

    def _get_motor_bus_definition(self, robot: Robot, conn_key: str) -> MotorBusDefinition | None:
        """Get the motor bus definition for a specific connection key."""
        from .spec_service import RobotSpecService

        defn = robot.definition
        if isinstance(defn, str):
            spec = RobotSpecService()
            defn = spec.get_robot_definition(defn)
            if defn is None:
                return None

        if defn and getattr(defn, "motor_buses", None):
            try:
                return defn.motor_buses.get(conn_key)
            except Exception:
                return None
        return None
