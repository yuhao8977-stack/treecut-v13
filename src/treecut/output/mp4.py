"""Render an edit decision list into a real MP4 through bundled FFmpeg."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import subprocess

from treecut.media import probe_media
from treecut.workflow import EditPlan
from treecut.output.presets import OutputPreset
from treecut.output.filters import post_concat_chain, watermark_overlay


@dataclass(frozen=True)
class RenderResult:
    path: str
    bytes: int
    duration: float
    width: int
    height: int
    segments: int
    has_audio: bool
    profile: str

    def to_dict(self) -> dict:
        return asdict(self)


PROFILES = {"preview": (540, 960, "veryfast", "26"), "final": (1080, 1920, "medium", "20")}


def render_video_plan(plan: EditPlan, output: Path, ffmpeg: Path, ffprobe: Path,
                      profile: str = "preview",
                      preset: OutputPreset | None = None,
                      style: str = "natural",
                      watermark_path: Path | None = None,
                      watermark_position: str = "bottom_right") -> RenderResult:
    if profile not in PROFILES:
        raise ValueError(f"未知渲染规格：{profile}")
    if not plan.segments:
        raise ValueError("剪辑计划没有片段")
    profile_width, profile_height, encoding_preset, crf = PROFILES[profile]
    width = preset.width if preset else profile_width
    height = preset.height if preset else profile_height
    command = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y"]
    for segment in plan.segments:
        command.extend(["-ss", f"{segment.source_start:.3f}", "-t",
                        f"{segment.source_end - segment.source_start:.3f}", "-i", segment.path])
    watermark_input = Path(watermark_path) if watermark_path else None
    if watermark_input is not None:
        command.extend(["-i", str(watermark_input)])
    filters = []
    labels = []
    for index, _ in enumerate(plan.segments):
        label = f"v{index}"
        fps = preset.fps if preset else 30
        filters.append(
            f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,fps={fps},setsar=1[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[outv]")
    map_label = "outv"
    chain = post_concat_chain(style, plan.planned_duration)
    if chain:
        filters.append(f"[outv]{chain}[graded]")
        map_label = "graded"
    if watermark_input is not None:
        overlay = watermark_overlay(watermark_input, watermark_position)
        filters.append(f"[{map_label}][{len(plan.segments)}:v]{overlay}[wm]")
        map_label = "wm"
    output.parent.mkdir(parents=True, exist_ok=True)
    command.extend(["-filter_complex", ";".join(filters), "-map", f"[{map_label}]", "-an",
                    "-c:v", "libx264", "-preset", encoding_preset, "-crf", crf,
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)])
    result = subprocess.run(command, capture_output=True, check=False, timeout=1800)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size < 10_000:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"MP4 渲染失败：{error or '输出文件无效'}")
    probe = probe_media(output, ffprobe)
    if abs(probe.duration - plan.planned_duration) > 0.5:
        raise RuntimeError(f"渲染时长不符：{probe.duration:.2f} / {plan.planned_duration:.2f} 秒")
    return RenderResult(str(output), output.stat().st_size, probe.duration, probe.width,
                        probe.height, len(plan.segments), probe.has_audio, profile)
