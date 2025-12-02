import asyncio
import logging
import shutil
from pathlib import Path

from leropilot.models.environment import EnvironmentInstallationPlan, EnvironmentInstallStep
from leropilot.services.environment import EnvironmentInstallationExecutor

# Setup logging
logging.basicConfig(level=logging.DEBUG)


async def reproduce() -> None:
    env_id = "test_env_repro"
    env_dir = Path(f"/tmp/leropilot_envs/{env_id}")

    # Clean up
    if env_dir.exists():
        shutil.rmtree(env_dir)
    env_dir.mkdir(parents=True)

    # Create dummy plan
    plan = EnvironmentInstallationPlan(
        env_dir=str(env_dir),
        repo_dir=str(env_dir / "repo"),
        venv_path=str(env_dir / "venv"),
        log_file=str(env_dir / "installation.log"),
        steps=[
            EnvironmentInstallStep(
                id="step_1",
                name="Test Step",
                commands=["echo 'Hello World'", "exit 1"],  # Simulate failure
            )
        ],
        env_vars={},
        default_cwd=str(env_dir),
    )

    with open(env_dir / "installation_plan.json", "w") as f:
        f.write(plan.model_dump_json())

    print(f"Created test environment at {env_dir}")

    executor = EnvironmentInstallationExecutor(env_id, str(env_dir))

    print("Starting installation...")
    result = executor.start()
    print(f"Start result: {result}")

    # Simulate execution loop
    while result.get("next_step"):
        step = result["next_step"]
        print(f"Executing step: {step['name']} command {step['command_index']}")

        # Execute
        exec_res = executor.execute(step["step_id"], step["command_index"])
        print(f"Execute result: {exec_res}")

        # Wait a bit (simulate command running)
        await asyncio.sleep(1)

        # Handle result (simulate failure for the second command)
        exit_code = 0
        if "exit 1" in step["command"]:
            exit_code = 1

        print(f"Reporting result with exit code {exit_code}")
        result = executor.execute(step["step_id"], step["command_index"], exit_code=exit_code)
        print(f"Handle result: {result}")

        if result["status"] == "failed":
            print("Installation failed as expected.")
            break


if __name__ == "__main__":
    asyncio.run(reproduce())
