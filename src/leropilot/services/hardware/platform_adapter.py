"""
Platform abstraction layer for cross-platform hardware access.

Provides unified interface for:
- Serial port enumeration (Windows/macOS/Linux)
- Camera discovery (USB + RealSense)
- CAN interface enumeration (Linux)
- File system operations
- Process management

Each operation has platform-specific implementations, but exposes
a common interface so services don't need to know about OS differences.
"""

import logging
import platform
import subprocess
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Try to import platform-specific libraries
try:
    import serial.tools.list_ports

    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False

try:
    import cv2

    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

try:
    import pyrealsense2 as rs

    HAS_REALSENSE = True
except ImportError:
    HAS_REALSENSE = False


class PlatformDetector:
    """Detect and identify current OS"""

    @staticmethod
    def get_platform() -> str:
        """Get platform: 'windows', 'darwin', or 'linux'"""
        return platform.system().lower()

    @staticmethod
    def is_windows() -> bool:
        return PlatformDetector.get_platform() == "windows"

    @staticmethod
    def is_macos() -> bool:
        return PlatformDetector.get_platform() == "darwin"

    @staticmethod
    def is_linux() -> bool:
        return PlatformDetector.get_platform() == "linux"


class SerialPortBackend(ABC):
    """Abstract base for platform-specific serial port discovery"""

    @abstractmethod
    def discover_ports(self) -> list[dict]:
        """
        Discover all serial ports.

        Returns:
            List of dicts: {port, description, hwid, serial_number, manufacturer}
        """
        pass


class WindowsSerialBackend(SerialPortBackend):
    """Windows serial port discovery via COM ports"""

    def discover_ports(self) -> list[dict]:
        """Discover COM ports on Windows"""
        if not HAS_PYSERIAL:
            return []

        discovered = []
        try:
            for port_info in serial.tools.list_ports.comports():
                # Use serial_number directly from pyserial (it extracts from hwid automatically)
                serial_number = port_info.serial_number if port_info.serial_number else None

                # Extract VID/PID - pyserial provides these as integers or None
                vid = f"{port_info.vid:04X}" if port_info.vid is not None else "0000"
                pid = f"{port_info.pid:04X}" if port_info.pid is not None else "0000"

                port_data = {
                    "port": port_info.device,
                    "description": port_info.description,
                    "hwid": port_info.hwid,
                    "serial_number": serial_number,
                    "manufacturer": port_info.manufacturer or "Unknown",
                    "vid": vid,
                    "pid": pid,
                }
                discovered.append(port_data)
                logger.debug(f"Windows: Found port {port_info.device}")

            logger.info(f"Windows: Found {len(discovered)} serial ports")
            return discovered
        except Exception as e:
            logger.error(f"Windows serial discovery error: {e}")
            return []


class UnixSerialBackend(SerialPortBackend):
    """Unix (macOS/Linux) serial port discovery"""

    def discover_ports(self) -> list[dict]:
        """Discover serial ports on macOS/Linux"""
        if not HAS_PYSERIAL:
            return []

        discovered = []
        try:
            for port_info in serial.tools.list_ports.comports():
                # Use serial_number directly from pyserial (it extracts from hwid automatically)
                serial_number = port_info.serial_number if port_info.serial_number else None

                # Extract VID/PID - pyserial provides these as integers or None
                vid = f"{port_info.vid:04X}" if port_info.vid is not None else "0000"
                pid = f"{port_info.pid:04X}" if port_info.pid is not None else "0000"

                port_data = {
                    "port": port_info.device,
                    "description": port_info.description,
                    "hwid": port_info.hwid,
                    "serial_number": serial_number,
                    "manufacturer": port_info.manufacturer or "Unknown",
                    "vid": vid,
                    "pid": pid,
                }
                discovered.append(port_data)
                logger.debug(f"Unix: Found port {port_info.device}")

            logger.info(f"Unix: Found {len(discovered)} serial ports")
            return discovered
        except Exception as e:
            logger.error(f"Unix serial discovery error: {e}")
            return []


class CameraBackend(ABC):
    """Abstract base for platform-specific camera discovery"""

    @abstractmethod
    def discover_usb_cameras(self) -> list[dict]:
        """Discover USB video class cameras"""
        pass

    @abstractmethod
    def discover_realsense_cameras(self) -> list[dict]:
        """Discover RealSense depth cameras"""
        pass


class WindowsCameraBackend(CameraBackend):
    """Windows camera discovery using DirectShow via OpenCV"""

    def discover_usb_cameras(self) -> list[dict]:
        """Discover USB cameras on Windows (via DirectShow)"""
        if not HAS_OPENCV:
            return []

        discovered = []
        try:
            # Windows typically uses DirectShow; OpenCV handles this via CAP_DSHOW
            for index in range(10):
                cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    discovered.append(
                        {
                            "index": index,
                            "name": f"Camera {index}",
                            "width": width,
                            "height": height,
                            "type": "USB",
                        }
                    )
                    logger.info(f"Windows: Found camera {index} ({width}x{height})")
                    cap.release()

            logger.info(f"Windows: Found {len(discovered)} USB cameras")
            return discovered
        except Exception as e:
            logger.error(f"Windows camera discovery error: {e}")
            return []

    def discover_realsense_cameras(self) -> list[dict]:
        """Discover RealSense cameras on Windows"""
        if not HAS_REALSENSE:
            return []

        discovered = []
        try:
            context = rs.context()
            devices = context.query_devices()

            for device in devices:
                discovered.append(
                    {
                        "serial_number": device.get_info(rs.camera_info.serial_number),
                        "name": device.get_info(rs.camera_info.name),
                        "type": "RealSense",
                        "firmware": device.get_info(rs.camera_info.firmware_version),
                    }
                )
                logger.info(f"Windows: Found RealSense {discovered[-1]['name']}")

            logger.info(f"Windows: Found {len(discovered)} RealSense cameras")
            return discovered
        except Exception as e:
            logger.error(f"Windows RealSense discovery error: {e}")
            return []


class UnixCameraBackend(CameraBackend):
    """Unix (macOS/Linux) camera discovery"""

    def discover_usb_cameras(self) -> list[dict]:
        """Discover USB cameras on macOS/Linux"""
        if not HAS_OPENCV:
            return []

        discovered = []
        try:
            for index in range(10):
                cap = cv2.VideoCapture(index)
                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    discovered.append(
                        {
                            "index": index,
                            "name": f"Camera {index}",
                            "width": width,
                            "height": height,
                            "type": "USB",
                        }
                    )
                    logger.info(f"Unix: Found camera {index} ({width}x{height})")
                    cap.release()

            logger.info(f"Unix: Found {len(discovered)} USB cameras")
            return discovered
        except Exception as e:
            logger.error(f"Unix camera discovery error: {e}")
            return []

    def discover_realsense_cameras(self) -> list[dict]:
        """Discover RealSense cameras on Unix"""
        if not HAS_REALSENSE:
            return []

        discovered = []
        try:
            context = rs.context()
            devices = context.query_devices()

            for device in devices:
                discovered.append(
                    {
                        "serial_number": device.get_info(rs.camera_info.serial_number),
                        "name": device.get_info(rs.camera_info.name),
                        "type": "RealSense",
                        "firmware": device.get_info(rs.camera_info.firmware_version),
                    }
                )
                logger.info(f"Unix: Found RealSense {discovered[-1]['name']}")

            logger.info(f"Unix: Found {len(discovered)} RealSense cameras")
            return discovered
        except Exception as e:
            logger.error(f"Unix RealSense discovery error: {e}")
            return []


class CANBackend(ABC):
    """Abstract base for platform-specific CAN interface discovery"""

    @abstractmethod
    def discover_can_interfaces(self) -> list[dict]:
        """Discover CAN interfaces"""
        pass


class LinuxCANBackend(CANBackend):
    """Linux CAN interface discovery via SocketCAN"""

    def discover_can_interfaces(self) -> list[dict]:
        """Discover CAN interfaces on Linux (SocketCAN)"""
        discovered = []
        try:
            result = subprocess.run(
                ["ip", "link", "show", "type", "can"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                logger.debug("No CAN interfaces found on Linux")
                return []

            for line in result.stdout.split("\n"):
                if not line.strip():
                    continue

                if ":" in line:
                    interface = line.split(":")[0].strip()
                    state = "UP" if "UP" in line else "DOWN"
                    discovered.append(
                        {
                            "interface": interface,
                            "state": state,
                            "bitrate": 1000000,
                        }
                    )
                    logger.info(f"Linux: Found CAN interface {interface} ({state})")

            logger.info(f"Linux: Found {len(discovered)} CAN interfaces")
            return discovered
        except Exception as e:
            logger.debug(f"Linux CAN discovery error: {e}")
            return []


class WindowsCANBackend(CANBackend):
    """Windows CAN backend (via SLCAN adapters only)"""

    def discover_can_interfaces(self) -> list[dict]:
        """Windows doesn't have native CAN support; only SLCAN adapters appear as serial ports"""
        logger.debug("Windows: CAN support via SLCAN adapters only (discovered as serial ports)")
        return []


class MacOSCANBackend(CANBackend):
    """macOS CAN backend (limited support)"""

    def discover_can_interfaces(self) -> list[dict]:
        """macOS: Limited native CAN support; SLCAN adapters appear as serial ports"""
        logger.debug("macOS: CAN support via SLCAN adapters only (discovered as serial ports)")
        return []


class PlatformAdapter:
    """
    Unified platform adapter that delegates to platform-specific backends.

    Services use this adapter instead of calling platform-specific code directly,
    ensuring clean separation of concerns and easy testing.
    """

    def __init__(self) -> None:
        """Initialize adapter with platform-specific backends"""
        self.platform = PlatformDetector.get_platform()
        logger.info(f"PlatformAdapter initialized for {self.platform}")

        # Create platform-specific backends
        if PlatformDetector.is_windows():
            self.serial_backend: SerialPortBackend = WindowsSerialBackend()
            self.camera_backend: CameraBackend = WindowsCameraBackend()
            self.can_backend: CANBackend = WindowsCANBackend()
        elif PlatformDetector.is_macos():
            self.serial_backend = UnixSerialBackend()
            self.camera_backend = UnixCameraBackend()
            self.can_backend = MacOSCANBackend()
        else:  # Linux
            self.serial_backend = UnixSerialBackend()
            self.camera_backend = UnixCameraBackend()
            self.can_backend = LinuxCANBackend()

    def discover_serial_ports(self) -> list[dict]:
        """Discover all serial ports"""
        return self.serial_backend.discover_ports()

    def discover_cameras(self) -> list[dict]:
        """Discover all cameras (USB + RealSense)"""
        usb_cameras = self.camera_backend.discover_usb_cameras()
        realsense_cameras = self.camera_backend.discover_realsense_cameras()
        return usb_cameras + realsense_cameras

    def discover_can_interfaces(self) -> list[dict]:
        """Discover all CAN interfaces (Linux only)"""
        return self.can_backend.discover_can_interfaces()
