"""Reliable media metadata inspection backed by the bundled ffprobe."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class MediaProbe:
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str | None
    has_audio: bool

    def to_dict(self) -> dict:
        return asdict(self)


def bundled_ffprobe(install_root: Path) -> Path:
    candidate = install_root / "tools" / "win32" / "ffprobe.exe"
    if not candidate.is_file():
        raise FileNotFoundError(f"缺少媒体检测工具：{candidate}")
    return candidate


def _rate(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    try:
        numerator, separator, denominator = value.partition("/")
        if separator:
            denominator_value = float(denominator)
            return float(numerator) / denominator_value if denominator_value else float(numerator)
        return float(numerator)
    except (TypeError, ValueError):
        return 0.0


def probe_media(path: Path, ffprobe: Path) -> MediaProbe:
    if not path.is_file():
        raise FileNotFoundError(path)
    command = [str(ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, check=False, timeout=60)
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"媒体文件无法读取：{path.name}；{error}")
    payload = json.loads(result.stdout.decode("utf-8", errors="replace"))
    streams = payload.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if video is None:
        raise RuntimeError(f"文件没有视频轨道：{path.name}")
    duration = float(payload.get("format", {}).get("duration") or video.get("duration") or 0)
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    if duration <= 0 or width <= 0 or height <= 0:
        raise RuntimeError(f"视频关键参数无效：{path.name}")
    return MediaProbe(duration, width, height,
                      _rate(video.get("avg_frame_rate") or video.get("r_frame_rate")),
                      str(video.get("codec_name") or "unknown"),
                      str(audio.get("codec_name")) if audio else None, audio is not None)
