"""
Message cache for Damiao CAN bus communication.

Provides thread-safe caching of CAN messages to reduce bus traffic and improve performance.
Stores raw bytes without parsing to avoid blocking in receive thread.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Event, Lock

logger = logging.getLogger(__name__)


@dataclass
class CachedMessage:
    """Cached raw CAN message with timestamp.

    Stores only raw bytes without parsing to keep receive thread non-blocking.
    Parsing is deferred to read time when parameter values are available.
    """

    timestamp: float
    """Time when message was received (time.time())"""

    raw_data: bytes
    """8-byte CAN data payload"""

    arbitration_id: int
    """CAN arbitration ID"""


class MessageCache:
    """Thread-safe cache for CAN messages.

    Caches two types of messages:
    1. Motor status feedback (position, velocity, torque, temps) - one per motor
    2. Parameter read/write responses - one per (motor_id, register_id) pair

    All messages stored as raw bytes. Parsing deferred to read time.
    """

    def __init__(self, max_age: float = 1.0) -> None:
        """Initialize message cache.

        Args:
            max_age: Maximum age in seconds for cached data to be considered valid.
                     Status messages typically need fresh data (< 1s).
                     Parameter messages can be cached longer.
        """
        self.max_age = max_age
        self._lock = Lock()

        # Status cache: motor_id -> CachedMessage (latest status feedback frame)
        self._status_cache: dict[tuple[int, int], CachedMessage] = {}

        # Parameter cache: (motor_id, register_id) -> CachedMessage (parameter read/write response)
        self._param_cache: dict[tuple[tuple[int, int], int], CachedMessage] = {}

        # Parameter wait events: (motor_id, register_id) -> Event
        # Used to wait for parameter responses after sending read/write commands
        self._param_events: dict[tuple[tuple[int, int], int], Event] = defaultdict(Event)

    def update_status(self, motor_id: tuple[int, int], msg_data: bytes, arb_id: int) -> None:
        """Update status cache with latest motor feedback frame.

        Called by receive thread when status feedback arrives.
        Stores raw bytes without parsing.

        Args:
            motor_id: Motor identifier (send_id, recv_id)
            msg_data: 8-byte CAN data payload
            arb_id: CAN arbitration ID
        """
        with self._lock:
            self._status_cache[motor_id] = CachedMessage(
                timestamp=time.time(), raw_data=msg_data, arbitration_id=arb_id
            )

    def get_status_raw(self, motor_id: tuple[int, int], max_age: float | None = None) -> bytes | None:
        """Get raw status data for a motor.

        Caller is responsible for parsing bytes using appropriate pmax/vmax/tmax values.

        Args:
            motor_id: Motor identifier (send_id, recv_id)
            max_age: Maximum age in seconds. If None, uses default max_age.

        Returns:
            8-byte raw CAN data if available and fresh, None otherwise.
        """
        max_age = max_age or self.max_age
        with self._lock:
            cached = self._status_cache.get(motor_id)
            if cached and (time.time() - cached.timestamp) < max_age:
                return cached.raw_data
            return None

    def update_parameter(self, motor_id: tuple[int, int], register_id: int, msg_data: bytes, arb_id: int) -> None:
        """Update parameter cache and notify waiting threads.

        Called by receive thread when parameter read/write response arrives.
        Stores raw bytes without parsing (caller determines int vs float).

        Args:
            motor_id: Motor identifier (send_id, recv_id)
            register_id: Register address (RID)
            msg_data: 8-byte CAN data payload
            arb_id: CAN arbitration ID
        """
        key = (motor_id, register_id)
        with self._lock:
            self._param_cache[key] = CachedMessage(timestamp=time.time(), raw_data=msg_data, arbitration_id=arb_id)
            # Notify any threads waiting for this parameter
            if key in self._param_events:
                self._param_events[key].set()

    def get_parameter_raw(
        self, motor_id: tuple[int, int], register_id: int, max_age: float | None = None
    ) -> bytes | None:
        """Get raw parameter data.

        Caller is responsible for parsing bytes as int or float based on register type.

        Args:
            motor_id: Motor identifier (send_id, recv_id)
            register_id: Register address (RID)
            max_age: Maximum age in seconds. If None, ignore age check.
        Returns:
            8-byte raw CAN data if available and fresh, None otherwise.
        """
        key = (motor_id, register_id)
        with self._lock:
            cached = self._param_cache.get(key)
            if cached and (max_age is None or (time.time() - cached.timestamp) < max_age):
                return cached.raw_data
            return None

    def wait_for_parameter(self, motor_id: tuple[int, int], register_id: int, timeout: float = 1.0) -> bool:
        """Wait for parameter response to arrive.

        Used after sending a read/write command to wait for the response.
        More reliable than fixed sleep delays.

        Args:
            motor_id: Motor identifier (send_id, recv_id)
            register_id: Register address (RID)
            timeout: Maximum time to wait in seconds

        Returns:
            True if parameter arrived, False if timeout
        """
        key = (motor_id, register_id)
        event = self._param_events[key]
        event.clear()
        return event.wait(timeout)

    def clear(self) -> None:
        """Clear all cached messages and wake waiting threads.

        Called on disconnect to ensure clean state and prevent deadlocks.
        """
        with self._lock:
            self._status_cache.clear()
            self._param_cache.clear()
            # Wake all waiting threads so they don't hang on disconnect
            for event in self._param_events.values():
                event.set()
            self._param_events.clear()
        logger.debug("Message cache cleared")
