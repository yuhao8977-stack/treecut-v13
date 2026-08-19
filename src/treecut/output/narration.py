"""Offline narration, subtitle timing, and MP4 muxing."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import json
import subprocess
import wave

from treecut.media import probe_media
from treecut.models.tts_local import synthesize


@dataclass(frozen=True)
class NarratedResult:
    path: str
    bytes: int
    duration: float
    narration_duration: float
    subtitle_count: int
    has_audio: bool

    def to_dict(self) -> dict:
        return asdict(self)


def mix_background_music(video: Path, bgm: Path, output: Path, ffmpeg: Path, ffprobe: Path,
                         bgm_volume: float = 0.10) -> NarratedResult:
    if not 0 <= bgm_volume <= 0.5:
        raise ValueError("背景音乐音量必须在 0–0.5 之间")
    source = probe_media(video, ffprobe)
    if not source.has_audio:
        raise RuntimeError("输入视频没有配音轨，不能执行配音优先混音")
    if not bgm.is_file():
        raise FileNotFoundError(bgm)
    output.parent.mkdir(parents=True, exist_ok=True)
    fade_start = max(0.0, source.duration - 2)
    audio_filter = (
        f"[0:a]volume=1.0[narration];"
        f"[1:a]volume={bgm_volume},atrim=0:{source.duration:.3f},"
        f"afade=t=out:st={fade_start:.3f}:d=2[bgm];"
        "[narration][bgm]amix=inputs=2:duration=first:normalize=0[mixed]"
    )
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
        "-stream_loop", "-1", "-i", str(bgm), "-filter_complex", audio_filter,
        "-map", "0:v:0", "-map", "[mixed]", "-map", "0:s?", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "160k", "-c:s", "copy", "-t", f"{source.duration:.3f}",
        "-movflags", "+faststart", str(output),
    ]
    result = subprocess.run(command, capture_output=True, check=False, timeout=600)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size < 10_000:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"背景音乐混音失败：{error or '输出无效'}")
    probe = probe_media(output, ffprobe)
    if not probe.has_audio or abs(probe.duration - source.duration) > 0.2:
        raise RuntimeError("混音输出缺少音轨或时长不符")
    cues = subtitle_cue_count(output, ffprobe)
    if cues <= 0:
        raise RuntimeError("混音后字幕轨为空")
    return NarratedResult(str(output), output.stat().st_size, probe.duration,
                          source.duration, cues, True)


def split_sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[。！？!?])\s*", text.strip()) if item.strip()]


def split_subtitle_cues(text: str, protected: tuple[str, ...] | None = None) -> list[str]:
    """Split narration into short subtitle lines that follow the spoken rhythm.

    Sentence-ending punctuation (。！？!?) is a hard boundary; soft punctuation
    (，、；：,) breaks long sentences into readable lines of roughly 6-14
    characters. Fragments without punctuation are hard-wrapped.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[。！？!?])", text.strip()) if s.strip()]
    cues: list[str] = []
    for sentence in sentences:
        fragments = [f for f in re.split(r"(?<=[，、；：,])", sentence) if f.strip()]
        if not fragments:
            fragments = [sentence]
        current = ""
        for fragment in fragments:
            candidate = current + fragment
            if current and (len(candidate) > 14 or len(current) >= 6):
                cues.append(current)
                current = fragment
            else:
                current = candidate
        if current:
            cues.append(current)

    if protected is None:
        from treecut.knowledge import protected_words
        protected = protected_words()
    protected_terms = tuple(sorted(
        (str(term).strip() for term in protected if str(term).strip()),
        key=len, reverse=True,
    ))
    wrapped: list[str] = []
    for cue in cues:
        while len(cue) > 14:
            cut = 12
            for term in protected_terms:
                position = cue.find(term)
                if 0 < position < cut < position + len(term):
                    cut = position
            wrapped.append(cue[:cut])
            cue = cue[cut:]
        wrapped.append(cue)
    return wrapped


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}"


def _detect_pauses(audio_path: Path, min_gap: float = 0.18,
                   silence_threshold: float = 0.015, block_ms: int = 20) -> list[float]:
    """Return midpoints (seconds) of silent pauses in a 16-bit PCM WAV."""
    try:
        with wave.open(str(audio_path), "rb") as audio:
            if audio.getsampwidth() != 2:
                return []
            framerate = audio.getframerate()
            channels = audio.getnchannels()
            block = max(1, int(framerate * block_ms / 1000))
            total = audio.getnframes()
            silent_blocks: list[bool] = []
            for _ in range(0, total, block):
                raw = audio.readframes(block)
                if not raw:
                    break
                samples = __import__("array").array("h")
                samples.frombytes(raw)
                if channels > 1:
                    samples = samples[0::channels]
                if samples:
                    energy = sum(s * s for s in samples) / len(samples)
                    silent_blocks.append(energy < (silence_threshold * 32768) ** 2)
                else:
                    silent_blocks.append(True)
    except Exception:
        return []
    pauses: list[float] = []
    start = None
    for index, silent in enumerate(silent_blocks):
        if silent and start is None:
            start = index
        elif not silent and start is not None:
            gap_seconds = (index - start) * block_ms / 1000.0
            if gap_seconds >= min_gap:
                pauses.append((index + start) / 2 * block_ms / 1000.0)
            start = None
    if start is not None:
        gap_seconds = (len(silent_blocks) - start) * block_ms / 1000.0
        if gap_seconds >= min_gap:
            pauses.append((len(silent_blocks) + start) / 2 * block_ms / 1000.0)
    return pauses


def build_srt(text: str, audio_duration: float, audio_path: Path | None = None) -> str:
    cues = split_subtitle_cues(text)
    if not cues or audio_duration <= 0:
        raise ValueError("字幕文字和配音时长必须有效")
    weights = [max(1, len(re.sub(r"\s", "", cue))) for cue in cues]
    total = sum(weights)
    cursor = 0.0
    ends = []
    for index, weight in enumerate(weights):
        end = audio_duration if index == len(weights) - 1 else cursor + audio_duration * weight / total
        ends.append(end)
        cursor = end
    pauses = _detect_pauses(audio_path) if audio_path is not None else []
    if pauses:
        snapped = []
        for end in ends[:-1]:
            nearest = min(pauses, key=lambda pause: abs(pause - end))
            snapped.append(nearest if abs(nearest - end) <= 0.45 else end)
        for index in range(len(snapped)):
            lower = 0.0 if index == 0 else snapped[index - 1] + 0.05
            upper = ends[index + 1] - 0.05
            snapped[index] = min(max(snapped[index], lower), upper)
        ends = snapped + [ends[-1]]
    blocks = []
    cursor = 0.0
    for index, (cue, end) in enumerate(zip(cues, ends), 1):
        blocks.append(f"{index}\n{_srt_time(cursor)} --> {_srt_time(end)}\n{cue}\n")
        cursor = end
    return "\n".join(blocks)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / audio.getframerate()


def validate_narration_fit(narration_seconds: float, video_seconds: float) -> None:
    """Reject any narration that would be cut by the fixed video timeline."""
    if narration_seconds <= 0 or video_seconds <= 0:
        raise ValueError("配音时长和画面时长必须大于 0")
    if narration_seconds > video_seconds:
        raise RuntimeError(
            f"配音长于画面，禁止静默截断：配音 {narration_seconds:.2f} 秒，"
            f"画面 {video_seconds:.2f} 秒。请增加目标时长或缩短配音文案。"
        )


def _atempo_filters(speed: float) -> list[str]:
    """Split a target speed into chained atempo filters (each supports 0.5-2.0)."""
    if speed <= 0:
        raise ValueError("语速必须大于 0")
    factors: list[str] = []
    current = speed
    while current > 2.0:
        factors.append("atempo=2.0")
        current /= 2.0
    while current < 0.5:
        factors.append("atempo=0.5")
        current /= 0.5
    factors.append(f"atempo={current:.6f}")
    return factors


def _apply_narration_speed(source: Path, target: Path, speed: float, ffmpeg: Path) -> None:
    """Time-stretch narration with pitch-preserving atempo so any speed is exact."""
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-af", ",".join(_atempo_filters(speed)),
        "-c:a", "pcm_s16le", str(target),
    ]
    result = subprocess.run(command, capture_output=True, check=False, timeout=180)
    if result.returncode != 0 or not target.is_file() or target.stat().st_size < 1000:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"配音变速失败：{error or '未生成有效音频'}")


def subtitle_cue_count(path: Path, ffprobe: Path) -> int:
    result = subprocess.run([
        str(ffprobe), "-v", "error", "-select_streams", "s", "-count_packets",
        "-show_entries", "stream=nb_read_packets", "-of", "json", str(path),
    ], capture_output=True, check=False, timeout=30)
    if result.returncode != 0:
        return 0
    payload = json.loads(result.stdout.decode("utf-8", errors="replace") or "{}")
    packets = sum(int(stream.get("nb_read_packets") or 0) for stream in payload.get("streams", []))
    return packets


def _ffmpeg_filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def burn_subtitles(video: Path, subtitle: Path, font_dir: Path, output: Path,
                   ffmpeg: Path, ffprobe: Path) -> NarratedResult:
    source = probe_media(video, ffprobe)
    if not source.has_audio:
        raise RuntimeError("烧录字幕的输入视频缺少音轨")
    if not subtitle.is_file():
        raise FileNotFoundError(subtitle)
    fonts = list(font_dir.glob("*.otf")) + list(font_dir.glob("*.ttf"))
    if not fonts or max(font.stat().st_size for font in fonts) < 1_000_000:
        raise RuntimeError("随软件字体不存在或不完整")
    output.parent.mkdir(parents=True, exist_ok=True)
    style = ("FontName=Noto Sans CJK SC,FontSize=19,PrimaryColour=&H00FFFFFF,"
             "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=75,Alignment=2")
    video_filter = (f"subtitles=filename='{_ffmpeg_filter_path(subtitle)}':"
                    f"fontsdir='{_ffmpeg_filter_path(font_dir)}':force_style='{style}'")
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
        "-vf", video_filter, "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "copy",
        "-t", f"{source.duration:.3f}", "-movflags", "+faststart", str(output),
    ]
    result = subprocess.run(command, capture_output=True, check=False, timeout=1200)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size < 10_000:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"字幕烧录失败：{error or '输出无效'}")
    probe = probe_media(output, ffprobe)
    if not probe.has_audio or abs(probe.duration - source.duration) > 0.2:
        raise RuntimeError("字幕烧录输出缺少音轨或时长不符")
    return NarratedResult(str(output), output.stat().st_size, probe.duration,
                          source.duration, subtitle_cue_count(video, ffprobe), True)


def create_narrated_video(video: Path, narration: str, output: Path, work_dir: Path,
                          tts_model: Path, ffmpeg: Path, ffprobe: Path,
                          speed: float = 1.0) -> NarratedResult:
    if not video.is_file():
        raise FileNotFoundError(video)
    if not 0.5 <= speed <= 2.0:
        raise ValueError(f"语速必须在 0.5–2.0 之间: {speed}")
    source_probe = probe_media(video, ffprobe)
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_path = work_dir / "narration.wav"
    subtitle_path = work_dir / "narration.srt"
    synthesize(narration, audio_path, tts_model)
    if abs(speed - 1.0) > 1e-6:
        stretched = work_dir / "narration_speed.wav"
        _apply_narration_speed(audio_path, stretched, speed, ffmpeg)
        stretched.replace(audio_path)
    narration_seconds = wav_duration(audio_path)
    validate_narration_fit(narration_seconds, source_probe.duration)
    subtitle_text = build_srt(narration, narration_seconds, audio_path)
    subtitle_path.write_text(subtitle_text, encoding="utf-8-sig")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video), "-i", str(audio_path), "-i", str(subtitle_path),
        "-map", "0:v:0", "-map", "1:a:0", "-map", "2:s:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-af", "apad",
        "-c:s", "mov_text", "-metadata:s:s:0", "language=zho",
        "-t", f"{source_probe.duration:.3f}",
        "-movflags", "+faststart", str(output),
    ]
    result = subprocess.run(command, capture_output=True, check=False, timeout=600)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size < 10_000:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"配音字幕封装失败：{error or '输出无效'}")
    probe = probe_media(output, ffprobe)
    if not probe.has_audio:
        raise RuntimeError("封装完成但没有音轨")
    if abs(probe.duration - source_probe.duration) > 0.2:
        raise RuntimeError(f"有声视频被截断：{probe.duration:.2f} / {source_probe.duration:.2f} 秒")
    expected_cues = len(split_subtitle_cues(narration))
    actual_cues = subtitle_cue_count(output, ffprobe)
    if actual_cues != expected_cues:
        raise RuntimeError(f"字幕数量不符：{actual_cues} / {expected_cues}")
    return NarratedResult(str(output), output.stat().st_size, probe.duration,
                          narration_seconds, actual_cues, True)
