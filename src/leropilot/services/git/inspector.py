"""Repository inspection and extras metadata service."""

import subprocess
from pathlib import Path

import tomllib

from leropilot.logger import get_logger
from leropilot.services.i18n import I18nService

logger = get_logger(__name__)


class RepositoryExtrasInspector:
    """Inspects a local git repository to extract metadata."""

    # Extras to exclude (development/testing only)
    EXCLUDED_EXTRAS = {"dev", "test", "tests", "doc", "docs", "quality", "lint", "video_benchmark"}

    def __init__(self, repo_path: Path, git_path: str = "git") -> None:
        """
        Initialize repo inspector.

        Args:
            repo_path: Path to git repository
            git_path: Path to git executable
        """
        self.repo_path = repo_path
        self.git_path = git_path

    def get_available_extras(self, ref: str = "HEAD") -> list[str]:
        """
        Parse pyproject.toml at the given ref to find optional-dependencies.
        Filters out dev/test/doc/quality groups.

        Args:
            ref: Git ref (branch, tag, or commit)

        Returns:
            List of extra keys (e.g., ['aloha', 'pusht'])
        """
        try:
            # Get pyproject.toml content from git
            # Method: Use git archive to extract the file to stdout as a tar stream,
            # then read the file content. This avoids encoding issues with git show on Windows.
            cmd = [self.git_path, "archive", ref, "pyproject.toml"]
            logger.info(f"Running command: {' '.join(cmd)} in {self.repo_path}")

            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                check=True,
                timeout=10,
            )

            # Extract file content from tar archive
            import io
            import tarfile

            try:
                tar_bytes = io.BytesIO(result.stdout)
                with tarfile.open(fileobj=tar_bytes, mode="r") as tar:
                    member = tar.getmember("pyproject.toml")
                    f = tar.extractfile(member)
                    if f is None:
                        logger.warning(f"Could not extract pyproject.toml from tar for ref {ref}")
                        return []
                    stdout_content = f.read().decode("utf-8")
            except Exception as e:
                logger.warning(f"Failed to extract pyproject.toml from tar: {e}")
                return []

            # Check if content is empty
            if not stdout_content:
                logger.warning(f"Empty pyproject.toml content for ref {ref}")
                return []

            logger.info(f"Got pyproject.toml content, length: {len(stdout_content)} chars")

            # Parse TOML
            pyproject = tomllib.loads(stdout_content)

            # Debug logging
            logger.info(f"Repo path: {self.repo_path}")
            logger.info(f"Git path: {self.git_path}")
            logger.info(f"Ref: {ref}")
            logger.info(f"Pyproject keys: {list(pyproject.keys())}")

            # Extract optional-dependencies
            optional_deps = pyproject.get("project", {}).get("optional-dependencies", {})
            logger.info(f"Raw optional-dependencies: {list(optional_deps.keys())}")

            # Filter out excluded extras
            extras = [
                key
                for key in optional_deps.keys()
                if key.lower() not in self.EXCLUDED_EXTRAS and not key.endswith("-dep")
            ]

            logger.info(f"Found {len(extras)} extras in {ref}: {extras}")

            return extras

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get pyproject.toml from {ref}: {e}")
            logger.error(f"Stderr: {e.stderr}")
            return []
        except Exception as e:
            logger.error(f"Failed to parse pyproject.toml: {e}")
            return []


class ExtrasMetadataService:
    """Provides localized UI metadata for extras."""

    def __init__(self, i18n_service: I18nService) -> None:
        """
        Initialize extras metadata service.

        Args:
            i18n_service: I18n service for localization
        """
        self.i18n = i18n_service

    def enrich_extras(self, raw_extras: list[str], lang: str = "en") -> list[dict[str, str]]:
        """
        Enrich raw extra keys with localized metadata.

        Args:
            raw_extras: List of extra keys from pyproject.toml
            lang: Language code

        Returns:
            List of dicts with id, name, description, category
        """
        enriched = []
        for extra_key in raw_extras:
            # Resolve localized name & description (prefer flat keys)
            name = self.i18n.translate(
                f"environment.lerobot_extra_packages.{extra_key}.name", lang=lang, default=extra_key
            )
            description = self.i18n.translate(
                f"environment.lerobot_extra_packages.{extra_key}.description", lang=lang, default=""
            )

            # Determine category from i18n data (strict flat key only)
            extra_data = self.i18n.get_block("environment.lerobot_extra_packages").get(extra_key, {})
            category = extra_data.get("category", "other")
            category_label = self.i18n.translate(
                f"environment.lerobot_extra_package_categories.{category}", lang=lang, default=category
            )

            enriched.append(
                {
                    "id": extra_key,
                    "name": name,
                    "description": description,
                    "category": category,
                    "category_label": category_label,
                }
            )
        return enriched
