"""Video keyframe extraction — downloads small temp video for reliable extraction."""

import os
import subprocess
import tempfile

from PIL import Image
import imagehash


def extract_frames(
    bilibili_url: str,
    output_dir: str,
    fps: float = 1.0 / 3.0,
    max_width: int = 1280,
) -> list[str]:
    """Extract frames from a Bilibili video at fixed interval.

    Downloads a low-res video temp file (~10-25 MB for 7-min video)
    for reliable extraction, then deletes it immediately.
    """
    from src.bilibili import _COOKIE_BROWSER, _COOKIE_FILE, _HEADER_ARGS

    os.makedirs(output_dir, exist_ok=True)
    pattern = os.path.join(output_dir, "frame_%04d.jpg")

    # Build yt-dlp command with cookies / headers
    ytdlp = ["yt-dlp", "--no-playlist", "--no-mtime"]
    if _COOKIE_FILE and os.path.isfile(_COOKIE_FILE):
        ytdlp += ["--cookies", _COOKIE_FILE]
    elif _COOKIE_BROWSER:
        ytdlp += ["--cookies-from-browser", _COOKIE_BROWSER]
    ytdlp += _HEADER_ARGS

    # Download smallest usable video stream as temp file
    import uuid
    tmp_video = os.path.join(tempfile.gettempdir(), f"bili_{uuid.uuid4().hex}.mp4")

    try:
        dl = subprocess.run(
            ytdlp + [
                "-f", "worstvideo[height<=480]+worstaudio/worst[height<=480]",
                "-o", tmp_video,
                bilibili_url,
            ],
            capture_output=True, text=True, timeout=300,
        )
        if dl.returncode != 0:
            # Fallback: try just worstvideo without audio
            dl2 = subprocess.run(
                ytdlp + [
                    "-f", "worstvideo[height<=480]",
                    "-o", tmp_video,
                    bilibili_url,
                ],
                capture_output=True, text=True, timeout=300,
            )
            if dl2.returncode != 0:
                stderr = (dl.stderr + dl2.stderr).strip()[:300]
                raise RuntimeError(f"Download failed: {stderr}")

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
