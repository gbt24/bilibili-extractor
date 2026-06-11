"""Bilibili video access via bilibili-api-python — no yt-dlp, no cookies."""

import asyncio
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import httpx
from bilibili_api import Credential, video

_CREDENTIAL: Credential | None = None


def set_credential(cred: Credential) -> None:
    global _CREDENTIAL
    _CREDENTIAL = cred


def _cred() -> Credential | None:
    return _CREDENTIAL  # None for public videos is OK


# ── URL helpers ─────────────────────────────────────────────────

def get_video_id(url: str) -> str:
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
    m = re.search(r"(BV[a-zA-Z0-9]{10})", url)
    if m:
        return m.group(1)
    m = re.search(r"av(\d+)", url)
    if m:
        return f"av{m.group(1)}"
    return url.split("/")[-1].split("?")[0]


# ── Core async API ──────────────────────────────────────────────

async def _get_video(bv_id: str) -> video.Video:
    return video.Video(bvid=bv_id, credential=_cred())


async def get_video_info(url: str) -> dict:
    bv = get_bv_id(url)
    v = await _get_video(bv)
    info = await v.get_info()
    return {
        "id": get_video_id(url),
        "title": info.get("title", ""),
        "duration": info.get("duration", 0),
        "webpage_url": f"https://www.bilibili.com/video/{bv}",
        "description": info.get("desc", ""),
    }


async def expand_url(url: str) -> list[str]:
    """Expand a Bilibili URL into individual video page URLs."""
    bv = get_bv_id(url)
    v = await _get_video(bv)

    try:
        pages = await v.get_pages()
    except Exception:
        return [f"https://www.bilibili.com/video/{bv}"]

    if not pages or len(pages) <= 1:
        return [f"https://www.bilibili.com/video/{bv}"]

    result = []
    for i, page in enumerate(pages, 1):
        result.append(f"https://www.bilibili.com/video/{bv}?p={i}")
    return result


async def download_audio(url: str, output_dir: str) -> str:
    """Download audio stream from Bilibili. Returns path to WAV file."""
    bv = get_bv_id(url)
    vid = get_video_id(url)

    # Determine page index from URL
    p_match = re.search(r"[?&]p=(\d+)", url)
    page_idx = int(p_match.group(1)) - 1 if p_match else 0

    v = await _get_video(bv)
    dash_data = await v.get_download_url(page_index=page_idx)

    dash = dash_data.get("dash", {})
    audio_list = dash.get("audio", [])
    if not audio_list:
        raise RuntimeError(f"No audio streams found for {bv}")

    best_audio = max(audio_list, key=lambda a: a.get("bandwidth", 0))
    audio = best_audio.get("base_url") or best_audio.get("baseUrl", "")
    if not audio:
        raise RuntimeError(f"No audio URL found for {bv}")

    tmp_audio = os.path.join(output_dir, f"{vid}.m4a")
    wav_path = os.path.join(output_dir, f"{vid}.wav")

    # Download
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    async with httpx.AsyncClient(timeout=300, follow_redirects=True, headers=headers) as client:
        resp = await client.get(audio)
        resp.raise_for_status()
        with open(tmp_audio, "wb") as f:
            f.write(resp.content)

    # Convert to WAV
    subprocess.run(
        ["ffmpeg", "-y", "-i", tmp_audio, "-ar", "16000", "-ac", "1", wav_path],
        capture_output=True, check=True,
    )
    os.remove(tmp_audio)

    return wav_path


async def get_video_stream_url(url: str, max_height: int = 480) -> str:
    """Get direct video-only stream URL for frame extraction."""
    bv = get_bv_id(url)
    p_match = re.search(r"[?&]p=(\d+)", url)
    page_idx = int(p_match.group(1)) - 1 if p_match else 0

    v = await _get_video(bv)
    dash_data = await v.get_download_url(page_index=page_idx)

    dash = dash_data.get("dash", {})
    video_list = dash.get("video", [])
    if video_list:
        suitable = sorted(video_list, key=lambda v: v.get("height", 0) if v.get("height") else 0)
        for v in reversed(suitable):
            h = v.get("height")
            if h and h <= max_height:
                return v.get("base_url") or v.get("baseUrl", "")
        best = suitable[-1]
        return best.get("base_url") or best.get("baseUrl", "")

    raise RuntimeError(f"No video streams found for {bv}")


# ── Sync wrappers for pipeline compatibility ────────────────────

def _run_async(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def get_video_info_sync(url: str) -> dict:
    return _run_async(get_video_info(url))


def expand_url_sync(url: str) -> list[str]:
    return _run_async(expand_url(url))


def download_audio_sync(url: str, output_dir: str) -> str:
    return _run_async(download_audio(url, output_dir))
