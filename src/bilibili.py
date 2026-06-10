"""Bilibili video access via yt-dlp — audio download, stream URL, metadata."""

import json
import os
import subprocess
import re


def get_video_id(url: str) -> str:
    """Extract BV/av id from bilibili URL, including part number if multi-P video.

    Examples:
        BV1xx → BV1xx
        BV1xx?p=3 → BV1xx_p3
    """
    m = re.search(r"(BV[a-zA-Z0-9]+)", url)
    if m:
        bv = m.group(1)
    else:
        m = re.search(r"av(\d+)", url)
        bv = f"av{m.group(1)}" if m else url.split("/")[-1].split("?")[0]

    p = re.search(r"[?&]p=(\d+)", url)
    if p:
        return f"{bv}_p{p.group(1)}"
    return bv


def get_bv_id(url: str) -> str:
    """Extract BV/av id WITHOUT part number (for grouping)."""
    m = re.search(r"(BV[a-zA-Z0-9]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"av(\d+)", url)
    if m:
        return f"av{m.group(1)}"
    return url.split("/")[-1].split("?")[0]


def get_video_info(url: str) -> dict:
    """Fetch video metadata (title, duration, id) without downloading."""
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        "--no-playlist",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp info failed: {result.stderr.strip()}")

    info = json.loads(result.stdout)
    return {
        "id": info.get("id", get_video_id(url)),
        "title": info.get("title", ""),
        "duration": info.get("duration", 0),
        "webpage_url": info.get("webpage_url", url),
        "description": info.get("description", ""),
    }


def download_audio(url: str, output_dir: str) -> str:
    """Download audio-only stream as WAV. Returns path to the downloaded file."""
    video_id = get_video_id(url)
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")
    expected = os.path.join(output_dir, f"{video_id}.wav")

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "-f", "bestaudio",
        "-o", output_template,
        "--no-playlist",
        "--no-mtime",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio download failed: {result.stderr.strip()}")

    # yt-dlp with -x may produce .opus → .wav, the output template handles this
    if os.path.isfile(expected):
        return expected

    # search for the output file if naming differs
    for f in os.listdir(output_dir):
        if f.startswith(video_id) and f.endswith(".wav"):
            return os.path.join(output_dir, f)

    raise FileNotFoundError(f"Audio file not found in {output_dir} for {video_id}")


def get_stream_url(url: str, max_height: int = 720) -> str:
    """Get a direct video-stream URL at or below max_height pixels."""
    fmt = f"bestvideo[height<={max_height}]/best[height<={max_height}]/best"
    cmd = ["yt-dlp", "-g", "-f", fmt, "--no-playlist", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Stream URL failed: {result.stderr.strip()}")
    return result.stdout.strip().split("\n")[0]


_COLLECTION_PATTERNS = [
    r"collectiondetail",
    r"channel/collection",
    r"medialist/play",
    r"/series/",
    r"space\.bilibili\.com/\d+/channel",
]


def is_collection_url(url: str) -> bool:
    """Check whether a URL is a bilibili collection/playlist/series."""
    return any(re.search(p, url) for p in _COLLECTION_PATTERNS)


def expand_url(url: str) -> list[str]:
    """Expand any bilibili URL into individual video page URLs.

    Works for:
      - Multi-part videos (same BV, different ?p=N)
      - Collections/playlists
      - Standalone videos (returns [url])
    """
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(webpage_url)s",
        "--no-download",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"URL expansion failed: {result.stderr.strip()}")
    urls = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    if not urls:
        raise RuntimeError(f"No videos found at: {url}")
    return urls
