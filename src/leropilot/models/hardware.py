"""Hardware related models."""

from pydantic import BaseModel


class HardwareCapabilities(BaseModel):
    """System hardware capabilities."""

    has_nvidia_gpu: bool = False
    has_amd_gpu: bool = False
    is_apple_silicon: bool = False
    detected_cuda: str | None = None
    detected_rocm: str | None = None
