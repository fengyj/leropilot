import importlib.resources
import logging
import platform
import threading
from collections.abc import AsyncGenerator
from typing import Any

import cv2
from fastapi import APIRouter, Body, File, HTTPException, Query, Response, UploadFile, Request
from fastapi.responses import FileResponse, StreamingResponse

from leropilot.models.hardware import CameraSummary, Device, DeviceCategory, DeviceStatus, DiscoveryResult
from leropilot.services.hardware.cameras import CameraService
from leropilot.services.hardware.manager import get_hardware_manager
from leropilot.services.hardware.motors import MotorService
from leropilot.services.hardware.robots import RobotsDiscoveryService
from leropilot.services.hardware.urdf import validate_file as validate_urdf_file
from leropilot.utils.subprocess_executor import SubprocessExecutor

logger = logging.getLogger(__name__)

# Body parameter constants to avoid B008 issues
BODY_NONE = Body(default=None)
BODY_NONE_EMBED = Body(default=None, embed=True)
BODY_NONE_WITH_DESC = Body(default=None, description="Detailed configuration (motors, custom)")
UPLOAD_FILE = File(...)

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


def get_discovery_service() -> RobotsDiscoveryService:
    """Return a fresh RobotsDiscoveryService instance for discovery calls.

    Note: We intentionally create a new instance per call to ensure discovery
    reflects current platform state and to avoid caching issues during tests.
    """
    return RobotsDiscoveryService()


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
    - CAN interfaces (Linux)
    """
    try:
        service = get_discovery_service()
        # This is a blocking operation, usually fast enough for HTTP req (~1-2s max)
        # If it gets slower, we might need to make it async or background
        result = service.discover_all()

        # Filter out devices already managed (only return un-added devices)
        manager = get_hardware_manager()
        existing_ids = {d.id for d in manager.list_devices()}

        # For robots/controllers with serial numbers, exclude those already added
        result.robots = [
            r
            for r in result.robots
            if not (r.serial_number and r.serial_number in existing_ids)
        ]
        result.controllers = [
            c
            for c in result.controllers
            if not (c.serial_number and c.serial_number in existing_ids)
        ]

        return result
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}") from e


@router.post("/motor-discover", operation_id="hardware_motor_discover")
async def motor_discover(
    interface: str = Body(..., embed=True),
    baud_rates: list[int] | None = BODY_NONE_EMBED,
    device_id: str | None = BODY_NONE_EMBED,
) -> dict:
    """
    Probe a communication interface to detect motors and return detected motors with built-in protection defaults.

    Args:
        interface: Port name (e.g., "COM3", "/dev/ttyUSB0")
        baud_rates: Optional list of baud rates to try
        device_id: Optional device id to use saved connection settings (brand, etc.)
    Returns:
        dict with interface, detected_baud_rate, motors (id/model/model_number/protection params)
    """
    try:
        motor_service = get_motor_service()
        manager = get_hardware_manager()

        # Allow using device connection settings as hint
        brand_hint = None
        if device_id:
            device = manager.get_device(device_id)
            if device and device.connection_settings:
                brand_hint = device.connection_settings.get("brand")

        result = motor_service.probe_connection(interface=interface, probe_baud_list=baud_rates)
        if not result:
            raise HTTPException(status_code=404, detail=f"No motors found on {interface}")

        motors_info: list[dict] = []
        detected_brand = result.brand or brand_hint
        for m in result.discovered_motors:
            brand = detected_brand
            model = m.model
            specs = motor_service.get_motor_specs(brand or "", model or "")
            motors_info.append(
                {
                    "id": m.id,
                    "model": model,
                    "model_number": m.model_number,
                    "protection": specs.model_dump() if specs else None,
                }
            )

        return {
            "interface": result.interface,
            "detected_baud_rate": result.baud_rate,
            "detected_brand": detected_brand,
            "motors": motors_info,
            "scan_duration_ms": 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Motor discover failed: {e}")
        raise HTTPException(status_code=500, detail=f"Motor discover failed: {str(e)}") from e


@router.get("/motor-specs/{brand}/{model}", operation_id="hardware_get_motor_specs")
async def get_motor_specs(brand: str, model: str) -> dict:
    """Return built-in motor protection parameters for a brand/model."""
    motor_service = get_motor_service()
    specs = motor_service.get_motor_specs(brand, model)
    if not specs:
        raise HTTPException(status_code=404, detail="Motor model not found")
    # Return as JSON-friendly dict
    return specs.model_dump()


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


@router.get("/cameras", response_model=list[CameraSummary], operation_id="hardware_list_cameras")
async def list_cameras() -> list[CameraSummary]:
    """Stateless listing of available cameras (OpenCV indices)."""
    svc = get_camera_service()
    return svc.list_cameras()


@router.get("/cameras/{camera_id}/snapshot", operation_id="hardware_camera_snapshot")
async def camera_snapshot(
    camera_id: str,
    width: int | None = Query(None, description="Requested width"),
    height: int | None = Query(None, description="Requested height"),
    fmt: str = Query("jpeg", description="Image format: jpeg|png"),
) -> Response:
    """Capture a single frame from the specified camera id (e.g., cam_0 or "0")."""
    try:
        index = int(camera_id.split("_")[-1]) if camera_id.startswith("cam_") else int(camera_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid camera id") from None

    svc = get_camera_service()
    frame = svc.capture_snapshot(index, camera_type="USB", width=width, height=height)
    if frame is None:
        raise HTTPException(status_code=404, detail="Failed to capture frame")

    ext = ".jpg" if fmt.lower() == "jpeg" else ".png"
    ok, buf = cv2.imencode(ext, frame)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode frame")
    media = "image/jpeg" if fmt.lower() == "jpeg" else "image/png"
    return Response(content=buf.tobytes(), media_type=media)


@router.get("/cameras/{camera_id}/mjpeg", operation_id="hardware_camera_mjpeg")
async def camera_mjpeg(
    camera_id: str,
    fps: int = Query(15, description="Frames per second"),
    width: int | None = Query(None),
    height: int | None = Query(None),
) -> StreamingResponse:
    """Return an MJPEG multipart stream for the given camera id."""
    try:
        index = int(camera_id.split("_")[-1]) if camera_id.startswith("cam_") else int(camera_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid camera id") from None

    svc = get_camera_service()
    frames = svc.stream_encoded_frames(
        camera_index=index,
        camera_type="USB",
        fps=fps,
        width=width,
        height=height,
        fmt="jpeg",
    )

    async def generator() -> AsyncGenerator[bytes, None]:
        async for frame in frames:
            head = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
            yield head + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"

    return StreamingResponse(generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/resources/{device_id}/{path:path}", operation_id="hardware_get_resource")
async def get_resource(device_id: str, path: str) -> FileResponse:
    """Serve resource files with fallback to built-in resources."""
    manager = get_hardware_manager()
    device = manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Check user custom resources first
    from leropilot.services.hardware.manager import HARDWARE_DATA_DIR

    category_val = device.category.value if hasattr(device.category, "value") else str(device.category)
    device_dir = HARDWARE_DATA_DIR / category_val / device_id
    user_file = device_dir / path
    if user_file.exists():
        return FileResponse(user_file)

    # Fallback to built-in resource under resources/robots/{model}/{path}
    model = None
    # DeviceConfig stores custom fields under `custom`
    if device.config and getattr(device.config, "custom", None):
        model = device.config.custom.get("model")
    # Also allow label based mapping
    if not model:
        model = device.labels.get("leropilot.ai/robot_type_id")

    if model:
        resource_files = importlib.resources.files("leropilot.resources")
        builtin_dir = resource_files.joinpath("robots").joinpath(model)
        if builtin_dir.exists():
            # Try to find the requested path under builtin_dir
            candidate = builtin_dir.joinpath(path)
            if candidate.exists():
                return FileResponse(candidate)
            # If path is a direct URDF name fallback, find any .urdf file
            for p in builtin_dir.iterdir():
                if p.suffix == ".urdf" and p.is_file():
                    return FileResponse(p)

    raise HTTPException(status_code=404, detail="Resource not found")


@router.post("/udev/install", operation_id="hardware_udev_install")
async def install_udev_rule(
    request: Request,
    install: bool = Body(False, embed=True),
    subsystem: str = Body("tty", embed=True),
    vendor: str | None = BODY_NONE_EMBED,
    product: str | None = BODY_NONE_EMBED,
    group: str | None = BODY_NONE_EMBED,
    mode: str | None = BODY_NONE_EMBED,
    kernel: str | None = BODY_NONE_EMBED,
) -> dict:
    """Return udev rule content, or attempt to install it when `install=true` (Linux only).

    Supports `subsystem` values `tty` (default) and `video4linux` (for cameras). When
    `subsystem=="video4linux"` the default `group` is `video` and default `mode` is
    `0660` for safer permissions.
    """
    if platform.system() != "Linux":
        raise HTTPException(status_code=400, detail="udev installation is supported on Linux only")

    subsystem = (subsystem or "tty").strip()

    if subsystem not in ("tty", "video4linux"):
        raise HTTPException(status_code=400, detail="Unsupported subsystem; supported: tty, video4linux")

    # Defaults
    if subsystem == "tty":
        default_group = "dialout"
        default_mode = "0666"
        kernel_pat = kernel or "*"
    else:
        default_group = "video"
        default_mode = "0660"
        kernel_pat = kernel or "video*"

    used_group = group or default_group
    used_mode = mode or default_mode

    # Build attribute filters
    # FastAPI body parsing can be a bit subtle with multiple Body params; fall back to raw JSON body
    try:
        body_json = await request.json()
    except Exception:
        body_json = None

    if not vendor and isinstance(body_json, dict):
        vendor = body_json.get("vendor")
    if not product and isinstance(body_json, dict):
        product = body_json.get("product")

    attrs = []
    if vendor:
        attrs.append(f'ATTRS{{idVendor}}=="{vendor}"')
    if product:
        attrs.append(f'ATTRS{{idProduct}}=="{product}"')

    # Compose rule
    if subsystem == "tty":
        base = f'SUBSYSTEM=="tty", {{attrs}}, MODE="{used_mode}", GROUP="{used_group}"'
    else:
        base = f'SUBSYSTEM=="video4linux", KERNEL=="{kernel_pat}"{{attrs}}, MODE="{used_mode}", GROUP="{used_group}"'

    attrs_str = (", " + ", ".join(attrs)) if attrs else ""
    rule = base.replace("{attrs}", attrs_str)

    if not install:
        return {"rule": rule}

    try:
        # Use pkexec to write the file as root
        cmd_str = f'echo "{rule}" > /etc/udev/rules.d/99-leropilot.rules && udevadm control --reload && udevadm trigger'
        cmd = ("pkexec", "bash", "-c", cmd_str)
        SubprocessExecutor.run_sync(*cmd)
        return {"installed": True, "path": "/etc/udev/rules.d/99-leropilot.rules"}
    except Exception as e:
        logger.error(f"udev install failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ------------------------- URDF Management Endpoints -------------------------

@router.post("/devices/{device_id}/urdf", operation_id="hardware_upload_urdf")
async def upload_urdf(device_id: str, file: UploadFile = UPLOAD_FILE) -> dict:
    """Upload a custom URDF file for a robot. Validates using URDFValidator and saves to device dir."""
    manager = get_hardware_manager()
    device = manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.category != DeviceCategory.ROBOT:
        raise HTTPException(status_code=400, detail="URDFs can only be uploaded for robots")

    urdf_path = manager.get_urdf_file(device_id, device.category)
    urdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    try:
        contents = await file.read()
        with open(urdf_path, "wb") as fh:
            fh.write(contents)
    except Exception as e:
        logger.error(f"Failed to save URDF: {e}")
        raise HTTPException(status_code=500, detail="Failed to save URDF") from e

    # Validate URDF using in-project validator
    result = validate_urdf_file(str(urdf_path))
    if not result.get("valid", False):
        # Remove invalid upload
        try:
            urdf_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail={"error": "URDF validation failed", "details": result})
    return {"message": "URDF uploaded successfully", "path": str(urdf_path), "validation": result}


@router.get("/devices/{device_id}/urdf", operation_id="hardware_get_urdf")
async def get_urdf(device_id: str) -> Response:
    """Download URDF for a device (custom or built-in fallback)."""
    manager = get_hardware_manager()
    device = manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    urdf_path = manager.get_urdf_file(device_id, device.category)
    if urdf_path.exists():
        return FileResponse(urdf_path, media_type="text/xml")

    # Try built-in fallback based on device config or label
    model = None
    if device.config and getattr(device.config, "custom", None):
        model = device.config.custom.get("model")
    if not model:
        model = device.labels.get("leropilot.ai/robot_type_id")

    if model:
        resource_files = importlib.resources.files("leropilot.resources")
        builtin_dir = resource_files.joinpath("robots").joinpath(model)
        if builtin_dir.exists():
            for p in builtin_dir.iterdir():
                if p.suffix == ".urdf" and p.is_file():
                    return FileResponse(p, media_type="text/xml")

    raise HTTPException(status_code=404, detail="URDF not found")


@router.delete("/devices/{device_id}/urdf", operation_id="hardware_delete_urdf")
async def delete_urdf(device_id: str) -> None:
    """Delete custom URDF and revert to built-in model."""
    manager = get_hardware_manager()
    device = manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    urdf_path = manager.get_urdf_file(device_id, device.category)
    if not urdf_path.exists():
        raise HTTPException(status_code=404, detail="Custom URDF not found")

    try:
        urdf_path.unlink()
    except Exception as e:
        logger.error(f"Failed to delete URDF: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete URDF") from e

    return Response(status_code=204)
