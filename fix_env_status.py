#!/usr/bin/env python3
"""Fix environment status for existing environments."""

import json
import sys
from pathlib import Path

# Add src to sys.path
sys.path.append(str(Path.cwd() / "src"))

from leropilot.core.app_config import get_config


def fix_environment_status(env_dir: Path) -> bool:
    """Fix status for a single environment.

    Returns:
        True if status was updated, False otherwise
    """
    state_file = env_dir / "installation_state.json"
    if not state_file.exists():
        return False

    try:
        with open(state_file, encoding="utf-8") as f:
            state_data = json.load(f)

        # Get current statuses
        env_config_status = state_data.get("env_config", {}).get("status")

        # Check steps to determine actual status
        steps = state_data.get("plan", {}).get("steps", [])
        if not steps:
            return False

        step_statuses = [s.get("status") for s in steps]

        # Determine correct status
        if all(s == "success" for s in step_statuses):
            # All steps successful
            correct_status = "ready"
            state_data["status"] = "success"
        elif any(s == "error" for s in step_statuses):
            # At least one step failed
            correct_status = "error"
            state_data["status"] = "error"
            # Find first failed step for error message
            for step in steps:
                if step.get("status") == "error":
                    error_msg = f"Step '{step.get('name')}' failed"
                    if step.get("exit_code"):
                        error_msg += f" with exit code {step.get('exit_code')}"
                    state_data["env_config"]["error_message"] = error_msg
                    break
        elif any(s == "running" for s in step_statuses):
            # Installation was interrupted
            correct_status = "error"
            state_data["status"] = "error"
            state_data["env_config"]["error_message"] = "Installation was interrupted"
        else:
            # Pending
            correct_status = "pending"

        # Update if needed
        if env_config_status != correct_status:
            state_data["env_config"]["status"] = correct_status

            # Save updated state
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)

            print(f"✓ Fixed {env_dir.name}: {env_config_status} → {correct_status}")
            return True
        else:
            print(f"  {env_dir.name}: already correct ({correct_status})")
            return False

    except Exception as e:
        print(f"✗ Error fixing {env_dir.name}: {e}")
        return False


def main() -> None:
    """Fix status for all environments."""
    config = get_config()
    envs_dir = config.paths.environments_dir

    if not envs_dir or not envs_dir.exists():
        print("No environments directory found")
        return

    print(f"Checking environments in {envs_dir}...")
    print()

    fixed_count = 0
    total_count = 0

    for env_dir in sorted(envs_dir.iterdir()):
        if env_dir.is_dir():
            total_count += 1
            if fix_environment_status(env_dir):
                fixed_count += 1

    print()
    print(f"Fixed {fixed_count} out of {total_count} environments")


if __name__ == "__main__":
    main()
