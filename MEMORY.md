# Memory: bilibili-extractor session

## Project
Bilibili video problem extraction tool. Takes a B站 video/collection URL, extracts
audio transcription + frame OCR, fuses via DeepSeek API into structured problems.

Repo: `github.com/gbt24/bilibili-extractor`
User's video set: BV1FdetzEEVA (王道2027计算机网络, 129 parts, ~14 min each)

## Key Architecture Decisions

### yt-dlp → bilibili-api-python migration
- **Why**: yt-dlp + browser cookies failed on Windows due to DPAPI decryption +
  Chrome/Edge cookie DB locks. Cookie file approach unreliable (SESSDATA HttpOnly).
- **Solution**: `bilibili-api-python` calls B站 REST APIs directly. Public videos
  need no auth at all. QR login (`login.py`) only needed for paid courses.
- Files: `src/bilibili.py` (API wrapper), `src/bilibili_auth.py` (QR login),
  `src/frames.py` (httpx download + ffmpeg extract).

### DASH stream detection
- `VideoDownloadURLDataDetecter.detect_best_streams()` returns merged best stream
  (video), not separate audio/video.
- Must parse `dash_data['dash']['audio']` and `['video']` arrays directly, then
  pick by `base_url` field.

### Vision model
- Works (ModelScope stepfun-ai/Step-3.7-Flash, via OpenAI-compatible API).
- But ~3s/frame × 47 frames = 2.5 min extra per video. Disabled by default.
- Flag: `--vision` to opt in. Only useful for videos heavy on charts/graphs.

### DeepSeek
- Model: `deepseek-v4-flash`
- `str.format()` breaks on Chinese chars in prompt templates (`{和}` → KeyError).
  Fixed by using `str.replace("{transcript}", ...)` instead.

### PaddleOCR
- v3.6 (PaddleX-based) has completely different API: returns `dict` with keys
  `rec_texts`, `rec_scores` instead of v2's list-of-tuples.
- No `lang=` or `use_gpu=` params in v3.6. Try v2 args, fall back to v3.

### Transcription
- Mac: whisper.cpp via brew (`whisper-cli`), CoreML accelerated, uses `.bin` model.
- Windows: `faster-whisper` Python package (auto-detected in `src/transcribe.py`),
  auto-downloads model, no compilation needed.

## Cross-platform Status

| Platform | B站 access | Whisper | OCR | Status |
|----------|-----------|---------|-----|--------|
| macOS | ✅ bilibili-api | whisper-cli | PaddleOCR CPU | Fully tested |
| Windows | ✅ bilibili-api | faster-whisper | PaddleOCR GPU | Code ready, untested |
| WSL2 Linux | ✅ bilibili-api | faster-whisper | PaddleOCR GPU | Supported in config |

## Past pitfalls

1. FFmpeg exit 251/183: CDN stream URLs expire quickly. Fixed by downloading
   temp video file first, then extracting frames.
2. `mkstemp` file descriptor leak: yt-dlp overwrites the file. Fixed by using
   uuid-based temp filenames instead.
3. Cookie Netscape format: Must use TAB separators (not spaces). yt-dlp
   rewrites `--cookies` file on each run (fixed by copying to temp).
4. Mac Safari cookies: `Operation not permitted` — SIP restriction.
5. SESSDATA is HttpOnly: JavaScript `document.cookie` can't read it.

## Test Results
- Single video (BV1FdetzEEVA p1): 5 problems correctly extracted
- Time: ~6 min/video (audio download + whisper + frame extract + OCR + DeepSeek)
- Full set (129 videos): est. 12 hours
- `--resume` flag supported for interrupted runs
