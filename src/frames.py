"""Video keyframe extraction — downloads video stream then extracts frames via ffmpeg."""

import os
import re
import subprocess
import tempfile

import httpx
from PIL import Image
import imagehash


def extract_frames(
    bilibili_url: str,
    output_dir: str,
    fps: float = 1.0 / 3.0,
    max_width: int = 1280,
) -> list[str]:
    """Extract frames from a Bilibili video at fixed interval.

    Uses bilibili-api-python to get stream URL, downloads via httpx.
    """
    os.makedirs(output_dir, exist_ok=True)
    pattern = os.path.join(output_dir, "frame_%04d.jpg")

    # Get stream URL
    from src.bilibili import get_video_stream_url, _run_async

    stream_url = _run_async(get_video_stream_url(bilibili_url, max_height=480))

    # Download video to temp file
    fd, tmp_video = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)

    try:
        print(f"        Downloading video stream...")
        with httpx.stream(
            "GET", stream_url, follow_redirects=True, timeout=300,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.bilibili.com/",
                "Origin": "https://www.bilibili.com",
            },
            proxy=None,
            trust_env=False,
        ) as r:
            r.raise_for_status()
            with open(tmp_video, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        sz = os.path.getsize(tmp_video)
        print(f"        Downloaded {sz/1e6:.1f} MB")

        # Extract frames from temp video
        ffmpeg = subprocess.run([
            "ffmpeg", "-i", tmp_video,
            "-vf", f"fps={fps},scale={max_width}:-1",
            "-vsync", "vfr", "-q:v", "2", "-threads", "0",
            "-y", pattern,
        ], capture_output=True, text=True)

    finally:
        os.remove(tmp_video)

    frames = sorted(
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )

    if not frames:
        raise RuntimeError(
            f"No frames extracted. ffmpeg: {ffmpeg.stderr.strip()[:300]}"
        )

    _deduplicate(output_dir, threshold=5)

    return sorted(
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )


def _deduplicate(frames_dir: str, threshold: int = 5) -> None:
    files = sorted(
        f for f in os.listdir(frames_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )
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
