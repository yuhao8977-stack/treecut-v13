"""One user-facing configuration file for every interface."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from treecut.platform.paths import RuntimePaths


@dataclass
class Settings:
    output_mode: Literal["jianying", "mp4", "both"] = "both"
    model_mode: Literal["auto", "cpu", "nvidia"] = "auto"
    vision_mode: Literal["auto", "florence", "qwen"] = "auto"
    asr_device: Literal["auto", "cpu", "cuda"] = "auto"
    default_duration: float = 30.0
    auto_preview: bool = True
    analysis_workers: int = 2
    material_sources: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if self.output_mode not in {"jianying", "mp4", "both"}:
            raise ValueError(f"不支持的输出模式: {self.output_mode}")
        if self.model_mode not in {"auto", "cpu", "nvidia"}:
            raise ValueError(f"不支持的模型模式: {self.model_mode}")
        if self.vision_mode not in {"auto", "florence", "qwen"}:
            raise ValueError(f"不支持的视觉模型选择: {self.vision_mode}")
        if self.asr_device not in {"auto", "cpu", "cuda"}:
            raise ValueError(f"不支持的 ASR 设备: {self.asr_device}（可选 auto/cpu/cuda）")
        if not isinstance(self.auto_preview, bool):
            raise ValueError("自动预览必须是布尔值")
        if not isinstance(self.analysis_workers, int) or not 1 <= self.analysis_workers <= 4:
            raise ValueError("分析并行数必须在 1–4 之间")
        if not isinstance(self.material_sources, list):
            raise ValueError("素材源列表格式错误")
        if not 5 <= self.default_duration <= 300:
            raise ValueError(f"默认时长必须在 5–300 秒之间: {self.default_duration}")
        cleaned = []
        for value in self.material_sources:
            path = Path(str(value)).expanduser()
            if not path.is_absolute():
                raise ValueError(f"素材源必须是绝对路径: {value}")
            text = str(path)
            if text not in cleaned:
                cleaned.append(text)
        self.material_sources = cleaned

    def output_flags(self) -> tuple[bool, bool]:
        """Return (MP4, Jianying) defaults consumed by every interface."""
        return self.output_mode in {"mp4", "both"}, self.output_mode in {"jianying", "both"}


def settings_path(paths: RuntimePaths | None = None) -> Path:
    paths = paths or RuntimePaths.discover()
    return paths.data_root / "config" / "settings.json"


def load_settings(paths: RuntimePaths | None = None) -> Settings:
    path = settings_path(paths)
    if not path.is_file():
        settings = Settings()
        save_settings(settings, paths)
        return settings
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("settings.json 必须是 JSON 对象")
        allowed = set(Settings.__dataclass_fields__)
        settings = Settings(**{key: value for key, value in data.items() if key in allowed})
        settings.validate()
        # Rewrite legacy decorative fields away so the file only advertises
        # settings that have real consumers in the current product.
        if set(data) != allowed or data != asdict(settings):
            save_settings(settings, paths)
        return settings
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        logging.getLogger("treecut").warning("设置文件损坏，已恢复默认设置：%s", error)
        settings = Settings()
        save_settings(settings, paths)
        return settings


def save_settings(settings: Settings, paths: RuntimePaths | None = None) -> Path:
    settings.validate()
    path = settings_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return path
