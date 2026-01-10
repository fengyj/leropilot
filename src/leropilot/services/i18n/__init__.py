"""Internationalization services."""

from .service import I18nService

_instance: I18nService | None = None


def get_i18n_service() -> I18nService:
    """Get the global I18nService instance."""
    global _instance
    if _instance is None:
        from leropilot.utils.paths import get_resources_dir

        _instance = I18nService(get_resources_dir() / "i18n.json")
    return _instance


__all__ = ["I18nService", "get_i18n_service"]
