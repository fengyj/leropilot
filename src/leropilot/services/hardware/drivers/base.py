"""
Abstract base driver for motor bus communication.

All motor drivers inherit from this base class and implement protocol-specific logic.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from leropilot.models.hardware import MotorInfo, MotorTelemetry


class BaseMotorDriver(ABC):
    """Abstract base class for motor bus drivers"""

    def __init__(self, interface: str, baud_rate: Optional[int] = None):
        """
        Initialize driver.
        
        Args:
            interface: Communication interface (e.g., "COM11", "can0")
            baud_rate: Baud rate (serial) or bit rate (CAN)
        """
        self.interface = interface
        self.baud_rate = baud_rate
        self.connected = False

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the motor bus.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from the motor bus.
        
        Returns:
            True if disconnection successful
        """
        pass

    @abstractmethod
    def ping_motor(self, motor_id: int) -> bool:
        """
        Check if motor with given ID is on the bus.
        
        Args:
            motor_id: Motor ID (1-254)
            
        Returns:
            True if motor responds
        """
        pass

    @abstractmethod
    def scan_motors(self, scan_range: Optional[List[int]] = None) -> List[MotorInfo]:
        """
        Scan motor bus and discover all motors.
        
        Args:
            scan_range: List of motor IDs to scan (default: 1-253)
            
        Returns:
            List of discovered motors
        """
        pass

    @abstractmethod
    def read_telemetry(self, motor_id: int) -> Optional[MotorTelemetry]:
        """
        Read real-time telemetry from a single motor.
        
        Args:
            motor_id: Motor ID
            
        Returns:
            Motor telemetry data or None if read fails
        """
        pass

    @abstractmethod
    def read_bulk_telemetry(self, motor_ids: List[int]) -> Dict[int, MotorTelemetry]:
        """
        Read telemetry from multiple motors efficiently.
        
        Args:
            motor_ids: List of motor IDs
            
        Returns:
            Dict mapping motor_id -> telemetry
        """
        pass

    @abstractmethod
    def set_position(self, motor_id: int, position: int, speed: Optional[int] = None) -> bool:
        """
        Set motor target position.
        
        Args:
            motor_id: Motor ID
            position: Target position (raw encoder units or raw values)
            speed: Optional movement speed
            
        Returns:
            True if command sent successfully
        """
        pass

    @abstractmethod
    def set_torque(self, motor_id: int, enabled: bool) -> bool:
        """
        Enable or disable motor torque.
        
        Args:
            motor_id: Motor ID
            enabled: True to enable torque, False to disable
            
        Returns:
            True if command sent successfully
        """
        pass

    @abstractmethod
    def reboot_motor(self, motor_id: int) -> bool:
        """
        Reboot a single motor.
        
        Args:
            motor_id: Motor ID
            
        Returns:
            True if reboot command sent
        """
        pass

    @abstractmethod
    def bulk_set_torque(self, motor_ids: List[int], enabled: bool) -> bool:
        """
        Set torque for multiple motors at once (more efficient than individual calls).
        
        Args:
            motor_ids: List of motor IDs
            enabled: True to enable, False to disable
            
        Returns:
            True if all commands sent successfully
        """
        pass

    def is_connected(self) -> bool:
        """Check if driver is connected"""
        return self.connected

    def __enter__(self):
        """Context manager support"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.disconnect()
        return False
