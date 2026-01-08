import asyncio
import importlib.resources
import logging
import threading
from collections.abc import AsyncGenerator
from typing import Any

import cv2
from fastapi import APIRouter, Body, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from leropilot.models.hardware import CameraSummary, Robot, DeviceCategory, DeviceStatus, RobotDefinition, MotorModelInfo, RobotVerificationError
from leropilot.services.hardware.cameras import CameraService
from leropilot.services.hardware.robots import get_robot_manager, get_robot_urdf_manager, RobotSpecService
from leropilot.services.hardware.motors import MotorService
from leropilot.utils.urdf import get_robot_resource, get_urdf_resource, validate_file as validate_urdf_file

logger = logging.getLogger(__name__)

# Body parameter constants to avoid B008 issues
# Use a sentinel object so the route handler can distinguish omitted params
_UNSET = object()
BODY_UNSET = Body(default=_UNSET)
BODY_UNSET_EMBED = Body(default=_UNSET, embed=True)
BODY_UNSET_WITH_DESC = Body(default=_UNSET, description="Detailed configuration (motors, custom)")
UPLOAD_FILE = File(...)

router = APIRouter(prefix="/api/hardware", tags=["Hardware"])

# Service instances (lazy loaded or singleton)
_motor_service = None
_camera_service = None
_robot_config_service = None
_service_lock = threading.Lock()


def get_camera_service() -> CameraService:
    global _camera_service
    if _camera_service is None:
        _camera_service = CameraService()
    return _camera_service




def get_motor_service() -> MotorService:
    global _motor_service
    with _service_lock:
        if _motor_service is None:
            _motor_service = MotorService()
        return _motor_service


def get_robot_spec_service() -> RobotSpecService:
    global _robot_config_service
    with _service_lock:
        if _robot_config_service is None:
            _robot_config_service = RobotSpecService()
        return _robot_config_service


# ============================================================================
# Discovery Endpoints
# ============================================================================

# Discovery endpoint moved to "Device Management Endpoints" to keep robot-related
# APIs grouped together.


# ============================================================================
# Robot Configuration Endpoints
# ============================================================================

@router.get("/robots/definitions", response_model=list[RobotDefinition], operation_id="hardware_list_robot_definitions")
async def list_robot_definitions() -> list[RobotDefinition]:
    """List all known robot definitions."""
    svc = get_robot_spec_service()
    return svc.get_all_definitions()


@router.get("/robots/definitions/{definition_id}/image", operation_id="hardware_get_robot_definition_image")
async def get_robot_definition_image(definition_id: str) -> FileResponse:
    """Get the image for a specific robot definition."""
    svc = get_robot_spec_service()
    definition = svc.get_robot_definition(definition_id)
    if not definition:
        logger.warning(f"Robot definition not found for image: {definition_id}")
        raise HTTPException(status_code=404, detail="Definition not found")

    from leropilot.utils.paths import get_resources_dir
    res_dir = get_resources_dir()

    try:
        # Try png then jpg
        for ext in [".png", ".jpg", ".jpeg"]:
            img_path = res_dir / "robots" / definition_id / f"thumbnail{ext}"
            if img_path.exists():
                return FileResponse(img_path)
    except Exception as e:
        logger.error(f"Error finding image for definition {definition_id}: {e}")
        pass

    logger.warning(f"Image not found for definition: {definition_id}")
    raise HTTPException(status_code=404, detail="Image not found")

# ============================================================================
# Device Management Endpoints
# ============================================================================

@router.get("/robots/discovery", response_model=list[Robot], operation_id="hardware_robots_discover")
async def discover_robots() -> list[Robot]:
    """
    Perform fresh robot hardware discovery.

    Scans for:
    - Serial ports
    - CAN interfaces
    """
    try:
        # Delegate to RobotManager which already knows about managed robots and
        # can return the pending (un-added) devices.
        manager = get_robot_manager()
        pending = manager.get_pending_devices()

        # Return list of pending Robot objects (controllers not applicable here)
        return pending
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}") from e


@router.get("/robots", response_model=list[Robot], operation_id="hardware_list_robots")
async def list_robots(refresh_status: bool = Query(False, description="Refresh online status from hardware")) -> list[Robot]:
    """List all managed robots.

    Args:
        refresh_status: If true, probe hardware to refresh each robot's status before returning.
    """
    manager = get_robot_manager()
    return manager.list_robots(refresh_status=refresh_status)


@router.get("/robots/{robot_id}", response_model=Robot, operation_id="hardware_get_robot")
async def get_robot(robot_id: str, refresh_status: bool = Query(False, description="Refresh online status from hardware")) -> Robot:
    """Get a specific robot details.

    Args:
        refresh_status: If true, probe hardware to refresh this robot's status before returning.
    """
    manager = get_robot_manager()
    robot = manager.get_robot(robot_id, refresh_status=refresh_status)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")
    return robot


@router.get("/robots/{robot_id}/motor_models_info", response_model=list[MotorModelInfo], operation_id="hardware_get_robot_motor_models_info")
async def get_robot_motor_models_info(robot_id: str) -> list[MotorModelInfo]:
    """Return a deduplicated list of motor model metadata for the robot's definition."""
    manager = get_robot_manager()
    try:
        return manager.get_robot_motor_models_info(robot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        logger.exception("Failed to retrieve motor models info for robot %s", robot_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve motor models info") from None


@router.post("/robots", response_model=Robot, operation_id="hardware_add_robot")
async def add_robot(robot: Robot) -> Robot:
    """
    Add a new robot to management.

    Notes:
      - The `status` field on the submitted `Robot` is ignored during creation
        (status is set at runtime based on discovery/verification).
      - The service will perform a hardware verification (`verify_robot`) during
        creation; when verification fails a 409 Conflict is returned.
    """
    manager = get_robot_manager()
    try:
        return manager.add_robot(
            robot=robot
        )
    except ValueError as e:
        # Covers verification failures and other validation errors
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to add device: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/robots/{robot_id}", response_model=Robot, operation_id="hardware_update_robot")
async def update_robot(
    robot_id: str,
    name: str | None = BODY_UNSET,
    labels: dict[str, str] | None = BODY_UNSET,
    motor_bus_connections: dict[str, dict] | None = BODY_UNSET,
    custom_protection_settings: dict[str, list[dict]] | None = BODY_UNSET_WITH_DESC,
    verify: bool = Query(True, description="Verify robot connectivity after applying updates"),
) -> Robot:
    """Update robot details.

    Supports updating `name`, `labels`, `motor_bus_connections`, and
    `custom_protection_settings` (use 'brand:model' or tuple keys where appropriate).

    Distinguishes between omitted fields (not updated) and explicit `null` which
    will be applied (clearing those fields).

    Notes:
      - `verify` defaults to **True**; the route delegates verification to the
        `RobotManager.update_robot` service method which will run verification when
        requested and raise `RobotVerificationError` on failure. Such failures are
        surfaced as HTTP 409 Conflict responses.
    """
    manager = get_robot_manager()
    try:
        # Build updates dict only from provided parameters (not the sentinel)
        updates: dict[str, object] = {}
        if name is not _UNSET:
            updates["name"] = name
        if labels is not _UNSET:
            updates["labels"] = labels
        if motor_bus_connections is not _UNSET:
            updates["motor_bus_connections"] = motor_bus_connections
        if custom_protection_settings is not _UNSET:
            updates["custom_protection_settings"] = custom_protection_settings

        # Delegate verification and update semantics to the service layer
        updated = manager.update_robot(
            robot_id,
            verify=verify,
            **updates,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Robot not found")

        return updated
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/robots/{robot_id}", operation_id="hardware_remove_robot")
async def remove_robot(
    robot_id: str, delete_data: bool = Query(False, description="Also delete calibration/data files")
) -> dict[str, Any]:
    """Remove a robot from management."""
    manager = get_robot_manager()
    success = manager.remove_robot(robot_id, delete_calibration=delete_data)
    if not success:
        raise HTTPException(status_code=404, detail="Robot not found")
    return {"success": True, "message": f"Robot {robot_id} removed"}


@router.get("/robots/{robot_id}/urdf", operation_id="hardware_get_robot_urdf")
@router.get("/robots/{robot_id}/urdf/{path:path}", operation_id="hardware_get_robot_urdf_resource")
async def get_robot_urdf(robot_id: str, path: str | None = None) -> FileResponse:
    """Serve a URDF resource for a robot.

    Supports both forms:
      - GET /robots/{robot_id}/urdf            -> serves the default "robot.urdf"
      - GET /robots/{robot_id}/urdf/{path:path} -> serves the specified resource path

    Resolves and lookup are delegated to `RobotUrdfManager.get_robot_urdf_resource`.
    The service returns the raw bytes of the requested resource when found, preferring
    a user-uploaded custom URDF under the robot's data directory and falling back
    to a packaged model resource.

    The router returns a `Response` with `media_type="text/xml"` and HTTP 404
    when the resource is not present. Any IO failures are translated to HTTP 500.
    """
    if path is None:
        path = "robot.urdf"

    urdf_mgr = get_robot_urdf_manager()
    try:
        content = urdf_mgr.get_robot_urdf_resource(robot_id, path)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    if content is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    try:
        return Response(content=content, media_type="text/xml")
    except Exception:
        logger.exception("Failed to serve URDF resource for %s", robot_id)
        raise HTTPException(status_code=500, detail="Failed to serve resource") from None
# NOTE: udev install logic has been moved to `leropilot.utils.unix`.
# Manual install endpoint is intentionally not exposed. The backend will automatically
# attempt to install udev (and update rules) as needed when a service operation requires it.
# UdevManager provides `ensure_rule_present()` which is idempotent and performs
# atomic updates (and optionally uses `pkexec` when root is required).

# ------------------------- URDF Management Endpoints -------------------------

@router.post("/robots/{robot_id}/urdf", operation_id="hardware_upload_robot_urdf")
async def upload_robot_urdf(robot_id: str, file: UploadFile = UPLOAD_FILE) -> dict:
    """Upload a custom URDF file for a robot.

    Accepts either a raw `.urdf` file or an archive (`.zip` or `.tar.gz`) that
    contains exactly one top-level `.urdf` file. Files are validated via
    `leropilot.utils.urdf.validate_file` and saved under the robot's data
    directory when valid.

    Error semantics:
      - 404 if the robot does not exist
      - 400 for validation or archive-format errors
      - 500 for unexpected processing errors

    Returns a JSON object containing the saved path and the validation result.
    """
    manager = get_robot_manager()
    robot = manager.get_robot(robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")
    if getattr(robot, "category", DeviceCategory.ROBOT) != DeviceCategory.ROBOT:
        raise HTTPException(status_code=400, detail="URDFs can only be uploaded for robots")

    contents = await file.read()
    try:
        urdf_mgr = get_robot_urdf_manager()
        saved_path = urdf_mgr.upload_custom_urdf(robot_id, contents)
    except ValueError as e:
        # Validation or archive errors
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to process uploaded URDF")
        raise HTTPException(status_code=500, detail="Failed to process uploaded URDF") from e

    # Return standardized response
    result = validate_urdf_file(str(saved_path))
    return {"message": "URDF uploaded successfully", "path": str(saved_path), "validation": result}





@router.delete("/robots/{robot_id}/urdf", operation_id="hardware_delete_robot_urdf")
async def delete_robot_urdf(robot_id: str) -> Response:
    """Delete a previously uploaded custom URDF for the robot.

    After successful deletion the robot will fall back to its built-in model
    resource (if available).

    Error semantics:
      - 404 if no such robot or if no custom URDF exists
      - 500 for unexpected errors while removing files
    """
    manager = get_robot_manager()
    robot = manager.get_robot(robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="Robot not found")

    urdf_mgr = get_robot_urdf_manager()
    try:
        urdf_mgr.delete_custom_urdf(robot_id)
    except ValueError:
        # Robot not found
        raise HTTPException(status_code=404, detail="Robot not found")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Custom URDF not found")
    except Exception:
        logger.exception("Failed to delete custom URDF")
        raise HTTPException(status_code=500, detail="Failed to delete URDF")

    return Response(status_code=204)


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
        try:
            async for frame in frames:
                head = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                yield head + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
        except (GeneratorExit, asyncio.CancelledError):
            logger.info("MJPEG stream cancelled for camera %s", camera_id)
        finally:
            # Explicitly close the frames generator to trigger cap.release()
            await frames.aclose()

    return StreamingResponse(generator(), media_type="multipart/x-mixed-replace; boundary=frame")


# URDF endpoints moved to "Device Management Endpoints" to keep robot-related
# APIs grouped together; implementations are preserved in that section.
