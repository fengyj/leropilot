"""Internationalization service for LeRoPilot."""

import json
from pathlib import Path
from typing import Any, cast

from leropilot.logger import get_logger

logger = get_logger(__name__)


class I18nService:
    """
    Loads and provides localized strings from i18n.json.

    Structure ensures consistency across languages:
    {
        "steps": {
            "create_venv": {
                "name": { "en": "Create Virtual Environment", "zh": "创建虚拟环境" },
                "comment": { "en": "...", "zh": "..." }
            }
        },
        "extras": {
            "aloha": {
                "name": { "en": "Aloha", "zh": "Aloha" },
                "description": { "en": "...", "zh": "..." },
                "category": "robots"
            }
        }
    }
    """

    def __init__(self, i18n_file: Path) -> None:
        """
        Initialize I18n service.

        Args:
            i18n_file: Path to i18n.json file
        """
        self.i18n_file = i18n_file
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load i18n data from file."""
        try:
            if self.i18n_file.exists():
                with open(self.i18n_file, encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info(f"Loaded i18n data from {self.i18n_file}")
            else:
                logger.warning(f"I18n file not found: {self.i18n_file}")
                self._data = {}
        except Exception as e:
            logger.error(f"Failed to load i18n file: {e}")
            self._data = {}

    def get_step_text(self, step_id: str, field: str, lang: str = "en") -> str:
        """
        Get localized text for an installation step.

        Args:
            step_id: Step identifier (e.g., "create_venv")
            field: Field name (e.g., "name", "comment")
            lang: Language code (e.g., "en", "zh")

        Returns:
            Localized text, or step_id if not found
        """
        try:
            text = self._data.get("steps", {}).get(step_id, {}).get(field, {}).get(lang)
            if text:
                return cast(str, text)
        except (KeyError, AttributeError):
            pass

        # Fallback to English
        if lang != "en":
            try:
                text = self._data.get("steps", {}).get(step_id, {}).get(field, {}).get("en")
                if text:
                    return cast(str, text)
            except (KeyError, AttributeError):
                pass

        # Ultimate fallback
        return step_id

    def get_category_label(self, category: str, lang: str = "en") -> str:
        """
        Get localized label for a category.

        Args:
            category: Category identifier (e.g., "robots")
            lang: Language code

        Returns:
            Localized label
        """
        try:
            label = self._data.get("categories", {}).get(category, {}).get(lang)
            if label:
                return cast(str, label)
        except (KeyError, AttributeError):
            pass

        # Fallback to English
        if lang != "en":
            try:
                label = self._data.get("categories", {}).get(category, {}).get("en")
                if label:
                    return cast(str, label)
            except (KeyError, AttributeError):
                pass

        return category

    def get_extra_info(self, extra_key: str, lang: str = "en") -> dict[str, str]:
        """
        Get localized information for an extra.

        Args:
            extra_key: Extra identifier (e.g., "aloha")
            lang: Language code

        Returns:
            Dictionary with name, description, and category
        """
        try:
            extra_data = self._data.get("extras", {}).get(extra_key, {})
            if not extra_data:
                # Fallback: use key as name
                return {
                    "name": extra_key,
                    "description": "",
                    "category": "other",
                    "category_label": self.get_category_label("other", lang),
                }

            name = extra_data.get("name", {}).get(lang) or extra_data.get("name", {}).get("en") or extra_key
            description = (
                extra_data.get("description", {}).get(lang) or extra_data.get("description", {}).get("en") or ""
            )
            category = extra_data.get("category", "other")
            category_label = self.get_category_label(category, lang)

            return {
                "name": name,
                "description": description,
                "category": category,
                "category_label": category_label,
            }
        except (KeyError, AttributeError):
            return {
                "name": extra_key,
                "description": "",
                "category": "other",
                "category_label": self.get_category_label("other", lang),
            }

    def reload(self) -> None:
        """Reload i18n data from file."""
        self._load()
