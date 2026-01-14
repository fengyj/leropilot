from leropilot.models.environment import EnvironmentConfig
from leropilot.services.config.installation import EnvironmentInstallationConfigService
from leropilot.services.environment.installation import EnvironmentInstallationPlanGenerator
from leropilot.services.i18n import get_i18n_service
from leropilot.utils import get_resources_dir

# Prepare services
resources_dir = get_resources_dir()
config_service = EnvironmentInstallationConfigService(resources_dir / "environment_installation_config.json")
i18n = get_i18n_service()

generator = EnvironmentInstallationPlanGenerator(config_service, i18n)

# Construct a prospective env config (not registered)
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

plan = generator.generate_plan(env, lang='zh')
print(f"Generated {len(plan.steps)} steps")
for s in plan.steps[:5]:
    print(f"- {s.id}: {s.name} ({len(s.commands)} cmds)")
print('env_dir:', plan.env_dir)
print('venv_path:', plan.venv_path)
