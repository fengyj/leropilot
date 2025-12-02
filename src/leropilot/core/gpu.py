"""GPU detection service for LeRoPilot."""

import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel


class GPUInfo(BaseModel):
    """GPU and driver information."""

    has_nvidia_gpu: bool = False
    has_amd_gpu: bool = False
    is_apple_silicon: bool = False
    gpu_name: str | None = None
    driver_version: str | None = None
    cuda_version: str | None = None
    rocm_version: str | None = None


class GPUDetector:
    """
    Detects GPU hardware and driver versions.
    Future hardware (cameras, arms) will be handled by separate detectors.
    """

    # Driver version to CUDA version mapping (NVIDIA)
    # Based on https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/
    DRIVER_TO_CUDA = {
        "560": "12.6",
        "555": "12.5",
        "550": "12.4",
        "545": "12.3",
        "535": "12.2",
        "530": "12.1",
        "525": "12.0",
        "520": "12.0",
        "515": "11.7",
        "510": "11.6",
    }

    def detect(self) -> GPUInfo:
        """Detect GPU hardware and return information."""
        info = GPUInfo()

        # 1. Check NVIDIA
        if shutil.which("nvidia-smi"):
            nvidia_info = self._detect_nvidia()
            if nvidia_info:
                info.has_nvidia_gpu = True
                info.gpu_name = nvidia_info.get("name")
                info.driver_version = nvidia_info["driver_version"]
                info.cuda_version = nvidia_info["cuda_version"]

        # 2. Check AMD (ROCm) - Linux Only
        elif sys.platform == "linux" and Path("/dev/kfd").exists():
            rocm_info = self._detect_rocm()
            if rocm_info:
                info.has_amd_gpu = True
                info.rocm_version = rocm_info["rocm_version"]

        # 3. Check Apple Silicon
        elif platform.system() == "Darwin" and platform.machine() == "arm64":
            info.is_apple_silicon = True
            info.gpu_name = "Apple Silicon"

        return info

    def _detect_nvidia(self) -> dict[str, str | None] | None:
        """Detect NVIDIA GPU and driver version."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version,name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            output = result.stdout.strip()
            if output:
                # Output format: "535.183.01, NVIDIA GeForce RTX 4090"
                parts = output.split(", ")
                driver_version = parts[0]
                name = parts[1] if len(parts) > 1 else None

                cuda_version = self._map_driver_to_cuda(driver_version)
                return {"driver_version": driver_version, "cuda_version": cuda_version, "name": name}
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def _detect_rocm(self) -> dict[str, str] | None:
        """Detect AMD ROCm version."""
        try:
            # Try rocm-smi
            if shutil.which("rocm-smi"):
                result = subprocess.run(
                    ["rocm-smi", "--showdriverversion"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5,
                )
                # Parse version from output
                match = re.search(r"(\d+\.\d+)", result.stdout)
                if match:
                    return {"rocm_version": match.group(1)}
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def _map_driver_to_cuda(self, driver_version: str) -> str:
        """Map NVIDIA driver version to maximum supported CUDA version."""
        # Extract major version (e.g., "535.129.03" -> "535")
        major = driver_version.split(".")[0]

        # Look up in mapping
        cuda_version = self.DRIVER_TO_CUDA.get(major)
        if cuda_version:
            return cuda_version

        # If not found, try to infer based on version number
        try:
            major_int = int(major)
            # Find the closest lower version
            for driver_major in sorted(self.DRIVER_TO_CUDA.keys(), reverse=True):
                if major_int >= int(driver_major):
                    return self.DRIVER_TO_CUDA[driver_major]
        except ValueError:
            pass

        # Default fallback
        return "12.0"
