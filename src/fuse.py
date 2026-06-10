"""DeepSeek API integration for fusing transcript + OCR into structured problems."""

import json
import os
import time
from pathlib import Path

import httpx

DEEPSEEK_BASE = "https://api.deepseek.com/v1"
PROMPT_TEMPLATE = Path(__file__).resolve().parent.parent / "prompts" / "fuse.txt"


def load_prompt_template() -> str:
    """Load the fuse prompt template from prompts/fuse.txt."""
    if PROMPT_TEMPLATE.is_file():
        return PROMPT_TEMPLATE.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt template not found: {PROMPT_TEMPLATE}")


def fuse(
    transcript: str,
    ocr_text: str,
    vision_text: str = "",
    api_key: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    max_retries: int = 3,
) -> list[dict]:
    """Send transcript + OCR results to DeepSeek, return structured problems.

    Args:
        transcript: SRT subtitle content (with timestamps).
        ocr_text: Formatted OCR results from video frames.
        api_key: DeepSeek API key (falls back to DEEPSEEK_API_KEY env).
        model: Model name.
        temperature: Sampling temperature (0 for deterministic).
        max_retries: Number of retries on failure.

    Returns:
        List of problem dicts with keys: id, time_range, topic, content,
        has_solution, solution_summary.
    """
    if api_key is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError(
            "DeepSeek API key not provided. Set DEEPSEEK_API_KEY env var."
        )

    template = load_prompt_template()
    prompt = template.format(
        transcript=transcript,
        ocr_results=ocr_text,
        vision_results=vision_text or "(无视觉描述)",
    )

    if model is None:
        model = "deepseek-v4-flash"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个专业的数学题目提取助手。请只返回JSON数组，不要包含markdown标记。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "stream": False,
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{DEEPSEEK_BASE}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return _parse_json_response(content)
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code == 429:
                wait = min(2 ** attempt * 5, 60)
                time.sleep(wait)
                continue
            raise
        except (json.JSONDecodeError, KeyError) as exc:
            last_error = exc
            break

    raise RuntimeError(f"DeepSeek API failed after {max_retries} retries: {last_error}")


def _parse_json_response(content: str) -> list[dict]:
    """Parse JSON array from LLM response, handling ``` fences."""
    text = content.strip()
    # Remove ```json ... ``` fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)
