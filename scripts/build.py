#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


def build() -> None:
    root = Path(__file__).parent.parent
    frontend_dir = root / "frontend"
    dist_dir = root / "dist"

    print("Step 1: Building frontend...")
    subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
    subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True)

    print("\nStep 2: Building backend with PyInstaller...")
    spec_file = root / "build.spec"
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec_file), "--clean"],
        cwd=root,
        check=True,
    )

    print("\nStep 3: Creating version.txt...")
    version_file = dist_dir / "version.txt"
    version_file.write_text("0.1.0\n")

    print("\n✓ Build completed successfully!")
    print(f"Executable location: {dist_dir / 'leropilot'}")

    executable = dist_dir / "leropilot.exe" if sys.platform == "win32" else dist_dir / "leropilot"
    if executable.exists():
        size_mb = executable.stat().st_size / (1024 * 1024)
        print(f"Executable size: {size_mb:.2f} MB")


if __name__ == "__main__":
    build()
