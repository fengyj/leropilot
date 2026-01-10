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







    def translate(self, path: str, lang: str = "en", default: str | None = None, **kwargs: object) -> str | None:
        """Translate a dot-separated path into a localized string.

        Resolution strategy:
        - Try flat migration keys first (e.g., `environment.install_steps`),
          then nested keys (e.g., `environment.install.steps`), and finally
          legacy top-level keys (e.g., `steps`, `extras`) if applicable.
        - Expects leaf nodes to be mapping of language codes to strings.
        - Falls back to English when requested lang is missing.
        - If nothing matches, returns `default` when provided, otherwise
          returns the original path string (preserves historical behavior).
        """
        # Build candidate paths in preferred order
        candidates: list[str] = []

        # No automatic path rewriting here — `translate` only attempts the
        # exact path presented. Callers and thin wrappers (e.g. `get_step_text`)
        # are responsible for trying alternate paths (flat -> nested -> legacy).
        candidates.append(path)

        # Deduplicate preserving order
        seen = set()
        candidate_list = [p for p in candidates if not (p in seen or seen.add(p))]

        # Try each candidate path
        for candidate in candidate_list:
            node: Any = self._data
            for part in candidate.split("."):
                if not isinstance(node, dict):
                    node = None
                    break
                node = node.get(part)

            result: str | None = None
            if isinstance(node, dict) and any(isinstance(v, str) for v in node.values()):
                result = node.get(lang) or node.get("en")

            if result is not None:
                # Format with kwargs
                try:
                    return cast(str, result).format(**kwargs)
                except Exception:
                    return cast(str, result)

        # Nothing matched
        if default is not None:
            return default
        return path

    def get_block(self, path: str) -> dict[str, Any]:
        """
        Return a mapping located at the dot-separated `path` inside the loaded
        i18n data.

        This is a generic accessor for callers that need to read a full block
        (e.g., all `environment.lerobot_extra_packages`). It returns an empty
        dict when the path does not exist or does not point to a mapping.
        """
        node: Any = self._data
        for part in path.split("."):
            if not isinstance(node, dict):
                return {}
            node = node.get(part, {})
        return node if isinstance(node, dict) else {}



    def reload(self) -> None:
        """Reload i18n data from file."""
        self._load()
