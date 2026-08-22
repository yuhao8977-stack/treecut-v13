"""P2.5: Worker25 — per-stage analysis worker running inside a pool process.

旁路设计：复用现有引擎类（SceneDetector / KeyframeExtractor / WhisperEngine /
OcrEngine）与 SegmentStore / ProcessingState 的写入方法，但任务的领取/完成
走 TaskStore 原子协议。不修改 p2_worker.py 任何行为。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from treecut.asr.engine import WhisperEngine
from treecut.keyframes.extractor import KeyframeExtractor
from treecut.library.processing_state import ProcessingState
from treecut.library.segments import SegmentStore
from treecut.library.task_store import TaskStore
from treecut.ocr.engine import OcrEngine
from treecut.platform.paths import RuntimePaths
from treecut.scenes.detector import SceneDetector

PIPELINE_VERSION = "p2.5-v1"


class Worker25:
    """一个阶段的执行者：scene / keyframe / asr / ocr。

    worker_id 标识本 Worker；task_type 与 stages 决定它领取哪类任务。
    每个阶段执行前做幂等护栏（should_process / PROCESSING 占用检查），
    执行后写结果表 → 更新 asset_processing_state → 完成任务。
    """

    def __init__(self, worker_id: str, task_type: str, stages: list[str],
                 db_path: str | Path | None = None, log_path: str | Path | None = None,
                 asr_model: str = "small", asr_device: str | None = "auto"):
        self.worker_id = worker_id
        self.task_type = task_type
        self.stages = stages
        self.asr_device = asr_device or "auto"
        self.paths = RuntimePaths.discover()
        self.store = TaskStore(db_path or (self.paths.databases / "materials.db"))
        self.ps = ProcessingState()
        self.segments_store = SegmentStore()
        self.scene_detector = SceneDetector()
        self.keyframe_extractor = KeyframeExtractor(paths=self.paths)
        self.asr_engine = WhisperEngine(model_size=asr_model, device=self.asr_device)
        self.ocr_engine = OcrEngine()
        self.logger = logging.getLogger(f"treecut.worker.{worker_id}")
        self._setup_logging(log_path)

    def _setup_logging(self, log_path: str | Path | None) -> None:
        if not log_path:
            log_path = self.paths.logs / f"worker_{self.worker_id}.log"
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(handler)
        self.logger.propagate = False

    def _log(self, task_id: str, asset_id: str, stage: str, result: str,
             seconds: float, detail: str = "") -> None:
        extra = f" | {detail}" if detail else ""
        self.logger.info(
            "%s | task=%s | asset=%s | stage=%s | result=%s | 耗时=%.2fs%s",
            self.worker_id, task_id, asset_id, stage, result, seconds, extra,
        )

    # ------------------------------------------------------------------
    # 阶段执行
    # ------------------------------------------------------------------

    def _run_scene(self, asset_id: str, video_path: str) -> bool:
        result = self.scene_detector.detect(video_path)
        existing = {s["scene_no"]: s for s in self.segments_store.list_segments(asset_id)}
        segs = []
        for s in result.segments:
            seg = dict(s)
            old = existing.get(s["scene_no"])
            if old:
                seg["segment_id"] = old["segment_id"]
            segs.append(seg)
        self.segments_store.save_segments(
            asset_id, segs, algorithm_version=result.algorithm_version)
        self.ps.mark_done(asset_id, "scene", reason="P2.5 scene 完成",
                          pipeline_version=PIPELINE_VERSION,
                          algorithm_version=result.algorithm_version,
                          result_count=len(segs))
        return True

    def _run_keyframe(self, asset_id: str, video_path: str) -> bool:
        segments = self.segments_store.list_segments(asset_id)
        if not segments:
            self.ps.mark_skipped(asset_id, "keyframe", reason="无 segments，跳过关键帧")
            return True
        result = self.keyframe_extractor.extract(video_path, asset_id, segments)
        frames = [{
            "frame_id": f"{asset_id}_{f['timestamp_ms']}",
            "segment_id": f["segment_id"],
            "timestamp_ms": f["timestamp_ms"],
            "image_path": f["image_path"],
            "sharpness": f["sharpness"],
            "brightness": f["brightness"],
            "selected": f["selected"],
        } for f in result.frames]
        self.segments_store.save_keyframes(asset_id, frames)
        self.ps.mark_done(asset_id, "keyframe", reason="P2.5 keyframe 完成",
                          pipeline_version=PIPELINE_VERSION,
                          result_count=len(frames))
        return True

    def _run_asr(self, asset_id: str, video_path: str) -> bool:
        result = self.asr_engine.transcribe(video_path)
        for seg in result.segments:
            self.segments_store.save_transcript(asset_id, {
                "segment_id": None,
                "start_ms": seg["start_ms"],
                "end_ms": seg["end_ms"],
                "text_raw": seg["text_raw"],
                "text_corrected": seg["text_corrected"],
                "language": result.language,
                "confidence": seg["confidence"],
                "model_name": result.model_name,
                "model_version": result.model_version,
            })
        self.ps.mark_done(asset_id, "asr", reason="P2.5 ASR 完成",
                          model_name=result.model_name,
                          model_version=result.model_version,
                          pipeline_version=PIPELINE_VERSION,
                          result_count=len(result.segments))
        return True

    def _run_ocr(self, asset_id: str) -> bool:
        frames = self.segments_store.list_keyframes(asset_id)
        if not frames:
            self.ps.mark_skipped(asset_id, "ocr", reason="无关键帧，跳过 OCR")
            return True
        ocr_frames = [{
            "frame_id": f["frame_id"],
            "timestamp_ms": f["timestamp_ms"],
            "image_path": f["image_path"],
        } for f in frames]
        result = self.ocr_engine.analyze_frames(ocr_frames)
        items = [{
            "frame_id": item["frame_id"],
            "frame_timestamp_ms": item["frame_timestamp_ms"],
            "text": item["text"],
            "bbox": item["bbox"],
            "subtitle_flag": item["subtitle_flag"],
            "coverage": item["coverage"],
            "confidence": item["confidence"],
        } for item in result.items]
        self.segments_store.save_ocr(asset_id, items)
        self.ps.mark_done(asset_id, "ocr", reason="P2.5 OCR 完成",
                          model_name=result.model_name,
                          model_version=result.model_version,
                          pipeline_version=PIPELINE_VERSION,
                          result_count=len(items))
        return True

    # ------------------------------------------------------------------
    # 执行一个任务（含幂等护栏）
    # ------------------------------------------------------------------

    def execute(self, task: dict) -> str:
        """执行单个任务，返回 'completed'|'skipped'|'failed'|'occupied'。"""
        task_id = task["task_id"]
        asset_id = task["asset_id"]
        video_path = task["absolute_path"]
        stages = [s for s in (task.get("stages") or "").split(",") if s] or self.stages
        if not stages:
            stages = ["scene", "keyframe", "asr", "ocr"]

        # 幂等护栏：已 DONE/SKIPPED 的任务直接完成
        all_done = True
        for stage in stages:
            decision = self.ps.should_process(
                asset_id, stage, pipeline_version=PIPELINE_VERSION)
            if decision == "SKIP_ALREADY_DONE":
                continue
            all_done = False
            state = self.ps.get_state(asset_id, stage)
            if state and state.status == "PROCESSING":
                # 旧进程（PID 19152）或另一 Worker 持有 → 不抢，标记 occupied
                self.store.skip_task(task_id, f"occupied by another worker: {stage}")
                self._log(task_id, asset_id, stage, "occupied", 0.0,
                          "阶段被其他进程占用")
                return "occupied"
        if all_done:
            self.store.complete_task(task_id)
            self._log(task_id, asset_id, ",".join(stages), "completed", 0.0,
                      "已由其他任务完成，跳过")
            return "completed"

        # 按序执行（依赖链 scene→keyframe；asr/ocr 独立）
        stage_results: dict[str, str] = {}
        for stage in stages:
            started = time.perf_counter()
            try:
                if stage == "scene":
                    ok = self._run_scene(asset_id, video_path)
                elif stage == "keyframe":
                    ok = self._run_keyframe(asset_id, video_path)
                elif stage == "asr":
                    ok = self._run_asr(asset_id, video_path)
                elif stage == "ocr":
                    ok = self._run_ocr(asset_id)
                else:
                    ok = False
                stage_results[stage] = "done" if ok else "failed"
                self._log(task_id, asset_id, stage,
                          "success" if ok else "failed",
                          round(time.perf_counter() - started, 2))
            except Exception as exc:
                stage_results[stage] = "failed"
                self.ps.mark_failed(asset_id, stage, reason=str(exc)[:200],
                                    error_message=str(exc)[:500])
                self._log(task_id, asset_id, stage, "failed",
                          round(time.perf_counter() - started, 2), str(exc)[:200])
                # 阶段失败：任务交还重试（单个失败不阻塞其余阶段，但本任务视为失败）
                self.store.fail_task(task_id, f"{stage}: {exc}", retryable=True)
                return "failed"

        self.store.complete_task(task_id)
        self._log(task_id, asset_id, ",".join(stages), "completed",
                  round(time.perf_counter() - started, 2))
        return "completed"

    # ------------------------------------------------------------------
    # 主循环：持续领取直到无任务
    # ------------------------------------------------------------------

    def run(self, limit: int | None = None) -> dict:
        counts = {"processed": 0, "completed": 0, "failed": 0,
                  "skipped": 0, "occupied": 0}
        started_total = time.perf_counter()
        while True:
            if limit is not None and counts["processed"] >= limit:
                break
            task = self.store.claim_task(
                worker_id=self.worker_id, task_type=self.task_type,
                stages=",".join(self.stages))
            if task is None:
                break
            counts["processed"] += 1
            result = self.execute(task)
            counts[result] = counts.get(result, 0) + 1
        counts["seconds"] = round(time.perf_counter() - started_total, 2)
        counts["worker_id"] = self.worker_id
        counts["task_type"] = self.task_type
        return counts
