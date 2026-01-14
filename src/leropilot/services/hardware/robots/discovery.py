"""
Robot discovery service.

This module handles discovering motor buses and building pending robot devices
from discovered hardware.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from leropilot.services.hardware.motor_buses.motor_bus import MotorBus

from leropilot.models.hardware import (
    DeviceStatus,
    MotorBusDefinition,
    Robot,
    RobotDefinition,
    RobotMotorBusConnection,
    RobotMotorDefinition,
)
from leropilot.services.hardware.platform_adapter import PlatformAdapter
from leropilot.services.i18n import get_i18n_service

logger = logging.getLogger(__name__)


class MotorBusDiscovery:
    """Service for discovering motor buses and attached motors."""

    def __init__(self) -> None:
        self._adapter = PlatformAdapter()

    def discover_motor_buses(
        self, filters: list[tuple[str, int | None]] | None = None
    ) -> list[tuple["MotorBus", str | None, str | None]]:
        """Discover motor bus instances that have motors attached.

        The returned ``bus`` objects are lightweight proxies (disconnected) that
        expose `interface`, `baud_rate` and `motors` attributes. Implementations
        should not assume the underlying hardware connection remains open.

        Args:
            filters: Optional list of (motorbus_type, baudrate) pairs to restrict discovery.
                     If provided, only the specified motorbus types / baudrates will be tried.
        Returns:
            List[tuple]: list of tuples (bus_proxy, serial_number, manufacturer) for each
                         motorbus where motors were successfully found. `serial_number` and
                         `manufacturer` may be None when not available.
        """
        from leropilot.services.hardware.motor_buses.motor_bus import MotorBus

        # Build allowed map from filters: class -> set(baudrates)
        allowed: dict[type, set[int] | None] = {}
        if filters:
            for t, baud in filters:
                try:
                    cls = MotorBus.resolve_bus_class(t)
                except Exception:
                    logger.debug(f"Unknown motorbus type in filters: {t}")
                    continue
                # Ensure an entry exists and is a set before adding
                if cls not in allowed:
                    allowed[cls] = set()
                if baud is not None:
                    vals = allowed.get(cls)
                    if vals is None:
                        allowed[cls] = set()
                        vals = allowed[cls]
                    # mypy can't always infer that vals is a set; assert its type
                    if isinstance(vals, set):
                        vals.add(int(baud))
                    else:
                        allowed[cls] = {int(baud)}
                else:
                    allowed[cls] = None

        results: list = []

        # Discover serial and CAN buses
        results.extend(self._discover_serial_buses(allowed, filters))
        results.extend(self._discover_can_buses(allowed, filters))

        return results

    def _get_allowed_baudrates_for(
        self,
        cls: type,
        allowed: dict[type, set[int] | None],
        filters: list | None,
    ) -> list[int] | None:
        """Get allowed baudrates for a given motor bus class."""
        from typing import cast

        # `cls` is assumed to be a MotorBus class with `supported_baudrates`.
        # Use a runtime Any cast to help mypy understand it has the attribute.
        if not filters:
            return cast(Any, cls).supported_baudrates()  # type: ignore[return-value]
        if cls not in allowed:
            return None
        vals = allowed[cls]
        if vals is None or len(vals) == 0:
            return cast(Any, cls).supported_baudrates()  # type: ignore[return-value]
        # preserve class ordering but filter to allowed set
        return [b for b in cast(Any, cls).supported_baudrates() if b in vals]

    def _discover_serial_buses(
        self, allowed: dict[type, set[int] | None], filters: list | None
    ) -> list[tuple["MotorBus", str | None, str | None]]:
        """Discover serial-based motor buses."""
        from leropilot.services.hardware.motor_buses.motor_bus import MotorBus

        results: list = []
        serial_ports = self._adapter.discover_serial_ports()

        # If filters provided and none of the filtered classes are serial types, skip serial
        if filters:
            serial_classes = set(MotorBus.serial_types())
            if not any(cls in serial_classes for cls in allowed.keys()):
                serial_ports = []

        for port in serial_ports:
            port_name = port.port
            serial_number = port.serial_number
            manufacturer = port.manufacturer

            for cls in MotorBus.serial_types():
                baud_candidates = self._get_allowed_baudrates_for(cls, allowed, filters)
                if baud_candidates is None:
                    continue

                bus_proxy = self._try_probe_bus(cls, port_name, baud_candidates, serial_number, manufacturer)
                if bus_proxy:
                    results.append(bus_proxy)
                    break  # Do not try other serial motorbus types for this port if one succeeded

        return results

    def _discover_can_buses(
        self, allowed: dict[type, set[int] | None], filters: list | None
    ) -> list[tuple["MotorBus", str | None, str | None]]:
        """Discover CAN-based motor buses."""
        from leropilot.services.hardware.motor_buses.motor_bus import MotorBus

        results: list = []
        can_interfaces = self._adapter.discover_can_interfaces()

        # If filters provided and none of the filtered classes are CAN types, skip CAN
        if filters:
            can_classes = set(MotorBus.can_types())
            if not any(cls in can_classes for cls in allowed.keys()):
                can_interfaces = []

        for interface in can_interfaces:
            if_name = interface.interface
            serial_number = interface.serial_number
            manufacturer = interface.manufacturer

            for cls in MotorBus.can_types():
                bitrate_candidates = self._get_allowed_baudrates_for(cls, allowed, filters)
                if bitrate_candidates is None:
                    continue

                bus_proxy = self._try_probe_bus(cls, if_name, bitrate_candidates, serial_number, manufacturer)
                if bus_proxy:
                    results.append(bus_proxy)
                    break

        return results

    def _try_probe_bus(
        self, cls: type, interface: str, baudrates: list[int], serial_number: str | None, manufacturer: str | None
    ) -> tuple["MotorBus", str | None, str | None] | None:
        """Try to probe a motor bus at different baudrates."""
        from leropilot.services.hardware.motor_buses.motor_bus import MotorBus

        for baud in baudrates:
            bus = None
            try:
                bus = MotorBus.create(cls, interface, baud)
                if not bus.connect():
                    try:
                        bus.disconnect()
                    except Exception:
                        pass
                    continue

                motors = bus.scan_motors()
                if motors:
                    logger.info(f"Found motors on {interface} using {cls.__name__} @ {baud}")
                    # Snapshot motors and disconnect to avoid leaving hardware open
                    motors_snapshot = dict(getattr(bus, "motors", {}))
                    try:
                        bus.disconnect()
                    except Exception:
                        pass

                    # Create lightweight proxy class so callers can inspect .motors, .interface, .baud_rate
                    BusProxy = type(cls.__name__, (), {})
                    bus_proxy = BusProxy()
                    bus_proxy.interface = interface
                    bus_proxy.baud_rate = baud
                    bus_proxy.motors = motors_snapshot
                    return (bus_proxy, serial_number, manufacturer)  # type: ignore[return-value]
                else:
                    try:
                        bus.disconnect()
                    except Exception:
                        pass

            except Exception as e:
                logger.debug(f"Error probing {cls} on {interface} @ {baud}: {e}")
                if bus is not None:
                    try:
                        bus.disconnect()
                    except Exception:
                        pass

        return None


class PendingDeviceBuilder:
    """Service for building pending robot devices from discovered motor buses."""

    def __init__(self) -> None:
        self._i18n = get_i18n_service()

    def build_pending_robots(
        self, discovered_buses: list[tuple["MotorBus", str | None, str | None]], lang: str = "en"
    ) -> list[Robot]:
        """Build a list of pending Robot objects from discovered motor buses.

        Args:
            discovered_buses: List of (bus_proxy, serial_number, manufacturer) tuples
            lang: Language code for localized names/descriptions

        Returns:
            List of Robot objects representing discovered devices
        """
        pending: list[Robot] = []

        for bus, serial_number, _manufacturer in discovered_buses:
            robot = self._build_robot_from_bus(bus, serial_number, lang)
            pending.append(robot)

        return pending

    def _build_robot_from_bus(self, bus: "MotorBus", serial_number: str | None, lang: str) -> Robot:
        """Build a single Robot object from a motor bus."""
        robot_id = uuid4().hex

        # Localized device name
        name = self._i18n.translate(
            "hardware.robot_device.unknown_device_on", lang=lang, port=bus.interface
        ) or f"Unknown device on {bus.interface}"

        status = DeviceStatus.AVAILABLE
        is_transient = not bool(serial_number)

        # MotorBus connection entry
        baud_raw = getattr(bus, "baud_rate", None)
        baud_val = int(baud_raw) if baud_raw is not None else 0
        conn = RobotMotorBusConnection(
            motor_bus_type=bus.__class__.__name__,
            interface=bus.interface,
            baudrate=baud_val,
            serial_number=serial_number,
        )
        motor_bus_connections = {"motorbus": conn}

        # Build motor definitions and robot definition
        motor_defs, type_counts = self._build_motor_definitions(bus)
        descriptions = self._build_descriptions(type_counts)
        display_name = self._build_display_name()

        mb_def = MotorBusDefinition(
            type=bus.__class__.__name__,
            motors=motor_defs,
            baud_rate=getattr(bus, "baud_rate", None),
            interface_type=None,
        )

        rdef = RobotDefinition(
            id="",
            lerobot_name=None,
            display_name=display_name,
            description=descriptions,
            support_version_from=None,
            support_version_end=None,
            urdf=None,
            motor_buses={"motorbus": mb_def},
        )

        robot = Robot(
            id=robot_id,
            name=name,
            status=status,
            manufacturer=None,
            labels={},
            created_at=datetime.now(),
            is_transient=is_transient,
            definition=rdef,
            calibration_settings={},
            custom_protection_settings={},
            motor_bus_connections=motor_bus_connections,
        )

        return robot

    def _build_motor_definitions(self, bus: "MotorBus") -> tuple[dict[str, RobotMotorDefinition], dict[str, int]]:
        """Build motor definitions and type counts from a bus."""
        motor_defs: dict[str, RobotMotorDefinition] = {}
        type_counts: dict[str, int] = {}
        idx = 1

        for motor_key, entry in bus.motors.items():
            _, minfo = entry  # type: ignore[assignment]
            name_idx = str(idx)
            idx += 1

            if minfo is not None and minfo.brand is not None:
                brand = str(minfo.brand.value)
            else:
                brand = minfo.model if minfo else ""

            model = minfo.model if (minfo and getattr(minfo, "model", None)) else ""
            variant = minfo.variant if (minfo and getattr(minfo, "variant", None)) else None

            motor_def = RobotMotorDefinition(
                name=name_idx,
                id=motor_key,
                brand=str(brand),
                model=str(model),
                variant=variant,
                need_calibration=True,
                drive_mode=0,
            )
            motor_defs[name_idx] = motor_def

            # Canonical type key for grouping (variant > model > unknown)
            typ_key = variant or model or "unknown"
            type_counts[typ_key] = type_counts.get(typ_key, 0) + 1

        return motor_defs, type_counts

    def _build_descriptions(self, type_counts: dict[str, int]) -> dict[str, str]:
        """Build localized description strings from motor type counts."""
        templates = self._i18n.get_block("hardware.robot_definition.motor_count_templates")
        descriptions: dict[str, str] = {}

        if templates:
            for lang, tmpl in templates.items():
                parts = []
                for typ_key, cnt in type_counts.items():
                    if typ_key == "unknown":
                        part = tmpl.get("unknown", "{count} unknown motors").replace("{count}", str(cnt))
                    else:
                        part = tmpl.get("motor", "{count}x {type}")
                        part = part.replace("{count}", str(cnt)).replace("{type}", typ_key)
                    try:
                        parts.append(part)
                    except Exception:
                        pass
                sep = tmpl.get("sep", ", ")
                descriptions[lang] = sep.join(parts)

        return descriptions

    def _build_display_name(self) -> dict[str, str] | str:
        """Build display name from i18n or use default."""
        display_name_block = self._i18n.get_block("hardware.robot_definition.custom_robot_device")
        if display_name_block:
            return {k: v for k, v in display_name_block.items() if isinstance(v, str)}
        return "Custom Robot Device"
