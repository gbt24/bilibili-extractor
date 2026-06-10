"""Bilibili video access via yt-dlp — audio download, stream URL, metadata."""

import json
import os
import platform
import shutil
import subprocess
import re


# ── Browser cookie auto-detection ──────────────────────────────

def _detect_browser() -> str | None:
    """Detect an installed browser with Bilibili cookies."""
    candidates = {
        "Darwin": ["chrome", "safari", "firefox", "edge"],
        "Windows": ["chrome", "edge", "firefox", "brave"],
        "Linux": ["chrome", "firefox", "edge", "brave"],
    }
    system = platform.system()

    # Prefer env override
    env_browser = os.environ.get("YTDLP_COOKIES_BROWSER", "")
    if env_browser:
        return env_browser

    for browser in candidates.get(system, ["chrome"]):
        if _browser_available(browser):
            return browser
    return None


def _browser_available(browser: str) -> bool:
    """Check if a browser likely exists on this system."""
    system = platform.system()
    if system == "Windows":
        paths = {
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
            "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        }
        return os.path.isfile(paths.get(browser, ""))
    if system == "Darwin":
        paths = {
            "chrome": "/Applications/Google Chrome.app",
            "safari": "/Applications/Safari.app",
            "firefox": "/Applications/Firefox.app",
            "edge": "/Applications/Microsoft Edge.app",
        }
        return os.path.isdir(paths.get(browser, ""))
    # Linux: just try it
    return True


# ── yt-dlp command builder ─────────────────────────────────────

_YTDLP_BASE = None


def _get_ytdlp_base(cookies_browser: str | None = None) -> list[str]:
    """Build base yt-dlp command with cookies and headers."""
    global _YTDLP_BASE
    if _YTDLP_BASE is not None:
        return _YTDLP_BASE

    browser = cookies_browser or _detect_browser()
    cmd = ["yt-dlp"]

    if browser:
        cmd += ["--cookies-from-browser", browser]

    cmd += [
        "--add-header", "User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "--add-header", "Referer:https://www.bilibili.com/",
        "--extractor-retries", "3",
    ]
    _YTDLP_BASE = cmd
    return cmd


def set_cookies_browser(browser: str | None) -> None:
    """Override the auto-detected cookies browser. Call before any other function."""
    global _YTDLP_BASE
    if browser:
        _YTDLP_BASE = _get_ytdlp_base(browser)
    else:
        _YTDLP_BASE = None


# ── URL helpers ─────────────────────────────────────────────────

def get_video_id(url: str) -> str:
    """Extract BV/av id from bilibili URL, including part number if multi-P video."""
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


# ── Core API ────────────────────────────────────────────────────

def get_video_info(url: str) -> dict:
    """Fetch video metadata without downloading."""
    cmd = _get_ytdlp_base() + [
        "--dump-json",
        "--no-download",
        "--no-playlist",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        msg = result.stderr.strip()
        if "412" in msg or "Precondition" in msg:
            raise RuntimeError(
                f"Bilibili blocked the request (412). "
                f"Make sure you are logged into Bilibili in Chrome/Edge, then retry.\n"
                f"You can also specify a browser: python pipeline.py --cookies-browser chrome\n"
                f"Details: {msg}"
            )
        raise RuntimeError(f"yt-dlp info failed: {msg}")

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

    cmd = _get_ytdlp_base() + [
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

    if os.path.isfile(expected):
        return expected

    for f in os.listdir(output_dir):
        if f.startswith(video_id) and f.endswith(".wav"):
            return os.path.join(output_dir, f)

    raise FileNotFoundError(f"Audio file not found in {output_dir} for {video_id}")


def get_stream_url(url: str, max_height: int = 720) -> str:
    """Get a direct video-stream URL at or below max_height pixels."""
    fmt = f"bestvideo[height<={max_height}]/best[height<={max_height}]/best"
    cmd = _get_ytdlp_base() + ["-g", "-f", fmt, "--no-playlist", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Stream URL failed: {result.stderr.strip()}")
    return result.stdout.strip().split("\n")[0]


def expand_url(url: str) -> list[str]:
    """Expand any bilibili URL into individual video page URLs."""
    cmd = _get_ytdlp_base() + [
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
