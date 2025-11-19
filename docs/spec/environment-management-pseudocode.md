import sys
import os
import subprocess
import shutil
import platform
from pathlib import Path

# Environment Management Pseudo-code

## 1. UVManager

```python
class UVManager:
    def ensure_uv_installed(self):
        """Ensures uv is available."""
        if self.find_system_uv():
            return

        if not self.local_uv_exists():
            self.download_uv()

    def get_uv_path(self) -> Path:
        """Locates the bundled uv binary."""
        # In PyInstaller, sys._MEIPASS is the temp folder where assets are unpacked
        if hasattr(sys, "_MEIPASS"):
            base_path = Path(sys._MEIPASS)
        else:
            # In dev mode, look in local bin dir or system path
            base_path = Path(__file__).parent.parent / "bin"

        # Platform specific name
        uv_name = "uv.exe" if platform.system() == "Windows" else "uv"
        bundled_path = base_path / uv_name

        if bundled_path.exists():
            return bundled_path

        # Fallback to system uv
        system_path = shutil.which("uv")
        if system_path:
            return Path(system_path)

        raise RuntimeError("uv binary not found.")

    def run_command(self, args: list[str], cwd: Path, env: dict = None):
        """Runs a uv command."""
        uv_path = self.get_uv_path()
        # Important: propagate env vars like UV_INDEX_URL
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        return subprocess.run([uv_path] + args, cwd=cwd, env=full_env, check=True)

    def create_venv(self, path: Path, python_version: str):
        self.run_command(["venv", str(path), "--python", python_version])

class GitService:
    def get_git_path(self) -> str:
        """Finds git in PATH."""
        git_path = shutil.which("git")
        if not git_path:
            raise RuntimeError("Git not found in PATH. Please install Git or specify path.")
        return git_path
```

## 2. GPUService & Compatibility

```python
import platform

class GPUService:
    def detect_hardware(self) -> HardwareInfo:
        """Detects GPU and Driver version."""
        # 1. Check for Apple Silicon first
        if platform.system() == "Darwin" and platform.machine() == "arm64":
            return HardwareInfo(type="mps", name="Apple Silicon")

        # 2. Check for NVIDIA GPU (Windows/Linux)
        # shutil.which checks if the command exists in PATH
        if shutil.which("nvidia-smi"):
            try:
                # Run nvidia-smi
                output = subprocess.check_output(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
                driver_version = output.decode().strip()
                cuda_version = self.map_driver_to_cuda(driver_version)
                return HardwareInfo(type="cuda", driver=driver_version, cuda=cuda_version)
            except subprocess.CalledProcessError:
                pass # nvidia-smi failed to run

        # 3. Check for AMD GPU (Linux)
        if shutil.which("rocm-smi"):
             try:
                # Run rocm-smi
                output = subprocess.check_output(["rocm-smi", "--showdriverversion", "--json"])
                import json
                data = json.loads(output.decode())
                # Assuming a single card for simplicity, or taking the first one
                card_info = next(iter(data.values()))
                driver_version = card_info.get("Driver version")
                rocm_version = card_info.get("ROCm version")
                if driver_version and rocm_version:
                    return HardwareInfo(type="rocm", driver=driver_version, rocm=rocm_version)
             except Exception: # Catch all exceptions for robustness
                pass

        # 4. Fallback to CPU
        return HardwareInfo(type="cpu")

    def get_recommended_torch(self, hardware: HardwareInfo, software_constraints: dict) -> dict:
        """
        Returns {'version': TorchVersion, 'reason': str, 'warning': str | None}
        """
        compat_map = self.fetch_compatibility_map()

        # Filter candidates based on Hardware first (Hard Constraint)
        hardware_candidates = []
        for version in compat_map.torch_versions:
                break # Assuming sorted by newest first

        if not best_for_hardware:
             # Hardware is too new (newer than anything in our map)
             return compat_map.get_latest_stable()

        return best_for_hardware

        # Note: Similar logic applies for AMD/ROCm matching
        if hardware.type == "rocm":
            # Match hardware.rocm with version.rocm_version
            pass
```

## 3. RepoManager (Caching)

```python
class RepoManager:
    CACHE_ROOT = "~/.leropilot/cache/repos"

    def get_cache_dir(self, repo_url: str) -> Path:
        # Use a safe name based on the URL (e.g., hash or sanitized string)
        safe_name = hashlib.md5(repo_url.encode()).hexdigest()
        return self.CACHE_ROOT / safe_name

    def ensure_cache_updated(self, repo_url: str):
        """Updates the bare git repo cache for a specific repo URL."""
        cache_dir = self.get_cache_dir(repo_url)
        if not cache_dir.exists():
            git.clone(repo_url, cache_dir, bare=True)
        else:
            git.fetch(cache_dir, all=True)

    def get_dependencies(self, repo_url: str, ref: str) -> dict:
        """Parses pyproject.toml for python and torch constraints."""
        # git show <ref>:pyproject.toml
        cache_dir = self.get_cache_dir(repo_url)
        try:
            content = git.show(cache_dir, f"{ref}:pyproject.toml")
            data = toml.loads(content)
            return {
                "python": data.get("project", {}).get("requires-python", ">=3.10"),
                "dependencies": data.get("project", {}).get("dependencies", [])
            }
        except:
            return {"python": ">=3.10", "dependencies": []}

    def checkout_to_env(self, repo_url: str, env_src_dir: Path, ref: str):
        """Clones from cache to env dir."""
        cache_dir = self.get_cache_dir(repo_url)
        git.clone(cache_dir, env_src_dir)
        git.checkout(env_src_dir, ref)
```

## 4. EnvironmentInstaller (The Flow)

```python
class EnvironmentInstaller:
    def create_environment(self, config: EnvironmentConfig):
        # Use 'name' for the directory name
        env_dir = self.get_env_dir(config.name)
        env_dir.mkdir()

        # 1. Create venv
        self.uv.create_venv(env_dir / ".venv", config.python_version)

        # 2. Checkout Source
        src_dir = env_dir / "src" / "lerobot"
        # self.repo.ensure_cache_updated(config.repo_url)
        self.repo.checkout_to_env(config.repo_url, src_dir, config.ref)

        # 3. Install PyTorch (Pre-install)
        # We install torch first to ensure the correct CUDA version is selected
        # before other deps might pull in a default CPU version.
        torch_pkg = f"torch=={config.torch_version}"
        self.uv.run_command(["pip", "install", torch_pkg], cwd=env_dir)

        # 4. Install FFmpeg
        self.ffmpeg.install_to_env(env_dir, config.ffmpeg_version)

        # 5. Install LeRobot & Extras
        # uv pip install -e .[aloha,pusht]
        extras = "[" + ",".join(config.selected_robots) + "]"
        self.uv.run_command(["pip", "install", "-e", f".{extras}"], cwd=src_dir)

        # 6. Save Config
        self.save_config(env_dir, config)
```

## 5. Advanced Mode (Script Generation)

```python
class InstallPlanGenerator:
    def generate_script(self, config: EnvironmentConfig) -> str:
        """Generates a platform-specific script for the user to review/edit."""
        is_windows = platform.system() == "Windows"
        lines = []

        if is_windows:
            # PowerShell syntax
            # Quote paths to handle spaces
            lines.append(f"# Environment: {config.display_name}")
            lines.append(f'& "{uv_path}" venv .venv --python {config.python_version}')
            lines.append(f".venv\\Scripts\\activate")
            # ...
        else:
            # Bash syntax
            lines.append(f"#!/bin/bash")
            lines.append(f"# Environment: {config.display_name}")
            lines.append(f'"{uv_path}" venv .venv --python {config.python_version}')
            lines.append(f"source .venv/bin/activate")

        # ... add torch install command ...
        lines.append(f"uv pip install torch=={config.torch_version} ...")

        # ... add ffmpeg copy instructions ...

        # ... add lerobot install ...
        lines.append(f"cd src/lerobot")
        lines.append(f"uv pip install -e .[{','.join(config.selected_robots)}]")

        return "\n".join(lines)
```

```

```
