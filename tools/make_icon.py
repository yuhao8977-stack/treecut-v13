"""Generate the TreeCut desktop icon (assets/icon.ico) with Pillow only."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


SIZE = 256
SUPER = 4
BG = (46, 125, 50, 255)          # 树剪绿
BG_EDGE = (27, 94, 32, 255)      # 深一档的描边
LEAF = (255, 255, 255, 255)      # 白色树冠
TRUNK = (180, 130, 60, 255)      # 树干


def draw_icon() -> Image.Image:
    canvas = Image.new("RGBA", (SIZE * SUPER, SIZE * SUPER), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    radius = 58 * SUPER
    draw.rounded_rectangle(
        (8 * SUPER, 8 * SUPER, (SIZE - 8) * SUPER, (SIZE - 8) * SUPER),
        radius=radius, fill=BG, outline=BG_EDGE, width=3 * SUPER,
    )
    # 树干
    draw.rectangle(
        ((SIZE // 2 - 16) * SUPER, (SIZE // 2 + 28) * SUPER,
         (SIZE // 2 + 16) * SUPER, (SIZE // 2 + 74) * SUPER),
        fill=TRUNK,
    )
    # 三层树冠
    for dx, dy, r in ((0, -58, 72), (-44, -6, 54), (44, -6, 54)):
        cx = (SIZE // 2 + dx) * SUPER
        cy = (SIZE // 2 + dy) * SUPER
        draw.ellipse((cx - r * SUPER, cy - r * SUPER, cx + r * SUPER, cy + r * SUPER), fill=LEAF)
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "assets"
    root.mkdir(parents=True, exist_ok=True)
    image = draw_icon()
    image.save(
        root / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"icon written: {root / 'icon.ico'}")


if __name__ == "__main__":
    main()
