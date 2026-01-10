"""Environment creation API endpoints."""

import platform
from functools import lru_cache
from typing import Any, cast

from fastapi import APIRouter, Query

from leropilot.logger import get_logger
from leropilot.models.api.environment import (
    CancelInstallationResponse,
    CreateEnvironmentRequest,
    CreateEnvironmentResponse,
    DeleteEnvironmentResponse,
    EnvironmentListItem,
    ExecuteInstallationResponse,
    ExecuteRequest,
    ExtraInfo,
    GenerateStepsRequest,
    GenerateStepsResponse,
    HardwareInfo,
    HasEnvironmentsResponse,
    InstallationStatusResponse,
    OpenTerminalResponse,
    StartInstallationResponse,
)
from leropilot.models.environment import (
    EnvironmentConfig,
    EnvironmentInstallationPlan,
    EnvironmentInstallStep,
)
from leropilot.services.config import EnvironmentInstallationConfigService, get_config
from leropilot.services.environment import (
    EnvironmentInstallationExecutor,
    EnvironmentInstallationPlanGenerator,
    EnvironmentManager,
    InstallationManager,
    TerminalService,
)
from leropilot.services.git import ExtrasMetadataService, RepositoryExtrasInspector
from leropilot.services.hardware import GPUDetector
from leropilot.services.i18n import get_i18n_service
from leropilot.utils import get_resources_dir

logger = get_logger(__name__)
router = APIRouter(prefix="/api/environments", tags=["environments"])

# Dependency injection functions


@lru_cache
def get_services() -> tuple[EnvironmentInstallationConfigService, GPUDetector]:
    """Get or initialize services (singleton)."""
    resources_dir = get_resources_dir()
    config_service = EnvironmentInstallationConfigService(resources_dir / "environment_installation_config.json")
    gpu_detector = GPUDetector()
    return config_service, gpu_detector


@lru_cache
def get_env_manager() -> EnvironmentManager:
    """Get or initialize environment manager (singleton)."""
    from leropilot.services.environment import get_env_manager as _get_env_manager

    return _get_env_manager()


@lru_cache
def get_installation_executor() -> InstallationManager:
    """Get or initialize installation executor (singleton)."""
    return InstallationManager(get_env_manager())


# Active executors storage (consider using Redis/DB in production)
_active_executors: dict[str, EnvironmentInstallationExecutor] = {}

# API response cache for React strict mode protection
_api_cache: dict[str, Any] = {}


def clear_env_cache(env_id: str) -> None:
    """Clear execution cache for an environment."""
    # For now, we just clear the entire cache as we don't track env_id per execution_id
    # and this is a single-user application.
    _api_cache.clear()


# Request/Response Models


# Endpoints


@router.get("/has-environments", response_model=HasEnvironmentsResponse)
async def get_has_environments() -> HasEnvironmentsResponse:
    """Check if any environments have been created.

    Returns:
        Dictionary with has_environments boolean
    """
    env_manager = get_env_manager()
    has_envs = len(env_manager.list_environments()) > 0
    return HasEnvironmentsResponse(has_environments=has_envs)


@router.get("", response_model=list[EnvironmentListItem])
async def list_environments() -> list[EnvironmentListItem]:
    """
    List all environments.

    Returns:
        List of environment list items
    """
    env_manager = get_env_manager()
    return env_manager.list_environments()


@router.get("/hardware", response_model=HardwareInfo)
async def get_hardware_info() -> HardwareInfo:
    """
    Get detected hardware information.

    Returns:
        Hardware detection results
    """
    config_service, gpu_detector = get_services()

    gpu_info = gpu_detector.detect()

    # Build response
    hardware_info = HardwareInfo(
        detected_cuda=gpu_info.cuda_version,
        detected_rocm=gpu_info.rocm_version,
        detected_driver=gpu_info.driver_version,
        detected_gpu=gpu_info.gpu_name,
        has_nvidia_gpu=gpu_info.has_nvidia_gpu,
        has_amd_gpu=gpu_info.has_amd_gpu,
        is_apple_silicon=gpu_info.is_apple_silicon,
    )

    return hardware_info


@router.get("/extras", response_model=list[ExtraInfo])
async def get_available_extras(
    repo_id: str = Query(..., description="Repository ID"),
    ref: str = Query("main", description="Git ref (branch/tag)"),
    lang: str = Query("en", description="Language code"),
) -> list[ExtraInfo]:
    """
    Get available extras for a repository version.
    """
    i18n_service = get_i18n_service()

    # Get repository path from cache
    config = get_config()
    repo_path = config.paths.get_repo_path(repo_id)

    if not repo_path.exists():
        return []

    # Inspect repository
    from leropilot.services.git import GitToolManager

    git_manager = GitToolManager()
    git_path = git_manager.get_git_executable()

    inspector = RepositoryExtrasInspector(repo_path, git_path)
    raw_extras = inspector.get_available_extras(ref)

    # Enrich with metadata
    metadata_service = ExtrasMetadataService(i18n_service)
    enriched = metadata_service.enrich_extras(raw_extras, lang)

    return [
        ExtraInfo(
            id=extra["id"],
            name=extra["name"],
            description=extra["description"],
            category=extra["category"],
            category_label=extra["category_label"],
        )
        for extra in enriched
    ]


@router.post("/generate-steps", response_model=GenerateStepsResponse)
async def generate_installation_steps(
    request: GenerateStepsRequest,
    lang: str = Query("en", description="Language code"),
) -> GenerateStepsResponse:
    """
    Generate installation steps preview based on configuration.
    """
    config_service, _ = get_services()
    i18n_service = get_i18n_service()

    # Generate complete installation plan
    generator = EnvironmentInstallationPlanGenerator(config_service, i18n_service)
    plan = generator.generate_plan(request.env_config, lang)

    return GenerateStepsResponse(steps=plan.steps)


@router.post("/create", response_model=CreateEnvironmentResponse)
async def create_environment(
    request: CreateEnvironmentRequest,
    lang: str = Query("en", description="Language code"),
) -> CreateEnvironmentResponse:
    """
    Start environment creation/installation.
    """
    config_service, _ = get_services()
    i18n_service = get_i18n_service()
    executor = get_installation_executor()
    env_manager = get_env_manager()

    # Register environment in registry FIRST (before any path resolution)
    env_manager.register_environment(request.env_config)

    # Use custom steps if provided, otherwise generate from config
    if request.custom_steps:
        from leropilot.services.config import get_config
        from leropilot.services.environment import get_path_resolver

        config = get_config()
        path_resolver = get_path_resolver()
        env_config = request.env_config

        # Calculate paths
        env_dir = path_resolver.get_environment_path(env_config.id)
        repo_dir = config.paths.get_repo_path(env_config.repo_id)
        venv_path = path_resolver.get_environment_venv_path(env_config.id)
        log_file = env_dir / "installation.log"

        # Prepare environment variables
        from leropilot.models.environment import EnvironmentInstallationPlan

        env_vars = {
            "VIRTUAL_ENV": str(venv_path),
        }

        plan = EnvironmentInstallationPlan(
            env_dir=str(env_dir),
            repo_dir=str(repo_dir),
            venv_path=str(venv_path),
            log_file=str(log_file),
            steps=request.custom_steps,
            env_vars=env_vars,
            default_cwd=str(repo_dir),
        )
    else:
        # Generate plan from configuration
        generator = EnvironmentInstallationPlanGenerator(config_service, i18n_service)
        plan = generator.generate_plan(request.env_config, lang)

    # Create installation with plan
    installation = executor.create_installation(request.env_config, plan)

    return CreateEnvironmentResponse(
        installation_id=installation.id,
        env_id=installation.env_config.id,
        status=installation.status,
        steps=[
            EnvironmentInstallStep(
                id=step.id,
                name=step.name,
                comment=step.comment,
                commands=step.commands,
                status=step.status,
                logs=step.logs[-10:],
            )
            for step in installation.plan.steps
        ],
        message="Installation created",
    )


@router.get("/{env_id}/installation", response_model=InstallationStatusResponse)
async def get_environment_installation_status(env_id: str) -> InstallationStatusResponse:
    """
    Get installation status for a specific environment.
    """
    executor = get_installation_executor()

    # Find the active installation for this environment
    installation = None
    for _inst_id, inst in executor.active_installations.items():
        if inst.env_config.id == env_id:
            installation = inst
            break

    if not installation:
        raise ResourceNotFoundError("environment.instance.install_no_active", id=env_id)

    # Calculate progress
    total_steps = len(installation.plan.steps)
    completed_steps = sum(1 for step in installation.plan.steps if step.status == "success")
    progress = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0

    return InstallationStatusResponse(
        installation_id=installation.id,
        env_id=installation.env_config.id,
        status=installation.status,
        progress=progress,
        steps=[
            EnvironmentInstallStep(
                id=step.id,
                name=step.name,
                comment=step.comment,
                commands=step.commands,
                status=step.status,
                logs=step.logs[-10:],
            )
            for step in installation.plan.steps
        ],
        created_at=installation.created_at,
        completed_at=installation.completed_at,
    )


@router.post("/{env_id}/installation/cancel", response_model=CancelInstallationResponse)
async def cancel_environment_installation(env_id: str) -> CancelInstallationResponse:
    """
    Cancel the active installation for a specific environment.
    """
    executor = get_installation_executor()

    # Find the active installation for this environment
    installation_id = None
    for _inst_id, inst in executor.active_installations.items():
        if inst.env_config.id == env_id:
            installation_id = _inst_id
            break

    if not installation_id:
        raise ResourceNotFoundError("environment.instance.install_no_active", id=env_id)

    success = await executor.cancel_installation(installation_id)

    if not success:
        raise ValidationError("environment.instance.install_cannot_cancel")

    return CancelInstallationResponse(success=True, message="Installation cancelled")


@router.get("/{env_id}")
async def get_environment_details(env_id: str) -> EnvironmentConfig:
    """
    Get detailed information about a specific environment.
    """
    env_manager = get_env_manager()
    env_config = env_manager.load_environment_config(env_id)

    if not env_config:
        raise ResourceNotFoundError("environment.instance.not_found", id=env_id)

    return env_config


@router.delete("/{env_id}", response_model=DeleteEnvironmentResponse)
async def delete_environment(env_id: str) -> DeleteEnvironmentResponse:
    """
    Delete an environment.
    """
    env_manager = get_env_manager()
    env_manager.delete_environment(env_id)
    return DeleteEnvironmentResponse(success=True, message=f"Environment {env_id} deleted successfully")


@router.post("/{env_id}/installation/start", response_model=StartInstallationResponse)
async def start_installation(env_id: str) -> StartInstallationResponse:
    """
    Start environment installation.
    """
    # Check if there's already an active executor for this environment
    existing_executor = _active_executors.get(env_id)
    if existing_executor and existing_executor.installation and existing_executor.installation.session_id:
        # Return existing session information
        session_id = existing_executor.installation.session_id
        assert existing_executor.plan is not None
        env_name = existing_executor.installation.env_config.display_name
        return StartInstallationResponse(
            session_id=session_id,
            plan=existing_executor.plan,
            env_name=env_name,
            is_windows=platform.system() == "Windows",
        )

    from leropilot.services.environment import get_path_resolver

    path_resolver = get_path_resolver()
    env_dir = path_resolver.get_environment_path(env_id)
    executor = EnvironmentInstallationExecutor(env_id, str(env_dir))

    result = executor.start()

    # Store executor for later use
    _active_executors[env_id] = executor

    # Get environment display name
    env_name = executor.installation.env_config.display_name if executor.installation else env_id
    return StartInstallationResponse(
        session_id=result["session_id"],
        plan=EnvironmentInstallationPlan(**result["plan"]),
        env_name=env_name,
        is_windows=platform.system() == "Windows",
    )


@router.post("/{env_id}/installation/execute", response_model=ExecuteInstallationResponse)
async def execute_installation(env_id: str, request: ExecuteRequest) -> ExecuteInstallationResponse:
    """
    Execute a command or report execution result.
    """
    # Check for cached response (React strict mode protection)
    if request.execution_id and request.execution_id in _api_cache:
        return cast(ExecuteInstallationResponse, _api_cache[request.execution_id])

    executor = _active_executors.get(env_id)
    if not executor:
        raise ResourceNotFoundError("environment.instance.install_session_not_found", id=env_id)

    result = executor.execute(
        step_id=request.step_id, command_index=request.command_index, exit_code=request.exit_code
    )

    # Cache the response if we have an execution_id
    if request.execution_id:
        _api_cache[request.execution_id] = result

    # Clean up executor if installation is completed or failed
    if result.get("status") in ["completed", "failed"]:
        executor.cleanup()
        _active_executors.pop(env_id, None)
        # Clean up execution cache for this environment
        clear_env_cache(env_id)

    return ExecuteInstallationResponse(**result)


@router.get("/{env_id}/installation/status", response_model=InstallationStatusResponse)
async def get_installation_status(env_id: str) -> InstallationStatusResponse:
    """
    Get current installation status and steps.
    """
    executor = _active_executors.get(env_id)

    # If not in memory, try to load from disk
    if not executor:
        try:
            from leropilot.services.environment import get_path_resolver

            path_resolver = get_path_resolver()
            env_dir = path_resolver.get_environment_path(env_id)
            if env_dir.exists():
                executor = EnvironmentInstallationExecutor(env_id, str(env_dir))
                # This will load existing state if available
                if executor.installation and executor.installation.status != "pending":
                    _active_executors[env_id] = executor
        except Exception as e:
            logger.warning(f"Failed to load executor for {env_id}: {e}")

    if not executor or not executor.installation:
        raise ResourceNotFoundError("environment.instance.install_not_found")

    assert executor.plan is not None

    # Calculate progress
    total_steps = len(executor.plan.steps)
    completed_steps = sum(1 for step in executor.plan.steps if step.status == "success")
    progress = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0

    return InstallationStatusResponse(
        installation_id=executor.installation.id,
        env_id=env_id,
        status=executor.installation.status,
        progress=progress,
        steps=[
            EnvironmentInstallStep(
                id=step.id,
                name=step.name,
                status=step.status,
                commands=step.commands,  # Required field
            )
            for step in executor.plan.steps
        ],
        created_at=executor.installation.created_at,
        completed_at=executor.installation.completed_at,
    )


@router.post("/{env_id}/open-terminal", response_model=OpenTerminalResponse)
async def open_terminal(env_id: str) -> OpenTerminalResponse:
    """
    Open a system terminal for the environment with virtual environment activated.
    """
    env_manager = get_env_manager()
    env_config = env_manager.load_environment_config(env_id)

    if not env_config:
        raise ResourceNotFoundError("environment.instance.not_found", id=env_id)

    if env_config.status != "ready":
        raise ValidationError("environment.instance.not_ready_open_terminal")

    # Get paths
    from leropilot.services.environment import get_path_resolver

    path_resolver = get_path_resolver()
    env_dir = path_resolver.get_environment_path(env_id)
    venv_path = path_resolver.get_environment_venv_path(env_id)

    TerminalService.open_terminal(env_dir, venv_path)
    return OpenTerminalResponse(success=True, message="Terminal opened successfully")
