"""P2: Unified analysis worker — scene / keyframe / asr / ocr.

生命周期（P1.1 强制，禁止绕过）:
  should_process() → claim(PROCESSING) → run → save → DONE/FAILED/SKIPPED
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.asr.engine import WhisperEngine
from treecut.keyframes.extractor import KeyframeExtractor
from treecut.library.assets import AssetsManager
from treecut.library.processing_state import ProcessingState, STAGES
from treecut.library.segments import SegmentStore
from treecut.ocr.engine import OcrEngine
from treecut.platform.paths import RuntimePaths
from treecut.scenes.detector import SceneDetector

PIPELINE_VERSION = "P2.1"


@dataclass(frozen=True)
class P2RunResult:
    scanned: int = 0
    scene_done: int = 0
    keyframe_done: int = 0
    asr_done: int = 0
    ocr_done: int = 0
    failed: int = 0
    skipped: int = 0
    remaining: int = 0
    errors: tuple[str, ...] = ()
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class P2Worker:
    """按依赖顺序处理 scene → keyframe → asr → ocr（每阶段幂等）。"""

    def __init__(self, paths: RuntimePaths | None = None,
                 assets: AssetsManager | None = None,
                 pipeline_version: str = PIPELINE_VERSION,
                 asr_model: str = "small", max_asr_segments: int = 2000,
                 include_asr: bool = True, include_ocr: bool = True):
        self.paths = paths or RuntimePaths.discover()
        self.assets = assets or AssetsManager()
        self.state = ProcessingState(assets=self.assets)
        self.store = SegmentStore(assets=self.assets)
        self.pipeline_version = pipeline_version
        self.scene_detector = SceneDetector()
        self.keyframe_extractor = KeyframeExtractor(paths=self.paths)
        self.asr_engine = WhisperEngine(model_size=asr_model)
        self.ocr_engine = OcrEngine()
        self.max_asr_segments = max_asr_segments
        self.include_asr = include_asr
        self.include_ocr = include_ocr
        self.assets.ensure_all_video_assets()
        self.state.ensure_asset_stages_all()

    # ---------------- 任务选取（待处理 asset） ----------------

    def _pending_assets(self, limit: int) -> list[dict]:
        """选择 scene/keyframe/asr/ocr 任一阶段未 DONE 的 asset。"""
        with self.state._connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT a.asset_id, s.path source_path, m.relative_path, "
                "m.media_type, m.available, s.online "
                "FROM assets a "
                "JOIN media_files m ON m.id=a.media_id "
                "JOIN sources s ON s.id=m.source_id "
                "WHERE m.media_type='video' AND m.available=1 AND s.online=1 "
                "AND EXISTS (SELECT 1 FROM asset_processing_state ps "
                "            WHERE ps.asset_id=a.asset_id "
                "            AND ps.stage IN ('scene','keyframe','asr','ocr') "
                "            AND ps.status NOT IN ('DONE','SKIPPED')) "
                "LIMIT ?", (limit,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["absolute_path"] = str(Path(item["source_path"]) / item["relative_path"])
            result.append(item)
        return result

    def _claim(self, asset_id: str, stage: str) -> bool:
        """事务领取：仅当阶段可处理且未并发占用。返回是否领取成功。"""
        decision = self.state.should_process(asset_id, stage, pipeline_version=self.pipeline_version)
        if decision == "SKIP_ALREADY_DONE":
            return False
        cur = self.state.get_state(asset_id, stage)
        if cur and cur.status == "PROCESSING":
            return False
        self.state.mark_processing(asset_id, stage, reason="P2 worker 领取")
        return True

    # ---------------- 阶段处理 ----------------

    def _run_scene(self, asset_id: str, video_path: str) -> bool:
        if not self._claim(asset_id, "scene"):
            return False
        try:
            result = self.scene_detector.detect(video_path)
            # 保存 segments（先查已有，保留 segment_id 稳定）
            existing = {s["scene_no"]: s for s in self.store.list_segments(asset_id)}
            segs = []
            for s in result.segments:
                seg = dict(s)
                old = existing.get(s["scene_no"])
                if old:
                    seg["segment_id"] = old["segment_id"]
                segs.append(seg)
            self.store.save_segments(asset_id, segs,
                                     algorithm_version=result.algorithm_version)
            self.state.mark_done(asset_id, "scene", reason="场景切分完成",
                                 pipeline_version=self.pipeline_version,
                                 algorithm_version=result.algorithm_version,
                                 result_count=len(segs))
            return True
        except Exception as exc:
            self.state.mark_failed(asset_id, "scene", reason=str(exc)[:200],
                                   error_message=str(exc)[:500])
            return False

    def _run_keyframe(self, asset_id: str, video_path: str) -> bool:
        if not self._claim(asset_id, "keyframe"):
            return False
        try:
            segments = self.store.list_segments(asset_id)
            if not segments:
                self.state.mark_skipped(asset_id, "keyframe",
                                        reason="无 segments，跳过关键帧")
                return True
            result = self.keyframe_extractor.extract(video_path, asset_id, segments)
            frames = []
            for f in result.frames:
                frames.append({
                    "frame_id": f"{asset_id}_{f['timestamp_ms']}",
                    "segment_id": f["segment_id"],
                    "timestamp_ms": f["timestamp_ms"],
                    "image_path": f["image_path"],
                    "sharpness": f["sharpness"],
                    "brightness": f["brightness"],
                    "selected": f["selected"],
                })
            self.store.save_keyframes(asset_id, frames)
            self.state.mark_done(asset_id, "keyframe", reason="关键帧提取完成",
                                 pipeline_version=self.pipeline_version,
                                 result_count=len(frames))
            return True
        except Exception as exc:
            self.state.mark_failed(asset_id, "keyframe", reason=str(exc)[:200],
                                   error_message=str(exc)[:500])
            return False

    def _run_asr(self, asset_id: str, video_path: str) -> bool:
        if not self._claim(asset_id, "asr"):
            return False
        try:
            result = self.asr_engine.transcribe(video_path)
            for seg in result.segments:
                self.store.save_transcript(asset_id, {
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
            self.state.mark_done(asset_id, "asr", reason="语音转写完成",
                                 model_name=result.model_name,
                                 model_version=result.model_version,
                                 pipeline_version=self.pipeline_version,
                                 result_count=len(result.segments))
            return True
        except Exception as exc:
            self.state.mark_failed(asset_id, "asr", reason=str(exc)[:200],
                                   error_message=str(exc)[:500])
            return False

    def _run_ocr(self, asset_id: str) -> bool:
        if not self._claim(asset_id, "ocr"):
            return False
        try:
            frames = self.store.list_keyframes(asset_id)
            if not frames:
                self.state.mark_skipped(asset_id, "ocr",
                                        reason="无关键帧，跳过 OCR")
                return True
            # 只用关键帧（禁逐帧 OCR）
            ocr_frames = [{
                "frame_id": f["frame_id"],
                "timestamp_ms": f["timestamp_ms"],
                "image_path": f["image_path"],
            } for f in frames]
            result = self.ocr_engine.analyze_frames(ocr_frames)
            items = []
            for item in result.items:
                items.append({
                    "frame_id": item["frame_id"],
                    "frame_timestamp_ms": item["frame_timestamp_ms"],
                    "text": item["text"],
                    "bbox": item["bbox"],
                    "subtitle_flag": item["subtitle_flag"],
                    "coverage": item["coverage"],
                    "confidence": item["confidence"],
                })
            self.store.save_ocr(asset_id, items)
            self.state.mark_done(asset_id, "ocr", reason="OCR 完成",
                                 model_name=result.model_name,
                                 model_version=result.model_version,
                                 pipeline_version=self.pipeline_version,
                                 result_count=len(items))
            return True
        except Exception as exc:
            self.state.mark_failed(asset_id, "ocr", reason=str(exc)[:200],
                                   error_message=str(exc)[:500])
            return False

    # ---------------- 主入口 ----------------

    def run(self, limit: int = 10) -> P2RunResult:
        started = time.perf_counter()
        counts = {"scanned": 0, "scene": 0, "keyframe": 0, "asr": 0,
                  "ocr": 0, "failed": 0, "skipped": 0}
        errors: list[str] = []

        pending = self._pending_assets(limit)
        counts["scanned"] = len(pending)
        for item in pending:
            asset_id = item["asset_id"]
            video_path = item["absolute_path"]
            try:
                if self._run_scene(asset_id, video_path):
                    counts["scene"] += 1
                if self._run_keyframe(asset_id, video_path):
                    counts["keyframe"] += 1
                if self.include_asr and self._run_asr(asset_id, video_path):
                    counts["asr"] += 1
                if self.include_ocr and self._run_ocr(asset_id):
                    counts["ocr"] += 1
            except Exception as exc:
                counts["failed"] += 1
                if len(errors) < 20:
                    errors.append(f"{Path(video_path).name}: {exc}")

        return P2RunResult(
            scanned=counts["scanned"],
            scene_done=counts["scene"],
            keyframe_done=counts["keyframe"],
            asr_done=counts["asr"],
            ocr_done=counts["ocr"],
            failed=counts["failed"],
            skipped=counts["skipped"],
            remaining=len(self._pending_assets(1000)),
            errors=tuple(errors),
            seconds=round(time.perf_counter() - started, 3),
        )
