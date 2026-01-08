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

# Import typed models for platform discovery
import cv2

# Import platform-specific libraries
import serial.tools.list_ports

from leropilot.models.hardware import PlatformCANInterface, PlatformSerialPort

logger = logging.getLogger(__name__)

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
        """Check if running on Windows"""
        return platform.system().lower() == "windows"

    @staticmethod
    def is_macos() -> bool:
        """Check if running on macOS"""
        return platform.system().lower() == "darwin"

    @staticmethod
    def is_linux() -> bool:
        """Check if running on Linux"""
        return platform.system().lower() == "linux"


def _map_device_to_pcan_channel(device_name: str, serial_number: str) -> str | None:
    """Map our detected device names to proper PCAN channel names.

    Args:
        device_name: Our internal device name (e.g., "PCAN_0C72_0011_0000")
        serial_number: Device serial number

    Returns:
        PCAN channel name (e.g., "PCAN_USBBUS1") or None if no mapping found
    """
    try:
        import can

        # Get available PCAN configurations
        configs = can.interface.detect_available_configs("pcan")
        if not configs:
            logger.debug("No PCAN configurations detected")
            return None

        # For now, map based on device suffix pattern
        # PCAN_0C72_0011_0000 -> PCAN_USBBUS1
        # PCAN_0C72_0011_0001 -> PCAN_USBBUS2
        if device_name.startswith("PCAN_") and "_0000" in device_name:
            return "PCAN_USBBUS1"
        elif device_name.startswith("PCAN_") and "_0001" in device_name:
            return "PCAN_USBBUS2"
        else:
            logger.debug(f"No PCAN channel mapping found for device: {device_name}")
            return None

    except Exception as e:
        logger.debug(f"Error mapping PCAN channel for {device_name}: {e}")
        return None


class SerialPortBackend(ABC):
    """Abstract base for platform-specific serial port discovery"""

    @abstractmethod
    def discover_ports(self) -> list["PlatformSerialPort"]:
        """
        Discover all serial ports.

        Returns:
            List of `PlatformSerialPort` objects describing discovered serial ports.
        """
        pass


class WindowsSerialBackend(SerialPortBackend):
    """Windows serial port discovery via COM ports"""

    def discover_ports(self) -> list["PlatformSerialPort"]:
        """Discover COM ports on Windows"""
        discovered: list[PlatformSerialPort] = []
        try:
            for port_info in serial.tools.list_ports.comports():
                # Use serial_number directly from pyserial (it extracts from hwid automatically)
                serial_number = port_info.serial_number if port_info.serial_number else None

                # Extract VID/PID - pyserial provides these as integers or None
                vid = f"{port_info.vid:04X}" if port_info.vid is not None else "0000"
                pid = f"{port_info.pid:04X}" if port_info.pid is not None else "0000"

                port_data = PlatformSerialPort(
                    port=port_info.device,
                    description=port_info.description,
                    hwid=port_info.hwid,
                    serial_number=serial_number,
                    manufacturer=port_info.manufacturer or "Unknown",
                    vid=vid,
                    pid=pid,
                )
                discovered.append(port_data)
                logger.debug(f"Windows: Found port {port_info.device}")

            logger.info(f"Windows: Found {len(discovered)} serial ports")
            return discovered
        except Exception as e:
            logger.error(f"Windows serial discovery error: {e}")
            return []


class UnixSerialBackend(SerialPortBackend):
    """Unix (macOS/Linux) serial port discovery"""

    def discover_ports(self) -> list["PlatformSerialPort"]:
        """Discover serial ports on macOS/Linux"""
        discovered: list[PlatformSerialPort] = []
        try:
            for port_info in serial.tools.list_ports.comports():
                # Use serial_number directly from pyserial (it extracts from hwid automatically)
                serial_number = port_info.serial_number if port_info.serial_number else None

                # Extract VID/PID - pyserial provides these as integers or None
                vid = f"{port_info.vid:04X}" if port_info.vid is not None else "0000"
                pid = f"{port_info.pid:04X}" if port_info.pid is not None else "0000"

                port_data = PlatformSerialPort(
                    port=port_info.device,
                    description=port_info.description,
                    hwid=port_info.hwid,
                    serial_number=serial_number,
                    manufacturer=port_info.manufacturer or "Unknown",
                    vid=vid,
                    pid=pid,
                )
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
    def discover_can_interfaces(self) -> list["PlatformCANInterface"]:
        """Discover CAN interfaces and return a list of `PlatformCANInterface` objects"""
        pass


class LinuxCANBackend(CANBackend):
    """Linux CAN interface discovery via SocketCAN"""

    def discover_can_interfaces(self) -> list["PlatformCANInterface"]:
        """Discover CAN interfaces on Linux (SocketCAN)"""
        discovered: list[PlatformCANInterface] = []
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
                        PlatformCANInterface(
                            interface=interface,
                            state=state,
                        )
                    )
                    logger.info(f"Linux: Found CAN interface {interface} ({state})")

            logger.info(f"Linux: Found {len(discovered)} CAN interfaces")
            return discovered
        except Exception as e:
            logger.debug(f"Linux CAN discovery error: {e}")
            return []


class WindowsCANBackend(CANBackend):
    """Windows CAN backend (via SLCAN adapters and specific USB CAN devices)"""

    def discover_can_interfaces(self) -> list["PlatformCANInterface"]:
        """Discover CAN interfaces on Windows via SLCAN adapters and known USB CAN devices"""
        # _discover_slcan_interfaces already includes USB CAN device detection for Windows
        discovered: list[PlatformCANInterface] = _discover_slcan_interfaces()
        logger.info(f"Windows: Found {len(discovered)} CAN interfaces")
        return discovered


class MacOSCANBackend(CANBackend):
    """macOS CAN backend (limited support)"""

    def discover_can_interfaces(self) -> list["PlatformCANInterface"]:
        """macOS: Limited native CAN support; SLCAN adapters appear as serial ports"""
        logger.debug("macOS: CAN support via SLCAN adapters only (discovered as serial ports)")
        return []


def _find_windows_can_devices() -> list:
    """Find known CAN devices on Windows that may not appear as serial ports"""
    devices = []

    # Create platform port_info objects for known CAN devices
    class PlatformPortInfo:
        def __init__(
            self,
            device: str,
            description: str = "CAN Device",
            vid: int | None = None,
            pid: int | None = None,
            manufacturer: str = "",
            product: str = "",
            hwid: str = "",
            serial_number: str | None = None,
        ) -> None:
            self.device = device
            self.description = description
            self.vid = vid
            self.pid = pid
            self.manufacturer = manufacturer
            self.product = product
            self.hwid = hwid
            self.serial_number = serial_number

    # Known CAN device VID/PID combinations
    known_can_devices = [
        # Peak Systems PCAN-USB
        (0x0C72, 0x000C, "Peak Systems", "PCAN-USB"),
        # Peak Systems PCAN-USB Pro FD
        (0x0C72, 0x0011, "Peak Systems", "PCAN-USB Pro FD"),
        # Kvaser devices
        (0x0BFD, None, "Kvaser", "CAN Device"),
        # Vector Informatik
        (0x1B91, None, "Vector Informatik", "CAN Device"),
        # ESD Electronics
        (0x0CE4, None, "ESD Electronics", "CAN Device"),
    ]

    # Check if these devices are present using Windows Management Instrumentation
    try:
        import subprocess

        # Use PowerShell to check for USB devices
        cmd = (
            "powershell \"Get-PnpDevice | Where-Object { $_.InstanceId -like '*VID_*' } | "
            'Select-Object FriendlyName,InstanceId"'
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines[2:]:  # Skip header lines
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        friendly_name = " ".join(parts[:-1])
                        instance_id = parts[-1]

                        # Check if this is a known CAN device
                        for known_vid, known_pid, manufacturer, product in known_can_devices:
                            if f"VID_{known_vid:04X}" in instance_id and (
                                known_pid is None or f"PID_{known_pid:04X}" in instance_id
                            ):
                                # Extract serial number from InstanceId
                                # Format: USB\VID_XXXX&PID_XXXX&MI_XX\serial_info
                                # The serial number is typically the last part after the final backslash
                                serial_parts = instance_id.split("\\")
                                if len(serial_parts) >= 2:
                                    # The last part is usually the serial number
                                    serial_candidate = serial_parts[-1]
                                    # Clean up the serial number (remove interface suffixes like &0000)
                                    if "&" in serial_candidate:
                                        # For USB devices, the serial number is often before the interface number
                                        serial_parts_amp = serial_candidate.split("&")
                                        # Look for a part that looks like a serial number (hex digits)
                                        for part in serial_parts_amp:
                                            if len(part) >= 6 and all(c in "0123456789ABCDEFabcdef" for c in part):
                                                serial_number = part
                                                break
                                        else:
                                            serial_number = serial_candidate.split("&")[0]
                                    else:
                                        serial_number = serial_candidate
                                else:
                                    serial_number = "unknown"

                                # Create unique device name based on instance ID
                                device_suffix = instance_id.split("&")[-1] if "&" in instance_id else "0"
                                device_name = f"PCAN_{known_vid:04X}_{known_pid or 0:04X}_{device_suffix}"
                                devices.append(
                                    PlatformPortInfo(
                                        device=device_name,
                                        description=friendly_name,
                                        vid=known_vid,
                                        pid=known_pid,
                                        manufacturer=manufacturer,
                                        product=product,
                                        hwid=instance_id,
                                        serial_number=f"{known_vid:04X}:{known_pid or 0:04X}:{serial_number}",
                                    )
                                )
                                logger.info(
                                    f"Found CAN device: {friendly_name} "
                                    f"({manufacturer} {product}) - {device_name} "
                                    f"Serial: {serial_number}"
                                )
                                break
    except Exception as e:
        logger.debug(f"Failed to enumerate CAN devices via PowerShell: {e}")

    logger.debug(f"Found {len(devices)} CAN devices")
    return devices


def _discover_slcan_interfaces() -> list[PlatformCANInterface]:
    """Common SLCAN interface discovery for Windows/macOS"""
    discovered = []

    # First try the standard pyserial method
    ports = serial.tools.list_ports.comports()
    logger.debug(f"pyserial found {len(ports)} ports")

    # Also try to find known CAN devices that may not appear as serial ports
    if platform.system() == "Windows":
        can_devices = _find_windows_can_devices()
        # Add CAN devices to ports list for processing
        ports.extend(can_devices)

    for port_info in ports:
        vid = port_info.vid
        pid = port_info.pid

        # Handle serial number formatting differently for PlatformPortInfo vs real port_info
        if hasattr(port_info, "__class__") and "PlatformPortInfo" in str(port_info.__class__):
            # This is from _find_windows_can_devices, serial_number is already formatted
            serial_number = port_info.serial_number
        else:
            # This is from pyserial, format the serial number
            serial_number = f"{vid}:{pid}:{port_info.serial_number}" if port_info.serial_number else None
        manufacturer = port_info.manufacturer or ""
        product = port_info.product or ""

        # Check for Peak Systems PCAN-USB (including Pro FD)
        if vid == 0x0C72 and (pid == 0x000C or pid == 0x0011):
            # Map our detected device names to proper PCAN channel names
            pcan_channel = _map_device_to_pcan_channel(port_info.device, serial_number)
            if pcan_channel:
                discovered.append(
                    PlatformCANInterface(
                        interface=f"pcan:{pcan_channel}",
                        manufacturer=manufacturer,
                        product=product,
                        vid=f"{vid:04X}",
                        pid=f"{pid:04X}",
                        serial_number=serial_number,
                    )
                )
                logger.info(f"Found PCAN-USB device on {pcan_channel}")

        # Check for Kvaser devices
        elif vid == 0x0BFD:
            discovered.append(
                PlatformCANInterface(
                    interface=f"kvaser:{port_info.device}",
                    manufacturer=manufacturer,
                    product=product,
                    vid=f"{vid:04X}",
                    pid=f"{pid:04X}",
                    serial_number=serial_number,
                )
            )
            logger.info(f"Found Kvaser device on {port_info.device}")

        # Check for Vector Informatik devices
        elif vid == 0x1B91:
            discovered.append(
                PlatformCANInterface(
                    interface=f"vector:{port_info.device}",
                    manufacturer=manufacturer,
                    product=product,
                    vid=f"{vid:04X}",
                    pid=f"{pid:04X}",
                    serial_number=serial_number,
                )
            )
            logger.info(f"Found Vector device on {port_info.device}")

        # Check for ESD Electronics devices
        elif vid == 0x0CE4:
            discovered.append(
                PlatformCANInterface(
                    interface=f"esd:{port_info.device}",
                    manufacturer=manufacturer,
                    product=product,
                    vid=f"{vid:04X}",
                    pid=f"{pid:04X}",
                    serial_number=serial_number,
                )
            )
            logger.info(f"Found ESD device on {port_info.device}")

        # Generic SLCAN detection - test actual SLCAN communication
        else:
            # Try to verify if this is actually an SLCAN device by testing communication
            if _test_slcan_device(port_info.device):
                discovered.append(
                    PlatformCANInterface(
                        interface=f"slcan:{port_info.device}",
                        manufacturer=manufacturer,
                        product=product,
                        vid=f"{vid:04X}" if vid else "0000",
                        pid=f"{pid:04X}" if pid else "0000",
                        serial_number=serial_number,
                    )
                )
                logger.info(f"Found SLCAN device on {port_info.device} (verified by communication)")

    return discovered


def _test_slcan_device(port: str, timeout: float = 1.0) -> bool:
    """Test if a serial port is connected to an SLCAN device by attempting communication.

    Args:
        port: Serial port name (e.g., 'COM3', '/dev/ttyUSB0')
        timeout: Timeout in seconds for the test

    Returns:
        True if the device responds like an SLCAN device, False otherwise
    """

    import serial

    try:
        # Try to open the port with common SLCAN settings
        ser = serial.Serial(
            port=port,
            baudrate=115200,  # Common SLCAN baudrate
            timeout=timeout,
            write_timeout=timeout,
        )

        # Clear any pending data
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # Send SLCAN version command
        ser.write(b"V\r")

        # Wait for response
        response = ser.read(10)  # Read up to 10 bytes

        # Close the port
        ser.close()

        # Check if we got a response that looks like SLCAN version
        # SLCAN version response typically starts with 'V' followed by version digits
        if response and response.startswith(b"V") and len(response) >= 2:
            logger.debug(f"SLCAN test successful on {port}: {response}")
            return True
        else:
            logger.debug(f"No SLCAN response on {port}: {response}")
            return False

    except (serial.SerialException, OSError) as e:
        logger.debug(f"Failed to test SLCAN on {port}: {e}")
        return False
    except Exception as e:
        logger.debug(f"Unexpected error testing SLCAN on {port}: {e}")
        return False


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

    def discover_serial_ports(self) -> list["PlatformSerialPort"]:
        """Discover all serial ports (returns `PlatformSerialPort` instances)"""
        return self.serial_backend.discover_ports()

    def discover_cameras(self) -> list[dict]:
        """Discover all cameras (USB + RealSense)"""
        usb_cameras = self.camera_backend.discover_usb_cameras()
        realsense_cameras = self.camera_backend.discover_realsense_cameras()
        return usb_cameras + realsense_cameras

    def discover_can_interfaces(self) -> list["PlatformCANInterface"]:
        """Discover all CAN interfaces (returns `PlatformCANInterface` instances)"""
        return self.can_backend.discover_can_interfaces()
