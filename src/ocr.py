"""PaddleOCR wrapper for frame text extraction. Supports CPU and GPU."""

import os
from pathlib import Path


def recognize_frames(
    frame_paths: list[str],
    device: str = "cpu",
    lang: str = "ch",
) -> dict[str, list[dict]]:
    """Run PaddleOCR on a list of frame images.

    Args:
        frame_paths: List of absolute paths to frame images.
        device: 'cpu' or 'gpu'.
        lang: Language code, 'ch' for Chinese.

    Returns:
        Dict mapping frame filename -> list of {'text': str, 'confidence': float}.
        Failed frames contain {'error': str} instead.
    """
    from paddleocr import PaddleOCR

    use_gpu = device == "gpu"
    ocr = PaddleOCR(lang=lang, use_gpu=use_gpu)

    results: dict[str, list[dict]] = {}
    for fpath in frame_paths:
        fname = os.path.basename(fpath)
        try:
            raw = ocr.ocr(fpath)
            lines: list[dict] = []
            if raw and raw[0]:
                for item in raw[0]:
                    if len(item) == 2:
                        _box, (text, conf) = item
                        lines.append({"text": text, "confidence": float(conf)})
                    elif isinstance(item, dict):
                        lines.append(item)
            results[fname] = lines
        except Exception as exc:
            results[fname] = [{"error": str(exc)}]
    return results


def format_ocr_results(results: dict[str, list[dict]]) -> str:
    """Format OCR results dictionary into a readable string for the LLM prompt."""
    lines: list[str] = []
    for fname in sorted(results.keys()):
        entries = results[fname]
        texts = []
        for e in entries:
            if "error" in e:
                texts.append(f"[ERROR: {e['error']}]")
            else:
                texts.append(e.get("text", ""))
        combined = " ".join(t for t in texts if t)
        if combined:
            lines.append(f"[{fname}] {combined}")
    return "\n".join(lines)
