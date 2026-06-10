"""Audio transcription via whisper.cpp."""

import os
import subprocess


def find_whisper_binary() -> str:
    """Locate the whisper-cli binary."""
    candidates = ["whisper-cli", "whisper"]
    for name in candidates:
        try:
            result = subprocess.run(
                ["which", name], capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except FileNotFoundError:
            continue
    raise FileNotFoundError(
        "whisper-cli not found. Install with: brew install whisper-cpp"
    )


def transcribe(
    audio_path: str,
    model_path: str,
    output_dir: str,
    language: str = "zh",
) -> str:
    """Transcribe a WAV file to SRT using whisper.cpp.

    Returns the path to the generated .srt file.
    """
    binary = find_whisper_binary()
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
        # some builds use different suffix
        for alt in [output_prefix + ".wav.srt", output_prefix + ".srt"]:
            if os.path.isfile(alt):
                return alt
        raise FileNotFoundError(f"SRT output not found near {output_prefix}")

    return srt_path


def read_srt(srt_path: str) -> str:
    """Read SRT file content as plain text string."""
    with open(srt_path, "r", encoding="utf-8") as f:
        return f.read()
