"""Cross-platform runtime detection and configuration."""

import os
import platform
import subprocess
from dataclasses import dataclass, field


@dataclass
class RuntimeConfig:
    system: str = field(default_factory=platform.system)
    has_cuda: bool = False
    ocr_device: str = "cpu"
    whisper_backend: str = "cpu"
    whisper_model: str = "ggml-large-v3-turbo.bin"

    def __post_init__(self):
        self.has_cuda = self._detect_cuda()
        self.ocr_device = "gpu" if self.has_cuda else "cpu"
        self.whisper_backend = self._detect_whisper_backend()

    def _detect_cuda(self) -> bool:
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _detect_whisper_backend(self) -> str:
        if self.system == "Darwin":
            return "coreml"
        elif self.has_cuda:
            return "cuda"
        return "cpu"

    @property
    def is_macos(self) -> bool:
        return self.system == "Darwin"

    @property
    def is_windows(self) -> bool:
        return self.system == "Windows"

    @property
    def is_linux(self) -> bool:
        return self.system == "Linux"

    @property
    def is_wsl(self) -> bool:
        if self.system != "Linux":
            return False
        try:
            with open("/proc/version", "r") as f:
                return "microsoft" in f.read().lower()
        except Exception:
            return False

    def summary(self) -> str:
        lines = [
            f"System:       {self.system}",
            f"CUDA:         {'yes' if self.has_cuda else 'no'}",
            f"OCR device:   {self.ocr_device}",
            f"Whisper:      {self.whisper_backend}",
        ]
        return "\n".join(lines)


def load_config(
    model_path: str | None = None,
    model_dir: str | None = None,
) -> RuntimeConfig:
    """Create runtime config, optionally locating the whisper model."""
    cfg = RuntimeConfig()

    if model_path:
        cfg.whisper_model = model_path
    elif model_dir:
        for name in [
            "ggml-large-v3-turbo.bin",
            "ggml-large-v3.bin",
            "ggml-medium.bin",
        ]:
            candidate = os.path.join(model_dir, name)
            if os.path.isfile(candidate):
                cfg.whisper_model = candidate
                break

    os.environ.setdefault("WHISPER_MODEL", cfg.whisper_model)
    return cfg
