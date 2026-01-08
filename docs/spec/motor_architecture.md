# Motor Subsystem — Architecture & Design

## Overview

This document proposes a refactor and higher-level architecture for the motor subsystem, inspired by the `lerobot` design (motors_bus, per-protocol tables, batched operations). The goals are:

- Provide clear separation of concerns between robot, bus, protocol, and driver layers
- Make drivers responsible for model-specific knowledge and limits
- Make protocols responsible for bus-level discovery and support for a family of drivers
- Keep motor *models* and *variants* typed and implemented in code (enums / classes) where appropriate instead of stuffing low-level control tables into `motor_specs.json`
- Improve robustness, testability and performance (group sync / batch ops)

## Layered Architecture

High-level picture:

Robot
  └─ MotorBus (one or more)
       └─ BusProtocol (Serial/Can)
            └─ MotorDriver (per motor family/model)

### Robot
- Represents a device containing one or more motor buses (e.g., an arm with multiple serial buses or mixed CAN/serial)
- Responsible for high-level orchestration and exposing a device-level API to the rest of the system
- Responsible for device configuration (which MotorBus instances are present, mapping motor names to bus+id)

### MotorBus
- Higher-level abstraction which hides protocol and driver details behind a small, unified API
- Responsible for:
  - connect/disconnect (with optional handshake)
  - scan/identify motors on that bus
  - sync_read / sync_write (batched reads/writes) for performance
  - read_calibration / write_calibration / normalize/unnormalize helpers
  - enable/disable torque (bulk and single)
  - context-manager helpers (`with bus.torque_disabled(...):`)
- Implementation approach: **composition-first, single `MotorBus` class.**
  - The `MotorBus` holds a `BusProtocol` instance and delegates protocol-specific primitives to it.
  - **Do not** create multiple `MotorBus` subclasses for each protocol. Protocol-specific behavior should live in `BusProtocol` implementations (and optional protocol helpers) and be exposed via capability flags.
  - **Design rule:** MotorBus should *not* implement protocol fallback logic or scatter conditional checks for protocol capabilities. Instead, `BusProtocol` provides high-level primitives (e.g., `bulk_read`) with safe default implementations; protocol subclasses override these when efficient mechanisms are available. This keeps MotorBus code clean and adheres to the Interface Segregation Principle.

### Protocol capabilities & fallback behavior
- Each `BusProtocol` should declare capability flags and optional high-level helpers, for example:
  - `supports_group_read`, `supports_broadcast_ping`, `supports_batch_recv`, `supports_can_fd`
  - Optional helpers: `group_read(addr, length, ids)`, `broadcast_ping()`, `recv_all_responses(expected_recv_ids, timeout)`
- **Important design rule:** Protocols must implement **high-level primitives** with sensible defaults placed *inside the Protocol layer*. In particular, `BusProtocol` should provide a `bulk_read` (or `group_read`) method that **defaults to a safe sequential implementation** (looping single reads). Protocol subclasses that support native, efficient group operations must override this method. MotorBus should simply call the protocol primitive and not implement capability-specific fallback logic.

Example pseudocode:

```py
# Protocol
class BusProtocol(ABC):
    supports_group_read: bool = False
    supports_batch_recv: bool = False

    # Default bulk_read falls back to sequential reads
    def bulk_read(self, addr, length, ids):
        result = {}
        for id_ in ids:
            result[id_] = self.read(addr, length, id_)
        return result

    # Protocols with native group read override bulk_read
    def group_read(self, addr, length, ids):
        return self.bulk_read(addr, length, ids)  # optional alias

# MotorBus uses the protocol primitive directly
class MotorBus:
    def sync_read(self, name, motor_ids):
        addr, length = addr_for(name), len_for(name)
        return self.protocol.bulk_read(addr, length, motor_ids)
```

Rationale: this keeps the MotorBus API stable and centralizes device-level semantics, while letting protocols implement efficient primitives and take responsibility for frame/packet parsing and timing-critical behavior.

### BusProtocol
- Encapsulates how to talk to motors using a given bus type but does not encode specific motor model register maps
- Examples: `SerialBusProtocol`, `CanBusProtocol`, `FeetechStsSerialBusProtocol`, `DynamixelSerialBusProtocol`, `DamiaoCanBusProtocol` (specialized subclasses can carry protocol-specific helpers)
- Responsibilities:
  - Lower-level operations like ping, broadcast_ping, set_baudrate (protocol-specific semantics)
  - Provide mechanisms to create or select the correct MotorDriver for a discovered motor
  - Provide batched operations support (Group Sync or OpenArms pattern)

### MotorDriver
- Contains the *model-specific* logic: encoding/decoding, unit conversions, safe limits and higher-level per-model helpers
- Responsibilities:
  - Interpret raw registers/frames into `MotorTelemetry` in *agreed SI units* (documented contract)
  - Provide `read_telemetry`, `set_position`, `set_torque`, `reboot`, `read_bulk_telemetry` optimized for the motor family
  - Model detection: provide `identify_model(motor_id) -> MotorModel | MotorFamily` (should return the most precise model available, fall back to family-level, e.g. `STS3215` when variant unknown)
  - Expose model capabilities and limits (resolution, voltage range, current limits, operating modes)
- Note: Model information should be represented by a single typed `MotorModelInfo` dataclass in code (merged model + variant) rather than split enums or untyped JSON. This `MotorModelInfo` centralizes identification and model metadata for drivers and higher layers.

## Data / Metadata Placement

Design decision: **Do NOT use JSON files to maintain motor information or control tables.**

Rationale:
- Motor model metadata and protocol control tables are best represented as typed, versioned code artifacts (Python constants, enums, dataclasses, or Pydantic models). Storing these in JSON fragments loses type safety, tooling support (IDE errors, static analysis), and encourages ad-hoc edits that can break protocol logic.
- Many register addresses, encodings and limits are protocol- and model-specific and behave like compile-time constants; keeping them in Python modules enables better validation, test coverage, and discoverability.

Proposal:
- **Maintain protection, identification and control tables as typed Python modules** under `services/hardware/{dynamixel,feetech,damiao}/tables.py` (or `services/hardware/protocol_tables/`). Use enums, constants and small dataclasses to represent control tables, baud maps, encodings, resolutions and operating modes.
- For safety & configuration data (e.g., factory protection thresholds), prefer Python-embedded Pydantic models or a validated configuration store (database, or YAML with strict schema + loader). Avoid free-form JSON files for motor definitions in the repo.
- If externalization is absolutely required for runtime updates, do so via a strict, versioned schema (YAML/DB) plus a loader that validates and converts entries into the typed runtime objects used by drivers and protocols.

Benefits:
- Strong typing and IDE help when using constants/enums
- Easier unit tests and static validation of control tables
- Single source of truth in code, reducing accidental mismatches between drivers and table data

## Model Detection API

MotorDriver should offer:

- `identify_model(motor_id: int) -> MotorModelInfo | None`
  - Read the motor's model number and return a Pydantic `MotorModelInfo` representing the most precise model available (e.g., `STS3215-C001`). The `variant` field may be `None` to indicate only the base model is known.
  - **Driver ownership:** Drivers declare the models they support and are authoritative for identification of their motor families; there is no requirement for a centralized model registry.
  - **Ambiguity behavior:** If multiple models match the observed identifiers and no base-model fallback is available, the driver **must raise an explicit `AmbiguousModelError`** (or another explicit exception) so the caller handles ambiguity deterministically.
- `supported_models() -> list[MotorModelInfo]` – list of models/variants the driver can handle

Protocol layer should offer:
- `scan_bus(range: Iterable[int]) -> list[MotorModelInfo]` where each entry is a best-effort identification result (may be `None` for unknown motors). Returning `MotorModelInfo` directly (augmented with bus metadata like ID/firmware) is preferred for simplicity.
- `probe_port(...) -> MotorDiscoverResult` that determines which protocol/driver is present on a port (paralleling current `probe_connection` behavior)

Notes:
- Drivers should maintain their own supported model lists (module-level or in driver classes) and attempt identification using driver-specific logic; a central registry is unnecessary and not recommended.
- Default tie-breaker policy: prefer an entry with `variant is None` (base model) when present; otherwise, the driver should raise `AmbiguousModelError` to force explicit handling.

## Units and Normalization

Contract: drivers MUST return `MotorTelemetry` in agreed units (documented). Example:
- position: radians
- velocity: rad/s
- current: mA
- voltage: V
- temperature: °C

Why: this centralizes unit conversion, simplifies protection checks, and prevents inconsistent behavior. Bus-level or driver-level normalize/unnormalize helpers bridge raw register units and these SI units.

## Calibration & Normalization Behavior

- Calibration stored per-device in `DeviceConfig` (use `MotorCalibration` Pydantic model already present)
- `MotorBus` exposes `read_calibration` and `write_calibration` with `normalize=False` to read raw values and a `normalize=True` option for friendlier units
- Provide convenience routines: `set_half_turn_homings`, `record_ranges_of_motion` like lerobot

## Protocol + Driver Responsibilities Matrix

- BusProtocol: discovery, baud management, group/broadcast primitives, bus-level handshake
- MotorDriver: model detection, encode/decode, per-model limits, unit conversions, per-model register access helpers
- MotorBus: combine both to offer high-level batch operations and calibration helpers

## Operational semantics & behavior

To make implementations deterministic and testable, the spec defines concrete operational behavior for common, error-prone areas.

### Timeouts, retries, and backoff
- Each protocol implementation **must** expose configurable timeout and retry settings (per operation or global). Reasonable defaults:
  - read/write timeout: 50–200 ms for serial devices (protocol-specific)
  - retries: 0–2 (default 1)
  - exponential backoff on retries: optional, but recommended for flaky buses
- Implementations should document their defaults and allow overrides via `BusProtocol` constructor or `MotorBus` configuration.
- When mirroring `lerobot`, consult its `motors_bus` implementation for per-protocol timeout/retry patterns and adopt compatible defaults where present.

### Partial failures & error reporting
- For bulk/group operations the protocol primitive should provide a clear policy for partial failures. Two acceptable patterns:
  - **Raise-on-partial (strict)**: if any member of a group operation fails, raise a `PartialReadError` (with details of `ids_failed`) to force the caller to handle it explicitly; or
  - **Best-effort with report (for diagnostics)**: return a mapping `{id: Result | ErrorInfo}` where `ErrorInfo` contains error type and message. This is useful for diagnostics and for callers that can tolerate partial data.
- The default `BusProtocol.bulk_read` can implement raise-on-partial to be conservative; protocols with low-level multi-read guarantees may opt for best-effort.
- Tests must cover both behaviors (simulated partial failures) to ensure callers know which policy an implementation follows.

### Lifecycle, connection management & reconnection
- Define explicit connect/disconnect lifecycle APIs: `connect(handshake=True)`, `disconnect()`, and a context-manager `with MotorBus.open(...)` for short-lived sessions.
- Document and implement an optional auto-reconnect policy with a limited retry budget; provide hooks/callbacks for connection state changes so higher layers can react.
- Handshake/port probing should be idempotent and safe to run multiple times; tests must verify behavior when devices disconnect mid-operation.

### Concurrency / async API
- Provide both synchronous and asynchronous interfaces where it is meaningful. `BusProtocol` implementations **may** implement async methods (e.g., `async bulk_read`) for high-throughput apps.
- Document thread-safety guarantees: for simplicity, implementations may assume single-threaded use and callers should coordinate concurrent operations (e.g., scan vs write). If an implementation supports concurrent calls, document the guarantees (reentrancy, internal locking).
- In practice, scanning and high-rate sync_write rarely happen concurrently on the same bus; document that callers should avoid such concurrent mixes or use coordination utilities on top of `MotorBus`.

### Atomicity / transaction semantics
- Full multi-motor atomic transactions are **not** required and are generally not supported by common motor protocols. The spec does not mandate atomic group writes; if a protocol provides strong atomic guarantees (hardware-level), document them explicitly.

### Observability & metrics
- Protocol and bus implementations should expose metrics and logs for:
  - operation latencies (bulk_read/write)
  - retry counts
  - partial failure counts
  - connection events (connect/disconnect/reconnect)
- These metrics help to reproduce and debug flakiness and to compare performance to `lerobot` baselines.

---

## Tests & Migration Strategy

1. Add unit tests for model identification (fake drivers or mocked responses). Each driver must be able to map id → model/family.
2. Add tests for unit consistency and conversions (Feetech raw→SI, Dynamixel raw→SI, Damiao CAN decode) using fixtures.
3. Add performance tests demonstrating improved throughput after implementing group sync / batch ops.
4. Migration path:
   - Step A: Introduce APIs (BusProtocol, MotorDriver base classes) and small adapter wrappers for current drivers to implement the new interfaces.
   - Step B: For Feetech, update driver to implement `identify_model()` and to return SI units in `read_telemetry()`; add tests.
   - Step C: Implement MotorBus-level helpers that use Protocol + Driver to provide sync_read/sync_write and calibration routines.
   - Step D: For Dynamixel and Damiao, adopt group/batch operations and tests.

## Example API Stubs (simplified)

```py
class BusProtocol(ABC):
    def connect(self, handshake: bool = True) -> None: ...
    def disconnect(self) -> None: ...
    def scan(self, ids: Iterable[int]) -> dict[int, MotorModelInfo]: ...
    def broadcast_ping(self) -> dict[int, int]: ...

class MotorDriver(ABC):
    def identify_model(self, motor_id: int) -> MotorModel | None: ...
    def read_telemetry(self, motor_id: int) -> MotorTelemetry | None: ...
    def set_position(self, motor_id: int, position_rad: float, speed: float | None) -> bool: ...
    def set_torque(self, motor_id: int, enabled: bool) -> bool: ...
    def read_bulk_telemetry(self, motor_ids: list[int]) -> dict[int, MotorTelemetry]: ...

class MotorBus:
    def sync_read(self, name: str, motor_ids: list[int]) -> dict[int, float]: ...
    def sync_write(self, name: str, id_to_value: dict[int, float]) -> None: ...
    def read_calibration(self) -> dict[str, MotorCalibration]: ...

# MotorModelInfo (Pydantic) — example

```py
from pydantic import BaseModel, Field
from typing import Optional, Dict, List

class MotorLimit(BaseModel):
    """Single typed limit entry. Flexible key/value representation allows adding new limit types without changing the model."""
    type: str = Field(..., description="Limit type identifier, e.g., 'voltage_min', 'current_max_ma', 'temperature_max_c'")
    value: float = Field(..., description="Limit value in SI units (float)")


class MotorModelInfo(BaseModel):
    """Combined model/variant metadata for a motor model.

    Changes vs previous design:
    - Uses Pydantic for runtime validation and serialization.
    - `limits` is a flexible mapping from limit-type string -> `MotorLimit` so new limit kinds can be added easily.
    - `model_ids` and `datasheet_url` are intentionally omitted (not needed in the model definition).
    - Drivers are authoritative for their supported models; no central registry required.
    """

    model: str
    variant: Optional[str] = None
    description: Optional[str] = None

    # Flexible limits mapping: key -> MotorLimit
    limits: Dict[str, MotorLimit] = Field(default_factory=dict)

    # Conversion/encoding helpers
    encoder_resolution: Optional[int] = None
    position_scale: Optional[float] = None
    encoding: Optional[str] = None
    endianness: Optional[str] = None
    gear_ratio: Optional[float] = None
    direction_inverted: Optional[bool] = None

    # Protocol references (point to shared objects in protocol tables)
    baudrates: Optional[List[int]] = None
    # operating_modes: Commonly represents the control modes this motor supports (e.g., 'position', 'velocity', 'torque', or protocol-specific numeric codes).
    # Recommendation: use an Enum where possible in driver code; in the model store a list of strings or ints so the schema remains protocol-agnostic.
    operating_modes: Optional[List[str]] = None
    registries: Optional[dict] = None


# Common limit type constants (recommended helpers)
LIMIT_VOLTAGE_MIN = "voltage_min"
LIMIT_VOLTAGE_MAX = "voltage_max"
LIMIT_CURRENT_MAX_MA = "current_max_ma"
LIMIT_TEMPERATURE_MAX_C = "temperature_max_c"
LIMIT_TORQUE_MAX_NM = "torque_max_nm"
```

Notes:
- `operating_modes` describes supported control modes and may be protocol-specific (examples: Dynamixel numeric mode codes, or strings like 'position'/'velocity'/'current'). Drivers should translate between protocol codes and higher-level enums when needed.
- `limits` maps limit-type strings to `MotorLimit` entries to make the set of limit kinds easily extensible and to centralize unit conventions (all in SI units).
- `model_ids` and `datasheet_url` were removed: model identification should be done by drivers, which own model->id mappings when needed.

```

## Why not put control tables in JSON (again)

- Control tables contain addresses, sizes, encodings and limits that are easiest to reason about when represented as typed Python objects. Keeping them in code:
  - Enables IDE static checking and safer refactors
  - Works naturally with protocol SDKs that expect typed constants
  - Simplifies writing deterministic unit tests and static validations

- If externalization is required (for runtime updates or non-developers to edit), prefer a **strict, versioned schema** and an external store (e.g., YAML with a schema or a configuration service) that is loaded and validated into typed Python objects at runtime. JSON files checked into the repo are discouraged because they encourage unsupported ad-hoc edits and reduce the benefits of typed code.

## Deliverables & Checklist

- [x] Specification document (this file)
- [ ] API interface definitions (type-annotated stubs under `services/hardware/`)
- [ ] Table definitions as typed Python modules and validation helpers (no JSON files for motor info)
- [ ] Driver changes to provide `identify_model` and SI unit telemetry outputs
- [ ] MotorBus implementation (sync_read/sync_write, torque_disabled, handshake)
- [ ] Tests for identification, unit conversion, batch operations, calibration

---

If you want, my next action is to create the initial API stub files and a sample `Feetech` driver adapter implementing `identify_model` and telemetry unit conversion, plus tests; select one of: 

- `A` — Implement Feetech changes first (identify + units + tests)
- `B` — Implement MotorBus + protocol base classes and tests
- `C` — Create `motor_tables.json` schema + loader and validation tests

Tell me which you'd prefer and I will proceed with a concrete PR plan and begin implementation.