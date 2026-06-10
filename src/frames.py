"""Video keyframe extraction via ffmpeg with perceptual-hash dedup."""

import os
import subprocess
from PIL import Image
import imagehash


def extract_frames(
    stream_url: str,
    output_dir: str,
    fps: float = 1.0 / 3.0,
    max_width: int = 1280,
) -> list[str]:
    """Extract frames from a video stream at fixed interval.

    Uses perceptual hash to deduplicate near-identical frames.
    Returns sorted list of kept frame paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    pattern = os.path.join(output_dir, "frame_%04d.jpg")

    cmd = [
        "ffmpeg",
        "-i", stream_url,
        "-vf", f"fps={fps},scale={max_width}:-1",
        "-vsync", "vfr",
        "-q:v", "2",
        "-threads", "0",
        "-y",
        pattern,
    ]

    subprocess.run(cmd, capture_output=True, check=True)

    # Deduplicate
    _deduplicate(output_dir, threshold=5)

    frames = sorted(
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )
    return frames


def _deduplicate(frames_dir: str, threshold: int = 5) -> None:
    """Remove near-duplicate frames using perceptual hash (pHash).

    Frames with hamming distance <= threshold are considered duplicates.
    The first occurrence is kept.
    """
    files = sorted(f for f in os.listdir(frames_dir) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    if len(files) <= 1:
        return

    hashes: dict[str, imagehash.ImageHash] = {}
    for fname in files:
        fpath = os.path.join(frames_dir, fname)
        img = Image.open(fpath)
        hashes[fname] = imagehash.phash(img)

    kept = [files[0]]
    for fname in files[1:]:
        if any(abs(hashes[fname] - hashes[k]) <= threshold for k in kept):
            os.remove(os.path.join(frames_dir, fname))
        else:
            kept.append(fname)
