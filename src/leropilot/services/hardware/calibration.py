"""Robot motor calibration framework.

Provides an extensible state-machine-based calibration system that guides users
through multi-step motor calibration procedures via a UI-friendly API.

Two built-in calibration methods are provided:

- ``HalfwayCalibrator``: moves joints to middle (sets homing offsets), then records
  the full min/max range in a single step (lerobot-style "halfway" calibration).
- ``ZeroPositionCalibrator``: sets the current joint positions as the zero reference
  and assigns ±90° (±π/2 rad) as the working range.

Architecture
------------
* ``Calibrator`` (abstract base) owns the state machine, position-tracking logic,
  i18n resolution, and the ``available_methods_for_robot`` discovery helper.
* Subclasses declare ``METHOD_ID`` and ``REQUIRED_METHODS`` class variables and
  implement ``get_steps()``, ``_recording_steps()``, and ``_execute_step()``.
* ``CalibrationState`` is returned by ``start()`` / ``next()`` and carries all
  information the frontend needs to render progress UI in a single response.
* ``on_telemetry_frame()`` is called by ``RobotTelecontrolService`` for each telemetry
  frame during an active session; the calibrator tracks running min/max positions
  during recording steps without issuing its own MotorBus reads (to avoid conflicting
  with the telemetry loop).
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leropilot.models.hardware import Robot, RobotDefinition, RobotTelemetryFrame
    from leropilot.services.hardware.motor_buses.motor_bus import MotorBus

logger = logging.getLogger(__name__)

_PI_OVER_2: float = math.pi / 2.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CalibrationState:
    """Snapshot of calibration progress returned by ``start()`` and ``next()``.

    Args:
        step_index: Current step index (0-based). ``-1`` when calibration is complete.
        step_count: Total number of steps in this calibration method.
        is_complete: ``True`` when all steps have been executed successfully.
        method_id: Identifier of the calibration method (e.g. ``"halfway"``).
        step_descriptions: Localised descriptions for **every** step in order, in the
            language requested at ``start()`` time.  Empty list when calibration is
            complete.
    """

    step_index: int
    step_count: int
    is_complete: bool
    method_id: str
    step_descriptions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class Calibrator(ABC):
    """Abstract base for all calibration strategies.

    Each subclass represents one calibration *method* (e.g. "halfway", "zero_position").

    Class-level attributes
    ----------------------
    METHOD_ID
        Unique string identifier used to look up and route calibration commands.
    REQUIRED_METHODS
        Frozenset of ``MotorBus`` method names that a bus must expose for this
        calibrator to support it.  Used by ``supports_bus_class()`` to determine
        capability at robot-configuration time without instantiating hardware.

    Instance lifecycle
    ------------------
    1. Instantiate with the robot object: ``calibrator = HalfwayCalibrator(robot)``.
    2. Call ``start(motor_buses)`` once (typically from ``RobotTelecontrolService``).
    3. For each user confirmation, call ``next()``; it executes the step action and
       returns the new ``CalibrationState``.
    4. During the active session, ``RobotTelecontrolService`` calls
       ``on_telemetry_frame(frame)`` after every telemetry read so that recording
       steps can track position extremes.
    """

    METHOD_ID: str = ""
    REQUIRED_METHODS: frozenset[str] = frozenset()

    def __init__(self, robot: Robot) -> None:
        """Initialise the calibrator with the target robot.

        Args:
            robot: The robot instance whose ``calibration_settings`` will be updated.
                   The object MUST be the manager-owned reference so that in-place
                   mutations are visible to ``RobotManager.update_robot``.
        """
        self._robot = robot
        self._motor_buses: dict[str, MotorBus] | None = None
        self._current_step: int = -1  # -1 means not started / complete
        self._lang: str = "en"

        # Running min/max for recording steps, stored in RAW_IN_RADIAN units.
        # Key: (bus_name, motor_name)
        self._min_radian: dict[tuple[str, str], float] = {}
        self._max_radian: dict[tuple[str, str], float] = {}

    # ------------------------------------------------------------------
    # Abstract interface – subclasses MUST implement
    # ------------------------------------------------------------------

    @classmethod
    @abstractmethod
    def get_steps(cls) -> list[str]:
        """Return ordered step key suffixes for this calibration method.

        Each entry is a leaf key that, combined with ``"calibration.<METHOD_ID>."``
        forms the full i18n lookup path.  Example for the halfway method::

            ["step_move_to_halfway", "step_move_to_min_max"]

        The length of the returned list determines the total step count reported to
        the UI.  Step index 0 is the first instruction shown to the user; ``next()``
        at each index executes the associated hardware action and advances to the next.
        """

    @abstractmethod
    def _recording_steps(self) -> frozenset[int]:
        """Return the set of step indices during which min/max positions are recorded.

        While the calibration is at one of these steps and ``on_telemetry_frame``
        is called, the calibrator updates its running min/max position accumulators.
        """

    @abstractmethod
    def _execute_step(self, step_index: int) -> None:
        """Execute the hardware action for transitioning *out of* ``step_index``.

        Called synchronously inside ``next()``.  Long-running or blocking operations
        are acceptable here because ``RobotTelecontrolService`` suspends telemetry
        polling before invoking ``next()`` and resumes it afterwards.

        Args:
            step_index: The step being confirmed/completed.
        """

    # ------------------------------------------------------------------
    # Class-level helpers
    # ------------------------------------------------------------------

    @classmethod
    def supports_bus_class(cls, bus_cls: type[MotorBus]) -> bool:
        """Return ``True`` if *bus_cls* exposes all methods required by this calibrator.

        The check uses ``hasattr`` on the class (not an instance), so it works without
        connecting to any hardware.

        Args:
            bus_cls: A ``MotorBus`` subclass (e.g. ``FeetechMotorBus``).
        """
        return all(hasattr(bus_cls, m) for m in cls.REQUIRED_METHODS)

    @classmethod
    def all_calibrators(cls) -> list[type[Calibrator]]:
        """Return all registered ``Calibrator`` subclasses (recursively).

        New calibration methods are auto-discovered as long as their module is
        imported before this method is called.
        """
        results: list[type[Calibrator]] = []

        def _collect(klass: type[Calibrator]) -> None:
            for sub in klass.__subclasses__():
                results.append(sub)
                _collect(sub)

        _collect(cls)
        return results

    @classmethod
    def _i18n_step_descriptions(cls, lang: str = "en") -> list[str]:
        """Resolve all step keys to localised description strings.

        Uses the global ``I18nService`` singleton.  Falls back to English when
        the requested language is not available, and falls back to the raw key
        string when the key is missing entirely.

        Args:
            lang: BCP-47 language code (e.g. ``"en"``, ``"zh"``).

        Returns:
            A list of translated description strings, one per step, in order.
        """
        from leropilot.services.i18n import get_i18n_service

        i18n = get_i18n_service()
        descriptions: list[str] = []
        for step_key in cls.get_steps():
            full_key = f"calibration.{cls.METHOD_ID}.{step_key}"
            desc = i18n.translate(full_key, lang=lang) or i18n.translate(full_key, lang="en")
            descriptions.append(desc or full_key)
        return descriptions

    @classmethod
    def available_methods_for_robot(
        cls,
        robot: Robot,
        lang: str = "en",
    ) -> list[dict]:
        """Return calibration methods supported by all motor buses of the robot.

        Logic
        -----
        1. Resolve all ``MotorBus`` classes referenced by the robot definition.
        2. If the definition specifies a ``calibration_method``, return **only** that
           method when it is supported by every bus (intersection rule).  Returns an
           empty list when the specified method is not supported.
        3. Otherwise, return all calibrators whose ``REQUIRED_METHODS`` are satisfied
           by **all** bus classes (intersection).

        Args:
            robot: Manager-owned robot object with populated ``definition``.
            lang: Language code for step description localisation.

        Returns:
            List of ``{"method_id": str, "steps": list[str]}`` dicts — one per
            supported calibration method — ordered by ``all_calibrators()`` discovery
            order.
        """
        from leropilot.models.hardware import RobotDefinition
        from leropilot.services.hardware.motor_buses.motor_bus import MotorBus as _MotorBus

        defn = robot.definition
        if not isinstance(defn, RobotDefinition):
            return []

        # Collect the MotorBus *classes* used by this robot.
        bus_classes: list[type[_MotorBus]] = []
        for bus_def in defn.motor_buses.values():
            try:
                bus_cls = _MotorBus.resolve_bus_class(bus_def.type)
                bus_classes.append(bus_cls)
            except ValueError:
                logger.warning(
                    f"Unknown motor bus type {bus_def.type!r} for robot {robot.id!r}; "
                    "skipping for calibration method resolution"
                )

        if not bus_classes:
            return []

        def _all_buses_support(cal_cls: type[Calibrator]) -> bool:
            return all(cal_cls.supports_bus_class(bc) for bc in bus_classes)

        all_cals = cls.all_calibrators()

        # Honour the preferred method declared in the robot specification.
        preferred: str | None = getattr(defn, "calibration_method", None)
        if preferred:
            matched = [c for c in all_cals if c.METHOD_ID == preferred]
            if matched and _all_buses_support(matched[0]):
                cal_cls = matched[0]
                return [{"method_id": cal_cls.METHOD_ID, "steps": cal_cls._i18n_step_descriptions(lang)}]
            logger.warning(
                f"Preferred calibration_method={preferred!r} not supported by all "
                f"buses of robot {robot.id!r}; returning empty list"
            )
            return []

        # No preference – return all methods supported by every bus.
        return [
            {"method_id": c.METHOD_ID, "steps": c._i18n_step_descriptions(lang)}
            for c in all_cals
            if c.METHOD_ID and _all_buses_support(c)
        ]

    # ------------------------------------------------------------------
    # State machine API
    # ------------------------------------------------------------------

    def start(self, motor_buses: dict[str, MotorBus], lang: str = "en") -> CalibrationState:
        """Initialise and start the calibration state machine at step 0.

        Args:
            motor_buses: Mapping from bus name to connected ``MotorBus`` instances,
                as provided by the active ``RobotTelecontrolService``.
            lang: Language code used to localise step descriptions in all subsequent
                ``CalibrationState`` responses.

        Returns:
            The initial ``CalibrationState`` describing step 0.
        """
        self._motor_buses = motor_buses
        self._current_step = 0
        self._lang = lang
        self._min_radian.clear()
        self._max_radian.clear()
        logger.info(
            f"Calibration started: method={self.METHOD_ID!r}, "
            f"robot={self._robot.id!r}, total_steps={len(self.get_steps())}, lang={lang!r}"
        )
        return self._build_state()

    def next(self) -> CalibrationState:
        """Execute the current step's action and advance to the next step.

        Must be called only after ``start()`` and only while ``is_complete`` is
        ``False``.

        Returns:
            Updated ``CalibrationState``. When all steps are done, ``is_complete``
            is ``True`` and ``step_index`` is ``-1``.

        Raises:
            RuntimeError: If called before ``start()`` or after completion.
        """
        if self._motor_buses is None or self._current_step < 0:
            raise RuntimeError(
                "Calibrator.next() called before start() or after completion. "
                "Call start() first."
            )

        executing_step = self._current_step
        logger.info(
            f"Calibration executing step {executing_step}: method={self.METHOD_ID!r}, "
            f"robot={self._robot.id!r}"
        )
        self._execute_step(executing_step)

        self._current_step += 1
        if self._current_step >= len(self.get_steps()):
            self._current_step = -1  # mark complete

        logger.info(
            f"Calibration advanced: step={self._current_step}, "
            f"is_complete={self._current_step == -1}"
        )
        return self._build_state()

    def on_telemetry_frame(self, frame: RobotTelemetryFrame) -> None:
        """Update running min/max position accumulators from a telemetry frame.

        This method is called by ``RobotTelecontrolService`` on every telemetry
        read during an active session.  It only processes the frame when the
        current step is one of the recording steps (as declared by the subclass).

        Positions are received in ``RAW_IN_RADIAN`` units (the unit used by the
        telemetry loop) and stored as-is.  The ``_radian_to_raw`` helper converts
        them to encoder units when calibration data is written.

        Args:
            frame: The latest ``RobotTelemetryFrame`` from the telemetry loop.
        """
        if self._current_step not in self._recording_steps():
            return
        if self._motor_buses is None:
            return

        for bus_name, bus_data in frame.motor_buses.items():
            for motor_name, telemetry in bus_data.motors.items():
                if telemetry.position is None:
                    continue

                pos_radian: float = telemetry.position
                key = (bus_name, motor_name)

                if key not in self._min_radian:
                    self._min_radian[key] = pos_radian
                    self._max_radian[key] = pos_radian
                else:
                    self._min_radian[key] = min(self._min_radian[key], pos_radian)
                    self._max_radian[key] = max(self._max_radian[key], pos_radian)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _radian_to_raw(self, radian: float, motor_info: object) -> float:  # motor_info: MotorModelInfo
        """Convert a ``RAW_IN_RADIAN`` position to raw encoder units.

        Args:
            radian: Position in radians.
            motor_info: ``MotorModelInfo`` instance with ``position_to_radian_ratio``.

        Returns:
            Raw encoder units, or *radian* unchanged if the ratio is zero/unavailable.
        """
        ratio: float = getattr(motor_info, "position_to_radian_ratio", 0.0) or 0.0
        if ratio != 0.0:
            return radian / ratio
        return radian

    def _build_state(self) -> CalibrationState:
        """Build a ``CalibrationState`` snapshot from the current internal state."""
        steps = self.get_steps()
        is_complete = self._current_step == -1
        all_descriptions = self._i18n_step_descriptions(self._lang)

        return CalibrationState(
            step_index=self._current_step,
            step_count=len(steps),
            is_complete=is_complete,
            method_id=self.METHOD_ID,
            step_descriptions=all_descriptions,
        )


    def save(self) -> None:
        """Persist calibration data and mark the robot as calibrated.

        Call this after ``is_complete`` is ``True`` to durably write
        ``calibration_settings`` to the robot manager.  Separating save
        from the last ``next()`` call allows the UI to display a
        confirmation step before committing changes.

        Raises:
            RuntimeError: If called before ``start()`` has been invoked.
        """
        if self._motor_buses is None:
            raise RuntimeError(
                "Calibrator.save() called before start(). Call start() first."
            )
        self._save_calibration()

    def _save_calibration(self) -> None:
        """Persist calibration settings and mark robot as calibrated.

        Writes ``calibration_settings`` to the robot manager and sets
        ``is_calibrated=True``.  Subclasses may call this via ``save()``
        or override for custom persistence logic.
        """
        from leropilot.services.hardware.robots.manager import get_robot_manager

        robot_manager = get_robot_manager()
        robot_manager.update_robot(
            self._robot.id,
            verify=False,
            calibration_settings=self._robot.calibration_settings,
            is_calibrated=True,
        )
        logger.info(
            f"Calibration saved for robot {self._robot.id!r} "
            f"using method {self.METHOD_ID!r}"
        )


# ---------------------------------------------------------------------------
# Built-in calibrators
# ---------------------------------------------------------------------------


class HalfwayCalibrator(Calibrator):
    """Halfway (mid-point homing) calibration method.

    Procedure
    ---------
    Step 0 – **Move to halfway**
        User physically moves all joints to the midrange position.
        On ``next()``: calls ``bus.set_half_turn_homings(motor_ids)`` to capture the
        current position as the home (zero) reference.

    Step 1 – **Move through full range (min → max)**
        User slowly moves all joints from their mechanical minimum to their maximum
        (limit) positions.  During this entire step, every incoming telemetry frame
        updates the running min/max position per motor.
        On ``next()``: writes both min and max tracked values into
        ``calibration_settings`` in-memory.  Persistence happens when the frontend
        calls ``save()`` (triggered by the UI "Save" button).

    Required MotorBus method
    ------------------------
    ``set_half_turn_homings(motor_ids: list) -> None``
        Must be present on every MotorBus subclass used by the robot.
    """

    METHOD_ID = "halfway"
    REQUIRED_METHODS: frozenset[str] = frozenset({"set_half_turn_homings"})

    # Step index constants
    _STEP_MOVE_TO_HALFWAY: int = 0
    _STEP_MOVE_TO_MIN_MAX: int = 1

    @classmethod
    def get_steps(cls) -> list[str]:
        return ["step_move_to_halfway", "step_move_to_min_max"]

    def _recording_steps(self) -> frozenset[int]:
        # Record during the single combined move-through-range step.
        return frozenset({self._STEP_MOVE_TO_MIN_MAX})

    def _execute_step(self, step_index: int) -> None:
        assert self._motor_buses is not None, "motor_buses not set; call start() first"

        if step_index == self._STEP_MOVE_TO_HALFWAY:
            # Ask each bus to set current position as halfway home reference.
            for bus_name, bus in self._motor_buses.items():
                motor_ids = list(bus.motors.keys())
                logger.info(
                    f"set_half_turn_homings on bus={bus_name!r}, "
                    f"motor_ids={motor_ids}"
                )
                bus.set_half_turn_homings(motor_ids)  # type: ignore[attr-defined]

        elif step_index == self._STEP_MOVE_TO_MIN_MAX:
            # The user has moved through the full range; apply position bounds.
            # Persistence happens when save() is called explicitly by the frontend.
            self._apply_tracked_positions(use_min=True)
            self._apply_tracked_positions(use_min=False)

    def _apply_tracked_positions(self, *, use_min: bool) -> None:
        """Write tracked min or max positions (in raw encoder units) into calibrations.

        Args:
            use_min: If ``True``, update ``range_min``; otherwise update ``range_max``.
        """
        assert self._motor_buses is not None

        from leropilot.models.hardware import RobotDefinition

        defn = self._robot.definition
        if not isinstance(defn, RobotDefinition):
            logger.warning("HalfwayCalibrator: robot has no RobotDefinition, skipping position apply")
            return

        tracked = self._min_radian if use_min else self._max_radian
        field_label = "range_min" if use_min else "range_max"

        for bus_name, bus in self._motor_buses.items():
            cal_list = self._robot.calibration_settings.get(bus_name, [])
            bus_def = defn.motor_buses.get(bus_name)
            if bus_def is None:
                continue

            for cal in cal_list:
                motor_name = cal.name
                key = (bus_name, motor_name)

                if key not in tracked:
                    logger.warning(
                        f"HalfwayCalibrator: no tracked position for "
                        f"{bus_name!r}.{motor_name!r} – {field_label} not updated"
                    )
                    continue

                # Map motor_name → motor_id → MotorModelInfo for unit conversion.
                motor_def = bus_def.motors.get(motor_name)
                if motor_def is None:
                    continue
                motor_id_key = motor_def.id
                motor_id = motor_id_key[0] if isinstance(motor_id_key, tuple) else motor_id_key
                motor_info = bus.motors.get(motor_id)
                if motor_info is None:
                    continue

                raw_value = self._radian_to_raw(tracked[key], motor_info)
                if use_min:
                    cal.range_min = raw_value
                else:
                    cal.range_max = raw_value

                logger.debug(
                    f"HalfwayCalibrator: {bus_name!r}.{motor_name!r} "
                    f"{field_label}={raw_value:.1f} (radian={tracked[key]:.4f})"
                )




class ZeroPositionCalibrator(Calibrator):
    """Zero-position calibration method.

    Procedure
    ---------
    Step 0 – **Move to zero position**
        User physically moves all joints to the desired zero/home configuration.
        On ``next()``::

        1. Calls ``bus.set_zero_position(motor_id)`` for every motor so the hardware
           treats the current physical position as its new origin.
        2. Resets ``homing_offset`` to ``0.0`` for all motors in
           ``calibration_settings``.
        3. Sets ``range_min = −π/2`` and ``range_max = +π/2`` (±90°).  For buses
           that store limits in raw encoder units (e.g. Feetech, Dynamixel) the
           radian values are converted via ``position_to_radian_ratio``; for buses
           that store limits in radians (e.g. Damiao) the values are stored directly.
        4. Updates ``calibration_settings`` in-memory.  Persistence happens when
           the frontend calls ``save()`` (triggered by the UI "Save" button).

    Required MotorBus method
    ------------------------
    ``set_zero_position(motor_id) -> None``
        Must be present on every MotorBus subclass used by the robot.
    """

    METHOD_ID = "zero_position"
    REQUIRED_METHODS: frozenset[str] = frozenset({"set_zero_position"})

    _STEP_MOVE_TO_ZERO: int = 0

    @classmethod
    def get_steps(cls) -> list[str]:
        return ["step_move_to_zero"]

    def _recording_steps(self) -> frozenset[int]:
        # No continuous position recording needed for zero-position calibration.
        return frozenset()

    def _execute_step(self, step_index: int) -> None:  # noqa: C901
        assert self._motor_buses is not None, "motor_buses not set; call start() first"

        if step_index != self._STEP_MOVE_TO_ZERO:
            return

        from leropilot.models.hardware import RobotDefinition

        defn = self._robot.definition

        # 1. Issue the hardware zero command for every motor on every bus.
        for bus_name, bus in self._motor_buses.items():
            for motor_id in bus.motors:
                logger.info(
                    f"set_zero_position on bus={bus_name!r}, motor_id={motor_id}"
                )
                bus.set_zero_position(motor_id)  # type: ignore[attr-defined]

        # 2. Update calibration_settings: reset homing_offset and set ±π/2 range.
        for bus_name, bus in self._motor_buses.items():
            cal_list = self._robot.calibration_settings.get(bus_name, [])
            bus_def = (
                defn.motor_buses.get(bus_name)
                if isinstance(defn, RobotDefinition)
                else None
            )

            for cal in cal_list:
                cal.homing_offset = 0.0

                # Resolve position_to_radian_ratio to determine storage units.
                ratio: float = 0.0
                if bus_def is not None:
                    motor_def = bus_def.motors.get(cal.name)
                    if motor_def is not None:
                        motor_id_key = motor_def.id
                        motor_id = (
                            motor_id_key[0]
                            if isinstance(motor_id_key, tuple)
                            else motor_id_key
                        )
                        motor_info = bus.motors.get(motor_id)
                        ratio = (
                            getattr(motor_info, "position_to_radian_ratio", 0.0) or 0.0
                        )

                if ratio != 0.0:
                    # Bus stores limits in raw encoder units.
                    half_range = _PI_OVER_2 / ratio
                    cal.range_min = -half_range
                    cal.range_max = half_range
                else:
                    # Bus stores limits directly in radians (e.g. Damiao).
                    cal.range_min = -_PI_OVER_2
                    cal.range_max = _PI_OVER_2

                logger.debug(
                    f"ZeroPositionCalibrator: {bus_name!r}.{cal.name} "
                    f"range=[{cal.range_min:.4f}, {cal.range_max:.4f}] "
                    f"(ratio={ratio})"
                )

        # 3. Persistence is deferred — call save() after the UI "Save" button is pressed.
