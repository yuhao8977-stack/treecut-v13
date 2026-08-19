"""P4: 混合检索引擎 — FTS5 全文 + BGE-M3/FAISS 向量 + 标签加权 + 质量 + 去重惩罚。

流程:
Query → Metadata/Label Filter → FTS5 → FAISS Recall → Tag Match →
Quality Score → Duplicate Penalty → Rerank → Top K
排序: score = semantic*0.50 + tag*0.25 + quality*0.15 + text*0.10 - dup_penalty
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.library.assets import AssetsManager
from treecut.library.processing_state import ProcessingState
from treecut.library.segments import SegmentStore
from treecut.search.embedding import EmbeddingIndexer


@dataclass(frozen=True)
class SearchResult:
    query: str
    hits: tuple[dict, ...] = ()
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return {"query": self.query, "seconds": self.seconds, "hits": self.hits}


class HybridSearch:
    """混合检索（segment 级结果）。"""

    def __init__(self, assets: AssetsManager | None = None,
                 embedding: EmbeddingIndexer | None = None):
        self.assets = assets or AssetsManager()
        self.store = SegmentStore(assets=self.assets)
        self.embedding = embedding or EmbeddingIndexer()
        self._fts_init()

    # ---------------- FTS5 ----------------

    def _fts_init(self) -> None:
        with self.store._connect() as connection:
            connection.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_transcript USING fts5(
                asset_id UNINDEXED, segment_id UNINDEXED, text,
                tokenize='trigram'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_ocr USING fts5(
                asset_id UNINDEXED, frame_id UNINDEXED, text,
                tokenize='trigram'
            );
            """)

    def index_texts(self) -> int:
        """把 transcripts + ocr_text + labels 灌入 FTS（增量幂等：先清后灌）。"""
        with self.store._connect() as connection:
            connection.execute("DELETE FROM fts_transcript")
            connection.execute("DELETE FROM fts_ocr")
            n = 0
            rows = connection.execute(
                "SELECT asset_id, segment_id, text_raw, text_corrected FROM transcripts"
            ).fetchall()
            for r in rows:
                text = (r["text_corrected"] or r["text_raw"] or "").strip()
                if text:
                    connection.execute(
                        "INSERT INTO fts_transcript(asset_id, segment_id, text) VALUES(?,?,?)",
                        (r["asset_id"], r["segment_id"], text))
                    n += 1
            orows = connection.execute(
                "SELECT asset_id, frame_id, text FROM ocr_text").fetchall()
            for r in orows:
                if r["text"]:
                    connection.execute(
                        "INSERT INTO fts_ocr(asset_id, frame_id, text) VALUES(?,?,?)",
                        (r["asset_id"], r["frame_id"], r["text"]))
                    n += 1
            return n

    def _fts_search(self, query: str, limit: int = 30) -> list[dict]:
        q = query.replace('"', ' ').strip()
        if len(q) < 3:
            # trigram 需 ≥3 字符；短查询用 LIKE 兜底
            try:
                with self.store._connect() as connection:
                    rows = connection.execute(
                        "SELECT asset_id, text FROM fts_transcript WHERE text LIKE ? LIMIT ?",
                        (f"%{q}%", limit),
                    ).fetchall()
                    ocr_rows = connection.execute(
                        "SELECT asset_id, text FROM fts_ocr WHERE text LIKE ? LIMIT ?",
                        (f"%{q}%", limit),
                    ).fetchall()
            except Exception:
                return []
            hits: dict[str, dict] = {}
            for r in rows:
                hits.setdefault(r["asset_id"], {"asset_id": r["asset_id"], "text_score": 0.5})
            for r in ocr_rows:
                hits.setdefault(r["asset_id"], {"asset_id": r["asset_id"], "text_score": 0.3})
            return list(hits.values())
        try:
            with self.store._connect() as connection:
                rows = connection.execute(
                    "SELECT asset_id, segment_id, text, rank FROM fts_transcript "
                    "WHERE fts_transcript MATCH ? ORDER BY rank LIMIT ?",
                    (q, limit),
                ).fetchall()
                ocr_rows = connection.execute(
                    "SELECT asset_id, frame_id, text, rank FROM fts_ocr "
                    "WHERE fts_ocr MATCH ? ORDER BY rank LIMIT ?",
                    (q, limit),
                ).fetchall()
        except Exception:
            return []
        hits = {}
        for r in rows:
            key = r["asset_id"]
            hits.setdefault(key, {"asset_id": key, "text_score": 0.5}).setdefault(
                "text_score", 0.5)
        for r in ocr_rows:
            key = r["asset_id"]
            hits.setdefault(key, {"asset_id": key, "text_score": 0.3}).setdefault(
                "text_score", 0.3)
        return list(hits.values())

    # ---------------- 混合检索 ----------------

    def search(self, query: str, top_k: int = 10,
               hard_filters: dict | None = None) -> SearchResult:
        started = time.perf_counter()
        hard_filters = hard_filters or {}
        text_hits = self._fts_search(query, limit=30)
        vec_hits = self.embedding.search(query, top_k=top_k * 3)

        # 汇总候选（asset 级）
        candidates: dict[str, dict] = {}
        for hit in text_hits:
            aid = hit["asset_id"]
            candidates.setdefault(aid, {"asset_id": aid, "text_score": 0.0,
                                        "vec_score": 0.0, "tag_score": 0.0,
                                        "quality_score": 0.0})
            candidates[aid]["text_score"] = max(
                candidates[aid]["text_score"], hit.get("text_score", 0.3))
        for hit in vec_hits:
            aid = self._segment_asset(hit["segment_id"])
            if aid is None:
                continue
            candidates.setdefault(aid, {"asset_id": aid, "text_score": 0.0,
                                        "vec_score": 0.0, "tag_score": 0.0,
                                        "quality_score": 0.0})
            candidates[aid]["vec_score"] = max(
                candidates[aid]["vec_score"], hit["score"])

        # 标签/质量/去重
        results = []
        with self.store._connect() as connection:
            for aid, c in candidates.items():
                if hard_filters:
                    if not self._pass_filters(connection, aid, hard_filters):
                        continue
                c["tag_score"] = self._tag_score(connection, aid, query)
                c["quality_score"] = self._quality_score(connection, aid)
                c["dup_penalty"] = self._dup_penalty(connection, aid)
                final = (c["vec_score"] * 0.50 + c["tag_score"] * 0.25 +
                         c["quality_score"] * 0.15 + c["text_score"] * 0.10 -
                         c["dup_penalty"])
                c["score"] = round(final, 4)
                results.append(c)

        results.sort(key=lambda x: x["score"], reverse=True)
        hits = tuple(results[:top_k])
        return SearchResult(query=query, hits=hits,
                            seconds=round(time.perf_counter() - started, 3))

    def _segment_asset(self, segment_id: str) -> str | None:
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT asset_id FROM segments WHERE segment_id=?", (segment_id,)
            ).fetchone()
        return row["asset_id"] if row else None

    def _pass_filters(self, connection, asset_id: str, filters: dict) -> bool:
        # 支持 asset_type / person 等（当前按 asset_types 表）
        if "asset_type" in filters:
            row = connection.execute(
                "SELECT asset_type FROM asset_types WHERE asset_id=?", (asset_id,)
            ).fetchone()
            if row and filters["asset_type"] not in (row["asset_type"], "UNKNOWN", ""):
                return False
        return True

    def _tag_score(self, connection, asset_id: str, query: str) -> float:
        """标签匹配：query 中的标签词命中加分。"""
        rows = connection.execute(
            "SELECT label FROM labels WHERE asset_id=?", (asset_id,)
        ).fetchall()
        labels = {r["label"] for r in rows}
        if not labels:
            return 0.0
        q_tokens = [t for t in query.replace("，", " ").split() if t]
        hits = sum(1 for t in q_tokens if t in labels)
        return min(1.0, hits * 0.5) if hits else 0.0

    def _quality_score(self, connection, asset_id: str) -> float:
        row = connection.execute(
            "SELECT duration, width, height FROM assets WHERE asset_id=?", (asset_id,)
        ).fetchone()
        if not row:
            return 0.0
        score = 0.3
        if row["width"] and row["width"] >= 1920:
            score += 0.2
        elif row["width"] and row["width"] >= 1280:
            score += 0.1
        if row["duration"] and 5 <= row["duration"] <= 120:
            score += 0.2
        return round(min(1.0, score), 3)

    def _dup_penalty(self, connection, asset_id: str) -> float:
        """重复组惩罚：重复素材降权。"""
        rows = connection.execute(
            "SELECT asset_ids FROM duplicate_groups").fetchall()
        for r in rows:
            import json
            try:
                ids = json.loads(r["asset_ids"])
            except Exception:
                continue
            if asset_id in ids and len(ids) > 1:
                return 0.15
        return 0.0
