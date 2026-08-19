"""Claim catalog jobs, inspect real media, extract real frames, and persist evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import gc
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from treecut.analysis_version import ANALYSIS_PIPELINE_VERSION, ANALYSIS_RESULT_SCHEMA_VERSION
from treecut.analysis_contract import require_complete_analysis
from treecut.library import Catalog
from treecut.library.classification import classify_filename, resolve_business_category
from treecut.media import bundled_ffprobe, probe_media
from treecut.models.policy import select_model_plan
from treecut.models.object_detection import assess_detections, combine_review_evidence
from treecut.models.speech_whisper import WhisperTranscriber
from treecut.models.vision_florence import FlorenceVision, assess_captions, classify_captions
from treecut.models.vision_qwen import QwenVision
from treecut.platform.capabilities import detect_capabilities
from treecut.platform.memory import available_ram_gb
from treecut.platform.paths import RuntimePaths
from treecut.platform.progress import ProgressCallback, no_progress
from treecut.config.settings import load_settings
from treecut.extensions import run_hooks


def caption_frame_sequence(vision, frame_paths: list[Path], use_batch: bool) -> list[str]:
    """Caption every sampled frame; CPU mode releases per-frame temporaries between calls."""
    if use_batch:
        captions = vision.caption_many(frame_paths)
    else:
        captions = []
        for frame_path in frame_paths:
            captions.append(vision.caption(frame_path))
            gc.collect()
    if len(captions) != len(frame_paths) or any(not str(caption).strip() for caption in captions):
        raise RuntimeError(
            f"视觉模型只完成 {len(captions)}/{len(frame_paths)} 张抽样帧，禁止保存部分分析"
        )
    return captions


@dataclass(frozen=True)
class WorkerRun:
    claimed: int = 0
    succeeded: int = 0
    retried: int = 0
    failed: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class AnalysisWorker:
    def __init__(self, catalog: Catalog | None = None, paths: RuntimePaths | None = None):
        self.paths = paths or RuntimePaths.discover()
        self.paths.apply_environment()
        self.catalog = catalog or Catalog(self.paths.databases / "materials.db")
        self.recovered_jobs = self.catalog.recover_interrupted_jobs()
        self.orphan_frame_attempts_removed = self._cleanup_orphan_frame_attempts()
        self.ffprobe = bundled_ffprobe(self.paths.install_root)
        self.ffmpeg = self.paths.install_root / "tools" / "win32" / "ffmpeg.exe"
        if not self.ffmpeg.is_file():
            raise FileNotFoundError(f"缺少抽帧工具：{self.ffmpeg}")
        self.capabilities = detect_capabilities(self.paths)
        self.model_plan = select_model_plan(self.capabilities, load_settings(self.paths).model_mode)
        self._vision = None
        self._vision_name = "unavailable"
        self._vision_fallback = ""
        self._speech = None
        self._object_vision = None

    def _get_object_detector(self):
        if self.model_plan.object_detection != "florence-2-base-od":
            return None
        if isinstance(self._vision, FlorenceVision):
            return self._vision
        if self._object_vision is None:
            self._object_vision = FlorenceVision(self.paths.models / "Florence-2-base")
        return self._object_vision

    def _get_vision(self):
        if self._vision is not None:
            return self._vision
        if self.model_plan.vision == "qwen3-vl-4b":
            try:
                self._vision = QwenVision(self.paths.models / "Qwen3-VL-4B-Instruct-FP8")
                self._vision_name = "qwen3-vl-4b"
                return self._vision
            except Exception as error:
                self._vision_fallback = f"{type(error).__name__}: {error}"
        self._vision = FlorenceVision(self.paths.models / "Florence-2-base")
        self._vision_name = "florence-2-base"
        return self._vision

    def _get_speech(self):
        if self._speech is not None:
            return self._speech
        if self.model_plan.speech == "whisper":
            device = "cuda" if self.capabilities.cuda_available else "cpu"
            self._speech = WhisperTranscriber(self.paths.models / "Whisper-small", device)
        return self._speech

    def _frame_root(self, media_id: int) -> Path:
        return self.paths.cache / "analysis_frames" / str(media_id)

    def _new_frame_attempt(self, media_id: int) -> Path:
        frame_dir = self._frame_root(media_id) / f"attempt_{uuid.uuid4().hex}"
        frame_dir.mkdir(parents=True, exist_ok=True)
        return frame_dir

    def _validate_frame_attempt(self, media_id: int, frame_dir: Path) -> Path:
        root = self._frame_root(media_id).resolve()
        candidate = frame_dir.resolve()
        if candidate.parent != root or not candidate.name.startswith("attempt_"):
            raise ValueError(f"Refusing unsafe frame-cache path: {candidate}")
        return candidate

    def _cleanup_frame_attempt(self, media_id: int, frame_dir: Path) -> None:
        candidate = self._validate_frame_attempt(media_id, frame_dir)
        if not candidate.exists():
            return
        if candidate.is_symlink():
            raise RuntimeError(f"Refusing linked frame-cache directory: {candidate}")
        shutil.rmtree(candidate)
        root = self._frame_root(media_id)
        try:
            if root.is_dir() and not root.is_symlink() and not any(root.iterdir()):
                root.rmdir()
        except OSError:
            pass

    def _cleanup_orphan_frame_attempts(self, min_age_seconds: float = 3600.0) -> int:
        """Remove unreferenced frame attempts, but never one a concurrent worker
        may still be writing (an attempt younger than the safety window)."""
        cache_root = self.paths.cache / "analysis_frames"
        if not cache_root.is_dir() or cache_root.is_symlink():
            return 0
        referenced = self.catalog.referenced_frame_directories()
        now = time.time()
        removed = 0
        for media_root in cache_root.iterdir():
            if not media_root.is_dir() or media_root.is_symlink() or not media_root.name.isdigit():
                continue
            media_id = int(media_root.name)
            for candidate in list(media_root.iterdir()):
                if (not candidate.name.startswith("attempt_") or not candidate.is_dir()
                        or candidate.is_symlink() or str(candidate.resolve()) in referenced):
                    continue
                try:
                    age = max(0.0, now - candidate.stat().st_mtime)
                except OSError:
                    continue
                if age < min_age_seconds:
                    continue
                self._cleanup_frame_attempt(media_id, candidate)
                removed += 1
        return removed

    def _cleanup_superseded_frame_attempts(self, media_id: int, keep: Path) -> int:
        root = self._frame_root(media_id)
        keep = self._validate_frame_attempt(media_id, keep)
        if not root.is_dir() or root.is_symlink():
            return 0
        removed = 0
        for candidate in root.iterdir():
            if candidate == keep:
                continue
            if (candidate.is_file() and not candidate.is_symlink()
                    and candidate.name.startswith("frame_") and candidate.suffix.lower() == ".jpg"
                    and candidate.stem[6:].isdigit()):
                candidate.unlink()
                removed += 1
                continue
            if (not candidate.name.startswith("attempt_") or not candidate.is_dir()
                    or candidate.is_symlink()):
                continue
            self._cleanup_frame_attempt(media_id, candidate)
            removed += 1
        return removed

    def _extract_frames(self, path: Path, media_id: int, duration: float,
                        frame_dir: Path) -> list[dict]:
        frame_dir = self._validate_frame_attempt(media_id, frame_dir)
        moments = sorted({max(0.0, min(duration - 0.05, duration * ratio)) for ratio in (0.1, 0.5, 0.9)})
        frames: list[dict] = []
        for index, moment in enumerate(moments, 1):
            output = frame_dir / f"frame_{index:02}.jpg"
            command = [str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
                       "-ss", f"{moment:.3f}", "-i", str(path), "-frames:v", "1",
                       "-q:v", "3", str(output)]
            result = subprocess.run(command, capture_output=True, check=False, timeout=90)
            if result.returncode != 0 or not output.is_file() or output.stat().st_size < 1000:
                error = result.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"抽取第 {index} 帧失败：{error or '没有生成有效图片'}")
            frames.append({"path": str(output), "time": round(moment, 3), "bytes": output.stat().st_size})
        if not frames:
            raise RuntimeError("抽帧结果为空")
        return frames

    def analyze_job(self, job: dict) -> tuple[dict, str, str]:
        media_id = int(job["media_id"])
        frame_dir = self._new_frame_attempt(media_id)
        try:
            return self._analyze_video_job(job, frame_dir)
        except Exception:
            self._cleanup_frame_attempt(media_id, frame_dir)
            raise

    def _analyze_video_job(self, job: dict, frame_dir: Path) -> tuple[dict, str, str]:
        if (not self.capabilities.cuda_available and self.capabilities.ram_gb < 24
                and self._speech is not None):
            self._speech = None
            gc.collect()
        path = Path(job["absolute_path"])
        if job["media_type"] != "video":
            raise NotImplementedError(f"暂不支持的素材类型：{job['media_type']}")
        metadata = probe_media(path, self.ffprobe)
        frames = self._extract_frames(path, int(job["media_id"]), metadata.duration, frame_dir)
        preliminary = classify_filename(path)
        captions, vision_error = [], ""
        vision_attempted = False
        try:
            vision = self._get_vision()
            vision_attempted = True
            all_frame_paths = [Path(item["path"]) for item in frames]
            frame_paths = all_frame_paths
            captions = caption_frame_sequence(
                vision, frame_paths, use_batch=self.capabilities.cuda_available
            )
            del vision
        except Exception as error:
            vision_error = f"{type(error).__name__}: {error}"
        vision_result = classify_captions(captions) if captions else {
            "category": "unclassified", "confidence": 0.0, "matched_words": [],
        }
        vision_result.update({
            "model": self._vision_name, "captions": captions,
            "representative_caption": captions[len(captions) // 2] if captions else "",
            "caption_evidence": [
                {"frame_path": str(frame_path), "time": frames[index]["time"], "caption": caption}
                for index, (frame_path, caption) in enumerate(zip(frame_paths, captions))
            ] if captions else [],
            "frame_strategy": "batched_all_samples" if self.capabilities.cuda_available else "sequential_all_samples",
            "risk": assess_captions(captions), "error": vision_error,
            "fallback_reason": self._vision_fallback,
        })
        object_result = {"model": self.model_plan.object_detection, "detections": [], "error": ""}
        object_attempted = object_completed = False
        try:
            detector = self._get_object_detector()
            if detector is not None:
                object_attempted = True
                object_result["detections"] = detector.detect(Path(frames[len(frames) // 2]["path"]))
                object_completed = True
        except Exception as error:
            object_result["error"] = f"{type(error).__name__}: {error}"
        object_result.update(assess_detections(object_result["detections"]))
        speech_result = {"model": self.model_plan.speech, "transcript": "",
                          "has_speech": False, "segments": [], "error": ""}
        speech_attempted = speech_completed = False
        if metadata.has_audio:
            try:
                if not self.capabilities.cuda_available and self.capabilities.ram_gb < 24:
                    self._vision = None
                    gc.collect()
                speech = self._get_speech()
                if speech is not None:
                    speech_attempted = True
                    speech_result = speech.transcribe(path, int(job["media_id"]))
                    speech_result["error"] = ""
                    speech_completed = True
                else:
                    speech_result["error"] = "当前环境没有可用的本地语音模型"
            except Exception as error:
                speech_result["error"] = f"{type(error).__name__}: {error}"
        resolved = resolve_business_category(preliminary, vision_result, object_result)
        risk = vision_result["risk"]
        selection = combine_review_evidence(risk, object_result)
        result = {
            "schema_version": ANALYSIS_RESULT_SCHEMA_VERSION,
            "pipeline_version": ANALYSIS_PIPELINE_VERSION,
            "media": metadata.to_dict(),
            "frames": frames,
            "preliminary_category": asdict(preliminary),
            "vision": vision_result,
            "objects": object_result,
            "speech": speech_result,
            "selection": selection,
            "category_resolution": resolved,
            "evidence": {"media_probed": True, "frames_extracted": len(frames),
                          "vision_captions": len(captions),
                          "vision_attempted": vision_attempted,
                          "vision_completed": bool(captions) and not bool(vision_error),
                          "speech_expected": metadata.has_audio,
                          "speech_attempted": speech_attempted,
                          "speech_completed": speech_completed,
                          "object_detection_expected": self.model_plan.object_detection == "florence-2-base-od",
                          "object_detection_attempted": object_attempted,
                          "object_detection_completed": object_completed},
        }
        require_complete_analysis(result)
        return result, resolved["category"], resolved["source"]

    def run(self, limit: int = 1, max_attempts: int = 3,
            progress: ProgressCallback = no_progress,
            media_id: int | None = None) -> WorkerRun:
        claimed = succeeded = retried = failed = 0
        for _ in range(max(0, limit)):
            if available_ram_gb() < 6.0:
                progress(f"可用内存不足（{available_ram_gb():.1f}GB < 6GB），"
                         "暂停分析以避免崩溃；请关闭其他程序后重试。")
                break
            cache_path = getattr(getattr(self, "paths", None), "cache", None)
            if cache_path is not None:
                try:
                    free_gb = shutil.disk_usage(cache_path).free / 2**30
                except OSError:
                    free_gb = 0.0
                if free_gb < 1.0:
                    progress(f"缓存盘剩余空间不足（{free_gb:.1f}GB < 1GB），暂停分析。")
                    break
            job = self.catalog.claim_job(media_id)
            if job is None:
                break
            media_id = None
            claimed += 1
            progress(f"正在分析第 {claimed}/{limit} 个素材：{Path(job['absolute_path']).name}")
            result = None
            try:
                result, category, source = self.analyze_job(job)
                self.catalog.complete_job(job["id"], result, category, source)
                run_hooks("post_analysis", result)
                current_frame_dir = Path(result["frames"][0]["path"]).parent
                succeeded += 1
                try:
                    self._cleanup_superseded_frame_attempts(int(job["media_id"]), current_frame_dir)
                except Exception as cleanup_error:
                    progress(f"旧抽帧缓存暂未清理：{cleanup_error}")
                progress(f"素材分析完成：{Path(job['absolute_path']).name}")
            except Exception as exc:
                if result:
                    frames = result.get("frames") or []
                    if frames:
                        self._cleanup_frame_attempt(
                            int(job["media_id"]), Path(frames[0]["path"]).parent
                        )
                    result = None
                state = self.catalog.fail_job(job["id"], f"{type(exc).__name__}: {exc}", max_attempts)
                if state == "failed":
                    failed += 1
                else:
                    retried += 1
                progress(f"素材分析失败：{Path(job['absolute_path']).name}；{exc}")
        return WorkerRun(claimed, succeeded, retried, failed)
