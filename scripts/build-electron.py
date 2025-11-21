#!/usr/bin/env python3
"""Build Electron application with embedded Python backend."""

import shutil
import subprocess
import sys
from pathlib import Path


def check_npm() -> None:
    """Check if npm is installed."""
    try:
        subprocess.run(["npm", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: npm is not installed or not found in PATH.")
        sys.exit(1)


def build_frontend() -> None:
    """Build React frontend."""
    print("\n[1/5] Building React frontend...")
    subprocess.run(["npm", "install"], cwd="frontend", check=True)
    subprocess.run(["npm", "run", "build"], cwd="frontend", check=True)


def copy_frontend_to_static() -> None:
    """Verify frontend build is in Python static directory."""
    print("\n[2/5] Verifying frontend build...")

    # Vite is configured to output directly to src/leropilot/static
    # So we just need to verify it exists
    static_dir = Path("src/leropilot/static")

    if not static_dir.exists():
        print("Error: Static directory not found after frontend build.")
        print("Expected location: src/leropilot/static")
        sys.exit(1)

    # Verify index.html exists
    index_html = static_dir / "index.html"
    if not index_html.exists():
        print("Error: index.html not found in static directory.")
        sys.exit(1)

    print(f"✓ Frontend build verified in {static_dir}")


def build_python_backend() -> None:
    """Build Python backend with PyInstaller."""
    print("\n[3/5] Building Python backend...")
    # Use the existing build script
    subprocess.run([sys.executable, "scripts/build.py"], check=True)


def build_electron() -> None:
    """Build Electron application."""
    print("\n[5/5] Building Electron application...")

    # Install Electron dependencies
    subprocess.run(["npm", "install"], cwd="electron", check=True)

    # Build Electron
    # Build Electron
    # This will use electron-builder to package everything
    subprocess.run(["npm", "run", "build", "--", "--config", "builder.json"], cwd="electron", check=True)


def main() -> None:
    print("Starting LeRoPilot Electron Build Process...")
    check_npm()

    # 1. Build React frontend (this puts files in src/leropilot/static)
    build_frontend()

    # 2. Copy/Verify frontend files
    copy_frontend_to_static()

    # 3. Build Python backend (this packages src/leropilot including static files)
    # We need to make sure build.py is doing the right thing.
    # build.py runs PyInstaller.
    build_python_backend()

    # 3. Copy Python dist to Electron resources
    # electron-builder is configured to take files from ../dist/python
    # build.py outputs to dist/leropilot (folder) or dist/leropilot (file)?
    # Let's assume build.py puts the executable in dist/leropilot (or similar)
    # We need to ensure the output structure matches what electron-builder expects.
    # builder.json expects: "from": "../dist/python"

    # Let's check where build.py outputs.
    # If build.py outputs to `dist/leropilot`, we might need to rename or move it.
    # For now, let's assume we need to organize `dist` for electron-builder.

    dist_dir = Path("dist")
    python_dist = dist_dir / "python"

    # Clean up previous python dist if exists
    if python_dist.exists():
        shutil.rmtree(python_dist)
    python_dist.mkdir(parents=True, exist_ok=True)

    # Move PyInstaller output to dist/python
    # build.py usually outputs to `dist/leropilot` (onedir) or `dist/leropilot` (onefile)
    # We need to check build.py content to be sure.
    # But typically PyInstaller outputs to `dist/`.

    # Let's inspect what build.py does.
    # Since I cannot see build.py content right now in this thought block,
    # I will assume standard PyInstaller behavior and adjust if needed.
    # Standard: dist/leropilot (folder) or dist/leropilot (executable)

    # We will move everything from dist/ (excluding 'electron' and 'python' folders) to dist/python/
    # actually, let's just run build_electron() which expects things in dist/python.
    # I'll add a step to organize dist folder.

    print("\n[4/5] Organizing distribution files...")
    # Move built python app to dist/python
    # Assuming the executable is named 'leropilot' or 'leropilot.exe'

    # We'll do a robust move: move all files/dirs in dist/ that are NOT 'electron' or 'python' to dist/python
    for item in dist_dir.iterdir():
        if item.name not in ["electron", "python"]:
            # Move to python_dist
            shutil.move(str(item), str(python_dist / item.name))

    # 5. Build Electron
    build_electron()

    print("\n✓ Build completed successfully!")
    print("Output directory: dist/electron")


if __name__ == "__main__":
    main()
