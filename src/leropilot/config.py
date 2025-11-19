from pathlib import Path

import yaml
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    data_dir: Path = Path.home() / ".leropilot"
    port: int = 8000

    model_config = {
        "env_prefix": "LEROPILOT_",
    }

    @classmethod
    def load(cls) -> "AppConfig":
        config_path = Path.home() / ".leropilot" / "config.yaml"
        config_data = {}

        if config_path.exists():
            with open(config_path) as f:
                config_data = yaml.safe_load(f) or {}

        return cls(**config_data)


_config: AppConfig | None = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config
