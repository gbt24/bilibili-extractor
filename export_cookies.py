#!/usr/bin/env python3
"""
Edge cookie extractor for Bilibili.
Tries multiple methods to extract bilibili.com cookies from Edge
and save as Netscape-format cookies.txt for yt-dlp.

Usage:
    python export_cookies.py
    python export_cookies.py --browser edge
    python export_cookies.py --browser chrome --domain bilibili.com
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone


def try_browser_cookie3(browser: str, domain: str) -> dict[str, str] | None:
    """Try using browser-cookie3 library."""
    try:
        import browser_cookie3
    except ImportError:
        print("  browser-cookie3 not installed. Install: pip install browser-cookie3")
        return None

    loaders = {
        "edge": browser_cookie3.edge,
        "chrome": browser_cookie3.chrome,
        "firefox": browser_cookie3.firefox,
        "brave": browser_cookie3.brave,
    }
    loader = loaders.get(browser)
    if not loader:
        print(f"  Unsupported browser: {browser}")
        return None

    try:
        cj = loader(domain_name=domain)
    except Exception as e:
        print(f"  browser-cookie3 failed: {e}")
        return None

    cookies: dict[str, str] = {}
    for cookie in cj:
        if domain in cookie.domain:
            cookies[cookie.name] = cookie.value
    return cookies


def try_ytdlp_dump(browser: str, output_file: str) -> bool:
    """Try yt-dlp --cookies to dump cookies."""
    cmd = [
        "yt-dlp",
        "--cookies-from-browser", browser,
        "--cookies", output_file,
        "--skip-download",
        "--no-playlist",
        "--print", "Cookies saved",
        "https://www.bilibili.com",
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return True
    print(f"  yt-dlp cookie dump failed: {result.stderr.strip()[:200]}")
    return False


def try_ytdlp_single(browser: str) -> bool:
    """Try yt-dlp to download one page info as a direct test."""
    cmd = [
        "yt-dlp",
        "--cookies-from-browser", browser,
        "--dump-json",
        "--no-download",
        "--no-playlist",
        "https://www.bilibili.com/video/BV1GJ411x7h7",  # short public video
    ]
    print(f"  Testing with: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        print("  Cookie extraction WORKS!")
        return True
    print(f"  Failed: {result.stderr.strip()[:300]}")
    return False


def kill_browser(browser: str) -> None:
    """Try to kill all browser processes."""
    exe_map = {
        "edge": "msedge.exe",
        "chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "brave": "brave.exe",
    }
    exe = exe_map.get(browser, "")
    if not exe:
        return
    print(f"  Killing {exe}...")
    subprocess.run(["taskkill", "/f", "/im", exe], capture_output=True)
    time.sleep(2)


def write_netscape(cookies: dict[str, str], path: str, domain: str) -> None:
    """Write cookies in Netscape format."""
    with open(path, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# Extracted by export_cookies.py\n\n")
        for name, value in cookies.items():
            f.write(f"{domain}\tTRUE\t/\tFALSE\t9999999999\t{name}\t{value}\n")
    print(f"  Saved {len(cookies)} cookies to {path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Extract Bilibili cookies from Edge/Chrome")
    p.add_argument("--browser", default="edge", help="Browser name (default: edge)")
    p.add_argument("--domain", default="bilibili.com", help="Domain to extract (default: bilibili.com)")
    p.add_argument("--output", default="cookies.txt", help="Output file (default: cookies.txt)")
    p.add_argument("--aggressive", action="store_true", help="Kill browser processes first")
    args = p.parse_args()

    output = args.output
    domain = args.domain

    print(f"Extracting {domain} cookies from {args.browser}...\n")

    if args.aggressive:
        kill_browser(args.browser)

    # Method 1: yt-dlp cookie dump
    print("[1] Trying yt-dlp --cookies dump...")
    if try_ytdlp_dump(args.browser, output):
        print(f"\nSUCCESS! Cookies saved to {output}")
        print(f"Now run: python pipeline.py --cookies-file {output}")
        return

    # Method 2: yt-dlp direct test
    print("\n[2] Testing direct yt-dlp cookie access...")
    if try_ytdlp_single(args.browser):
        # Re-try dump since direct access works
        if try_ytdlp_dump(args.browser, output):
            print(f"\nSUCCESS! Cookies saved to {output}")
            print(f"Now run: python pipeline.py --cookies-file {output}")
            return

    # Method 3: browser-cookie3 Python library
    print("\n[3] Trying browser-cookie3 library...")
    cookies = try_browser_cookie3(args.browser, domain)
    if cookies:
        write_netscape(cookies, output, domain)
        print(f"\nSUCCESS! Cookies saved to {output}")
        print(f"Now run: python pipeline.py --cookies-file {output}")
        return

    # All failed
    print("\n" + "=" * 60)
    print("All automatic methods failed. Manual extraction:")
    print("=" * 60)
    print(f"""
1. Open Edge, go to bilibili.com (make sure you're logged in)

2. Press F12 → Application tab → Cookies → bilibili.com

3. For each of these cookies, note the Value:
   - SESSDATA
   - bili_jct
   - DedeUserID
   - sid

4. Create a file named {output} with this content:

# Netscape HTTP Cookie File
.bilibili.com   TRUE   /   FALSE   9999999999   SESSDATA   <PASTE-VALUE>
.bilibili.com   TRUE   /   FALSE   9999999999   bili_jct    <PASTE-VALUE>
.bilibili.com   TRUE   /   FALSE   9999999999   DedeUserID  <PASTE-VALUE>
.bilibili.com   TRUE   /   FALSE   9999999999   sid         <PASTE-VALUE>

5. Run: python pipeline.py --cookies-file {output}
""")


if __name__ == "__main__":
    main()
