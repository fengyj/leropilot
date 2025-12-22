"""
Camera capture and streaming service.

Supports:
- USB video class cameras (via OpenCV)
- Intel RealSense depth cameras (D415, D435, etc.)
- Snapshot capture
- Camera enumeration and info retrieval
- Real-time streaming frames (generator pattern)

Works cross-platform (Windows/macOS/Linux).
"""

import logging
from typing import Optional, List, Dict, Generator
import numpy as np

logger = logging.getLogger(__name__)

# Try to import camera libraries
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    logger.warning("opencv-python not installed; USB camera support disabled")

try:
    import pyrealsense2 as rs
    HAS_REALSENSE = True
except ImportError:
    HAS_REALSENSE = False
    logger.warning("pyrealsense2 not installed; RealSense support disabled")


class CameraInfo:
    """Metadata for a camera"""

    def __init__(
        self,
        index: int,
        name: str,
        camera_type: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: Optional[int] = None,
        serial_number: Optional[str] = None,
        vid: Optional[str] = None,
        pid: Optional[str] = None,
        manufacturer: Optional[str] = None,
    ):
        self.index = index
        self.name = name
        self.camera_type = camera_type  # "USB" or "RealSense"
        self.width = width
        self.height = height
        self.fps = fps
        self.serial_number = serial_number  # Unique identifier
        self.vid = vid  # Vendor ID
        self.pid = pid  # Product ID
        self.manufacturer = manufacturer  # Manufacturer name

    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "name": self.name,
            "type": self.camera_type,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "serial_number": self.serial_number,
            "vid": self.vid,
            "pid": self.pid,
            "manufacturer": self.manufacturer,
        }


class USBCamera:
    """Wrapper for USB video class cameras"""

    def __init__(self, index: int, width: int = 640, height: int = 480, fps: int = 30):
        """
        Initialize USB camera.

        Args:
            index: Camera index (0, 1, 2, ...)
            width: Frame width
            height: Frame height
            fps: Target frames per second
        """
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_open = False

    def open(self) -> bool:
        """Open camera device"""
        if not HAS_OPENCV:
            logger.error("OpenCV not available")
            return False

        try:
            self.cap = cv2.VideoCapture(self.index)
            if not self.cap.isOpened():
                logger.error(f"Failed to open USB camera {self.index}")
                return False

            # Set resolution and FPS
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)

            self.is_open = True
            logger.info(f"Opened USB camera {self.index} ({self.width}x{self.height}@{self.fps}fps)")
            return True
        except Exception as e:
            logger.error(f"Error opening USB camera {self.index}: {e}")
            return False

    def capture_frame(self) -> Optional[np.ndarray]:
        """
        Capture single frame.

        Returns:
            Frame as numpy array (BGR) or None if capture fails
        """
        if not self.is_open or not self.cap:
            return None

        try:
            ret, frame = self.cap.read()
            if ret:
                return frame
            else:
                logger.warning(f"Failed to read frame from USB camera {self.index}")
                return None
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None

    def close(self) -> None:
        """Close camera device"""
        if self.cap:
            self.cap.release()
        self.is_open = False
        logger.info(f"Closed USB camera {self.index}")

    def __enter__(self):
        """Context manager support"""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.close()


class RealSenseCamera:
    """Wrapper for Intel RealSense depth cameras"""

    def __init__(self, serial_number: Optional[str] = None, width: int = 640, height: int = 480, fps: int = 30):
        """
        Initialize RealSense camera.

        Args:
            serial_number: Camera serial number (None to use first available)
            width: RGB frame width
            height: RGB frame height
            fps: Target frames per second
        """
        self.serial_number = serial_number
        self.width = width
        self.height = height
        self.fps = fps
        self.pipeline: Optional[rs.pipeline] = None
        self.config: Optional[rs.config] = None
        self.is_open = False

    def open(self) -> bool:
        """Open RealSense camera"""
        if not HAS_REALSENSE:
            logger.error("RealSense SDK not available")
            return False

        try:
            self.pipeline = rs.pipeline()
            self.config = rs.config()

            # Configure streams
            self.config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
            self.config.enable_stream(rs.stream.depth, self.width, self.height, rs.format.z16, self.fps)

            # If serial number specified, connect to that specific camera
            if self.serial_number:
                self.config.enable_device(self.serial_number)

            self.pipeline.start(self.config)
            self.is_open = True
            logger.info(
                f"Opened RealSense camera {self.serial_number or 'default'} ({self.width}x{self.height}@{self.fps}fps)"
            )
            return True
        except Exception as e:
            logger.error(f"Error opening RealSense camera: {e}")
            return False

    def capture_frame(self) -> Optional[Dict[str, np.ndarray]]:
        """
        Capture frame from RealSense camera.

        Returns:
            Dict with 'color' and 'depth' frames or None if capture fails
        """
        if not self.is_open or not self.pipeline:
            return None

        try:
            frames = self.pipeline.wait_for_frames()

            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()

            if not color_frame or not depth_frame:
                return None

            # Convert to numpy arrays
            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())

            return {
                "color": color_image,
                "depth": depth_image,
            }
        except Exception as e:
            logger.error(f"Error capturing RealSense frame: {e}")
            return None

    def close(self) -> None:
        """Close camera"""
        if self.pipeline:
            self.pipeline.stop()
        self.is_open = False
        logger.info(f"Closed RealSense camera {self.serial_number or 'default'}")

    def __enter__(self):
        """Context manager support"""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.close()


class CameraService:
    """High-level camera management service"""

    def __init__(self):
        """Initialize camera service"""
        logger.info("CameraService initialized")

    def list_cameras(self) -> List[CameraInfo]:
        """
        List all available cameras (USB + RealSense).

        Returns:
            List of CameraInfo objects
        """
        cameras = []

        # Enumerate USB cameras
        if HAS_OPENCV:
            try:
                # Get camera metadata (platform-specific)
                camera_metadata = self._get_camera_metadata()
                
                # Always check at least 10 indices, regardless of metadata count
                # This ensures we find cameras that WMI might have missed
                for index in range(10):
                    cap = cv2.VideoCapture(index)
                    if cap.isOpened():
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        
                        # Try to match with metadata by index first
                        # If no match, use default values
                        meta = camera_metadata.get(index, {})
                        name = meta.get('name', f"USB Camera {index}")
                        serial = meta.get('serial_number')
                        vid = meta.get('vid')
                        pid = meta.get('pid')
                        manufacturer = meta.get('manufacturer', 'Unknown')
                        
                        cameras.append(CameraInfo(
                            index=index,
                            name=name,
                            camera_type="USB",
                            width=width,
                            height=height,
                            serial_number=serial,
                            vid=vid,
                            pid=pid,
                            manufacturer=manufacturer
                        ))
                        cap.release()
                        logger.debug(f"Found USB camera {index}: {name}")
            except Exception as e:
                logger.error(f"Error enumerating USB cameras: {e}")
        
        # Enumerate RealSense cameras
        if HAS_REALSENSE:
            try:
                context = rs.context()
                devices = context.query_devices()

                for i, device in enumerate(devices):
                    sn = device.get_info(rs.camera_info.serial_number)
                    name = device.get_info(rs.camera_info.name)
                    cameras.append(CameraInfo(
                        index=i,
                        name=f"{name} (SN: {sn})",
                        camera_type="RealSense",
                        serial_number=sn
                    ))
            except Exception as e:
                logger.error(f"Error enumerating RealSense cameras: {e}")

        logger.info(f"Found {len(cameras)} cameras")
        return cameras
    
    def _get_camera_metadata(self) -> Dict[int, Dict]:
        """
        Get camera metadata (name, serial number, VID/PID) for each camera index.
        
        Returns:
            Dictionary mapping camera index to metadata dict
        """
        import platform
        system = platform.system()
        
        if system == "Windows":
            return self._get_camera_metadata_windows()
        elif system == "Linux":
            return self._get_camera_metadata_linux()
        elif system == "Darwin":
            return self._get_camera_metadata_macos()
        else:
            logger.warning(f"Camera metadata not supported on {system}")
            return {}
    
    def _get_camera_metadata_windows(self) -> Dict[int, Dict]:
        """Get camera metadata on Windows using wmi package"""
        try:
            try:
                import wmi  # type: ignore[import-not-found]
                use_wmi = True
            except ImportError:
                logger.debug("wmi package not installed, falling back to PowerShell")
                use_wmi = False
            
            camera_map = {}
            
            if use_wmi:
                # Use wmi package for better device information
                c = wmi.WMI()
                
                # Collect all camera devices from WMI
                wmi_cameras = []
                for driver in c.Win32_PnPSignedDriver():
                    device_class = driver.DeviceClass or ""
                    device_name = (driver.DeviceName or "").lower()
                    device_id = (driver.DeviceID or "").upper()
                    
                    # Check for camera-related devices (exclude audio)
                    is_camera = (
                        device_class in ("Image", "Camera") or
                        "camera" in device_name or
                        "webcam" in device_name
                    )
                    
                    is_audio = (
                        "audio" in device_name or
                        "microphone" in device_name or
                        "sound" in device_name or
                        "INTELAUDIO" in device_id
                    )
                    
                    if not is_camera or is_audio:
                        continue
                    
                    # Extract VID/PID/Serial from DeviceID
                    # Format: USB\VID_xxxx&PID_yyyy\serial
                    vid, pid, serial = None, None, None
                    if 'VID_' in device_id and 'PID_' in device_id:
                        parts = device_id.split('\\')
                        for part in parts:
                            if 'VID_' in part:
                                vid = part.split('VID_')[1].split('&')[0]
                            if 'PID_' in part:
                                pid = part.split('PID_')[1].split('&')[0] if '&' in part else part.split('PID_')[1]
                        # Serial number is usually the last part
                        if len(parts) >= 3 and parts[-1] and parts[-1] not in ['0', '0000', '']:
                            serial = parts[-1]
                    
                    wmi_cameras.append({
                        'name': driver.DeviceName or 'Unknown Camera',
                        'manufacturer': driver.Manufacturer or 'Unknown',
                        'serial_number': serial,
                        'vid': vid,
                        'pid': pid
                    })
                
                # Map WMI cameras to indices (best effort - order may not match OpenCV)
                # OpenCV will enumerate independently, this is just for metadata
                for idx, cam_info in enumerate(wmi_cameras):
                    camera_map[idx] = cam_info
                
                logger.debug(f"WMI found {len(wmi_cameras)} camera devices")
                return camera_map
            
            else:
                # Fallback to PowerShell if wmi not available
                import subprocess
                import json
                
                ps_command = """
                Get-CimInstance -ClassName Win32_PnPEntity | 
                Where-Object { 
                    ($_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image') -and 
                    $_.Status -eq 'OK' 
                } | 
                Select-Object Name, DeviceID, Manufacturer, Status | 
                ConvertTo-Json
                """
                
                result = subprocess.run(
                    ["powershell", "-Command", ps_command],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode != 0:
                    logger.debug(f"WMI camera query failed: {result.stderr}")
                    return {}
                
                devices = json.loads(result.stdout)
                if not isinstance(devices, list):
                    devices = [devices] if devices else []
                
                # Parse device info and map to indices
                for idx, device in enumerate(devices):
                    device_id = device.get('DeviceID', '')
                    name = device.get('Name', f'USB Camera {idx}')
                    manufacturer = device.get('Manufacturer', 'Unknown')
                    
                    # Extract VID/PID from DeviceID (format: USB\VID_xxxx&PID_yyyy\serial)
                    vid, pid, serial = None, None, None
                    if 'VID_' in device_id and 'PID_' in device_id:
                        parts = device_id.split('\\')
                        for part in parts:
                            if 'VID_' in part:
                                vid = part.split('VID_')[1].split('&')[0]
                            if 'PID_' in part:
                                pid = part.split('PID_')[1].split('&')[0] if '&' in part else part.split('PID_')[1]
                        # Serial number is usually the last part
                        if len(parts) > 2 and parts[-1] and parts[-1] not in ['OK', 'Error']:
                            serial = parts[-1]
                    
                    camera_map[idx] = {
                        'name': name,
                        'manufacturer': manufacturer,
                        'serial_number': serial,
                        'vid': vid,
                        'pid': pid
                    }
                
                return camera_map
            
        except Exception as e:
            logger.debug(f"Error getting Windows camera metadata: {e}")
            return {}
    
    def _get_camera_metadata_linux(self) -> Dict[int, Dict]:
        """Get camera metadata on Linux from /dev/v4l/by-id/"""
        try:
            import glob
            import os
            
            camera_map = {}
            by_id_path = "/dev/v4l/by-id/"
            
            if not os.path.exists(by_id_path):
                return {}
            
            # List symlinks in /dev/v4l/by-id/
            for symlink in glob.glob(f"{by_id_path}*-video-index*"):
                try:
                    # Parse filename: usb-Manufacturer_Product_Serial-video-index0
                    basename = os.path.basename(symlink)
                    
                    # Extract index
                    if '-video-index' in basename:
                        index_str = basename.split('-video-index')[-1]
                        index = int(index_str)
                    else:
                        continue
                    
                    # Parse device info
                    parts = basename.split('-')
                    if len(parts) >= 2 and parts[0] == 'usb':
                        device_info = parts[1].replace('_', ' ')
                        
                        # Read target to get more info
                        target = os.readlink(symlink)
                        
                        camera_map[index] = {
                            'name': device_info,
                            'serial_number': None,  # Would need udevadm to extract
                            'vid': None,
                            'pid': None
                        }
                except Exception as e:
                    logger.debug(f"Error parsing camera symlink {symlink}: {e}")
                    continue
            
            return camera_map
            
        except Exception as e:
            logger.debug(f"Error getting Linux camera metadata: {e}")
            return {}
    
    def _get_camera_metadata_macos(self) -> Dict[int, Dict]:
        """Get camera metadata on macOS using system_profiler"""
        try:
            import subprocess
            import json
            
            result = subprocess.run(
                ["system_profiler", "SPCameraDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return {}
            
            data = json.loads(result.stdout)
            cameras = data.get("SPCameraDataType", [])
            
            camera_map = {}
            for idx, camera in enumerate(cameras):
                name = camera.get("_name", f"Camera {idx}")
                model_id = camera.get("model_id", "")
                
                camera_map[idx] = {
                    'name': name,
                    'serial_number': model_id if model_id else None,
                    'vid': None,
                    'pid': None
                }
            
            return camera_map
            
        except Exception as e:
            logger.debug(f"Error getting macOS camera metadata: {e}")
            return {}

    def capture_snapshot(
        self,
        camera_index: int,
        camera_type: str = "USB",
    ) -> Optional[np.ndarray]:
        """
        Capture single frame from camera.

        Args:
            camera_index: Camera index
            camera_type: "USB" or "RealSense"

        Returns:
            Frame as numpy array (BGR) or None if capture fails
        """
        if camera_type == "USB":
            with USBCamera(camera_index) as camera:
                return camera.capture_frame()

        elif camera_type == "RealSense":
            with RealSenseCamera(serial_number=None) as camera:
                result = camera.capture_frame()
                if result:
                    return result["color"]
                return None

        logger.error(f"Unknown camera type: {camera_type}")
        return None

    def capture_depth_snapshot(
        self,
        camera_index: int,
    ) -> Optional[np.ndarray]:
        """
        Capture depth frame from RealSense camera.

        Args:
            camera_index: RealSense camera index

        Returns:
            Depth frame as numpy array or None if capture fails
        """
        with RealSenseCamera(serial_number=None) as camera:
            result = camera.capture_frame()
            if result:
                return result["depth"]
            return None

    def stream_frames(
        self,
        camera_index: int,
        camera_type: str = "USB",
        frame_count: Optional[int] = None,
    ) -> Generator[np.ndarray, None, None]:
        """
        Stream frames from camera.

        Yields frames until stopped or frame_count reached.

        Args:
            camera_index: Camera index
            camera_type: "USB" or "RealSense"
            frame_count: Optional max frames to stream

        Yields:
            Frames as numpy arrays (BGR)
        """
        frame_number = 0

        try:
            if camera_type == "USB":
                camera = USBCamera(camera_index)
                camera.open()

                while True:
                    frame = camera.capture_frame()
                    if frame is not None:
                        yield frame
                        frame_number += 1

                        if frame_count and frame_number >= frame_count:
                            break
                    else:
                        break

                camera.close()

            elif camera_type == "RealSense":
                camera = RealSenseCamera()
                camera.open()

                while True:
                    result = camera.capture_frame()
                    if result:
                        yield result["color"]
                        frame_number += 1

                        if frame_count and frame_number >= frame_count:
                            break
                    else:
                        break

                camera.close()

            else:
                logger.error(f"Unknown camera type: {camera_type}")

        except Exception as e:
            logger.error(f"Error streaming frames: {e}")

        logger.info(f"Streamed {frame_number} frames")

    def save_snapshot(
        self,
        camera_index: int,
        output_path: str,
        camera_type: str = "USB",
    ) -> bool:
        """
        Capture and save single frame to disk.

        Args:
            camera_index: Camera index
            output_path: File path to save to
            camera_type: "USB" or "RealSense"

        Returns:
            True if successful
        """
        if not HAS_OPENCV:
            logger.error("OpenCV not available for saving images")
            return False

        frame = self.capture_snapshot(camera_index, camera_type)
        if frame is None:
            logger.error(f"Failed to capture frame from camera {camera_index}")
            return False

        try:
            cv2.imwrite(output_path, frame)
            logger.info(f"Saved snapshot to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")
            return False
