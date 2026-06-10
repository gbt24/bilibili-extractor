"""Audio transcription — auto-selects faster-whisper (pip) or whisper-cli (binary)."""

import os
import shutil
import subprocess


# Favourites order: faster-whisper → whisper-cli
_FASTER_WHISPER_AVAILABLE = False
try:
    import faster_whisper  # noqa: F401
    _FASTER_WHISPER_AVAILABLE = True
except ImportError:
    pass


def _has_cuda() -> bool:
    try:
        subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _transcribe_faster_whisper(
    audio_path: str,
    model_name: str,
    output_dir: str,
    language: str,
) -> str:
    from faster_whisper import WhisperModel

    device = "cuda" if _has_cuda() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    print(f"        faster-whisper  device={device}  model={model_name}")

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _info = model.transcribe(audio_path, language=language)

    base = os.path.splitext(os.path.basename(audio_path))[0]
    srt_path = os.path.join(output_dir, base + ".srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = _format_timestamp(seg.start)
            end = _format_timestamp(seg.end)
            text = seg.text.strip()
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
    return srt_path


def _find_whisper_cli() -> str:
    """Locate whisper-cli binary (macOS/Linux only)."""
    for name in ["whisper-cli", "whisper"]:
        path = shutil.which(name)
        if path:
            return path

    if os.name == "nt":
        raise FileNotFoundError(
            "whisper-cli.exe not found. "
            "On Windows, use faster-whisper instead:  pip install faster-whisper"
        )
    raise FileNotFoundError(
        "whisper-cli not found. "
        "Install with: brew install whisper-cpp  (or pip install faster-whisper)"
    )


def _transcribe_whisper_cli(
    audio_path: str,
    model_path: str,
    output_dir: str,
    language: str,
) -> str:
    binary = _find_whisper_cli()
    base = os.path.splitext(os.path.basename(audio_path))[0]
    output_prefix = os.path.join(output_dir, base)

    cmd = [
        binary,
        "-m", model_path,
        "-f", audio_path,
        "-l", language,
        "-osrt",
        "-of", output_prefix,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Whisper transcription failed: {result.stderr.strip()}")

    srt_path = output_prefix + ".srt"
    if not os.path.isfile(srt_path):
        for alt in [output_prefix + ".wav.srt"]:
            if os.path.isfile(alt):
                return alt
        raise FileNotFoundError(f"SRT output not found near {output_prefix}")
    return srt_path


# Map whisper.cpp model filenames → faster-whisper model names
_MODEL_MAP = {
    "ggml-large-v3-turbo.bin": "large-v3",
    "ggml-large-v3.bin": "large-v3",
    "ggml-large-v2.bin": "large-v2",
    "ggml-medium.bin": "medium",
    "ggml-small.bin": "small",
}


def _resolve_fw_model(model_path: str | None) -> str:
    """Map whisper.cpp .bin filename to faster-whisper model name."""
    if model_path and os.path.isfile(model_path):
        basename = os.path.basename(model_path)
        if basename in _MODEL_MAP:
            return _MODEL_MAP[basename]
    return "large-v3"


def transcribe(
    audio_path: str,
    model_path: str | None = None,
    output_dir: str = ".",
    language: str = "zh",
) -> str:
    """Transcribe a WAV file to SRT.

    Auto-selects the best available backend:
      1. faster-whisper (pip install, zero-compile, CUDA auto-detect)
      2. whisper-cli  (system binary, falls back to CPU)

    If model_path is a whisper.cpp .bin file, its name is mapped to the
    equivalent faster-whisper model (e.g. ggml-large-v3-turbo.bin → large-v3).

    Returns the path to the generated .srt file.
    """
    if _FASTER_WHISPER_AVAILABLE:
        fw_model = _resolve_fw_model(model_path)
        return _transcribe_faster_whisper(audio_path, fw_model, output_dir, language)

    # Fallback to whisper-cli binary
    if not model_path:
        raise ValueError(
            "model_path is required when using whisper-cli. "
            "Install faster-whisper for zero-config: pip install faster-whisper"
        )
    return _transcribe_whisper_cli(audio_path, model_path, output_dir, language)


def read_srt(srt_path: str) -> str:
    """Read SRT file content as plain text string."""
    with open(srt_path, "r", encoding="utf-8") as f:
        return f.read()
