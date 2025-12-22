#!/usr/bin/env python
"""
Example: Camera Capture

Capture snapshots from USB and RealSense cameras.

Usage:
    python -m examples.hardware.camera_capture [output_dir]

Example:
    python -m examples.hardware.camera_capture ./snapshots
"""

import logging
import sys
from pathlib import Path

from leropilot.services.hardware.camera import CameraService

# Try to import OpenCV for saving images
try:
    import cv2

    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Capture snapshots from all available cameras"""
    if not HAS_OPENCV:
        print("❌ Error: opencv-python is required to save images")
        print("   Install with: pip install opencv-python")
        return

    # Use centralized output directory (project_root/output/camera_snapshots)
    project_root = Path(__file__).parent.parent.parent
    default_output = project_root / "output" / "camera_snapshots"
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else default_output
    output_dir.mkdir(parents=True, exist_ok=True)

    service = CameraService()

    print("\n" + "=" * 60)
    print("CAMERA CAPTURE EXAMPLE")
    print("=" * 60)

    try:
        # List cameras
        cameras = service.list_cameras()
        print(f"\n📷 Found {len(cameras)} camera(s):\n")

        for i, camera in enumerate(cameras):
            print(f"  {i + 1}. {camera.name}")
            print(f"     Type: {camera.camera_type}")
            if camera.width:
                print(f"     Resolution: {camera.width}x{camera.height}")
            if hasattr(camera, "serial_number") and camera.serial_number:
                print(f"     Serial: {camera.serial_number}")
            if camera.vid and camera.pid:
                print(f"     VID:PID: {camera.vid}:{camera.pid}")

        if not cameras:
            print("  No cameras detected")
            return

        # Capture from each camera
        print(f"\nCapturing snapshots to: {output_dir}")
        print("-" * 60)

        for i, camera in enumerate(cameras):
            try:
                # Capture RGB snapshot
                print(f"\n📸 Capturing from: {camera.name}")
                filename = f"{i + 1:02d}_{camera.camera_type}_{camera.index}.jpg"
                filepath = output_dir / filename

                if camera.camera_type == "RealSense":
                    # For RealSense, also capture depth
                    frame = service.capture_snapshot(camera_index=camera.index, camera_type=camera.camera_type)
                    if frame is not None:
                        cv2.imwrite(str(filepath), frame)
                        print(f"  ✅ RGB: {filepath}")

                    # Capture depth
                    depth_filepath = output_dir / f"{i + 1:02d}_depth_{camera.index}.png"
                    depth_frame = service.capture_depth_snapshot(camera_index=camera.index)
                    if depth_frame is not None:
                        # Normalize depth to 0-255 for visualization
                        depth_normalized = cv2.normalize(depth_frame, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                        cv2.imwrite(str(depth_filepath), depth_normalized)
                        print(f"  ✅ Depth: {depth_filepath}")
                else:
                    # For USB cameras, just capture RGB
                    frame = service.capture_snapshot(camera_index=camera.index, camera_type=camera.camera_type)
                    if frame is not None:
                        cv2.imwrite(str(filepath), frame)
                        print(f"  ✅ Snapshot: {filepath}")
                    else:
                        print("  ❌ Failed to capture")

            except Exception as e:
                print(f"  ❌ Error: {e}")
                logger.exception(f"Error capturing from camera {i}")

        print("\n" + "=" * 60)
        print(f"✅ Snapshots saved to: {output_dir}")
        print(f"   {len(list(output_dir.glob('*.jpg')))} RGB images")
        print(f"   {len(list(output_dir.glob('*.png')))} depth images")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Exception during camera capture")


if __name__ == "__main__":
    main()
