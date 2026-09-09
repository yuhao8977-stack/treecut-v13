"""Offline SenseVoice transcription with an explicit coarse chunk timeline."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import os
import re
import subprocess
import shutil
import uuid
import wave


CONTROL_TOKEN = re.compile(r"<\|[^|>]+\|>")
EMOTIONS = {"HAPPY", "SAD", "ANGRY", "NEUTRAL", "FEARFUL", "DISGUSTED", "SURPRISED"}
EVENTS = {"bgm", "applause", "laughter", "cry", "cough", "sneeze"}
DOMAIN_CORRECTIONS = {"倒台": "岛台", "导台": "岛台", "打台": "岛台"}


def normalize_domain_terms(text: str) -> tuple[str, tuple[dict, ...]]:
    corrected = text
    changes = []
    for wrong, right in DOMAIN_CORRECTIONS.items():
        count = corrected.count(wrong)
        if count:
            corrected = corrected.replace(wrong, right)
            changes.append({"from": wrong, "to": right, "count": count})
    return corrected, tuple(changes)


@dataclass(frozen=True)
class SpeechSegment:
    start: float
    end: float
    text: str
    emotion: str
    events: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class SenseVoiceTranscriber:
    def __init__(self, model_dir: Path, ffmpeg: Path, cache_root: Path):
        if not (model_dir / "model.pt").is_file():
            raise FileNotFoundError(f"SenseVoice 模型不完整：{model_dir}")
        if not ffmpeg.is_file():
            raise FileNotFoundError(ffmpeg)
        tool_dir = str(ffmpeg.parent)
        path_parts = os.environ.get("PATH", "").split(os.pathsep)
        if tool_dir.lower() not in {part.lower() for part in path_parts}:
            os.environ["PATH"] = tool_dir + os.pathsep + os.environ.get("PATH", "")
        from funasr import AutoModel

        self.ffmpeg = ffmpeg
        self.cache_root = cache_root
        self.model = AutoModel(
            model=str(model_dir), vad_model=None, device="cpu", disable_update=True,
        )

    def _prepare_chunks(self, video: Path, media_id: int,
                        chunk_seconds: int) -> tuple[Path, list[Path]]:
        media_root = self.cache_root / str(media_id)
        media_root.mkdir(parents=True, exist_ok=True)
        attempt = media_root / f"attempt_{uuid.uuid4().hex}"
        attempt.mkdir(parents=False, exist_ok=False)
        pattern = attempt / "chunk_%03d.wav"
        command = [
            str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            "-f", "segment", "-segment_time", str(chunk_seconds), "-reset_timestamps", "1", str(pattern),
        ]
        result = subprocess.run(command, capture_output=True, check=False, timeout=180)
        chunks = sorted(attempt.glob("chunk_*.wav"))
        if result.returncode != 0 or not chunks:
            error = result.stderr.decode("utf-8", errors="replace").strip()
            self._cleanup_attempt(attempt, remove_legacy=False)
            raise RuntimeError(f"音频分段失败：{error or '没有生成音频'}")
        return attempt, chunks

    def _cleanup_attempt(self, attempt: Path, remove_legacy: bool = True) -> None:
        media_root = attempt.parent
        expected_root = self.cache_root / media_root.name
        if (media_root != expected_root or attempt.parent != media_root
                or not attempt.name.startswith("attempt_")):
            raise RuntimeError(f"拒绝清理非 SenseVoice 尝试目录：{attempt}")
        if attempt.is_dir() and not attempt.is_symlink():
            shutil.rmtree(attempt)
        if remove_legacy:
            for legacy in media_root.glob("chunk_*.wav"):
                if legacy.is_file() and not legacy.is_symlink() and legacy.parent == media_root:
                    legacy.unlink()
        try:
            media_root.rmdir()
        except OSError:
            pass

    @staticmethod
    def _duration(path: Path) -> float:
        with wave.open(str(path), "rb") as audio:
            return audio.getnframes() / audio.getframerate()

    @staticmethod
    def _parse(raw: str) -> tuple[str, str, tuple[str, ...]]:
        tokens = CONTROL_TOKEN.findall(raw)
        emotion = next((token[2:-2].lower() for token in tokens if token[2:-2].upper() in EMOTIONS), "neutral")
        events = tuple(sorted({token[2:-2].lower() for token in tokens if token[2:-2].lower() in EVENTS}))
        text = re.sub(r"\s+", " ", CONTROL_TOKEN.sub("", raw)).strip()
        return text, emotion, events

    @staticmethod
    def _meaningful_text(text: str) -> bool:
        characters = re.findall(r"[A-Za-z0-9\u3400-\u9fff]", text)
        return len(characters) >= 2

    def transcribe(self, video: Path, media_id: int, chunk_seconds: int = 20) -> dict:
        if chunk_seconds < 5 or chunk_seconds > 60:
            raise ValueError("语音分段必须在 5–60 秒之间")
        attempt, chunks = self._prepare_chunks(video, media_id, chunk_seconds)
        segments = []
        corrections = []
        cursor = 0.0
        try:
            for chunk in chunks:
                duration = self._duration(chunk)
                generated = self.model.generate(
                    input=str(chunk), cache={}, language="auto", use_itn=True,
                    batch_size_s=60, merge_vad=False,
                )
                if not generated or not isinstance(generated, list):
                    raise RuntimeError(f"SenseVoice 返回空结果：{chunk.name}")
                text, emotion, events = self._parse(str(generated[0].get("text", "")))
                if not self._meaningful_text(text):
                    text = ""
                text, segment_corrections = normalize_domain_terms(text)
                corrections.extend(segment_corrections)
                segments.append(SpeechSegment(round(cursor, 3), round(cursor + duration, 3), text, emotion, events))
                cursor += duration
        finally:
            self._cleanup_attempt(attempt)
        transcript = " ".join(item.text for item in segments if item.text).strip()
        return {
            "model": "sensevoice-small",
            "timeline_precision": "fixed_audio_chunks",
            "chunk_seconds": chunk_seconds,
            "transcript": transcript,
            "has_speech": self._meaningful_text(transcript),
            "segments": [item.to_dict() for item in segments],
            "normalization": "treecut_domain_terms_v1",
            "corrections": corrections,
        }
