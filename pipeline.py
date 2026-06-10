#!/usr/bin/env python3
"""Main pipeline: Bilibili video problem extraction.

Usage:
    python pipeline.py                          # reads urls.txt
    python pipeline.py --urls my_urls.txt       # custom URL list
    python pipeline.py --model-path /path/to/model.bin
    python pipeline.py --resume                 # skip already-processed videos
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

from src.config import load_config, RuntimeConfig
from src.bilibili import (
    get_video_info,
    download_audio,
    get_video_id,
    get_bv_id,
    expand_url,
    set_cookies_browser,
    set_cookies_file,
)
from src.transcribe import transcribe, read_srt
from src.frames import extract_frames
from src.ocr import recognize_frames, format_ocr_results
from src.fuse import fuse
from src.vision import describe_frames, format_vision_results

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
WORK_DIR_BASE = PROJECT_ROOT / "work"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bilibili video problem extraction")
    p.add_argument(
        "--urls", default=str(PROJECT_ROOT / "urls.txt"),
        help="Path to file with one bilibili URL per line",
    )
    p.add_argument(
        "--model-path", default=None,
        help="Path to whisper.cpp model (.bin) or faster-whisper model name (e.g. large-v3)",
    )
    p.add_argument(
        "--model-dir", default=None,
        help="Directory containing whisper.cpp models",
    )
    p.add_argument(
        "--api-key", default=None,
        help="DeepSeek API key (or set DEEPSEEK_API_KEY env)",
    )
    p.add_argument(
        "--deepseek-model", default=None,
        help="DeepSeek model name (default: deepseek-v4-flash)",
    )
    p.add_argument(
        "--resume", action="store_true",
        help="Skip videos that already have output JSON",
    )
    p.add_argument(
        "--fps", type=float, default=1.0 / 3.0,
        help="Frame extraction rate (default: 1/3 = one frame per 3 seconds)",
    )
    p.add_argument(
        "--quality", type=int, default=720,
        help="Max video height for frame extraction (default: 720)",
    )
    p.add_argument(
        "--no-merge", action="store_true",
        help="Do not merge collection results into a single JSON",
    )
    p.add_argument(
        "--no-vision", action="store_true",
        help="Skip multimodal vision description (faster, cheaper)",
    )
    p.add_argument(
        "--cookies-browser", default=None,
        help="Browser to extract Bilibili cookies from (chrome, edge, firefox, safari)",
    )
    p.add_argument(
        "--cookies-file", default=None,
        help="Path to Netscape-format cookie file (export from browser extension)",
    )
    return p.parse_args()


def _sanitize_filename(name: str) -> str:
    """Strip characters that are unsafe in file names."""
    return re.sub(r"[\\/:*?\"<>|]", "_", name).strip()[:100]


def read_and_expand_urls(path: str) -> list[dict]:
    """Read urls.txt, expand all URLs, detect multi-video groupings.

    - Multi-part videos (same BV, ?p=1..N)  → grouped by BV number
    - Collection/playlist URLs               → grouped by collection id
    - Standalone single videos               → ungrouped
    """
    raw_urls: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                raw_urls.append(line)

    if not raw_urls:
        print(f"[ERROR] No URLs found in {path}")
        sys.exit(1)

    entries: list[dict] = []
    for url in raw_urls:
        print(f"  Expanding: {url[:80]}...")
        try:
            video_urls = expand_url(url)
        except Exception as exc:
            print(f"    WARNING: {exc}")
            video_urls = [url]

        if len(video_urls) > 1:
            # Multi-video: determine group name
            group = _derive_group_name(url)
            print(f"    → {len(video_urls)} videos  (group: {group})")
            for vurl in video_urls:
                entries.append({"url": vurl, "group": group})
        else:
            print(f"    → 1 video")
            entries.append({"url": video_urls[0], "group": ""})

    if not entries:
        print("[ERROR] No video URLs found after expansion")
        sys.exit(1)

    return entries


def _derive_group_name(url: str) -> str:
    """Derive a group identifier from the URL for merged output."""
    # Collection/detail URLs: extract sid
    m = re.search(r"sid=(\d+)", url)
    if m:
        return m.group(1)
    # Medialist URLs
    m = re.search(r"business_id=(\d+)", url)
    if m:
        return m.group(1)
    # Multi-part video: use BV number
    bv = get_bv_id(url)
    if bv:
        return bv
    return _sanitize_filename(url.rsplit("/", 1)[-1].split("?")[0])


def already_processed(video_id: str) -> bool:
    result_path = OUTPUT_DIR / f"{video_id}.json"
    return result_path.exists()


def process_video(
    url: str,
    cfg: RuntimeConfig,
    args: argparse.Namespace,
    vid_work_dir: Path,
) -> dict | None:
    """Run the full pipeline for a single video. Returns the result dict or None."""
    video_id = get_video_id(url)
    print(f"\n{'='*60}")
    print(f"  Processing: {video_id}")
    print(f"{'='*60}")

    # ── 1. Metadata ──────────────────────────────────────────
    print("  [1/7] Fetching video info...")
    try:
        info = get_video_info(url)
        print(f"        Title: {info['title']}")
        print(f"        Duration: {info['duration']:.0f}s")
    except Exception as e:
        print(f"        ERROR: {e}")
        return None

    # ── 2. Audio → Whisper ───────────────────────────────────
    print("  [2/7] Downloading audio...")
    try:
        audio_path = download_audio(url, str(vid_work_dir))
        print(f"        Audio: {audio_path}  ({os.path.getsize(audio_path)/1e6:.1f} MB)")
    except Exception as e:
        print(f"        ERROR: {e}")
        return None

    print("  [3/7] Transcribing with whisper.cpp...")
    t0 = time.time()
    try:
        srt_path = transcribe(
            audio_path,
            model_path=cfg.whisper_model,
            output_dir=str(vid_work_dir),
        )
        print(f"        Done in {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"        ERROR: {e}")
        return None
    finally:
        os.remove(audio_path)

    transcript = read_srt(srt_path)
    print(f"        Transcript: {len(transcript)} chars")

    # ── 3. Frames → OCR + Vision ──────────────────────────────
    print("  [4/7] Extracting frames from stream...")
    frames_dir = vid_work_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    try:
        frame_paths = extract_frames(url, str(frames_dir), fps=args.fps)
        print(f"        Kept {len(frame_paths)} frames (after dedup)")
    except Exception as e:
        print(f"        ERROR: {e}")
        print("        Continuing with transcript only...")
        frame_paths = []

    ocr_text = ""
    vision_text = ""
    if frame_paths:
        print("  [5/7] Running PaddleOCR...")
        t0 = time.time()
        try:
            ocr_results = recognize_frames(frame_paths, device=cfg.ocr_device)
            ocr_text = format_ocr_results(ocr_results)
            print(f"        Done in {time.time()-t0:.1f}s, {len(ocr_text)} chars of text")
        except Exception as e:
            print(f"        ERROR: {e}")
            print("        Continuing with transcript only...")

        if not args.no_vision:
            print("  [6/7] Running multimodal vision model...")
            t0 = time.time()
            try:
                vision_results = describe_frames(frame_paths)
                vision_text = format_vision_results(vision_results)
                print(f"        Done in {time.time()-t0:.1f}s, {len(vision_text)} chars")
            except Exception as e:
                print(f"        ERROR: {e}")
                print("        Continuing without vision descriptions...")
        else:
            print("  [6/7] Vision model skipped (--no-vision)")
    else:
        print("  [5/7] No frames to process, skipping...")

    # Clean up frames
    shutil.rmtree(frames_dir, ignore_errors=True)

    # ── 4. DeepSeek fusion ───────────────────────────────────
    print("  [7/7] Fusing with DeepSeek...")
    try:
        problems = fuse(
            transcript=transcript,
            ocr_text=ocr_text,
            vision_text=vision_text,
            api_key=args.api_key,
            model=args.deepseek_model,
        )
        print(f"        Extracted {len(problems)} problems")
    except Exception as e:
        print(f"        ERROR: {e}")
        return None

    # ── 5. Save result ───────────────────────────────────────
    result = {
        "video_id": video_id,
        "title": info["title"],
        "url": info["webpage_url"],
        "duration_seconds": info["duration"],
        "problems": problems,
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / f"{video_id}.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"        Saved → {output_path}")

    # Clean up SRT
    try:
        os.remove(srt_path)
    except OSError:
        pass

    return result


def main() -> None:
    args = parse_args()

    set_cookies_browser(args.cookies_browser)
    set_cookies_file(args.cookies_file)

    cfg = load_config(
        model_path=args.model_path,
        model_dir=args.model_dir,
    )

    print("Runtime config:")
    print(cfg.summary())
    print()

    entries = read_and_expand_urls(args.urls)
    n_total = len(entries)
    n_coll = len(set(e["group"] for e in entries if e["group"]))
    n_single = sum(1 for e in entries if not e["group"])
    print(f"Total videos: {n_total}  (collections: {n_coll}, standalone: {n_single})\n")

    WORK_DIR_BASE.mkdir(exist_ok=True)

    success = 0
    failed = 0
    skipped = 0
    results_by_group: dict[str, list[dict]] = {}

    for i, entry in enumerate(entries, 1):
        url = entry["url"]
        group = entry["group"]
        video_id = get_video_id(url)

        if args.resume and already_processed(video_id):
            print(f"[{i}/{n_total}] {video_id} — already processed, skipping")
            skipped += 1
            continue

        vid_work_dir = WORK_DIR_BASE / video_id
        vid_work_dir.mkdir(exist_ok=True)

        result = process_video(url, cfg, args, vid_work_dir)

        shutil.rmtree(vid_work_dir, ignore_errors=True)

        if result:
            success += 1
            if group:
                results_by_group.setdefault(group, []).append(result)
        else:
            failed += 1

    # ── Merge collection results ──────────────────────────────
    if not args.no_merge and results_by_group:
        print(f"\n{'='*60}")
        print("  Merging collection results...")
        OUTPUT_DIR.mkdir(exist_ok=True)
        for group, vids in results_by_group.items():
            # Sort by video id to preserve playlist order
            vids.sort(key=lambda v: v["video_id"])
            all_problems: list[dict] = []
            for v in vids:
                for p in v.get("problems", []):
                    p["_source_video"] = v["video_id"]
                    p["_source_title"] = v["title"]
                    all_problems.append(p)

            merged = {
                "collection_id": group,
                "video_count": len(vids),
                "total_problems": len(all_problems),
                "videos": [
                    {
                        "video_id": v["video_id"],
                        "title": v["title"],
                        "url": v["url"],
                        "duration_seconds": v["duration_seconds"],
                        "problem_count": len(v.get("problems", [])),
                    }
                    for v in vids
                ],
                "problems": all_problems,
            }
            merged_path = OUTPUT_DIR / f"{group}.merged.json"
            merged_path.write_text(
                json.dumps(merged, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"    {group} → {merged_path}  ({len(all_problems)} problems from {len(vids)} videos)")

    print(f"\n{'='*60}")
    print(f"  Done. Success: {success}  Failed: {failed}  Skipped: {skipped}")
    print(f"  Results: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
