"""Environment installation executor service."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from leropilot.logger import get_logger
from leropilot.models.environment import (
    EnvironmentConfig,
    EnvironmentInstallation,
    EnvironmentInstallationPlan,
    EnvironmentInstallStep,
)
from leropilot.services.pty import PtySession

logger = get_logger(__name__)


class EnvironmentInstallationExecutor:
    """Manages the execution of environment installation steps."""

    def __init__(self, env_id: str, env_dir: str) -> None:
        self.env_id = env_id
        self.env_dir = Path(env_dir)
        self.plan: EnvironmentInstallationPlan | None = None
        self.installation: EnvironmentInstallation | None = None
        self.pty_session: PtySession | None = None
        self.current_step_index = 0

        # Execution tracking for React strict mode protection
        self._executing_commands: set[tuple[str, int]] = set()  # (step_id, command_index)

    def start(self) -> dict[str, Any]:
        """
        Start installation: create PTY session and return plan.
        Always starts from the beginning (no resume support).

        Returns:
            dict with session_id, plan
        """
        logger.info(f"[EnvironmentInstallationExecutor] Starting installation for env_id: {self.env_id}")

        # Load installation plan
        logger.info(f"[EnvironmentInstallationExecutor] Loading installation plan from {self.env_dir}")
        self.plan = self._load_plan()
        if not self.plan:
            raise ValueError("Installation plan not found")
        logger.info(f"[EnvironmentInstallationExecutor] Plan loaded successfully with {len(self.plan.steps)} steps")

        # Delete old state file (always start fresh)
        state_file = self.env_dir / "installation_state.json"
        if state_file.exists():
            state_file.unlink()
            logger.info("[EnvironmentInstallationExecutor] Deleted old state file")

        # Initialize new installation
        logger.info("[EnvironmentInstallationExecutor] Initializing installation state")
        self.installation = self._load_or_init_installation()
        self.current_step_index = 0

        # Create PTY session with log file
        logger.info("[EnvironmentInstallationExecutor] Creating PTY session")
        log_file = str(self.env_dir / "installation.log")
        self.pty_session = PtySession(cols=80, rows=24, cwd=self.plan.repo_dir, log_file=log_file)
        logger.info(f"[EnvironmentInstallationExecutor] PTY session created: {self.pty_session.session_id}")

        self.installation.session_id = self.pty_session.session_id
        # Update env_config status to installing
        self.installation.env_config.status = "installing"

        # Write start message
        logger.info("[EnvironmentInstallationExecutor] Writing start message to PTY")
        # start_msg = "Starting environment installation..."
        assert self.pty_session is not None
        # self.pty_session.write_system_message(start_msg, color="green")

        # Save state with session_id
        logger.info("[EnvironmentInstallationExecutor] Saving installation state")
        self._save_state()

        session_id = self.pty_session.session_id
        logger.info(
            f"[EnvironmentInstallationExecutor] Installation started successfully, returning session_id: {session_id}"
        )
        return {"session_id": self.pty_session.session_id, "plan": self.plan.model_dump()}

    def execute(self, step_id: str, command_index: int, exit_code: int | None = None) -> dict[str, Any]:
        """
        Execute command or handle execution result.

        Args:
            step_id: ID of the step
            command_index: Index of the command within the step
            exit_code: If provided, marks the command as completed with this exit code

        Returns:
            dict with status and next_step (if applicable)
        """
        assert self.plan is not None
        assert self.installation is not None
        assert self.pty_session is not None

        if exit_code is None:
            # First call: execute the command
            return self._execute_command(step_id, command_index)
        else:
            # Second call: handle the result
            return self._handle_result(step_id, command_index, exit_code)

    def _execute_command(self, step_id: str, command_index: int) -> dict[str, Any]:
        """Execute the specified command."""
        step = self._find_step(step_id)
        if not step:
            raise ValueError(f"Step {step_id} not found")

        if command_index >= len(step.commands):
            raise ValueError(f"Command index {command_index} out of range")

        # Check if this command is already being executed
        command_key = (step_id, command_index)
        if command_key in self._executing_commands:
            logger.warning(f"Command {step_id}:{command_index} is already being executed")
            return {"status": "already_executing", "step_id": step_id, "command_index": command_index}

        self._executing_commands.add(command_key)

        # Write start message on first command
        if command_index == 0:
            assert self.pty_session is not None
            # start_msg = f"▶ Starting: {step.name}"
            # self.pty_session.write_system_message(start_msg, color="blue")
            step.status = "running"
            step.start_time = datetime.now()

        # Execute the specific command
        command = step.commands[command_index]
        if command:
            assert self.pty_session is not None
            # Execute command directly - Shell Integration will report exit code via OSC 633
            self.pty_session.write_command(command)

        self._save_state()
        return {"status": "executing", "step_id": step_id, "command_index": command_index}

    def _handle_result(self, step_id: str, command_index: int, exit_code: int) -> dict[str, Any]:
        """Handle command execution result."""
        assert self.plan is not None
        assert self.installation is not None
        assert self.pty_session is not None

        # Remove from executing commands
        command_key = (step_id, command_index)
        self._executing_commands.discard(command_key)

        step = self._find_step(step_id)
        if not step:
            return {"status": "error", "error": "Step not found"}

        if exit_code != 0:
            # Command failed
            step.exit_code = exit_code
            step.end_time = datetime.now()
            step.status = "error"
            self._save_state()

            error_msg = f"✗ Failed: {step.name} (exit code: {exit_code})"
            assert self.pty_session is not None
            assert self.pty_session is not None
            # self.pty_session.write_system_message(error_msg, color="red")

            assert self.installation is not None
            self.installation.status = "error"
            # Update env_config status to error
            self.installation.env_config.status = "error"
            self.installation.env_config.error_message = f"Step '{step.name}' failed with exit code {exit_code}"
            self._save_state()

            return {"status": "failed", "error": error_msg}

        # Command succeeded
        self._save_state()

        # Check if there are more commands in this step
        if command_index < len(step.commands) - 1:
            # More commands in this step
            next_command_index = command_index + 1
            return {
                "status": "next",
                "next_step": {
                    "step_id": step.id,
                    "step_index": self.current_step_index,
                    "total_steps": len(self.plan.steps),
                    "command_index": next_command_index,
                    "command": step.commands[next_command_index],
                    "name": step.name,
                },
            }

        # All commands in this step completed
        step.status = "success"
        step.exit_code = 0
        step.end_time = datetime.now()
        self._save_state()

        # success_msg = f"✓ Completed: {step.name}"
        # self.pty_session.write_system_message(success_msg, color="green")

        # Move to next step
        self.current_step_index += 1
        next_step = self.get_next_command()

        if next_step:
            return {"status": "next", "next_step": next_step}
        else:
            # All steps completed
            self.installation.status = "success"
            # Update env_config status to ready
            self.installation.env_config.status = "ready"
            self.installation.completed_at = datetime.now()
            self._save_state()

            complete_msg = "✨ Installation completed successfully!"
            self.pty_session.write_system_message(complete_msg, color="green")
            return {"status": "completed"}

    def get_next_command(self) -> dict[str, Any] | None:
        """Get the next command to execute."""
        assert self.plan is not None
        if self.current_step_index >= len(self.plan.steps):
            return None

        step = self.plan.steps[self.current_step_index]

        # Get the first command (always start from beginning of step)
        command_index = 0
        command = step.commands[command_index] if step.commands else ""

        return {
            "step_id": step.id,
            "step_index": self.current_step_index,
            "total_steps": len(self.plan.steps),
            "command_index": command_index,
            "command": command,
            "name": step.name,
        }

    def cleanup(self) -> None:
        """Cleanup resources."""
        if self.pty_session:
            logger.info(f"[EnvironmentInstallationExecutor] Cleaning up PTY session {self.pty_session.session_id}")
            self.pty_session.close()
            self.pty_session = None

        # Clear execution tracking
        self._executing_commands.clear()

    def _find_step(self, step_id: str) -> EnvironmentInstallStep | None:
        """Find a step by ID."""
        assert self.plan is not None
        for step in self.plan.steps:
            if step.id == step_id:
                return step
        return None

    def _load_plan(self) -> EnvironmentInstallationPlan | None:
        """Load installation plan from file."""
        plan_file = self.env_dir / "installation_plan.json"
        if not plan_file.exists():
            logger.error(f"Installation plan file not found: {plan_file}")
            return None

        try:
            with open(plan_file, encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Loaded plan data keys: {list(data.keys())}")
                # The plan data is nested under the "plan" key
                if "plan" in data:
                    logger.info(f"Plan data keys: {list(data['plan'].keys())}")
                    plan = EnvironmentInstallationPlan(**data["plan"])
                    logger.info(f"Successfully created InstallationPlan with {len(plan.steps)} steps")
                    return plan
                else:
                    # Fallback for old format
                    logger.warning("No 'plan' key found, trying old format")
                    return EnvironmentInstallationPlan(**data)
        except Exception as e:
            logger.error(f"Failed to load installation plan: {e}")
            logger.error(f"Exception type: {type(e)}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _load_or_init_installation(self) -> EnvironmentInstallation:
        """Load or initialize installation state."""
        state_file = self.env_dir / "installation_state.json"

        if state_file.exists():
            try:
                with open(state_file, encoding="utf-8") as f:
                    data = json.load(f)
                    return EnvironmentInstallation(**cast(dict[str, Any], data))
            except Exception as e:
                logger.warning(f"Failed to load installation state: {e}")

        # Load env_config from plan file
        env_config = self._load_env_config()
        assert env_config is not None

        # Create new installation (session_id will be set later in start())
        assert self.plan is not None
        return EnvironmentInstallation(id=str(uuid.uuid4()), env_config=env_config, plan=self.plan, status="pending")

    def _save_state(self) -> None:
        """Save installation state to file."""
        if not self.installation:
            return

        state_file = self.env_dir / "installation_state.json"

        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(self.installation.model_dump(), f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save installation state: {e}")

    def _load_env_config(self) -> EnvironmentConfig | None:
        """Load environment config from plan file."""
        plan_file = self.env_dir / "installation_plan.json"
        if not plan_file.exists():
            return None

        try:
            with open(plan_file, encoding="utf-8") as f:
                data = json.load(f)
                if "env_config" in data:
                    from leropilot.models.environment import EnvironmentConfig

                    return EnvironmentConfig(**data["env_config"])
        except Exception as e:
            logger.error(f"Failed to load env config: {e}")

        return None
