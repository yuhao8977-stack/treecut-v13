"""P4: Embedding worker — 为 segment 生成 BGE-M3 向量并构建 FAISS 索引。

生命周期：embedding 阶段。输入 = transcript + OCR + 标签拼接文本。
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.library.assets import AssetsManager
from treecut.library.processing_state import ProcessingState
from treecut.library.segments import SegmentStore
from treecut.search.embedding import EmbeddingIndexer


@dataclass(frozen=True)
class EmbedWorkerResult:
    embedded_assets: int = 0
    segments_indexed: int = 0
    failed: int = 0
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class EmbeddingWorker:
    """为所有已具备文本的 asset 生成 segment embedding + 建 FAISS 索引。"""

    def __init__(self, assets: AssetsManager | None = None,
                 indexer: EmbeddingIndexer | None = None,
                 pipeline_version: str = "P4.1"):
        self.assets = assets or AssetsManager()
        self.store = SegmentStore(assets=self.assets)
        self.state = ProcessingState(assets=self.assets)
        self.indexer = indexer or EmbeddingIndexer()
        self.pipeline_version = pipeline_version

    def run(self, limit: int = 50) -> EmbedWorkerResult:
        started = time.perf_counter()
        embedded = 0
        indexed = 0
        failed = 0

        # 收集待嵌入 asset（embedding 阶段未 DONE 且有 segments）
        with self.state._connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT a.asset_id FROM assets a "
                "JOIN segments s ON s.asset_id=a.asset_id "
                "WHERE NOT EXISTS (SELECT 1 FROM asset_processing_state ps "
                "   WHERE ps.asset_id=a.asset_id AND ps.stage='embedding' "
                "   AND ps.status IN ('DONE','SKIPPED')) "
                "LIMIT ?", (limit,),
            ).fetchall()

        vectors: list[list[float]] = []
        ids: list[str] = []
        done_assets: list[str] = []
        for row in rows:
            aid = row["asset_id"]
            try:
                texts = self._segment_texts(aid)
                seg_ids = self._segment_ids(aid)
                if not seg_ids:
                    continue
                seg_vectors = self.indexer.encode_texts(texts)
                vectors.extend(seg_vectors)
                ids.extend(seg_ids)
                done_assets.append(aid)
            except Exception:
                failed += 1
                continue

        if vectors:
            self.indexer.build_index(vectors, ids, force=True)
            for aid in done_assets:
                self.state.mark_done(aid, "embedding", reason="segment 嵌入完成",
                                     pipeline_version=self.pipeline_version,
                                     result_count=len(ids))
            embedded = len(done_assets)
            indexed = len(ids)

        return EmbedWorkerResult(
            embedded_assets=embedded, segments_indexed=indexed, failed=failed,
            seconds=round(time.perf_counter() - started, 3),
        )

    def _segment_texts(self, asset_id: str) -> list[str]:
        segs = self.store.list_segments(asset_id)
        texts = []
        for seg in segs:
            parts = []
            # transcript for segment (fallback full asset transcript)
            trs = [t for t in self.store.list_transcripts(asset_id)
                   if t.get("segment_id") == seg["segment_id"]]
            if not trs:
                trs = self.store.list_transcripts(asset_id)
            for t in trs:
                txt = (t.get("text_corrected") or t.get("text_raw") or "").strip()
                if txt:
                    parts.append(txt)
            # OCR for keyframes in this segment
            kfs = [k for k in self.store.list_keyframes(asset_id)
                   if k["segment_id"] == seg["segment_id"]]
            ocr = [o for o in self.store.list_ocr(asset_id)]
            for o in ocr:
                if o.get("frame_id") in {k["frame_id"] for k in kfs}:
                    parts.append(o["text"])
            # 拼接成单段文本
            text = " ".join(parts).strip()
            if not text:
                text = f"segment {seg['scene_no']}"
            texts.append(text)
        return texts

    def _segment_ids(self, asset_id: str) -> list[str]:
        return [s["segment_id"] for s in self.store.list_segments(asset_id)]
