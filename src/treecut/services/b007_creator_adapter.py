# -*- coding: utf-8 -*-
"""V0.2 — B007CreatorImportAdapterV1：Creator Sync 结果的幂等入库。

复用 Stage3 已验证的存储模式（published_content_v1 / performance_snapshot_v1），
以 account_id='B007' 区分工作区；纪律：
  - PublishedContent 以 note_id 为 canonical identity（account + note_id 幂等）
  - PerformanceSnapshot append-only（不覆盖历史 Truth）
  - join 状态显式记录：EXACT_MATCH / NORMALIZED_MATCH / REVIEW_REQUIRED / UNMATCHED
  - Raw Snapshot 由 pipeline 保持 IMMUTABLE（本适配器只读原始快照路径，不修改）
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid


class B007CreatorImportAdapterV1:
    ACCOUNT_ID = "B007"
    PLATFORM = "XIAOHONGSHU"

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS published_content_v1(
                published_content_id TEXT PRIMARY KEY,
                platform TEXT, account_id TEXT, note_id TEXT, note_url TEXT,
                title TEXT, publish_time TEXT, content_type TEXT, duration REAL,
                asset_id TEXT, asset_mapping_method TEXT, asset_mapping_confidence TEXT,
                source_refs TEXT, created_at REAL, updated_at REAL)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS performance_snapshot_v1(
                snapshot_id TEXT PRIMARY KEY, published_content_id TEXT,
                snapshot_time TEXT, window TEXT,
                views REAL, likes REAL, favorites REAL, comments REAL, shares REAL,
                private_messages REAL, leads REAL, forms REAL,
                ad_spend REAL, paid_impressions REAL, paid_clicks REAL, paid_leads REAL,
                metric_type TEXT, source TEXT, created_at REAL)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS content_join_status_v1(
                join_id TEXT PRIMARY KEY, published_content_id TEXT,
                note_id TEXT, join_method TEXT, join_status TEXT,
                matched_title TEXT, evidence TEXT, created_at REAL)
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def published_content_id(account_id: str, note_id: str) -> str:
        raw = f"{account_id}:{note_id}"
        return "PC-" + hashlib.sha256(raw.encode()).hexdigest()[:20]

    # ---- PublishedContent 幂等 upsert（§26） ----
    def upsert_published_content(self, record: dict) -> str:
        """account + note_id 幂等；同 note 合并 source_refs，不重复创建（§26）。"""
        pc_id = self.published_content_id(record["account_id"], record["note_id"])
        conn = sqlite3.connect(self.db_path)
        existing = conn.execute(
            "SELECT source_refs FROM published_content_v1 WHERE published_content_id=?",
            (pc_id,)).fetchone()
        now = time.time()
        if existing:
            refs = set(json.loads(existing[0] or "[]"))
            refs.update(record.get("source_refs", []))
            conn.execute(
                "UPDATE published_content_v1 SET title=?, publish_time=?, content_type=?,"
                "duration=?, note_url=?, source_refs=?, updated_at=? "
                "WHERE published_content_id=?",
                (record.get("title", ""), record.get("publish_time", ""),
                 record.get("content_type", ""), record.get("duration"),
                 record.get("note_url", ""), json.dumps(sorted(refs), ensure_ascii=False),
                 now, pc_id))
        else:
            conn.execute(
                "INSERT INTO published_content_v1(published_content_id,platform,account_id,"
                "note_id,note_url,title,publish_time,content_type,duration,"
                "asset_id,asset_mapping_method,asset_mapping_confidence,"
                "source_refs,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pc_id, self.PLATFORM, record["account_id"], record["note_id"],
                 record.get("note_url", ""), record.get("title", ""),
                 record.get("publish_time", ""), record.get("content_type", ""),
                 record.get("duration"), record.get("asset_id"),
                 record.get("asset_mapping_method", "UNKNOWN"),
                 record.get("asset_mapping_confidence", "UNKNOWN"),
                 json.dumps(record.get("source_refs", []), ensure_ascii=False),
                 now, now))
        conn.commit()
        conn.close()
        return pc_id

    # ---- Performance append-only（§15/16/26） ----
    def add_performance_snapshot(self, pc_id: str, metrics: dict) -> str:
        snap_id = f"SNAP-{uuid.uuid4().hex[:16]}"
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO performance_snapshot_v1(snapshot_id,published_content_id,"
            "snapshot_time,window,views,likes,favorites,comments,shares,"
            "private_messages,leads,forms,ad_spend,paid_impressions,paid_clicks,paid_leads,"
            "metric_type,source,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (snap_id, pc_id,
             metrics.get("snapshot_time", ""), metrics.get("window", "UNKNOWN"),
             metrics.get("views"), metrics.get("likes"), metrics.get("favorites"),
             metrics.get("comments"), metrics.get("shares"),
             metrics.get("private_messages"), metrics.get("leads"), metrics.get("forms"),
             metrics.get("ad_spend"), metrics.get("paid_impressions"),
             metrics.get("paid_clicks"), metrics.get("paid_leads"),
             metrics.get("metric_type", "UNKNOWN"), metrics.get("source", "CREATOR_SYNC"),
             time.time()))
        conn.commit()
        conn.close()
        return snap_id

    # ---- join 状态（§18） ----
    def record_join_status(self, pc_id: str, note_id: str, join_method: str,
                           join_status: str, matched_title: str = "",
                           evidence: str = "") -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO content_join_status_v1(join_id,published_content_id,note_id,"
            "join_method,join_status,matched_title,evidence,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (f"JOIN-{uuid.uuid4().hex[:16]}", pc_id, note_id, join_method, join_status,
             matched_title, evidence, time.time()))
        conn.commit()
        conn.close()

    # ---- 查询（报告用） ----
    def count_published(self, account_id: str = ACCOUNT_ID) -> int:
        conn = sqlite3.connect(self.db_path)
        n = conn.execute(
            "SELECT COUNT(*) FROM published_content_v1 WHERE account_id=?",
            (account_id,)).fetchone()[0]
        conn.close()
        return n

    def note_ids(self, account_id: str = ACCOUNT_ID) -> set[str]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT note_id FROM published_content_v1 WHERE account_id=?",
            (account_id,)).fetchall()
        conn.close()
        return {r[0] for r in rows}
