"""Single source of truth for render-time visual filters (style/watermark/fade)."""
from __future__ import annotations

from pathlib import Path


STYLE_FILTERS: dict[str, str] = {
    "natural": "",
    "warm": "colorbalance=rs=.08:gs=0:bs=-.08,eq=saturation=1.05",
    "vivid": "eq=saturation=1.35:contrast=1.08",
}

WATERMARK_POSITIONS = {
    "bottom_right": ("main_w-overlay_w-32", "main_h-overlay_h-32"),
    "bottom_left": ("32", "main_h-overlay_h-32"),
    "top_right": ("main_w-overlay_w-32", "32"),
    "top_left": ("32", "32"),
}


def resolve_style(style: str) -> str:
    if style not in STYLE_FILTERS:
        raise ValueError(f"不支持的画面风格: {style}")
    return STYLE_FILTERS[style]


def post_concat_chain(style: str, duration: float, fade: float = 0.4) -> str:
    """Filters applied to the concatenated timeline: grade + open/close fade."""
    parts = [resolve_style(style)] if resolve_style(style) else []
    if duration > 2.0 and fade > 0:
        parts.append(f"fade=t=in:st=0:d={fade:.3f}")
        parts.append(f"fade=t=out:st={max(0.0, duration - fade):.3f}:d={fade:.3f}")
    return ",".join(parts)


def watermark_overlay(watermark_path: Path, position: str = "bottom_right") -> str:
    if not watermark_path.is_file():
        raise FileNotFoundError(f"水印图片不存在: {watermark_path}")
    if position not in WATERMARK_POSITIONS:
        raise ValueError(f"不支持的水印位置: {position}")
    x, y = WATERMARK_POSITIONS[position]
    return f"overlay=({x}):({y}):eof_action=pass"
