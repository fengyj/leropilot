"""
Telemetry session service for robot/device realtime telemetry and protection handling.

Provides:
- TelemetrySession to run a polling loop that reads telemetry, detects protection violations,
  performs safety actions (e.g., disable torque), and emits structured events via an asyncio.Queue.

The session is intended to be protocol-agnostic and used by WebSocket handlers or other orchestrators.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from datetime import datetime

from leropilot.models.hardware import MotorTelemetry, Robot
from leropilot.services.hardware.motor_drivers.base import BaseMotorDriver
from leropilot.services.hardware.motors import MotorService

logger = logging.getLogger(__name__)


class TelemetrySession:
    """Run telemetry polling and emit events, and expose control APIs.

    Usage:
        session = TelemetrySession(device_id, driver, motor_service, device, brand="dynamixel")
        await session.start()
        await session.open_driver(interface, baud_rate)
        q = session.subscribe()
        # use session.set_position / set_torque to control
        await session.stop()
    """

    def __init__(
        self,
        device_id: str,
        driver: BaseMotorDriver | None,
        motor_service: MotorService,
        device: Robot,
        brand: str = "dynamixel",
        target_ids: Iterable[int] | None = None,
        poll_interval_ms: int = 100,
    ) -> None:
        self.device_id = device_id
        self.driver = driver
        self.motor_service = motor_service
        self.device = device
        self.brand = brand
        self.target_ids = list(target_ids) if target_ids is not None else list(range(1, 7))
        self.poll_interval_ms = poll_interval_ms

        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._running = False
        # Polling must be explicitly enabled by client via start_telemetry
        self._polling_enabled: bool = False
        self._disabled_by_protection: set[int] = set()

    def subscribe(self) -> asyncio.Queue[dict]:
        """Return the queue used for events/telemetry messages."""
        return self._queue

    @property
    def calibration_available(self) -> bool:
        """Return whether calibration data appears available for this device.

        Use `Robot.calibration_settings` (per-bus lists of `MotorCalibration`) rather than
        the deprecated `config.motors` structure.
        """
        if not self.device:
            return False
        # calibration_settings: dict[bus_name, list[MotorCalibration]]
        try:
            for _bus, cal_list in (self.device.calibration_settings or {}).items():
                for mc in cal_list or []:
                    if getattr(mc, "homing_offset", None) is not None:
                        return True
        except Exception:
            return False
        return False

    async def start(self) -> None:
        """Start session loop in background task.

        For backwards compatibility with earlier behavior, starting a session enables polling
        by default so that tests and simple usages don't require an explicit call to
        `enable_polling()`.
        """
        if self._running:
            return
        self._running = True
        # Enable polling by default for backwards-compatibility
        self._polling_enabled = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"TelemetrySession started for {self.device_id}")

    async def enable_polling(self) -> None:
        """Enable periodic telemetry polling (client-triggered)."""
        self._polling_enabled = True
        logger.info(f"TelemetrySession polling enabled for {self.device_id}")

    async def disable_polling(self) -> None:
        """Disable periodic telemetry polling (client-triggered)."""
        self._polling_enabled = False
        logger.info(f"TelemetrySession polling disabled for {self.device_id}")

    async def set_poll_interval_ms(self, interval_ms: int) -> None:
        """Set polling interval (ms). Enforces a reasonable minimum."""
        try:
            ival = max(20, int(interval_ms))
        except Exception:
            ival = 20
        self.poll_interval_ms = ival
        logger.info(f"TelemetrySession poll interval set to {ival}ms for {self.device_id}")

    async def stop(self) -> None:
        """Stop session and wait for background task to finish."""
        if not self._running:
            return
        self._running = False
        if self._task:
            try:
                await self._task
            except Exception:
                pass
            self._task = None
        logger.info(f"TelemetrySession stopped for {self.device_id}")

    async def open_driver(
        self,
        interface: str,
        baud_rate: int = 1000000,
        brand: str | None = None,
        interface_type: str | None = None,
    ) -> bool:
        """Open and attach a driver using motor_service. Returns True on success."""
        try:
            loop = asyncio.get_running_loop()
            # Call blocking create_driver in executor to avoid blocking event loop
            driver = await loop.run_in_executor(
                None,
                self.motor_service.create_driver,
                interface,
                brand or self.brand,
                interface_type
                or (
                    "can"
                    if any(
                        "can" in (getattr(c, "motor_bus_type", "") or "").lower()
                        for c in (self.device.motor_bus_connections or {}).values()
                    )
                    else "serial"
                ),
                baud_rate,
            )
            if not driver:
                return False
            self.driver = driver
            logger.info(f"TelemetrySession: driver opened for {self.device_id} on {interface}")
            return True
        except Exception as e:
            logger.error(f"TelemetrySession open_driver error: {e}")
            return False

    async def close_driver(self) -> None:
        """Disconnect driver if present."""
        try:
            if self.driver:
                # Disconnect may be blocking - call the disconnect method in executor
                loop = asyncio.get_running_loop()
                drv = self.driver

                def _drv_disconnect(drv_obj: BaseMotorDriver) -> None:
                    drv_obj.disconnect()

                await loop.run_in_executor(None, _drv_disconnect, drv)
        except Exception:
            logger.exception("Error disconnecting driver")
        finally:
            self.driver = None

    async def set_position(self, motor_id: int, position: int) -> dict:
        """Set a single motor position. Returns ack dict."""
        if not self.calibration_available:
            return {"success": False, "error": "Calibration required"}
        if not self.driver:
            return {"success": False, "error": "Driver not connected"}
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.driver.write_goal_position, motor_id, int(position))
            return {"success": True}
        except Exception as e:
            logger.error(f"set_position error: {e}")
            return {"success": False, "error": str(e)}

    async def set_positions(self, positions: list[dict]) -> dict:
        """Set multiple motor positions. positions: list of {id, position} dicts."""
        if not self.calibration_available:
            return {"success": False, "error": "Calibration required"}
        if not self.driver:
            return {"success": False, "error": "Driver not connected"}
        try:
            loop = asyncio.get_running_loop()
            for m in positions:
                mid = m.get("id")
                pos = m.get("position")
                if mid is not None and pos is not None:
                    await loop.run_in_executor(None, self.driver.write_goal_position, mid, int(pos))
            return {"success": True}
        except Exception as e:
            logger.error(f"set_positions error: {e}")
            return {"success": False, "error": str(e)}

    async def set_torque(self, enabled: bool, motor_id: int | None = None) -> dict:
        """Enable or disable torque for one or all motors."""
        if not self.calibration_available:
            return {"success": False, "error": "Calibration required"}
        if not self.driver:
            return {"success": False, "error": "Driver not connected"}
        try:
            loop = asyncio.get_running_loop()
            if motor_id is not None:
                await loop.run_in_executor(None, self.driver.write_torque_enable, motor_id, enabled)
            else:
                # Best-effort: disable discovered ids
                for mid in self.target_ids:
                    await loop.run_in_executor(None, self.driver.write_torque_enable, mid, enabled)
            return {"success": True}
        except Exception as e:
            logger.error(f"set_torque error: {e}")
            return {"success": False, "error": str(e)}

    async def emergency_stop(self) -> dict:
        """Disable all torque and emit EMERGENCY_STOP event."""
        try:
            loop = asyncio.get_running_loop()
            for mid in self.target_ids:
                try:
                    if self.driver:
                        await loop.run_in_executor(None, self.driver.write_torque_enable, mid, False)
                except Exception:
                    logger.exception(f"Failed to disable torque for motor {mid}")

            event = {
                "type": "event",
                "event": {
                    "code": "EMERGENCY_STOP",
                    "severity": "warning",
                    "message": "Emergency stop triggered - all motors disabled",
                    "timestamp": datetime.now().isoformat(),
                },
            }
            await self._queue.put(event)
            return {"success": True}
        except Exception as e:
            logger.error(f"emergency_stop error: {e}")
            return {"success": False, "error": str(e)}

    async def _run_loop(self) -> None:
        loop = asyncio.get_running_loop()

        while self._running:
            try:
                if not self._polling_enabled:
                    # Polling is disabled - sleep briefly and continue
                    await asyncio.sleep(0.1)
                    continue

                # Perform blocking telemetry reads in executor
                data = await loop.run_in_executor(
                    None,
                    self._sync_read,
                    self.target_ids,
                    self.device.labels.get("leropilot.ai/robot_type_id", "unknown"),
                )

                # Process protection and emit events
                await self._process_protection_and_emit(data)

                # Emit telemetry message
                msg = {"type": "telemetry", "timestamp": datetime.now().isoformat(), "motors": data}
                await self._queue.put(msg)

            except Exception as e:
                logger.error(f"TelemetrySession loop error for {self.device_id}: {e}")

            # Sleep
            await asyncio.sleep(self.poll_interval_ms / 1000.0)

    def _sync_read(self, target_ids: list[int], robot_type_id: str) -> list[dict]:
        """Synchronous read helper (runs in executor)."""
        results: list[dict] = []
        for mid in target_ids:
            try:
                driver = self.driver
                if driver is None:
                    continue
                telemetry: MotorTelemetry | None = self.motor_service.read_telemetry_with_protection(
                    driver, mid, self.brand, robot_type_id, None
                )
                if telemetry:
                    # model_dump ensures serializable dict
                    results.append(telemetry.model_dump())
            except Exception as e:
                logger.debug(f"Error reading telemetry for motor {mid}: {e}")
        return results

    async def _process_protection_and_emit(self, telemetry_list: list[dict]) -> None:
        """Handle protection statuses, disable torque on critical, and emit events."""
        for m in telemetry_list:
            try:
                mid = m.get("id")
                ps = m.get("protection_status") or {}
                if mid is None:
                    continue

                if ps.get("status") == "critical" and mid not in self._disabled_by_protection:
                    # Best-effort: try to disable torque
                    try:
                        if self.driver:
                            # driver may expose write_torque_enable or set_torque
                            if hasattr(self.driver, "write_torque_enable"):
                                self.driver.write_torque_enable(mid, False)
                            elif hasattr(self.motor_service, "bulk_set_torque"):
                                # fallback to motor service bulk disable
                                self.motor_service.bulk_set_torque(self.driver, [mid], False)
                    except Exception:
                        logger.exception(f"Failed to disable torque for motor {mid} (device {self.device_id})")

                    self._disabled_by_protection.add(mid)

                    # Emit event
                    event = {
                        "type": "event",
                        "event": {
                            "code": "EMERGENCY_PROTECTION",
                            "severity": "critical",
                            "message": f"Motor {mid} torque disabled due to critical protection",
                            "motor_id": mid,
                            "timestamp": datetime.now().isoformat(),
                        },
                    }
                    await self._queue.put(event)
            except Exception:
                logger.exception("Error while processing protection status for motor")
