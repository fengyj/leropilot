#!/usr/bin/env python3
import sys
from pathlib import Path


def check_size() -> None:
    dist_dir = Path(__file__).parent.parent / "dist"

    if sys.platform == "win32":
        executable = dist_dir / "leropilot.exe"
        max_size_mb = 80
    elif sys.platform == "darwin":
        executable = dist_dir / "leropilot"
        max_size_mb = 75
    else:
        executable = dist_dir / "leropilot"
        max_size_mb = 80

    if not executable.exists():
        print(f"Error: {executable} not found")
        sys.exit(1)

    size_mb = executable.stat().st_size / (1024 * 1024)

    print(f"Executable: {executable}")
    print(f"Size: {size_mb:.2f} MB")
    print(f"Limit: {max_size_mb} MB")

    if size_mb > max_size_mb:
        print("❌ FAIL: Size exceeds limit!")
        sys.exit(1)
    else:
        print("✓ PASS: Size within limit")
        sys.exit(0)


if __name__ == "__main__":
    check_size()
