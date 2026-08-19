"""Cover frame with a drawn title, generated from the final MP4."""
from __future__ import annotations

from pathlib import Path
import subprocess
import textwrap


def _extract_frame(final_mp4: Path, ffmpeg: Path, output: Path) -> Path:
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(final_mp4), "-vf", "select=eq(n\\,30)", "-frames:v", "1", "-q:v", "3",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, check=False, timeout=120)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size < 1000:
        raise RuntimeError("封面抽帧失败")
    return output


def _draw_title(frame_path: Path, title: str, font_dir: Path, output: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    fonts = sorted(font_dir.glob("*.ttf")) + sorted(font_dir.glob("*.otf"))
    font_path = next((p for p in fonts if "NotoSansCJK" in p.name or "NotoSansSC" in p.name),
                     fonts[0] if fonts else None)
    if font_path is None:
        raise RuntimeError("缺少中文字体，无法生成封面")
    image = Image.open(frame_path).convert("RGB")
    width, height = image.size
    font_size = max(28, int(width * 0.055))
    font = ImageFont.truetype(str(font_path), font_size)
    draw = ImageDraw.Draw(image)
    max_chars = max(8, int(width / font_size * 1.4))
    lines = textwrap.wrap(title, width=max_chars)[:2]
    line_height = int(font_size * 1.5)
    total_height = line_height * len(lines)
    y = height - total_height - int(height * 0.08)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255),
                  stroke_width=max(2, font_size // 12), stroke_fill=(0, 0, 0))
        y += line_height
    image.save(output, "JPEG", quality=88)
    return output


def make_cover(final_mp4: Path, title: str, font_dir: Path, ffmpeg: Path,
               project_dir: Path) -> Path:
    """Extract a frame and draw a centered title near the bottom."""
    if not title.strip():
        raise ValueError("封面标题不能为空")
    output = project_dir / "cover.jpg"
    frame = project_dir / "work" / "cover_frame.jpg"
    frame.parent.mkdir(parents=True, exist_ok=True)
    _extract_frame(final_mp4, ffmpeg, frame)
    _draw_title(frame, title.strip(), font_dir, output)
    return output
