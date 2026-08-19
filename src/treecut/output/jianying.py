"""Generate an editable Jianying draft from the same verified edit plan."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from treecut.workflow import EditPlan


def sec_to_us(seconds: float) -> int:
    return round(seconds * 1_000_000)


def _parse_srt_time(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    return int(hours) * 3_600_000_000 + int(minutes) * 60_000_000 + int(seconds) * 1_000_000 + int(milliseconds) * 1000


def parse_srt(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    pattern = re.compile(r"\d+\s*\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)", re.S)
    cues = []
    for start, end, content in pattern.findall(text):
        start_us, end_us = _parse_srt_time(start), _parse_srt_time(end)
        cues.append({"start_us": start_us, "duration_us": end_us - start_us,
                     "text": " ".join(line.strip() for line in content.splitlines()).strip()})
    if not cues:
        raise RuntimeError(f"字幕文件没有有效条目：{path}")
    return cues


def validate_timeline_bounds(start_us: int, duration_us: int, total_us: int,
                             label: str) -> None:
    if start_us < 0 or duration_us <= 0 or total_us <= 0:
        raise ValueError(f"{label} 时间范围无效")
    if start_us + duration_us > total_us:
        raise RuntimeError(
            f"{label} 超出成片时间线，禁止静默截断：结束于 "
            f"{(start_us + duration_us) / 1_000_000:.2f} 秒，"
            f"成片只有 {total_us / 1_000_000:.2f} 秒"
        )


def _prepare_timeline_audio(ffmpeg: Path, source: Path, output: Path, total_us: int,
                            loop: bool) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = total_us / 1_000_000
    command = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y"]
    if loop:
        command.extend(["-stream_loop", "-1"])
    command.extend(["-i", str(source)])
    if loop:
        command.extend(["-t", f"{duration:.6f}"])
    else:
        command.extend(["-af", f"apad=whole_dur={duration:.6f}", "-t", f"{duration:.6f}"])
    command.extend(["-vn", "-c:a", "pcm_s16le", str(output)])
    result = subprocess.run(command, capture_output=True, check=False, timeout=300)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size < 1000:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"剪映时间线音频准备失败：{error or output}")
    return output


@dataclass(frozen=True)
class DraftResult:
    path: str
    duration_us: int
    video_segments: int
    subtitle_segments: int
    has_voice: bool
    has_bgm: bool

    def to_dict(self) -> dict:
        return asdict(self)


def build_jianying_draft(plan: EditPlan, draft_dir: Path, narration_wav: Path,
                         bgm: Path, subtitle_srt: Path, ffmpeg: Path,
                         width: int = 1080, height: int = 1920,
                         fps: int = 30) -> DraftResult:
    if not plan.complete or not plan.segments:
        raise ValueError("只有完整且非空的剪辑计划才能导出剪映草稿")
    for path in (narration_wav, bgm, subtitle_srt, ffmpeg):
        if not path.is_file():
            raise FileNotFoundError(path)
    tool_dir = str(ffmpeg.parent)
    if tool_dir.lower() not in {item.lower() for item in os.environ.get("PATH", "").split(os.pathsep)}:
        os.environ["PATH"] = tool_dir + os.pathsep + os.environ.get("PATH", "")

    from pyJianYingDraft import TrackSpec
    from pyJianYingDraft.audio_segment import AudioSegment
    from pyJianYingDraft.local_materials import AudioMaterial, VideoMaterial
    from pyJianYingDraft.script_file import ScriptFile
    from pyJianYingDraft.segment import ClipSettings
    from pyJianYingDraft.text_segment import TextBorder, TextSegment, TextStyle
    from pyJianYingDraft.time_util import Timerange
    from pyJianYingDraft.track import TrackType
    from pyJianYingDraft.video_segment import VideoSegment

    total_us = sec_to_us(plan.planned_duration)
    original_voice = AudioMaterial(str(narration_wav))
    validate_timeline_bounds(0, original_voice.duration, total_us, "配音")
    draft_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = draft_dir / "treecut_assets"
    voice_path = _prepare_timeline_audio(
        ffmpeg, narration_wav, assets_dir / "voice_timeline.wav", total_us, loop=False
    )
    music_path = _prepare_timeline_audio(
        ffmpeg, bgm, assets_dir / "bgm_timeline.wav", total_us, loop=True
    )

    script = ScriptFile(width=width, height=height, fps=fps, maintrack_adsorb=True)
    draft_id = uuid.uuid4().hex
    script.content["id"] = draft_id
    script.content["name"] = draft_dir.name
    for spec in (TrackSpec(TrackType.video, "主画面"), TrackSpec(TrackType.audio, "配音"),
                 TrackSpec(TrackType.audio, "背景音乐"), TrackSpec(TrackType.text, "字幕")):
        script.append_track(spec)

    for item in plan.segments:
        duration_us = sec_to_us(item.timeline_end - item.timeline_start)
        segment = VideoSegment(
            VideoMaterial(item.path), Timerange(sec_to_us(item.timeline_start), duration_us),
            source_timerange=Timerange(sec_to_us(item.source_start), duration_us),
            volume=0.0, clip_settings=ClipSettings(),
        )
        script.add_segment(segment, "主画面")

    voice = AudioMaterial(str(voice_path))
    validate_timeline_bounds(0, voice.duration, total_us, "配音")
    script.add_segment(AudioSegment(voice, Timerange(0, total_us),
                                    source_timerange=Timerange(0, total_us), volume=1.0), "配音")
    music = AudioMaterial(str(music_path))
    validate_timeline_bounds(0, music.duration, total_us, "背景音乐")
    bgm_segment = AudioSegment(music, Timerange(0, total_us),
                               source_timerange=Timerange(0, total_us), volume=0.10)
    bgm_segment.add_fade(500_000, min(2_000_000, total_us))
    script.add_segment(bgm_segment, "背景音乐")

    cues = parse_srt(subtitle_srt)
    for cue in cues:
        validate_timeline_bounds(cue["start_us"], cue["duration_us"], total_us, "字幕")
        segment = TextSegment(
            cue["text"], Timerange(cue["start_us"], cue["duration_us"]),
            style=TextStyle(size=8.0, bold=True, color=(1, 1, 1), align=1, auto_wrapping=True),
            border=TextBorder(alpha=1.0, color=(0, 0, 0), width=35.0),
            clip_settings=ClipSettings(transform_y=-0.72),
        )
        script.add_segment(segment, "字幕")
    script.duration = total_us

    content = json.loads(script.dumps())
    content_path = draft_dir / "draft_content.json"
    content_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    now_ms = int(time.time() * 1000)
    meta = {
        "draft_id": draft_id.upper(), "draft_name": draft_dir.name,
        "draft_root_path": str(draft_dir).replace("\\", "/"), "tm_duration": total_us,
        "draft_cloud_materials": [], "draft_materials": [], "draft_is_invisible": False,
        "draft_create_time": now_ms, "draft_modified_time": now_ms,
    }
    (draft_dir / "draft_meta_info.json").write_text(
        json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8",
    )
    (draft_dir / "draft_settings").write_text(
        f"[General]\ndraft_create_time={now_ms // 1000}\ndraft_last_edit_time={now_ms // 1000}\n",
        encoding="utf-8",
    )
    reloaded = json.loads(content_path.read_text(encoding="utf-8"))
    if not reloaded.get("tracks") or int(reloaded.get("duration") or 0) != total_us:
        raise RuntimeError("剪映草稿结构校验失败")
    track_segments = {track.get("name"): track.get("segments") or [] for track in reloaded["tracks"]}
    return DraftResult(
        str(draft_dir), total_us, len(track_segments.get("主画面", [])),
        len(track_segments.get("字幕", [])), bool(track_segments.get("配音")),
        bool(track_segments.get("背景音乐")),
    )
