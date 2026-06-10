"""Multimodal vision model — describes charts/diagrams/formulas in video frames.

Uses ModelScope API (OpenAI-compatible) with stepfun-ai/Step-3.7-Flash.
"""

import base64
import os

from openai import OpenAI


MODELSCOPE_BASE = "https://api-inference.modelscope.cn/v1"


def _get_client(api_key: str | None = None) -> OpenAI:
    if api_key is None:
        api_key = os.environ.get("MODELSCOPE_API_KEY", "")
    if not api_key:
        raise ValueError(
            "ModelScope API key not set. "
            "Set MODELSCOPE_API_KEY env var."
        )
    return OpenAI(base_url=MODELSCOPE_BASE, api_key=api_key)


def describe_frames(
    frame_paths: list[str],
    api_key: str | None = None,
) -> dict[str, str]:
    """Send frames to multimodal model for visual description.

    Returns dict mapping frame filename → natural-language description.
    """
    client = _get_client(api_key)
    results: dict[str, str] = {}
    prompt = (
        "请详细描述这张PPT/板书截图中的内容，特别关注：\n"
        "1. 题目文本（如有）\n"
        "2. 数学公式和符号（用LaTeX格式描述）\n"
        "3. 几何图形、函数图像、图表的内容\n"
        "4. 图上坐标轴、标注、曲线等视觉元素\n"
        "5. 如果有解答步骤，描述解题过程"
    )

    for fpath in frame_paths:
        fname = os.path.basename(fpath)
        with open(fpath, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        try:
            resp = client.chat.completions.create(
                model="stepfun-ai/Step-3.7-Flash",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_b64}"
                            },
                        },
                    ],
                }],
            )
            results[fname] = resp.choices[0].message.content or ""
        except Exception as exc:
            results[fname] = f"[ERROR: {exc}]"

    return results


def format_vision_results(results: dict[str, str]) -> str:
    """Format vision results into a readable string for the LLM prompt."""
    lines: list[str] = []
    for fname in sorted(results.keys()):
        desc = results[fname].strip()
        if desc:
            lines.append(f"[{fname}] {desc}")
    return "\n".join(lines)
