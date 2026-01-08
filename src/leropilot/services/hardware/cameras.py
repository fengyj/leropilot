"""
Camera capture and streaming services (plural).

Provides:
- `CameraService`: minimal OpenCV-based capture and MJPEG-friendly frame encoding.

Note: This module replaces the older `camera.py` module; `camera.py` remains as a
compatibility shim re-exporting `CameraService` from here.
"""

import logging
from collections.abc import AsyncGenerator

import cv2
import numpy as np

from leropilot.models.hardware import CameraSummary

logger = logging.getLogger(__name__)

# OpenCV is a required dependency for camera support
# RealSense intentionally not supported in minimal service
HAS_REALSENSE = False


class CameraService:
    """High-level camera management service (minimal)."""

    def __init__(self) -> None:
        logger.info("CameraService initialized")

    def list_cameras(self) -> list[CameraSummary]:
        """Enumerate available cameras using OpenCV indices (0..19).

        Returns a list of `CameraSummary` objects with best-effort width/height.
        """
        summaries: list[CameraSummary] = []

        try:
            for index in range(20):
                cap = cv2.VideoCapture(index)
                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

                    # Quick availability check: try to read one frame then release
                    available = True
                    try:
                        ret, _ = cap.read()
                        if not ret:
                            available = False
                    except Exception:
                        available = False

                    summaries.append(
                        CameraSummary(
                            index=index,
                            name=f"USB Camera {index}",
                            width=width or None,
                            height=height or None,
                            available=available,
                        )
                    )
                    cap.release()
        except Exception as e:
            logger.debug(f"Error enumerating cameras: {e}")

        return summaries

    def capture_snapshot(
        self,
        camera_index: int,
        camera_type: str = "USB",
        width: int | None = None,
        height: int | None = None,
    ) -> np.ndarray | None:
        """Capture single frame from OpenCV index. Returns BGR numpy array or None.

        Attempts to auto-fix udev permissions on Linux when a permission issue is detected
        and retries once if the fix was applied.
        """
        from leropilot.utils.unix import UdevManager

        udev_manager = UdevManager()
        device_path = f"/dev/video{camera_index}"

        def _try_open() -> cv2.VideoCapture | None:
            cap = cv2.VideoCapture(camera_index)
            return cap if cap and cap.isOpened() else None

        cap = udev_manager.ensure_device_access_with_retry(device_path, _try_open, subsystem="video4linux")
        if not cap:
            return None

        try:
            if width:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height:
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            ret, frame = cap.read()
            if not ret:
                return None
            return frame
        finally:
            try:
                cap.release()
            except Exception:
                pass

    async def stream_encoded_frames(
        self,
        camera_index: int,
        camera_type: str = "USB",
        fps: int = 15,
        width: int | None = None,
        height: int | None = None,
        fmt: str = "jpeg",
    ) -> AsyncGenerator[bytes, None]:
        """Async generator yielding encoded frames as bytes (jpeg/png).

        Name: `stream_encoded_frames` is intentionally generic — it yields encoded images
        (JPEG or PNG). For WebSocket transport this is a simple and interoperable approach.
        """
        import asyncio

        fmt_lower = (fmt or "jpeg").lower()
        if fmt_lower not in ("jpeg", "png"):
            raise ValueError("Unsupported format; supported: jpeg, png")
        ext = ".jpg" if fmt_lower == "jpeg" else ".png"

        loop = asyncio.get_running_loop()
        interval = 1.0 / max(1, min(fps, 30))

        from leropilot.utils.unix import UdevManager

        udev_manager = UdevManager()
        device_path = f"/dev/video{camera_index}"

        def _try_open() -> cv2.VideoCapture | None:
            cap = cv2.VideoCapture(camera_index)
            return cap if cap and cap.isOpened() else None

        cap = udev_manager.ensure_device_access_with_retry(device_path, _try_open, subsystem="video4linux")
        if not cap:
            raise FileNotFoundError(f"Failed to open camera {camera_index}")

        try:
            if width:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height:
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)

            while True:
                ret, frame = await loop.run_in_executor(None, cap.read)
                if not ret or frame is None:
                    await asyncio.sleep(0.05)
                    continue
                ok, buf = await loop.run_in_executor(None, cv2.imencode, ext, frame)
                if not ok:
                    await asyncio.sleep(interval)
                    continue
                yield buf.tobytes()
                await asyncio.sleep(interval)
        finally:
            try:
                cap.release()
            except Exception:
                pass

    def save_snapshot(self, camera_index: int, output_path: str, camera_type: str = "USB") -> bool:
        """Capture and save single frame to disk using OpenCV."""
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
