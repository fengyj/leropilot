"""
Simple test to verify InstallationExecutor and PtySession log filtering.
"""

import json

# Add parent directory to path
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from leropilot.models.environment import EnvironmentInstallationPlan, EnvironmentInstallStep
from leropilot.services.environment import EnvironmentInstallationExecutor
from leropilot.services.pty import PtySession


def test_pty_log_filtering() -> None:
    """Test PtySession log filtering functionality."""
    print("Testing PtySession log filtering...")

    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"

        # Create PTY with log file
        pty = PtySession(cols=80, rows=24, cwd=tmpdir, log_file=str(log_file))

        # Write some commands with ANSI colors
        pty.write_system_message("Test message", color="green")
        time.sleep(0.5)

        # Write a command
        pty.write_command("echo 'Hello World'")
        time.sleep(1)

        # Clean up
        pty.close()

        # Check log file
        if log_file.exists():
            content = log_file.read_text()
            print(f"Log file content:\n{content}")
            print("✓ Log file created successfully")
        else:
            print("✗ Log file not created")


def test_installation_executor() -> None:
    """Test InstallationExecutor basic functionality."""
    print("\nTesting InstallationExecutor...")

    with tempfile.TemporaryDirectory() as tmpdir:
        env_dir = Path(tmpdir)

        # Create a simple installation plan
        plan = EnvironmentInstallationPlan(
            env_dir=str(env_dir),
            repo_dir=str(env_dir / "repo"),
            venv_path=str(env_dir / "venv"),
            log_file=str(env_dir / "installation.log"),
            steps=[
                EnvironmentInstallStep(id="step_1", name="Test Step 1", commands=["echo 'Step 1'"]),
                EnvironmentInstallStep(id="step_2", name="Test Step 2", commands=["echo 'Step 2'"]),
            ],
            env_vars={},
            default_cwd=str(env_dir),
        )

        # Save plan
        plan_file = env_dir / "installation_plan.json"
        with open(plan_file, "w") as f:
            json.dump(plan.model_dump(), f, indent=2)

        # Create executor
        executor = EnvironmentInstallationExecutor(env_id="test", env_dir=str(env_dir))

        try:
            # Start installation
            result = executor.start()
            print(f"Start result: {result}")

            # Check next_step
            if result.get("next_step"):
                print(f"✓ Got first step: {result['next_step']['name']}")
            else:
                print("✗ No next step returned")

            # Clean up
            executor.cleanup()

        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    test_pty_log_filtering()
    test_installation_executor()
    print("\n✨ Tests completed!")
