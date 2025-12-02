import sys
from pathlib import Path

# Add src to sys.path
sys.path.append(str(Path.cwd() / "src"))

from leropilot.core.app_config import get_config
from leropilot.services.environment.manager import EnvironmentManager


def check_environments() -> None:
    print("Checking environments...")
    try:
        config = get_config()
        print(f"Environments directory: {config.paths.environments_dir}")

        if not config.paths.environments_dir or not config.paths.environments_dir.exists():
            print("Environments directory does not exist!")
        else:
            print("Directory contents:")
            for item in config.paths.environments_dir.iterdir():
                print(f" - {item.name} (is_dir={item.is_dir()})")
                if item.is_dir():
                    config_file = item / "config.json"
                    plan_file = item / "installation_plan.json"
                    state_file = item / "installation_state.json"
                    print(f"   config.json exists: {config_file.exists()}")
                    print(f"   installation_plan.json exists: {plan_file.exists()}")
                    print(f"   installation_state.json exists: {state_file.exists()}")

                    # Read first installation_state.json to see structure
                    if state_file.exists():
                        import json

                        with open(state_file) as f:
                            state_data = json.load(f)
                        print(f"   State keys: {list(state_data.keys())}")
                        print(f"   env_config.status: {state_data.get('env_config', {}).get('status')}")
                        print(f"   installation.status: {state_data.get('status')}")

                        # Check steps status
                        steps = state_data.get("plan", {}).get("steps", [])
                        if steps:
                            step_statuses = [s.get("status") for s in steps]
                            print(f"   Steps count: {len(steps)}")
                            print(f"   Steps statuses: {set(step_statuses)}")
                            all_success = all(s == "success" for s in step_statuses)
                            print(f"   All steps successful: {all_success}")
                        break

        manager = EnvironmentManager()
        envs = manager.list_environments()
        print(f"Found {len(envs)} environments:")
        for env in envs:
            print(f" - {env.display_name} ({env.id})")

    except Exception as e:
        print(f"Error listing environments: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    check_environments()
