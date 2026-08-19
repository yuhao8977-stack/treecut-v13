"""P3: 分类/标签/重复识别 worker（接入生命周期）。"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.classify.asset_type import classify_asset_type
from treecut.content_tags import ALL_TAGS, TC_CONTENT_TAGS, category_of
from treecut.keyframes.extractor import KeyframeExtractor
from treecut.library.assets import AssetsManager
from treecut.library.classification_store import ClassificationStore
from treecut.library.processing_state import ProcessingState
from treecut.library.segments import SegmentStore
from treecut.ocr.engine import OcrEngine
from treecut.platform.paths import RuntimePaths

PIPELINE_VERSION = "P3.1"


@dataclass(frozen=True)
class P3RunResult:
    scanned: int = 0
    type_done: int = 0
    duplicate_done: int = 0
    labels_done: int = 0
    failed: int = 0
    remaining: int = 0
    errors: tuple[str, ...] = ()
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class P3Worker:
    """asset_type(duplicate) → labels，全部幂等。"""

    def __init__(self, paths: RuntimePaths | None = None,
                 assets: AssetsManager | None = None,
                 pipeline_version: str = PIPELINE_VERSION):
        self.paths = paths or RuntimePaths.discover()
        self.assets = assets or AssetsManager()
        self.state = ProcessingState(assets=self.assets)
        self.store = SegmentStore(assets=self.assets)
        self.cls = ClassificationStore(assets=self.assets)
        self.pipeline_version = pipeline_version
        self.ocr_engine = OcrEngine()
        self.assets.ensure_all_video_assets()
        self.state.ensure_asset_stages_all()

    def _pending_assets(self, limit: int) -> list[dict]:
        with self.state._connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT a.asset_id, a.fingerprint_quick, a.duration, "
                "s.path source_path, m.relative_path "
                "FROM assets a JOIN media_files m ON m.id=a.media_id "
                "JOIN sources s ON s.id=m.source_id "
                "WHERE m.media_type='video' AND m.available=1 AND s.online=1 "
                "AND EXISTS (SELECT 1 FROM asset_processing_state ps "
                "            WHERE ps.asset_id=a.asset_id "
                "            AND ps.stage IN ('duplicate','labels') "
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
        decision = self.state.should_process(asset_id, stage, pipeline_version=self.pipeline_version)
        if decision == "SKIP_ALREADY_DONE":
            return False
        cur = self.state.get_state(asset_id, stage)
        if cur and cur.status == "PROCESSING":
            return False
        self.state.mark_processing(asset_id, stage, reason="P3 worker 领取")
        return True

    # ---------------- 成片/原片分类 ----------------

    def _run_type(self, asset_id: str) -> bool:
        if not self._claim(asset_id, "duplicate"):
            return False  # duplicate 阶段承载 asset_type 判定
        try:
            # 特征收集
            segs = self.store.list_segments(asset_id)
            kfs = self.store.list_keyframes(asset_id)
            ocr = self.store.list_ocr(asset_id)
            transcripts = self.store.list_transcripts(asset_id)
            duration = 0.0
            with self.assets._connect() as conn:
                row = conn.execute(
                    "SELECT duration, has_audio FROM assets WHERE asset_id=?", (asset_id,)
                ).fetchone()
                duration = row["duration"] if row and row["duration"] else 0.0

            total_kf = len(kfs)
            subtitle_kf = len({o["frame_id"] for o in ocr if o["subtitle_flag"]})
            hard_sub_ratio = subtitle_kf / max(1, total_kf)
            has_speech = len(transcripts) > 0
            has_music = False  # P3 不分析音频分类，保守置 False（BGM 检测 P3.1 增强）
            asset_type, conf, reasons = classify_asset_type(
                duration_sec=duration or 30.0,
                scene_count=len(segs),
                hard_subtitle_ratio=hard_sub_ratio,
                has_speech=has_speech,
                has_music=has_music,
                text_items=len(ocr),
            )
            self.cls.save_asset_type(asset_id, asset_type, conf, reasons,
                                     model_version=self.pipeline_version)
            self.state.mark_done(asset_id, "duplicate", reason="成片/原片分类完成",
                                 pipeline_version=self.pipeline_version,
                                 result_count=1)
            return True
        except Exception as exc:
            self.state.mark_failed(asset_id, "duplicate", reason=str(exc)[:200],
                                   error_message=str(exc)[:500])
            return False

    # ---------------- 重复识别（精确 hash 分组） ----------------

    def _run_duplicate(self) -> int:
        """全库级精确重复识别：fingerprint_full 相同的 asset 归组。"""
        with self.assets._connect() as connection:
            rows = connection.execute(
                "SELECT fingerprint_full, asset_id FROM assets "
                "WHERE fingerprint_full<>'' AND fingerprint_full IS NOT NULL "
                "ORDER BY fingerprint_full").fetchall()
        groups: dict[str, list[str]] = {}
        for row in rows:
            fp = row["fingerprint_full"]
            if len(fp) < 16:  # 尚未计算完整 hash 的跳过
                continue
            groups.setdefault(fp, []).append(row["asset_id"])
        grouped = 0
        for fp, ids in groups.items():
            if len(ids) < 2:
                continue
            self.cls.save_duplicate_group(
                group_id=uuid.uuid5(uuid.NAMESPACE_URL, fp).hex,
                asset_ids=ids, duplicate_type="exact", similarity=1.0,
                status="high" if len(ids) > 2 else "review",
            )
            grouped += 1
        return grouped

    # ---------------- TC_CONTENT_TAGS ----------------

    def _rule_labels(self, asset_id: str, filename: str) -> list[dict]:
        """规则标签：文件名/路径关键词匹配 TC_CONTENT_TAGS。"""
        labels: list[dict] = []
        haystack = filename
        for tag in sorted(ALL_TAGS, key=len, reverse=True):
            if tag in haystack:
                labels.append({
                    "category": category_of(tag) or "",
                    "label": tag,
                    "confidence": 0.8,
                    "source": "rule",
                    "model_name": "filename-rule",
                    "model_version": self.pipeline_version,
                })
        # 路径级：source folder 关键词
        return labels

    def _run_labels(self, asset_id: str, filename: str) -> bool:
        if not self._claim(asset_id, "labels"):
            return False
        try:
            labels = self._rule_labels(asset_id, filename)
            self.cls.save_labels(asset_id, labels)
            self.state.mark_done(asset_id, "labels", reason="TC_CONTENT_TAGS 规则标签",
                                 pipeline_version=self.pipeline_version,
                                 result_count=len(labels))
            return True
        except Exception as exc:
            self.state.mark_failed(asset_id, "labels", reason=str(exc)[:200],
                                   error_message=str(exc)[:500])
            return False

    # ---------------- 主入口 ----------------

    def run(self, limit: int = 10) -> P3RunResult:
        started = time.perf_counter()
        counts = {"scanned": 0, "type": 0, "labels": 0, "failed": 0}
        errors: list[str] = []

        pending = self._pending_assets(limit)
        counts["scanned"] = len(pending)
        for item in pending:
            asset_id = item["asset_id"]
            try:
                if self._run_type(asset_id):
                    counts["type"] += 1
                if self._run_labels(asset_id, item["relative_path"]):
                    counts["labels"] += 1
            except Exception as exc:
                counts["failed"] += 1
                if len(errors) < 20:
                    errors.append(f"{item['relative_path']}: {exc}")

        dup_groups = self._run_duplicate()

        return P3RunResult(
            scanned=counts["scanned"],
            type_done=counts["type"],
            labels_done=counts["labels"],
            duplicate_done=dup_groups,
            failed=counts["failed"],
            remaining=len(self._pending_assets(1000)),
            errors=tuple(errors),
            seconds=round(time.perf_counter() - started, 3),
        )
