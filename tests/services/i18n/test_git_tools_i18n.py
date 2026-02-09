from leropilot.services.git.tools import GitToolManager


class DummyI18n:
    def translate(self, path: str, lang: str = "en", **kwargs: object) -> str:
        assert path == "app_settings.git.downloading_progress"
        return f"DL {kwargs.get('percent')}%"


def test_git_tool_manager_uses_translate() -> None:
    g = GitToolManager(i18n_service=DummyI18n())
    msg = g._get_message("downloading_progress", lang="en", percent=42)
    assert msg == "DL 42%"
