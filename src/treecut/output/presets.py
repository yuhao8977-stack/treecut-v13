"""One source of truth for output canvas presets (vertical/horizontal/square)."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OutputPreset:
    key: str
    label: str
    width: int
    height: int
    fps: int = 30

    def to_dict(self) -> dict:
        return asdict(self)


PRESETS: dict[str, OutputPreset] = {
    "vertical": OutputPreset("vertical", "竖屏 9:16（抖音/快手/小红书）", 1080, 1920),
    "horizontal": OutputPreset("horizontal", "横屏 16:9", 1920, 1080),
    "square": OutputPreset("square", "方屏 1:1", 1080, 1080),
}

PLATFORMS: dict[str, tuple[str, int]] = {
    "douyin": ("vertical", 30),
    "kuaishou": ("vertical", 30),
    "xiaohongshu": ("square", 30),
}


def resolve_preset(key: str | None) -> OutputPreset:
    if key in PLATFORMS:
        base_key, fps = PLATFORMS[key]
        base = PRESETS[base_key]
        return OutputPreset(key, f"平台预设 {key}", base.width, base.height, fps)
    if key not in PRESETS:
        raise ValueError(f"不支持的输出画幅: {key}")
    return PRESETS[key]
