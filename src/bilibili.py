"""Bilibili video access via yt-dlp — audio download, stream URL, metadata."""

import json
import os
import platform
import re
import subprocess
import sys


# ── Browser cookie auto-detection ──────────────────────────────

def _detect_browser() -> str | None:
    """Detect an installed browser with Bilibili cookies."""
    candidates = {
        "Darwin": ["chrome", "safari", "firefox", "edge"],
        "Windows": ["chrome", "edge", "firefox", "brave"],
        "Linux": ["chrome", "firefox", "edge", "brave"],
    }
    system = platform.system()
    env_browser = os.environ.get("YTDLP_COOKIES_BROWSER", "")
    if env_browser:
        return env_browser
    for browser in candidates.get(system, ["chrome"]):
        if _browser_available(browser):
            return browser
    return None


def _browser_available(browser: str) -> bool:
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
    return True


# ── yt-dlp runner with auto cookie-fallback ────────────────────

_COOKIE_BROWSER: str | None = None
_HEADER_ARGS = [
    "--add-header", "User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "--add-header", "Referer:https://www.bilibili.com/",
]


def set_cookies_browser(browser: str | None) -> None:
    global _COOKIE_BROWSER
    _COOKIE_BROWSER = browser


def _run_ytdlp(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Run yt-dlp. Tries with browser cookies first; falls back to headers-only on failure."""
    browser = _COOKIE_BROWSER or _detect_browser()

    # ── Attempt 1: with browser cookies ──
    if browser:
        cmd = ["yt-dlp", "--cookies-from-browser", browser] + _HEADER_ARGS + args
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result
        stderr = result.stderr.strip()
        # Cookie DB locked by running browser → retry without cookies
        if "cookie" in stderr.lower() or "copy" in stderr.lower() or "locked" in stderr.lower():
            print(f"        Cookie warning: browser DB locked, retrying without cookies...")
        else:
            raise RuntimeError(f"yt-dlp failed: {stderr}")

    # ── Attempt 2: headers only (no cookies) ──
    cmd = ["yt-dlp"] + _HEADER_ARGS + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        msg = result.stderr.strip()
        if "412" in msg or "Precondition" in msg:
            raise RuntimeError(
                "Bilibili blocked the request (412). Solutions:\n"
                "  1. Close Chrome/Edge completely before running\n"
                "  2. Or login to Bilibili in your browser first\n"
                f"  Details: {msg}"
            )
        raise RuntimeError(f"yt-dlp failed: {msg}")
    return result


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
    m = re.search(r"(BV[a-zA-Z0-9]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"av(\d+)", url)
    if m:
        return f"av{m.group(1)}"
    return url.split("/")[-1].split("?")[0]


# ── Core API ────────────────────────────────────────────────────

def get_video_info(url: str) -> dict:
    result = _run_ytdlp(["--dump-json", "--no-download", "--no-playlist", url])
    info = json.loads(result.stdout)
    return {
        "id": info.get("id", get_video_id(url)),
        "title": info.get("title", ""),
        "duration": info.get("duration", 0),
        "webpage_url": info.get("webpage_url", url),
        "description": info.get("description", ""),
    }


def download_audio(url: str, output_dir: str) -> str:
    video_id = get_video_id(url)
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")
    expected = os.path.join(output_dir, f"{video_id}.wav")

    _run_ytdlp([
        "-x", "--audio-format", "wav", "--audio-quality", "0",
        "-f", "bestaudio",
        "-o", output_template,
        "--no-playlist", "--no-mtime",
        url,
    ])

    if os.path.isfile(expected):
        return expected
    for f in os.listdir(output_dir):
        if f.startswith(video_id) and f.endswith(".wav"):
            return os.path.join(output_dir, f)
    raise FileNotFoundError(f"Audio file not found in {output_dir} for {video_id}")


def get_stream_url(url: str, max_height: int = 720) -> str:
    fmt = f"bestvideo[height<={max_height}]/best[height<={max_height}]/best"
    result = _run_ytdlp(["-g", "-f", fmt, "--no-playlist", url])
    return result.stdout.strip().split("\n")[0]


def expand_url(url: str) -> list[str]:
    result = _run_ytdlp([
        "--flat-playlist", "--print", "%(webpage_url)s", "--no-download", url,
    ])
    urls = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    if not urls:
        raise RuntimeError(f"No videos found at: {url}")
    return urls
