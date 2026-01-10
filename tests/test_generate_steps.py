from leropilot.services.environment.installation import EnvironmentInstallationPlanGenerator
from leropilot.services.config.installation import EnvironmentInstallationConfigService
from leropilot.services.i18n import get_i18n_service
from leropilot.models.environment import EnvironmentConfig
from leropilot.utils import get_resources_dir


def test_generate_plan_for_prospective_env():
    resources_dir = get_resources_dir()
    config_service = EnvironmentInstallationConfigService(resources_dir / "environment_installation_config.json")
    i18n = get_i18n_service()

    generator = EnvironmentInstallationPlanGenerator(config_service, i18n)

    env = EnvironmentConfig(
        id="test-temp-123",
        name="test",
        display_name="Test Env",
        repo_id="official",
        repo_url="https://github.com/huggingface/lerobot.git",
        ref="main",
        python_version="3.11",
        torch_version="2.7.1",
    )

    plan = generator.generate_plan(env, lang='en')

    assert plan is not None
    assert isinstance(plan.steps, list)
    assert len(plan.steps) > 0
