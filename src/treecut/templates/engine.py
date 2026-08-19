"""P5: 模板存储 + 槽位候选推荐引擎。

模板版本化（CT01-v1、CT01-v2 并存不覆盖）；每槽位推荐 3-10 候选，
带推荐原因（可解释，非黑盒）。
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.library.assets import AssetsManager
from treecut.library.segments import SegmentStore
from treecut.search.embedding import EmbeddingIndexer

P5_SCHEMA_VERSION = 1

P5_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS content_templates (
    template_id TEXT NOT NULL,
    version TEXT NOT NULL,
    name TEXT NOT NULL,
    content_goal TEXT DEFAULT '',
    user_problem TEXT DEFAULT '',
    min_duration REAL DEFAULT 0,
    max_duration REAL DEFAULT 0,
    slots_json TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at REAL NOT NULL,
    PRIMARY KEY (template_id, version)
);
CREATE TABLE IF NOT EXISTS template_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL,
    template_version TEXT NOT NULL,
    slot_order INTEGER NOT NULL,
    slot_name TEXT NOT NULL,
    min_duration REAL DEFAULT 0,
    max_duration REAL DEFAULT 0,
    required_tags TEXT DEFAULT '',
    preferred_tags TEXT DEFAULT '',
    avoid_tags TEXT DEFAULT '',
    semantic_query TEXT DEFAULT '',
    shot_type TEXT DEFAULT '',
    created_at REAL NOT NULL,
    UNIQUE(template_id, template_version, slot_order)
);
CREATE TABLE IF NOT EXISTS project_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    template_version TEXT NOT NULL,
    slot_order INTEGER NOT NULL,
    segment_id TEXT NOT NULL,
    rank INTEGER DEFAULT 0,
    selection_status TEXT DEFAULT 'candidate',  -- candidate/selected/backup/excluded
    score REAL DEFAULT 0,
    reason TEXT DEFAULT '',
    created_at REAL NOT NULL,
    UNIQUE(project_id, slot_order, segment_id)
);
CREATE INDEX IF NOT EXISTS idx_ps_project ON project_segments(project_id, slot_order);
"""


@dataclass(frozen=True)
class SlotCandidate:
    segment_id: str
    asset_id: str
    score: float
    reason: str
    source_start_ms: int = 0
    duration_ms: int = 0
    thumbnail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class TemplateEngine:
    """模板管理 + 槽位候选推荐。"""

    def __init__(self, assets: AssetsManager | None = None,
                 embedding: EmbeddingIndexer | None = None):
        self.assets = assets or AssetsManager()
        self.store = SegmentStore(assets=self.assets)
        self.embedding = embedding or EmbeddingIndexer()
        self.db_path = self.assets.db_path
        with self._connect() as connection:
            connection.executescript(P5_SCHEMA)
            connection.execute(f"PRAGMA user_version={P5_SCHEMA_VERSION}")

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # ---------------- 模板存取 ----------------

    def register_template(self, template: dict) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO content_templates(template_id,version,name,content_goal,"
                "user_problem,min_duration,max_duration,slots_json,status,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (template["template_id"], template["version"], template["name"],
                 ",".join(template.get("content_goal", [])), template.get("user_problem", ""),
                 template.get("min_duration", 0), template.get("max_duration", 0),
                 json.dumps(template.get("slots", []), ensure_ascii=False),
                 "active", now),
            )
            connection.execute(
                "DELETE FROM template_slots WHERE template_id=? AND template_version=?",
                (template["template_id"], template["version"]),
            )
            for slot in template.get("slots", []):
                connection.execute(
                    "INSERT INTO template_slots(template_id,template_version,slot_order,slot_name,"
                    "min_duration,max_duration,required_tags,preferred_tags,avoid_tags,"
                    "semantic_query,shot_type,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (template["template_id"], template["version"], slot["order"], slot["name"],
                     slot.get("min_duration", 0), slot.get("max_duration", 0),
                     ",".join(slot.get("required_tags", [])),
                     ",".join(slot.get("preferred_tags", [])),
                     ",".join(slot.get("avoid_tags", [])),
                     slot.get("semantic_query", ""), slot.get("shot_type", ""), now),
                )

    def list_registered(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT template_id,version,name FROM content_templates ORDER BY template_id").fetchall()
        return [dict(r) for r in rows]

    # ---------------- 候选推荐 ----------------

    def recommend_slot(self, template_id: str, version: str, slot_order: int,
                       top_k: int = 10) -> list[SlotCandidate]:
        """为模板槽位推荐候选镜头（3-10 个）。"""
        with self._connect() as connection:
            slot = connection.execute(
                "SELECT * FROM template_slots WHERE template_id=? AND template_version=? "
                "AND slot_order=?", (template_id, version, slot_order)
            ).fetchone()
        if slot is None:
            return []
        required = [t for t in (slot["required_tags"] or "").split(",") if t]
        preferred = [t for t in (slot["preferred_tags"] or "").split(",") if t]
        semantic = slot["semantic_query"] or ""

        # 候选池：所有 segment（带 asset 信息）
        candidates: list[dict] = []
        with self.store._connect() as connection:
            rows = connection.execute(
                "SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms, s.duration_ms "
                "FROM segments s JOIN assets a ON a.asset_id=s.asset_id "
                "JOIN media_files m ON m.id=a.media_id "
                "WHERE m.available=1").fetchall()
            # 标签
            labels_map: dict[str, set[str]] = {}
            for r in connection.execute("SELECT asset_id,label FROM labels").fetchall():
                labels_map.setdefault(r["asset_id"], set()).add(r["label"])
            # 重复组
            dup_ids: set[str] = set()
            for r in connection.execute("SELECT asset_ids FROM duplicate_groups").fetchall():
                try:
                    ids = json.loads(r["asset_ids"])
                    if len(ids) > 1:
                        dup_ids.update(ids)
                except Exception:
                    pass
            for r in rows:
                aid = r["asset_id"]
                labels = labels_map.get(aid, set())
                # 硬过滤：required tags 必须命中
                if required and not set(required).issubset(labels):
                    continue
                # 去重惩罚
                dup_penalty = 0.15 if aid in dup_ids else 0.0
                # 标签匹配分
                tag_hits = len(set(preferred) & labels)
                tag_score = min(1.0, tag_hits * 0.5)
                # 语义相似度
                vec_score = 0.0
                if semantic:
                    hits = self.embedding.search(semantic, top_k=20)
                    for h in hits:
                        if h["segment_id"] == r["segment_id"]:
                            vec_score = h["score"]
                            break
                # 质量分（时长合理性）
                dur = r["duration_ms"] or 0
                quality = 0.3
                if slot["min_duration"] and dur >= slot["min_duration"] * 1000:
                    quality += 0.2
                if slot["max_duration"] and dur <= slot["max_duration"] * 1000:
                    quality += 0.1
                score = (vec_score * 0.50 + tag_score * 0.30 + quality * 0.20 - dup_penalty)
                candidates.append({
                    "segment_id": r["segment_id"], "asset_id": aid,
                    "score": round(score, 4), "vec_score": round(vec_score, 3),
                    "tag_score": round(tag_score, 3),
                    "source_start_ms": r["start_ms"], "duration_ms": r["duration_ms"],
                    "reason": self._reason(vec_score, tag_score, required, preferred, labels),
                })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        top = candidates[:top_k]
        return [SlotCandidate(
            segment_id=c["segment_id"], asset_id=c["asset_id"], score=c["score"],
            reason=c["reason"], source_start_ms=c["source_start_ms"],
            duration_ms=c["duration_ms"],
        ) for c in top]

    def _reason(self, vec_score: float, tag_score: float,
                required: list[str], preferred: list[str], labels: set[str]) -> str:
        parts = []
        if vec_score > 0.3:
            parts.append(f"语义相似度 {vec_score:.2f}")
        if tag_score > 0:
            matched = [t for t in preferred if t in labels]
            if matched:
                parts.append(f"标签命中 {','.join(matched[:3])}")
        if required:
            matched_req = [t for t in required if t in labels]
            if matched_req:
                parts.append(f"必备标签 {','.join(matched_req)}")
        return "; ".join(parts) if parts else "综合评分"

    # ---------------- 项目选镜 ----------------

    def save_selection(self, project_id: str, template_id: str, version: str,
                       slot_order: int, segment_id: str, status: str,
                       score: float = 0.0, reason: str = "") -> None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO project_segments(project_id,template_id,template_version,"
                "slot_order,segment_id,rank,selection_status,score,reason,created_at) "
                "VALUES(?,?,?,?,?,0,?,?,?,?)",
                (project_id, template_id, version, slot_order, segment_id,
                 status, score, reason, now),
            )
