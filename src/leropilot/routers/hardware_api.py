import importlib.resources
import logging
import threading
from pathlib import Path
from typing import Any

import cv2
from fastapi import APIRouter, Body, HTTPException, Query, Response
from fastapi.responses import FileResponse

from leropilot.models.hardware import Device, DeviceCategory, DeviceStatus, DiscoveryResult, ProbeConnectionResult
from leropilot.services.hardware.camera import CameraService
from leropilot.services.hardware.discovery import DiscoveryService
from leropilot.services.hardware.manager import get_hardware_manager
from leropilot.services.hardware.motors import MotorService
from leropilot.services.hardware.robot_config import RobotConfigService
from leropilot.services.hardware.urdf_validator import URDFValidator

logger = logging.getLogger(__name__)

# Body parameter constants to avoid B008 issues
BODY_NONE = Body(default=None)
BODY_NONE_EMBED = Body(default=None, embed=True)
BODY_NONE_WITH_DESC = Body(default=None, description="Detailed configuration (motors, custom)")

router = APIRouter(prefix="/api/hardware", tags=["Hardware"])

# Service instances (lazy loaded or singleton)
_discovery_service = None
_motor_service = None
_camera_service = None
_service_lock = threading.Lock()


def get_camera_service() -> CameraService:
    global _camera_service
    if _camera_service is None:
        _camera_service = CameraService()
    return _camera_service


def get_discovery_service() -> DiscoveryService:
    global _discovery_service
    with _service_lock:
        if _discovery_service is None:
            _discovery_service = DiscoveryService()
        return _discovery_service


def get_motor_service() -> MotorService:
    global _motor_service
    with _service_lock:
        if _motor_service is None:
            _motor_service = MotorService()
        return _motor_service


# ============================================================================
# Discovery Endpoints
# ============================================================================


@router.get("/discovery", response_model=DiscoveryResult, operation_id="hardware_discover")
async def discover_hardware() -> DiscoveryResult:
    """
    Perform fresh hardware discovery.

    Scans for:
    - Serial ports (robots)
    - USB/RealSense cameras
    - CAN interfaces (Linux)
    """
    try:
        service = get_discovery_service()
        # This is a blocking operation, usually fast enough for HTTP req (~1-2s max)
        # If it gets slower, we might need to make it async or background
        return service.discover_all()
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}") from e


@router.post("/probe-connection", response_model=ProbeConnectionResult, operation_id="hardware_probe_connection")
async def probe_connection(
    interface: str = Body(..., embed=True), baud_rates: list[int] | None = BODY_NONE_EMBED
) -> ProbeConnectionResult:
    """
    Probe a specific interface to detect motors.

    Args:
        interface: Port name (e.g., "COM3", "/dev/ttyUSB0")
        baud_rates: Optional list of baud rates to try
    """
    try:
        motor_service = get_motor_service()
        result = motor_service.probe_connection(interface=interface, probe_baud_list=baud_rates)

        if not result:
            raise HTTPException(status_code=404, detail=f"No motors found on {interface}")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Probe failed: {e}")
        raise HTTPException(status_code=500, detail=f"Probe failed: {str(e)}") from e


# ============================================================================
# Device Management Endpoints
# ============================================================================


@router.get("/devices", response_model=list[Device], operation_id="hardware_list_devices")
async def list_devices(category: DeviceCategory | None = None, status: DeviceStatus | None = None) -> list[Device]:
    """List all managed devices."""
    manager = get_hardware_manager()
    return manager.list_devices(category=category, status=status)


@router.get("/devices/{device_id}", response_model=Device, operation_id="hardware_get_device")
async def get_device(device_id: str) -> Device:
    """Get a specific device details."""
    manager = get_hardware_manager()
    device = manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/devices", response_model=Device, operation_id="hardware_add_device")
async def add_device(device: Device) -> Device:
    """
    Add a new device to management.

    Note: 'status' field is ignored during creation (always defaults/runtime).
    """
    manager = get_hardware_manager()
    try:
        return manager.add_device(
            device_id=device.id,
            category=device.category,
            name=device.name,
            manufacturer=device.manufacturer,
            labels=device.labels,
            connection_settings=device.connection_settings,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to add device: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/devices/{device_id}", response_model=Device, operation_id="hardware_update_device")
async def update_device(
    device_id: str,
    name: str | None = BODY_NONE,
    labels: dict[str, str] | None = BODY_NONE,
    connection_settings: dict[str, Any] | None = BODY_NONE,
    config: dict[str, Any] | None = BODY_NONE_WITH_DESC,
) -> Device:
    """Update device details and configuration."""
    manager = get_hardware_manager()
    try:
        updated = manager.update_device(
            device_id=device_id, name=name, labels=labels, connection_settings=connection_settings, config=config
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Device not found")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/devices/{device_id}", operation_id="hardware_remove_device")
async def remove_device(
    device_id: str, delete_data: bool = Query(False, description="Also delete calibration/data files")
) -> dict[str, Any]:
    """Remove a device from management."""
    manager = get_hardware_manager()
    success = manager.remove_device(device_id, delete_calibration=delete_data)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"success": True, "message": f"Device {device_id} removed"}


# ============================================================================
# Motor Protection Endpoints
# ============================================================================

# Motor protection endpoints removed in favor of standard PATCH /devices/{id} for updates
# and Copy-on-Write for defaults (see HardwareManager.add_device).

# ============================================================================
# Telemetry Endpoints
# ============================================================================

# REST Telemetry endpoint removed in favor of WebSocket
# See ws_router below for real-time telemetry implementation


# ============================================================================
# Calibration Endpoints
# ============================================================================

# Calibration Endpoints Removed (Unified into PATCH /devices/{device_id})

# ============================================================================
# Camera Endpoints
# ============================================================================


@router.get("/devices/{device_id}/camera/snapshot", operation_id="hardware_camera_snapshot")
async def get_camera_snapshot(
    device_id: str,
    camera_index: int = Query(..., description="Camera index (e.g. 0)"),
    camera_type: str = Query("USB", description="Camera type: USB or RealSense"),
) -> Response:
    """
    Capture a snapshot from camera.
    Requires explicit camera index/type from frontend (stateless).
    """
    # Validation (mostly to ensure device exists in DB, though technically we just need index)
    manager = get_hardware_manager()
    device = manager.get_device(device_id)
    if not device:
        # We could allow snapshot without device_id if we have a generic endpoint,
        # but this is /devices/{id}/...
        raise HTTPException(status_code=404, detail="Device not found")

    camera_svc = get_camera_service()

    try:
        frame = camera_svc.capture_snapshot(camera_index, camera_type)
        if frame is None:
            raise HTTPException(status_code=500, detail="Capture failed")

        # Encode to JPEG
        success, buffer = cv2.imencode(".jpg", frame)
        if not success:
            raise HTTPException(status_code=500, detail="JPEG encoding failed")

        return Response(content=buffer.tobytes(), media_type="image/jpeg")
    except Exception as e:
        logger.error(f"Snapshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Resource Endpoints
# ============================================================================


@router.get("/resources/{device_id}/{path:path}", operation_id="hardware_get_resource")
async def get_resource(device_id: str, path: str) -> FileResponse:
    """
    Serve device-specific resources (STL, visuals) with fallback.
    Priority:
    1. Custom dir: ~/.leropilot/hardwares/{category}/{id}/{path}
    2. Builtin dir: src/leropilot/resources/robots/{model}/{path}
    """
    manager = get_hardware_manager()
    device = manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # 1. Custom Resource
    device_dir = manager.get_device_dir(device_id, device.category)
    custom_path = device_dir / path
    if custom_path.exists() and custom_path.is_file():
        return FileResponse(custom_path)

    # 2. Builtin Resource
    # Only for robots currently
    if device.category == DeviceCategory.ROBOT:
        # Use robot_type_id label to find the resource folder
        robot_type_id = device.labels.get("leropilot.ai/robot_type_id")
        if robot_type_id:
            # robot_type_id maps to folder name in resources (e.g., "koch-follower")

            # Try to locate in package resources using importlib
            try:
                # Get root of robots resources
                pkg_files = importlib.resources.files("leropilot.resources.robots")

                # Security: prevent directory traversal
                safe_path = Path(path)
                if safe_path.is_absolute() or ".." in str(safe_path):
                    raise HTTPException(status_code=403, detail="Invalid path")

                # Try exact robot_type_id as folder name
                target_file = pkg_files / robot_type_id / path
                if target_file.is_file():
                    return FileResponse(str(target_file))

                # Try sanitized version
                sanitized = robot_type_id.lower().replace("-", "_")
                target_file = pkg_files / sanitized / path
                if target_file.is_file():
                    return FileResponse(str(target_file))

            except Exception as e:
                logger.warning(f"Resource lookup error: {e}")

    raise HTTPException(status_code=404, detail="Resource not found")


# ============================================================================
# URDF Endpoints
# ============================================================================


@router.post("/devices/{device_id}/urdf", operation_id="hardware_upload_urdf")
async def upload_urdf(device_id: str, file: bytes = Body(..., media_type="application/xml")) -> dict[str, Any]:
    """
    Upload a custom URDF file for a robot.
    Validates URDF structure before saving.
    """
    manager = get_hardware_manager()
    device = manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if device.category != DeviceCategory.ROBOT:
        raise HTTPException(status_code=400, detail="Only robots support URDF upload")

    urdf_path = manager.get_urdf_file(device_id, device.category)

    # Write to temp file for validation
    import tempfile

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".urdf", delete=False) as tmp:
        tmp.write(file)
        tmp_path = tmp.name

    try:
        # Validate URDF
        validator = URDFValidator()
        validation_result = validator.validate_file(tmp_path)

        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "URDF_VALIDATION_ERROR",
                    "message": "URDF validation failed",
                    "validation": {
                        "valid": False,
                        "errors": validation_result["errors"],
                        "joints": validation_result["joints"],
                        "links": validation_result["links"],
                    },
                },
            )

        # Move validated file to final location
        urdf_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.move(tmp_path, urdf_path)

        return {
            "message": "URDF uploaded successfully",
            "path": str(urdf_path),
            "validation": {
                "valid": True,
                "errors": [],
                "joints": validation_result["joints"],
                "links": validation_result["links"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"URDF upload error for {device_id}: {e}")
        raise HTTPException(status_code=500, detail=f"URDF processing error: {e}") from e
    finally:
        # Always cleanup temp file if it still exists (i.e., move failed or validation failed)
        if Path(tmp_path).exists():
            Path(tmp_path).unlink(missing_ok=True)


@router.get("/devices/{device_id}/urdf", operation_id="hardware_get_urdf")
async def get_urdf(device_id: str) -> Response:
    """Download the URDF file for a robot (custom or builtin)."""
    manager = get_hardware_manager()
    device = manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # 1. Check custom URDF first
    urdf_path = manager.get_urdf_file(device_id, device.category)
    if urdf_path.exists():
        try:
            with open(urdf_path, "rb") as f:
                return Response(content=f.read(), media_type="application/xml")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read custom URDF: {e}") from e

    # 2. Fallback to builtin URDF
    robot_type_id = device.labels.get("leropilot.ai/robot_type_id")
    lerobot_name = device.labels.get("leropilot.ai/robot_lerobot_name")

    # Get robot definition to find lerobot_name if only robot_type_id is set
    if robot_type_id and not lerobot_name:
        robot_config = RobotConfigService()
        robot_def = robot_config.get_robot_definition(robot_type_id)
        if robot_def:
            lerobot_name = robot_def.lerobot_name

    # Try to find builtin URDF
    pkg_files = importlib.resources.files("leropilot.resources.robots")

    # Priority 1: Try robot_type_id as folder name
    if robot_type_id:
        urdf_candidates = [
            pkg_files / robot_type_id / "urdf" / "robot.urdf",
            pkg_files / robot_type_id / "robot.urdf",
            pkg_files / robot_type_id.replace("-", "_") / "urdf" / "robot.urdf",
        ]
        for candidate in urdf_candidates:
            try:
                if candidate.is_file():
                    content = candidate.read_bytes()
                    return Response(content=content, media_type="application/xml")
            except Exception:
                continue

    # Priority 2: Try lerobot_name as folder name
    if lerobot_name:
        urdf_candidates = [
            pkg_files / lerobot_name / "urdf" / "robot.urdf",
            pkg_files / lerobot_name / "robot.urdf",
        ]
        for candidate in urdf_candidates:
            try:
                if candidate.is_file():
                    content = candidate.read_bytes()
                    return Response(content=content, media_type="application/xml")
            except Exception:
                continue

    raise HTTPException(status_code=404, detail="URDF not found (no custom or builtin available)")


@router.delete("/devices/{device_id}/urdf", operation_id="hardware_delete_urdf")
async def delete_urdf(device_id: str) -> dict[str, str]:
    """Delete custom URDF."""
    manager = get_hardware_manager()
    device = manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    urdf_path = manager.get_urdf_file(device_id, device.category)
    if urdf_path.exists():
        urdf_path.unlink()

    return {"message": "Custom URDF deleted"}
