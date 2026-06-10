"""PaddleOCR wrapper for frame text extraction. Supports CPU and GPU.

Auto-detects PaddleOCR v2 (list-of-tuples) vs v3 (dict-based, PaddleX).
"""

import os


def recognize_frames(
    frame_paths: list[str],
    device: str = "cpu",
    lang: str = "ch",
) -> dict[str, list[dict]]:
    from paddleocr import PaddleOCR

    # v3 (PaddleX) doesn't accept lang=/use_gpu=; v2 does
    try:
        ocr = PaddleOCR(lang=lang, use_gpu=(device == "gpu"))
    except (TypeError, ValueError):
        ocr = PaddleOCR()

    results: dict[str, list[dict]] = {}
    for fpath in frame_paths:
        fname = os.path.basename(fpath)
        try:
            raw = ocr.ocr(fpath)
            lines: list[dict] = []

            if raw and isinstance(raw, list):
                page = raw[0]

                if isinstance(page, dict):
                    # ── PaddleOCR v3 (dict-based) ──
                    rec_texts = page.get("rec_texts", [])
                    rec_scores = page.get("rec_scores", [])
                    for i, text in enumerate(rec_texts):
                        conf = rec_scores[i] if i < len(rec_scores) else 1.0
                        if text:
                            lines.append({"text": str(text), "confidence": float(conf)})
                elif isinstance(page, list):
                    # ── PaddleOCR v2 (list-of-tuples) ──
                    for item in page:
                        if len(item) == 2:
                            _box, (text, conf) = item
                            lines.append({"text": text, "confidence": float(conf)})
                        elif isinstance(item, dict):
                            t = item.get("rec_text", item.get("text", ""))
                            if t:
                                lines.append({"text": str(t), "confidence": float(item.get("rec_score", 1.0))})

            results[fname] = lines
        except Exception as exc:
            results[fname] = [{"error": str(exc)}]
    return results


def format_ocr_results(results: dict[str, list[dict]]) -> str:
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
