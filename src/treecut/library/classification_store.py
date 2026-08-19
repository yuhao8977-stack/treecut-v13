"""P3: 分类与标签数据层 — labels / duplicate_groups / asset_types。

- labels: TC_CONTENT_TAGS（multi-label + confidence + source(rule/model/human) + human_override）
- duplicate_groups: 精确/近重复分组（只标记不删除）
- asset_type: RAW / FINISHED / SEMI_FINISHED / UNKNOWN（规则打分）
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from treecut.library.assets import AssetsManager
from treecut.library.segments import SegmentStore

P3_SCHEMA_VERSION = 1

P3_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    segment_id TEXT,
    category TEXT NOT NULL,
    label TEXT NOT NULL,
    confidence REAL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'model',   -- rule/model/human
    model_name TEXT DEFAULT '',
    model_version TEXT DEFAULT '',
    human_override INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_labels_asset ON labels(asset_id);
CREATE INDEX IF NOT EXISTS idx_labels_tag ON labels(label);
CREATE UNIQUE INDEX IF NOT EXISTS idx_labels_unique ON labels(asset_id, segment_id, label, source);

CREATE TABLE IF NOT EXISTS duplicate_groups (
    group_id TEXT PRIMARY KEY,
    asset_ids TEXT NOT NULL,               -- JSON array
    duplicate_type TEXT NOT NULL,          -- exact/near/hash
    similarity REAL DEFAULT 0,
    status TEXT DEFAULT 'review',          -- review/high/low
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dup_asset ON duplicate_groups(asset_ids);

CREATE TABLE IF NOT EXISTS asset_types (
    asset_id TEXT PRIMARY KEY REFERENCES assets(asset_id) ON DELETE CASCADE,
    asset_type TEXT NOT NULL DEFAULT 'UNKNOWN',  -- RAW/FINISHED/SEMI_FINISHED/UNKNOWN
    confidence REAL DEFAULT 0,
    reason_codes TEXT DEFAULT '',
    model_version TEXT DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""


class ClassificationStore:
    """P3 分类/标签/重复结果存储。"""

    def __init__(self, assets: AssetsManager | None = None):
        self.assets = assets or AssetsManager()
        self.db_path = self.assets.db_path
        with self._connect() as connection:
            connection.executescript(P3_SCHEMA)
            connection.execute(f"PRAGMA user_version={P3_SCHEMA_VERSION}")

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # ---------------- labels ----------------

    def save_labels(self, asset_id: str, labels: list[dict]) -> int:
        """保存标签（human 标签不覆盖；同 asset+segment+label+source 幂等）。"""
        now = time.time()
        with self._connect() as connection:
            for item in labels:
                category = item.get("category", "")
                label = item.get("label", "")
                if not label:
                    continue
                source = item.get("source", "model")
                seg_id = item.get("segment_id")
                existing = connection.execute(
                    "SELECT id, human_override FROM labels "
                    "WHERE asset_id=? AND segment_id IS ? AND label=? AND source=?",
                    (asset_id, seg_id, label, "human"),
                ).fetchone()
                if existing and source != "human":
                    # 人工标签优先，模型不覆盖
                    continue
                connection.execute(
                    "INSERT INTO labels(asset_id,segment_id,category,label,confidence,source,"
                    "model_name,model_version,human_override,created_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(asset_id,segment_id,label,source) DO UPDATE SET "
                    "confidence=excluded.confidence,category=excluded.category,created_at=excluded.created_at",
                    (asset_id, seg_id, category, label, float(item.get("confidence", 0)),
                     source, item.get("model_name", ""), item.get("model_version", ""),
                     int(item.get("human_override", 0)), now),
                )
        return len(labels)

    def save_human_label(self, asset_id: str, label: str, category: str = "",
                         segment_id: str | None = None, confidence: float = 1.0) -> None:
        """人工添加/修正标签（human_override=1，永远优先）。"""
        self.save_labels(asset_id, [{
            "category": category, "label": label, "confidence": confidence,
            "source": "human", "human_override": 1, "segment_id": segment_id,
        }])

    def list_labels(self, asset_id: str | None = None, label: str | None = None) -> list[dict]:
        where = []
        params: list = []
        if asset_id:
            where.append("asset_id=?")
            params.append(asset_id)
        if label:
            where.append("label=?")
            params.append(label)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM labels {clause} ORDER BY asset_id, confidence DESC", params
            ).fetchall()
        return [dict(row) for row in rows]

    def labels_for_asset(self, asset_id: str) -> list[dict]:
        return self.list_labels(asset_id=asset_id)

    # ---------------- asset_type ----------------

    def save_asset_type(self, asset_id: str, asset_type: str, confidence: float,
                        reason_codes: str = "", model_version: str = "rule-v1") -> None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO asset_types(asset_id,asset_type,confidence,reason_codes,"
                "model_version,created_at,updated_at) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(asset_id) DO UPDATE SET asset_type=excluded.asset_type,"
                "confidence=excluded.confidence,reason_codes=excluded.reason_codes,"
                "model_version=excluded.model_version,updated_at=excluded.updated_at",
                (asset_id, asset_type, confidence, reason_codes, model_version, now, now),
            )

    def get_asset_type(self, asset_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM asset_types WHERE asset_id=?", (asset_id,)
            ).fetchone()
        return dict(row) if row else None

    # ---------------- duplicate ----------------

    def save_duplicate_group(self, group_id: str, asset_ids: list[str],
                             duplicate_type: str, similarity: float,
                             status: str = "review") -> None:
        import json
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO duplicate_groups(group_id,asset_ids,duplicate_type,similarity,"
                "status,created_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(group_id) DO UPDATE SET asset_ids=excluded.asset_ids,"
                "duplicate_type=excluded.duplicate_type,similarity=excluded.similarity,"
                "status=excluded.status",
                (group_id, json.dumps(asset_ids, ensure_ascii=False),
                 duplicate_type, similarity, status, now),
            )

    def list_duplicate_groups(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM duplicate_groups ORDER BY similarity DESC").fetchall()
        result = []
        import json
        for row in rows:
            item = dict(row)
            try:
                item["asset_ids"] = json.loads(item["asset_ids"])
            except Exception:
                pass
            result.append(item)
        return result
