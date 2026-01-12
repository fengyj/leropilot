import asyncio
import importlib.resources
import logging
import threading
from collections.abc import AsyncGenerator
from typing import Any

import cv2
from fastapi import APIRouter, Body, File, Query, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from leropilot.exceptions import OperationalError, ResourceNotFoundError, ValidationError
from leropilot.models.hardware import CameraSummary, Robot, DeviceCategory, DeviceStatus, RobotDefinition, MotorModelInfo
from leropilot.services.hardware.cameras import CameraService
from leropilot.services.hardware.robots import get_robot_manager, get_robot_urdf_manager, RobotSpecService
from leropilot.services.hardware.motors import MotorService
from leropilot.services.i18n import get_i18n_service
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

# Service getter helpers...


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


def resolve_robot_definition(definition: RobotDefinition, lang: str) -> RobotDefinition:
    """Resolve localized fields in a RobotDefinition for a specific language."""
    resolved = definition.model_copy()

    def _resolve(val: str | dict[str, str], l: str) -> str:
        if isinstance(val, str):
            return val
        return val.get(l) or val.get("en") or (list(val.values())[0] if val else "")

    resolved.display_name = _resolve(definition.display_name, lang)
    resolved.description = _resolve(definition.description, lang)
    return resolved


def resolve_robot(robot: Robot, lang: str) -> Robot:
    """Resolve localized fields in a Robot's definition for a specific language."""
    if not robot.definition or isinstance(robot.definition, str):
        return robot

    resolved = robot.model_copy()
    resolved.definition = resolve_robot_definition(robot.definition, lang)
    return resolved


# ============================================================================
# Discovery Endpoints
# ============================================================================

# Discovery endpoint moved to "Device Management Endpoints" to keep robot-related
# APIs grouped together.


# ============================================================================
# Robot Configuration Endpoints
# ============================================================================

@router.get("/robots/definitions", response_model=list[RobotDefinition], operation_id="hardware_list_robot_definitions")
async def list_robot_definitions(lang: str = Query("en", description="Language code")) -> list[RobotDefinition]:
    """List all known robot definitions."""
    svc = get_robot_spec_service()
    definitions = svc.get_all_definitions()
    return [resolve_robot_definition(d, lang) for d in definitions]


@router.get("/robots/definitions/{definition_id}/image", operation_id="hardware_get_robot_definition_image")
async def get_robot_definition_image(definition_id: str, lang: str = Query("en", description="Language code")) -> FileResponse:
    """Get the image for a specific robot definition."""
    svc = get_robot_spec_service()
    definition = svc.get_robot_definition(definition_id)
    if not definition:
        raise ResourceNotFoundError("hardware.robot_definition.not_found", id=definition_id)

    from leropilot.utils.paths import get_resources_dir
    res_dir = get_resources_dir()

    # Try png then jpg
    for ext in [".png", ".jpg", ".jpeg"]:
        img_path = res_dir / "robots" / definition_id / f"thumbnail{ext}"
        if img_path.exists():
            return FileResponse(img_path)

    raise ResourceNotFoundError("hardware.robot_definition.thumbnail_not_found", id=definition_id)

# ============================================================================
# Device Management Endpoints
# ============================================================================

@router.get("/robots/discovery", response_model=list[Robot], operation_id="hardware_robots_discover")
async def discover_robots(lang: str = Query("en", description="Language code")) -> list[Robot]:
    """
    Perform fresh robot hardware discovery.
    """
    manager = get_robot_manager()
    robots = manager.get_pending_devices(lang=lang)
    return [resolve_robot(r, lang) for r in robots]


@router.get("/robots", response_model=list[Robot], operation_id="hardware_list_robots")
async def list_robots(
    refresh_status: bool = Query(False, description="Refresh online status from hardware"),
    lang: str = Query("en", description="Language code"),
) -> list[Robot]:
    """List all managed robots.

    Args:
        refresh_status: If true, probe hardware to refresh each robot's status before returning.
    """
    manager = get_robot_manager()
    robots = manager.list_robots(refresh_status=refresh_status)
    return [resolve_robot(r, lang) for r in robots]


@router.get("/robots/{robot_id}", response_model=Robot, operation_id="hardware_get_robot")
async def get_robot(
    robot_id: str,
    refresh_status: bool = Query(False, description="Refresh online status from hardware"),
    lang: str = Query("en", description="Language code"),
) -> Robot:
    """Get a specific robot details."""
    manager = get_robot_manager()
    robot = manager.get_robot(robot_id, refresh_status=refresh_status)
    if not robot:
        raise ResourceNotFoundError("hardware.robot_device.not_found", id=robot_id)
    return resolve_robot(robot, lang)


@router.get("/robots/{robot_id}/motor_models_info", response_model=list[MotorModelInfo], operation_id="hardware_get_robot_motor_models_info")
async def get_robot_motor_models_info(robot_id: str) -> list[MotorModelInfo]:
    """Return a deduplicated list of motor model metadata for the robot's definition."""
    manager = get_robot_manager()
    return manager.get_robot_motor_models_info(robot_id)


@router.post("/robots", response_model=Robot, operation_id="hardware_add_robot")
async def add_robot(robot: Robot, lang: str = Query("en", description="Language code")) -> Robot:
    """
    Add a new robot to management.
    """
    manager = get_robot_manager()
    added = manager.add_robot(robot=robot)
    return resolve_robot(added, lang)


@router.patch("/robots/{robot_id}", response_model=Robot, operation_id="hardware_update_robot")
async def update_robot(
    robot_id: str,
    name: str | None = BODY_UNSET,
    labels: dict[str, str] | None = BODY_UNSET,
    motor_bus_connections: dict[str, dict] | None = BODY_UNSET,
    custom_protection_settings: dict[str, list[dict]] | None = BODY_UNSET_WITH_DESC,
    verify: bool = Query(True, description="Verify robot connectivity after applying updates"),
    lang: str = Query("en", description="Language code"),
) -> Robot:
    """Update robot details."""
    manager = get_robot_manager()
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
    # updated raises ResourceNotFoundError or RobotVerificationError on failure
    updated = manager.update_robot(
        robot_id,
        verify=verify,
        **updates,
    )
    if not updated:
        return Response(status_code=404)
    return resolve_robot(updated, lang)


@router.delete("/robots/{robot_id}", operation_id="hardware_remove_robot")
async def remove_robot(
    robot_id: str,
    delete_data: bool = Query(False, description="Also delete calibration/data files"),
    lang: str = Query("en", description="Language code"),
) -> dict[str, Any]:
    """Remove a robot from management."""
    manager = get_robot_manager()
    success = manager.remove_robot(robot_id, delete_calibration=delete_data)
    if not success:
        raise ResourceNotFoundError("hardware.robot_device.not_found", id=robot_id)
    i18n = get_i18n_service()
    return {"success": True, "message": i18n.translate("hardware.robot_device.removed", lang=lang, id=robot_id)}


@router.get("/robots/{robot_id}/urdf", operation_id="hardware_get_robot_urdf")
@router.get("/robots/{robot_id}/urdf/{path:path}", operation_id="hardware_get_robot_urdf_resource")
async def get_robot_urdf(robot_id: str, path: str | None = None) -> Response:
    """Serve a URDF resource for a robot."""
    if path is None:
        path = "robot.urdf"

    urdf_mgr = get_robot_urdf_manager()
    content = urdf_mgr.get_robot_urdf_resource(robot_id, path)

    if content is None:
        raise ResourceNotFoundError("hardware.robot_device.urdf_resource_not_found")

    return Response(content=content, media_type="text/xml")
# NOTE: udev install logic has been moved to `leropilot.utils.unix`.
# Manual install endpoint is intentionally not exposed. The backend will automatically
# attempt to install udev (and update rules) as needed when a service operation requires it.
# UdevManager provides `ensure_rule_present()` which is idempotent and performs
# atomic updates (and optionally uses `pkexec` when root is required).

# ------------------------- URDF Management Endpoints -------------------------

@router.post("/robots/{robot_id}/urdf", operation_id="hardware_upload_robot_urdf")
async def upload_robot_urdf(
    robot_id: str,
    file: UploadFile = UPLOAD_FILE,
) -> dict[str, Any]:
    """
    Upload a custom URDF for the robot.
    """
    manager = get_robot_manager()
    robot = manager.get_robot(robot_id)
    if not robot:
        raise ResourceNotFoundError("hardware.robot_device.not_found", id=robot_id)
    
    contents = await file.read()
    urdf_mgr = get_robot_urdf_manager()
    saved_path = urdf_mgr.upload_custom_urdf(robot_id, contents)

    # Return standardized response
    result = validate_urdf_file(str(saved_path))




@router.delete("/robots/{robot_id}/urdf", operation_id="hardware_delete_robot_urdf")
async def delete_robot_urdf(robot_id: str) -> Response:
    """Delete a previously uploaded custom URDF for the robot."""
    manager = get_robot_manager()
    robot = manager.get_robot(robot_id)
    if not robot:
        raise ResourceNotFoundError("hardware.robot_device.not_found", id=robot_id)

    urdf_mgr = get_robot_urdf_manager()
    try:
        urdf_mgr.delete_custom_urdf(robot_id)
    except FileNotFoundError:
        raise ResourceNotFoundError("hardware.robot_device.custom_urdf_not_found")
    return Response(status_code=204)


# --------------------------- Camera Service ---------------------------


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
        raise ValidationError("hardware.camera_device.invalid_camera_id")

    svc = get_camera_service()
    frame = svc.capture_snapshot(index, camera_type="USB", width=width, height=height)
    if frame is None:
        raise ResourceNotFoundError("hardware.camera_device.failed_capture_frame")

    ext = ".jpg" if fmt.lower() == "jpeg" else ".png"
    ok, buf = cv2.imencode(ext, frame)
    if not ok:
        raise OperationalError("hardware.camera_device.failed_encode_frame")
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
        raise ValidationError("hardware.camera_device.invalid_camera_id")

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
            await frames.aclose()

    return StreamingResponse(generator(), media_type="multipart/x-mixed-replace; boundary=frame")


# URDF endpoints moved to "Device Management Endpoints" to keep robot-related
# APIs grouped together; implementations are preserved in that section.
