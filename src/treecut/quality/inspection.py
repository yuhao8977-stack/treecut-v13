"""Evidence-based output checks; no synthetic quality score is reported."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess

from treecut.media import probe_media
from treecut.workflow.planning import EditPlan


@dataclass(frozen=True)
class QualityCheck:
    code: str
    passed: bool
    actual: object
    expected: str
    critical: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    checks: tuple[QualityCheck, ...]

    def to_dict(self) -> dict:
        return {"passed": self.passed, "checks": [item.to_dict() for item in self.checks]}


def _report(checks: list[QualityCheck]) -> QualityReport:
    return QualityReport(
        passed=all(item.passed for item in checks if item.critical),
        checks=tuple(checks),
    )


def inspect_edit_plan(plan: EditPlan) -> QualityReport:
    """Reject structurally weak or unsupported edit decisions before rendering."""
    segments = list(plan.segments)
    timeline_ok = source_ok = lengths_ok = True
    cursor = 0.0
    for segment in segments:
        if abs(segment.timeline_start - cursor) > 0.002 or segment.timeline_end <= segment.timeline_start:
            timeline_ok = False
        if segment.source_start < 0 or segment.source_end <= segment.source_start:
            source_ok = False
        length = segment.timeline_end - segment.timeline_start
        if length < 1.0 or abs(length - (segment.source_end - segment.source_start)) > 0.002:
            lengths_ok = False
        cursor = segment.timeline_end
    fingerprints = [item.content_fingerprint for item in segments if item.content_fingerprint]
    media_ids = [item.media_id for item in segments]
    evidence_ok = all(item.matched_terms and item.match_score >= 0.10 for item in segments)
    return _report([
        QualityCheck("plan_complete", plan.complete, plan.complete, "计划明确标记完整"),
        QualityCheck("plan_timeline_coverage",
                     timeline_ok and abs(cursor - plan.requested_duration) <= 0.01,
                     {"end": cursor, "target": plan.requested_duration},
                     "时间线从 0 连续覆盖目标时长"),
        QualityCheck("plan_source_bounds", source_ok, source_ok, "所有源片段起止为有效正区间"),
        QualityCheck("plan_clip_lengths", lengths_ok, lengths_ok, "镜头至少 1 秒且源/目标长度一致"),
        QualityCheck("plan_unique_media", len(media_ids) == len(set(media_ids)), media_ids,
                     "同一素材编号不重复"),
        QualityCheck("plan_unique_content", len(fingerprints) == len(set(fingerprints)), fingerprints,
                     "同一内容指纹不重复"),
        QualityCheck("plan_matching_evidence", evidence_ok,
                     [{"media_id": item.media_id, "score": item.match_score,
                       "terms": item.matched_terms} for item in segments],
                     "每个镜头有匹配词且相关分 >= 0.10"),
    ])


def inspect_final_video(path: Path, ffprobe: Path, expected_duration: float,
                        expected_width: int = 1080, expected_height: int = 1920) -> QualityReport:
    if not path.is_file():
        return _report([QualityCheck("video_exists", False, False, "成片文件存在")])
    size = path.stat().st_size
    checks = [QualityCheck("video_bytes", size >= 10_000, size, ">= 10000 字节")]
    try:
        media = probe_media(path, ffprobe)
    except Exception as error:
        checks.append(QualityCheck("video_probe", False, str(error), "FFprobe 可读取"))
        return _report(checks)
    checks.extend([
        QualityCheck("video_duration", abs(media.duration - expected_duration) <= 0.5,
                     round(media.duration, 3), f"{expected_duration:.3f}±0.5 秒"),
        QualityCheck("video_dimensions",
                     media.width == expected_width and media.height == expected_height,
                     f"{media.width}x{media.height}", f"精确 {expected_width}x{expected_height}"),
        QualityCheck("video_audio", media.has_audio, media.has_audio, "包含音轨"),
    ])
    return _report(checks)


def inspect_jianying_draft(path: Path, expected_duration: float) -> QualityReport:
    content_path = path / "draft_content.json"
    meta_path = path / "draft_meta_info.json"
    settings_path = path / "draft_settings"
    checks = [
        QualityCheck("draft_content_exists", content_path.is_file(), content_path.is_file(), "存在"),
        QualityCheck("draft_meta_exists", meta_path.is_file(), meta_path.is_file(), "存在"),
        QualityCheck("draft_settings_exists", settings_path.is_file(), settings_path.is_file(), "存在"),
    ]
    if not content_path.is_file():
        return _report(checks)
    try:
        content = json.loads(content_path.read_text(encoding="utf-8"))
    except Exception as error:
        checks.append(QualityCheck("draft_json", False, str(error), "合法 JSON"))
        return _report(checks)
    duration_us = int(content.get("duration") or 0)
    tracks = content.get("tracks") or []
    materials = content.get("materials") or {}
    material_map = {
        item.get("id"): item
        for group in (materials.get("videos") or [], materials.get("audios") or [],
                      materials.get("texts") or [])
        for item in group if isinstance(item, dict) and item.get("id")
    }
    named = {track.get("name"): track for track in tracks if isinstance(track, dict)}
    required = {"主画面": "video", "配音": "audio", "背景音乐": "audio", "字幕": "text"}
    track_shape = all(
        name in named and named[name].get("type") == kind
        for name, kind in required.items()
    ) and len(named) == len(tracks)
    segment_counts = {name: len((named.get(name) or {}).get("segments") or []) for name in required}

    all_segments_valid = True
    all_sources_exist = True
    invalid_reasons: list[str] = []
    for name in required:
        for segment in (named.get(name) or {}).get("segments") or []:
            timerange = segment.get("target_timerange") or {}
            start = int(timerange.get("start") or 0)
            length = int(timerange.get("duration") or 0)
            material = material_map.get(segment.get("material_id"))
            if material is None or length <= 0 or start < 0 or start + length > duration_us:
                all_segments_valid = False
                invalid_reasons.append(f"{name}:素材引用或目标时间范围无效")
                continue
            if name != "字幕":
                source = segment.get("source_timerange") or {}
                source_start = int(source.get("start") or 0)
                source_length = int(source.get("duration") or 0)
                material_duration = int(material.get("duration") or 0)
                if source_length != length or source_start < 0 or source_start + source_length > material_duration:
                    all_segments_valid = False
                    invalid_reasons.append(f"{name}:源时间范围无效")
                material_path = material.get("path") or ""
                if not material_path or not Path(material_path).is_file():
                    all_sources_exist = False

    def continuous_full_track(name: str) -> bool:
        ranges = sorted(
            (int((item.get("target_timerange") or {}).get("start") or 0),
             int((item.get("target_timerange") or {}).get("duration") or 0))
            for item in (named.get(name) or {}).get("segments") or []
        )
        cursor = 0
        for start, length in ranges:
            if start != cursor or length <= 0:
                return False
            cursor += length
        return cursor == duration_us

    meta_valid = False
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta_valid = (int(meta.get("tm_duration") or 0) == duration_us
                          and str(meta.get("draft_id") or "").lower() == str(content.get("id") or "").lower())
        except Exception:
            meta_valid = False
    checks.extend([
        QualityCheck("draft_duration", abs(duration_us / 1_000_000 - expected_duration) <= 0.5,
                     duration_us, f"{expected_duration:.3f}±0.5 秒"),
        QualityCheck("draft_required_tracks", track_shape, segment_counts,
                     "主画面、配音、背景音乐、字幕四条唯一命名轨道且类型正确"),
        QualityCheck("draft_nonempty_tracks", all(value > 0 for value in segment_counts.values()),
                     segment_counts, "四条轨道均至少有一个片段"),
        QualityCheck("draft_segment_bounds", all_segments_valid,
                     invalid_reasons or "全部有效", "素材引用有效且所有源/目标时间范围不越界"),
        QualityCheck("draft_source_files", all_sources_exist, all_sources_exist,
                     "全部视频和音频源文件存在"),
        QualityCheck("draft_video_coverage", continuous_full_track("主画面"),
                     segment_counts["主画面"], "主画面从 0 连续覆盖至项目结尾"),
        QualityCheck("draft_voice_coverage", continuous_full_track("配音"),
                     segment_counts["配音"], "配音轨从 0 连续覆盖至项目结尾"),
        QualityCheck("draft_bgm_coverage", continuous_full_track("背景音乐"),
                     segment_counts["背景音乐"], "背景音乐从 0 连续覆盖至项目结尾"),
        QualityCheck("draft_meta_consistency", meta_valid, meta_valid,
                     "元数据 ID 和时长与草稿内容一致"),
    ])
    return _report(checks)


def _metric_values(text: str, name: str) -> list[float]:
    return [float(value) for value in re.findall(rf"{re.escape(name)}:\s*(-?[0-9.]+)", text)]


def inspect_playback_quality(path: Path, ffmpeg: Path, duration: float) -> QualityReport:
    """Decode the complete output and inspect black/frozen/silent ranges and volume."""
    command = [
        str(ffmpeg), "-hide_banner", "-nostats", "-i", str(path),
        "-vf", "blackdetect=d=0.5:pix_th=0.10,freezedetect=n=-50dB:d=3",
        "-af", "silencedetect=n=-45dB:d=1,volumedetect", "-f", "null", "NUL",
    ]
    result = subprocess.run(command, capture_output=True, check=False, timeout=1800)
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    if result.returncode != 0:
        return _report([QualityCheck("playback_decode", False, output[-1000:], "整段可解码")])
    safe_duration = max(duration, 0.001)
    black_seconds = sum(_metric_values(output, "black_duration"))
    freeze_seconds = sum(_metric_values(output, "freeze_duration"))
    silence_seconds = sum(_metric_values(output, "silence_duration"))
    mean_values = _metric_values(output, "mean_volume")
    max_values = _metric_values(output, "max_volume")
    mean_volume = mean_values[-1] if mean_values else -999.0
    max_volume = max_values[-1] if max_values else -999.0
    return _report([
        QualityCheck("playback_decode", True, True, "整段可解码"),
        QualityCheck("black_ratio", black_seconds / safe_duration <= 0.03,
                     round(black_seconds / safe_duration, 4), "<= 3%"),
        QualityCheck("freeze_ratio", freeze_seconds / safe_duration <= 0.35,
                     round(freeze_seconds / safe_duration, 4), "<= 35%"),
        QualityCheck("silence_ratio", silence_seconds / safe_duration <= 0.50,
                     round(silence_seconds / safe_duration, 4), "<= 50%"),
        QualityCheck("mean_volume", -45 <= mean_volume <= -5,
                     mean_volume, "-45 至 -5 dB"),
        QualityCheck("max_volume", -35 <= max_volume <= 0.1,
                     max_volume, "-35 至 0.1 dB"),
    ])


def _subtitle_sample_midpoints(srt_path: Path, maximum: int = 3) -> list[float]:
    text = srt_path.read_text(encoding="utf-8-sig")
    matches = list(re.finditer(
        r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)", text,
    ))
    if not matches:
        raise ValueError("字幕文件没有有效时间轴")
    indexes = sorted({0, len(matches) // 2, len(matches) - 1})[:max(1, maximum)]
    result = []
    for index in indexes:
        values = [int(item) for item in matches[index].groups()]
        start = values[0] * 3600 + values[1] * 60 + values[2] + values[3] / 1000
        end = values[4] * 3600 + values[5] * 60 + values[6] + values[7] / 1000
        result.append((start + end) / 2)
    return result


def inspect_burned_subtitles(source_video: Path, burned_video: Path,
                             srt_path: Path) -> QualityReport:
    """Compare a cue frame before/after burn-in; evidence must concentrate at the bottom."""
    try:
        import cv2
        import numpy as np

        timestamps = _subtitle_sample_midpoints(srt_path)
        captures = [cv2.VideoCapture(str(path)) for path in (source_video, burned_video)]
        samples = []
        try:
            for timestamp in timestamps:
                frames = []
                for path, capture in zip((source_video, burned_video), captures):
                    capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        raise RuntimeError(f"无法读取字幕验证帧：{path}")
                    frames.append(frame)
                if frames[0].shape != frames[1].shape:
                    raise RuntimeError("字幕烧录前后画面尺寸不同")
                difference = cv2.absdiff(frames[0], frames[1]).mean(axis=2)
                split = int(difference.shape[0] * 0.55)
                top_mean = float(np.mean(difference[:split]))
                bottom_mean = float(np.mean(difference[split:]))
                samples.append({
                    "timestamp": round(timestamp, 3),
                    "top_difference": round(top_mean, 3),
                    "bottom_difference": round(bottom_mean, 3),
                    "passed": bottom_mean >= 3.0 and bottom_mean >= top_mean * 2,
                })
        finally:
            for capture in captures:
                capture.release()
        passed = len(samples) == len(timestamps) and all(item["passed"] for item in samples)
        return _report([QualityCheck(
            "burned_subtitle_pixels", passed,
            samples,
            "首、中、末字幕抽样点的底部像素差均 >= 3 且至少为顶部 2 倍",
        )])
    except Exception as error:
        return _report([QualityCheck("burned_subtitle_pixels", False, str(error), "可验证字幕像素")])


def combine_reports(*reports: QualityReport) -> QualityReport:
    checks = [check for report in reports for check in report.checks]
    return _report(checks)
