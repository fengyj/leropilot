"""Path utilities for LeRoPilot, compatible with PyInstaller."""

import sys
from pathlib import Path


def get_resources_dir() -> Path:
    """Get the resources directory path.

    This function returns the correct path for both:
    - Development environment: src/leropilot/resources
    - PyInstaller packaged environment: <MEIPASS>/leropilot/resources

    Returns:
        Path to the resources directory
    """
    if getattr(sys, "frozen", False):
        # PyInstaller packaged environment
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        return base_path / "leropilot" / "resources"
    else:
        # Development environment
        # This file is at src/leropilot/utils/paths.py
        # Resources are at src/leropilot/resources
        return Path(__file__).parent.parent / "resources"


def get_static_dir() -> Path:
    """Get the static files directory path.

    This function returns the correct path for both:
    - Development environment: src/leropilot/static
    - PyInstaller packaged environment: <MEIPASS>/leropilot/static

    Returns:
        Path to the static directory
    """
    if getattr(sys, "frozen", False):
        # PyInstaller packaged environment
        base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        return base_path / "leropilot" / "static"
    else:
        # Development environment
        return Path(__file__).parent.parent / "static"
