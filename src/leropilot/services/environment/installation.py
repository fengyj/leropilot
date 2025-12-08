"""Environment installation manager service."""

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from leropilot.core import EnvironmentInstallationConfigService, I18nService
from leropilot.logger import get_logger
from leropilot.models.app_config import AppConfig
from leropilot.models.environment import (
    EnvironmentConfig,
    EnvironmentInstallation,
    EnvironmentInstallationPlan,
    EnvironmentInstallStep,
)
from leropilot.models.installation import (
    EnvironmentInstallStepTemplate,
    VersionConfig,
)

from .manager import EnvironmentManager

logger = get_logger(__name__)


class InstallationManager:
    """Manages installation state and lifecycle for environments."""

    def __init__(self, env_manager: EnvironmentManager) -> None:
        """
        Initialize installation manager.

        Args:
            env_manager: Environment manager instance
        """
        self.env_manager = env_manager
        self.active_installations: dict[str, EnvironmentInstallation] = {}

    def prepare_step_execution_command(self, installation_id: str, step_id: str) -> tuple[list[str], str] | None:
        """
        Prepare command to execute a single installation step.

        Args:
            installation_id: Installation ID
            step_id: Step ID to execute

        Returns:
            Tuple of (argv, cwd) or None if not found
        """
        installation = self.get_installation(installation_id)
        if not installation:
            logger.error(f"Installation not found: {installation_id}")
            return None

        plan = installation.plan

        # Find the specific step
        step = next((s for s in plan.steps if s.id == step_id), None)
        if not step:
            logger.error(f"Step not found: {step_id}")
            return None

        # Create temporary commands file for this step
        env_dir = Path(plan.env_dir)
        step_commands_file = env_dir / f"step_{step_id}_commands.json"

        with open(step_commands_file, "w", encoding="utf-8") as f:
            json.dump(step.commands, f, indent=2, ensure_ascii=False)

        # Merge global env vars with step-specific env vars
        # Step-specific env vars take precedence
        merged_env_vars = {**plan.env_vars, **step.env_vars}

        # Create temporary env vars file
        step_env_file = env_dir / f"step_{step_id}_env.json"
        with open(step_env_file, "w", encoding="utf-8") as f:
            json.dump(merged_env_vars, f, indent=2, ensure_ascii=False)

        # Build command to run script_runner for this step
        argv = [
            sys.executable,
            "-m",
            "leropilot.utils.script_runner",
            "--commands-file",
            str(step_commands_file),
            "--cwd",
            step.cwd or plan.default_cwd,
            "--env-file",
            str(step_env_file),
            "--log-file",
            plan.log_file,
        ]

        # Use step-specific cwd if provided, otherwise use default
        cwd = step.cwd or plan.default_cwd

        return (argv, cwd)

    def create_installation(
        self,
        env_config: EnvironmentConfig,
        plan: EnvironmentInstallationPlan,
    ) -> EnvironmentInstallation:
        """
        Create a new installation with a complete plan.

        Args:
            env_config: Environment configuration
            plan: Complete installation plan

        Returns:
            Installation object
        """
        installation = EnvironmentInstallation(
            id=str(uuid.uuid4()),
            env_config=env_config,
            plan=plan,
            status="pending",
        )

        self.active_installations[installation.id] = installation

        # Save installation plan to disk
        try:
            env_dir = Path(plan.env_dir)

            # Ensure directory exists
            self.env_manager.create_environment_directory(env_dir)

            # Save complete installation plan
            plan_file = env_dir / "installation_plan.json"
            plan_data = {
                "id": installation.id,
                "env_config": env_config.model_dump(mode="json"),
                "plan": plan.model_dump(mode="json"),
                "created_at": datetime.now().isoformat(),
            }

            with open(plan_file, "w", encoding="utf-8") as f:
                json.dump(plan_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved installation plan to {plan_file}")

        except Exception as e:
            logger.error(f"Failed to save installation plan: {e}")
            raise

        logger.info(f"Created installation: {installation.id}")
        return installation

    def get_installation(self, installation_id: str) -> EnvironmentInstallation | None:
        """
        Get installation by ID.

        Args:
            installation_id: Installation ID

        Returns:
            Installation object or None
        """
        # First check memory
        installation = self.active_installations.get(installation_id)

        # Check if there is a status file on disk that is newer
        if installation:
            try:
                from leropilot.core.app_config import get_config

                config = get_config()
                env_dir = config.paths.get_environment_path(installation.env_config.id)
                status_file = env_dir / "installation_status.json"

                if status_file.exists():
                    with open(status_file, encoding="utf-8") as f:
                        status_data = json.load(f)

                    # Update installation object from status file
                    if "status" in status_data:
                        installation.status = status_data["status"]

                    if "steps" in status_data:
                        # Update steps status
                        step_map = {s.id: s for s in installation.plan.steps}
                        for s_data in status_data["steps"]:
                            if s_data["id"] in step_map:
                                step = step_map[s_data["id"]]
                                step.status = s_data.get("status", step.status)
                                # We don't sync logs back to memory to avoid huge memory usage
                                # The frontend gets logs from terminal or we could read them if needed

                    if "completed_at" in status_data and status_data["completed_at"]:
                        installation.completed_at = datetime.fromisoformat(status_data["completed_at"])

            except Exception as e:
                logger.warning(f"Failed to sync installation status from disk: {e}")

        return installation

    def _save_installation_state(self, installation: EnvironmentInstallation) -> None:
        """
        Save installation state to disk.

        Args:
            installation: Installation object
        """
        try:
            env_dir = Path(installation.plan.env_dir)
            state_file = env_dir / "installation_state.json"

            state_data = {
                "id": installation.id,
                "status": installation.status,
                "steps": [
                    {
                        "id": step.id,
                        "status": step.status,
                        "start_time": step.start_time.isoformat() if step.start_time else None,
                        "end_time": step.end_time.isoformat() if step.end_time else None,
                        "exit_code": step.exit_code,
                    }
                    for step in installation.plan.steps
                ],
                "completed_at": installation.completed_at.isoformat() if installation.completed_at else None,
            }

            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save installation state: {e}")

    async def cancel_installation(self, installation_id: str) -> bool:
        """
        Cancel a running installation.

        Args:
            installation_id: Installation ID

        Returns:
            True if cancelled successfully
        """
        installation = self.active_installations.get(installation_id)
        if not installation:
            return False

        # Mark as cancelled in memory
        installation.status = "cancelled"

        # Try to kill the runner process if we can find its PID
        # The runner script should write its PID to status file, but we haven't implemented that yet.
        # For now, we rely on the fact that if the user navigates away or we close the terminal,
        # the process dies.
        # If we want to support explicit cancel button:
        # We could write a "cancel" flag to a file that the runner checks?
        # Or just rely on the user closing the terminal.

        logger.info(f"Cancelled installation: {installation_id}")
        return True


class EnvironmentInstallationPlanGenerator:
    """Generates installation plans based on environment configuration."""

    def __init__(self, config_service: EnvironmentInstallationConfigService, i18n_service: I18nService) -> None:
        """
        Initialize plan generator.

        Args:
            config_service: Configuration service
            i18n_service: I18n service for localization
        """
        self.config_service = config_service
        self.i18n = i18n_service

    def generate_plan(
        self,
        env_config: EnvironmentConfig,
        lang: str = "en",
    ) -> EnvironmentInstallationPlan:
        """
        Generate complete installation plan for an environment.

        Args:
            env_config: Environment configuration
            lang: Language code for localization

        Returns:
            Complete installation plan with all required information
        """
        from leropilot.core.app_config import get_config

        config = get_config()

        # Calculate all paths
        env_dir = config.paths.get_environment_path(env_config.id)
        repo_dir = config.paths.get_repo_path(env_config.repo_id)
        venv_path = config.paths.get_environment_venv_path(env_config.id)
        log_file = env_dir / "installation.log"

        # Get version config from service
        version_config = self.config_service.get_config_for_env(env_config)
        if not version_config:
            logger.error(f"No configuration found for {env_config.repo_url}@{env_config.ref}")
            raise ValueError(f"No configuration found for {env_config.repo_url}@{env_config.ref}")

        # Get platform-specific steps
        platform_steps = self._get_platform_steps(version_config)
        if not platform_steps:
            logger.error(f"No steps defined for platform {sys.platform}")
            raise ValueError(f"No steps defined for platform {sys.platform}")

        # Generate installation steps
        steps = []
        for step_tmpl in platform_steps:
            # Resolve variables in command templates
            commands = self._resolve_commands(step_tmpl, env_config, config)

            # Get localized name and comment
            name = self.i18n.get_step_text(step_tmpl.id, "name", lang)
            comment = self.i18n.get_step_text(step_tmpl.id, "comment", lang)

            # Determine working directory for this step
            cwd = self._resolve_cwd(step_tmpl, env_config, config)

            # Resolve step-specific environment variables
            step_env_vars = self._resolve_env_vars(step_tmpl, env_config, config)

            # Create install step
            step = EnvironmentInstallStep(
                id=step_tmpl.id,
                name=name,
                comment=comment,
                commands=commands,
                cwd=cwd,
                env_vars=step_env_vars,
            )
            steps.append(step)

        # Prepare environment variables
        # Note: We set VIRTUAL_ENV for tools that check it
        # PATH will be prepended with venv/bin by the runner (venv_path parameter)
        # We don't set PATH here because $PATH won't expand in JSON
        env_vars = {
            "VIRTUAL_ENV": str(venv_path),
        }

        # Create complete installation plan
        plan = EnvironmentInstallationPlan(
            env_dir=str(env_dir),
            repo_dir=str(repo_dir),
            venv_path=str(venv_path),
            log_file=str(log_file),
            steps=steps,
            env_vars=env_vars,
            default_cwd=str(repo_dir),  # Default to repo directory
        )

        logger.info(f"Generated installation plan with {len(steps)} steps for {env_config.name}")
        return plan

    def _get_platform_steps(self, version_config: VersionConfig) -> list[EnvironmentInstallStepTemplate]:
        """
        Get platform-specific installation steps.

        Args:
            version_config: Version configuration

        Returns:
            List of platform-specific step templates
        """
        if sys.platform == "darwin":
            return version_config.darwin
        elif sys.platform == "win32":
            return version_config.windows
        else:  # Linux and other Unix-like systems
            return version_config.linux

    def _resolve_commands(
        self,
        step_tmpl: EnvironmentInstallStepTemplate,
        env_config: EnvironmentConfig,
        config: AppConfig,
    ) -> list[str]:
        """
        Resolve variables in command templates.

        Variables:
        - {ref}: Git ref (tag/branch/commit)
        - {python_version}: Python version
        - {venv_path}: Virtual environment path
        - {cache_dir}: Cache directory for downloads
        - {tools_cache_dir}: Tools cache directory
        - {tools_dir}: Global tools directory
        - {env_tools_dir}: Environment-specific tools directory
        - {pytorch_version}: PyTorch version
        - {cuda_tag}: CUDA tag for PyTorch index URL (e.g., cu121, cpu)
        - {extras}: Extras to install (e.g., [aloha,pusht])
        - {repo_path}: Repository path
        - {pypi_mirror}: PyPI mirror index URL parameter (e.g., "--index-url <url>" or "")

        Args:
            step_tmpl: Step template
            env_config: Environment config

        Returns:
            List of resolved command strings
        """
        from leropilot.core.app_config import get_config

        app_config = get_config()

        # Build variable mapping
        venv_path = config.paths.get_environment_venv_path(env_config.id)
        venv_tool_path = config.paths.get_environment_bin_path(env_config.id)
        cuda_tag = self._get_cuda_tag(env_config)
        pypi_mirror = self._get_pypi_mirror_param(app_config)
        repo_path = config.paths.get_repo_path(env_config.repo_id)

        variables = {
            "ref": env_config.ref,
            "python_version": env_config.python_version,
            "venv_path": str(venv_path),
            "cache_dir": str(app_config.paths.cache_dir),
            "tools_cache_dir": str(app_config.paths.get_tools_cache_path()),
            "tools_dir": str(app_config.paths.tools_dir),
            "env_tools_dir": str(venv_tool_path),
            "pytorch_version": env_config.torch_version,
            "torchvision_version": env_config.torchvision_version or "",
            "torchaudio_version": env_config.torchaudio_version or "",
            "cuda_tag": cuda_tag,
            "extras": self._get_extras_spec(env_config),
            "pypi_mirror": pypi_mirror,
            "repo_path": str(repo_path),
        }

        # Resolve each command in the array
        resolved_commands = []
        for command in step_tmpl.commands:
            # Replace variables
            for key, value in variables.items():
                command = command.replace(f"{{{key}}}", value)
            resolved_commands.append(command)

        return resolved_commands

    def _get_cuda_tag(self, env_config: EnvironmentConfig) -> str:
        """
        Get CUDA tag for PyTorch index URL.

        Args:
            env_config: Environment config

        Returns:
            CUDA tag (e.g., "cu121", "cu118", "rocm6.0", "cpu")
        """
        if env_config.cuda_version:
            # Remove dots from CUDA version: "12.1" -> "cu121"
            cuda_ver = env_config.cuda_version.replace(".", "")
            return f"cu{cuda_ver}"
        elif env_config.rocm_version:
            # ROCm format: "6.0" -> "rocm6.0"
            return f"rocm{env_config.rocm_version}"
        else:
            # CPU-only
            return "cpu"

    def _get_extras_spec(self, env_config: EnvironmentConfig) -> str:
        """
        Get extras specification for pip install.

        Args:
            env_config: Environment config

        Returns:
            Extras spec (e.g., "[aloha,pusht]" or "")
        """
        if env_config.extras:
            return "[" + ",".join(env_config.extras) + "]"
        return ""

    def _get_pypi_mirror_param(self, app_config: AppConfig) -> str:
        """
        Get PyPI mirror index URL parameter.

        Args:
            app_config: Application config

        Returns:
            Mirror parameter (e.g., "--index-url https://pypi.tuna.tsinghua.edu.cn/simple" or "")
        """
        # Find enabled mirror (only one can be enabled at a time)
        enabled_mirror = next((m for m in app_config.pypi.mirrors if m.enabled), None)

        if enabled_mirror:
            return f"--index-url {enabled_mirror.url}"

        # No mirror enabled, use official PyPI (no --index-url parameter)
        return ""

    def _resolve_cwd(
        self,
        step_tmpl: EnvironmentInstallStepTemplate,
        env_config: EnvironmentConfig,
        config: AppConfig,
    ) -> str:
        """
        Resolve working directory for a step.

        Args:
            step_tmpl: Step template
            env_config: Environment config
            config: Application config

        Returns:
            Resolved working directory path
        """
        # If step template has explicit cwd, use it
        if hasattr(step_tmpl, "cwd") and step_tmpl.cwd:
            # Resolve variables in cwd
            repo_path = config.paths.get_repo_path(env_config.repo_id)
            cwd = step_tmpl.cwd.replace("{repo_path}", str(repo_path))
            return cwd

        # Default to repo directory for most steps
        repo_path = config.paths.get_repo_path(env_config.repo_id)
        return str(repo_path)

    def _resolve_env_vars(
        self,
        step_tmpl: EnvironmentInstallStepTemplate,
        env_config: EnvironmentConfig,
        config: AppConfig,
    ) -> dict[str, str]:
        """
        Resolve step-specific environment variables.

        Args:
            step_tmpl: Step template
            env_config: Environment config
            config: Application config

        Returns:
            Resolved environment variables
        """
        if not step_tmpl.env_vars:
            return {}

        # Build variable mapping for substitution
        venv_path = config.paths.get_environment_venv_path(env_config.id)
        repo_path = config.paths.get_repo_path(env_config.repo_id)

        variables = {
            "venv_path": str(venv_path),
            "repo_path": str(repo_path),
            "cache_dir": str(config.paths.cache_dir),
            "tools_cache_dir": str(config.paths.get_tools_cache_path()),
        }

        # Resolve each environment variable value
        resolved_env_vars = {}
        for key, value in step_tmpl.env_vars.items():
            # Replace variables in the value
            for var_key, var_value in variables.items():
                value = value.replace(f"{{{var_key}}}", var_value)
            resolved_env_vars[key] = value

        return resolved_env_vars
