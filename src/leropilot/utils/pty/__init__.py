"""
Cross-platform PTY Manager.

Automatically selects the appropriate implementation based on the platform:
- Windows: Uses pywinpty (ConPTY)
- Linux/macOS: Uses native Unix PTY
"""

import sys

# Import the appropriate implementation based on platform
if sys.platform == "win32":
    from .windows import PTYManagerWindows as PTYManager
else:
    from .unix import PTYManagerUnix as PTYManager

__all__ = ["PTYManager"]
