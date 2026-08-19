"""Offline narration draft generation from selling points (deterministic)."""
from __future__ import annotations

import re


def _phrases(text: str) -> list[str]:
    parts = [part.strip(" ，。、；：!?！？,. ") for part in re.split(r"[，。、；：!?！？,.]+", text)]
    seen: list[str] = []
    for part in parts:
        if 2 <= len(part) <= 18 and part not in seen:
            seen.append(part)
    return seen


def build_narration(selling_points: str, target_duration: float = 30) -> str:
    """Compose a short narration that fits the target video duration."""
    phrases = _phrases(selling_points)
    if not phrases:
        raise ValueError("卖点或画面需求不能为空")
    head = " ".join(phrases[:2])
    tail = "，".join(phrases[2:4])
    if tail:
        narration = f"{head}，{tail}，让家更舒适。"
    else:
        narration = f"{head}，让家更舒适。"
    max_chars = max(16, int(target_duration * 4.6))
    if len(narration) > max_chars:
        narration = narration[:max_chars].rstrip("，") + "。"
    return narration
