# -*- coding: utf-8 -*-
"""Stage 3A.1 — B003ManualImportAdapterV1 + PublishedContentRecord 模型。

数据模型（Stage3 数据血缘核心）：
  PublishedContentRecord（一次真实发布行为，≠ asset_id）
  PerformanceSnapshotV1（append-only）
  AccountIdentityRegistryV1（B003=BARBERRY坤宝岛台定制）
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time


class B003ManualImportAdapterV1:
    """B003 人工数据导入适配器（xlsx/csv/json → PublishedContentRecord）。

    纪律：
      - note_id 为发布身份证据；同 note 多来源合并，不生成重复记录
      - PerformanceSnapshot append-only（不覆盖）
      - added-WeChat 一律 UNATTRIBUTABLE_CENTRALIZED_B007
      - 不修改原始文件
    """

    DB_PATH = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"

    def __init__(self, db_path=None):
        self.db_path = db_path or self.DB_PATH
        self._ensure_schema()

    def _ensure_schema(self):
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
        conn.commit()
        conn.close()

    @staticmethod
    def published_content_id(account_id: str, note_id: str) -> str:
        """发布行为 ID：account + note_id 唯一（≠ asset_id）。"""
        raw = f"{account_id}:{note_id}"
        return "PC-" + hashlib.sha256(raw.encode()).hexdigest()[:20]

    def upsert_published_content(self, record: dict) -> str:
        """按 note_id 去重：同 note 合并 source_refs，不重复生成记录。"""
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
                "UPDATE published_content_v1 SET source_refs=?, updated_at=? "
                "WHERE published_content_id=?",
                (json.dumps(sorted(refs), ensure_ascii=False), now, pc_id))
        else:
            conn.execute(
                "INSERT INTO published_content_v1(published_content_id,platform,account_id,"
                "note_id,note_url,title,publish_time,content_type,duration,"
                "asset_id,asset_mapping_method,asset_mapping_confidence,"
                "source_refs,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (pc_id, record.get("platform", "XIAOHONGSHU"), record["account_id"],
                 record["note_id"], record.get("note_url", ""), record.get("title", ""),
                 record.get("publish_time", ""), record.get("content_type", ""),
                 record.get("duration"), record.get("asset_id"),
                 record.get("asset_mapping_method", "UNKNOWN"),
                 record.get("asset_mapping_confidence", "UNKNOWN"),
                 json.dumps(record.get("source_refs", []), ensure_ascii=False),
                 now, now))
        conn.commit()
        conn.close()
        return pc_id

    def add_performance_snapshot(self, pc_id: str, metrics: dict) -> str:
        """append-only 快照：新 snapshot_id，不覆盖旧值。"""
        snap_id = f"SNAP-{int(time.time() * 1000)}"
        metric_type = metrics.get("metric_type", "UNKNOWN")  # ORGANIC/PAID/MIXED/UNKNOWN
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO performance_snapshot_v1(snapshot_id,published_content_id,"
            "snapshot_time,window,views,likes,favorites,comments,shares,"
            "private_messages,leads,forms,ad_spend,paid_impressions,paid_clicks,paid_leads,"
            "metric_type,source,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (snap_id, pc_id, metrics.get("snapshot_time", ""), metrics.get("window", "UNKNOWN"),
             metrics.get("views"), metrics.get("likes"), metrics.get("favorites"),
             metrics.get("comments"), metrics.get("shares"),
             metrics.get("private_messages"), metrics.get("leads"), metrics.get("forms"),
             metrics.get("ad_spend"), metrics.get("paid_impressions"),
             metrics.get("paid_clicks"), metrics.get("paid_leads"),
             metric_type, metrics.get("source", "IMPORT"), time.time()))
        conn.commit()
        conn.close()
        return snap_id

    def count(self):
        conn = sqlite3.connect(self.db_path)
        n = conn.execute("SELECT COUNT(*) FROM published_content_v1").fetchone()[0]
        conn.close()
        return n
