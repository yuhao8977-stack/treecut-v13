"""P2.7: QualityValidationStore — 人工质量验证核心存储。

新增表（不修改任何既有表）：
  - human_feedback   人工反馈（每 AI 结果一行的 ✅/⚠️/❌ + 修改 + 评分）
  - broken_assets    损坏素材隔离（只记录不删除）
  - asset_quality    素材质量评分（100 分制）
  - asset_status     素材业务状态（READY/REVIEW/HIGH_VALUE/LOW_VALUE/REJECTED/BROKEN）
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path

SCHEMA_VERSION = 1
SCHEMA_NAME = "quality_validation"

# 素材业务状态
ASSET_STATUS = ("READY", "REVIEW", "HIGH_VALUE", "LOW_VALUE", "REJECTED", "BROKEN")

# 人工评价（每 AI 结果）
VERDICT_CORRECT = "correct"        # ✅ 正确
VERDICT_PARTIAL = "partial"        # ⚠️ 部分正确
VERDICT_WRONG = "wrong"            # ❌ 错误

# 100 分评分维度
SCORE_DIMENSIONS = ("scene", "product", "function", "value", "business")

SCHEMA = """
CREATE TABLE IF NOT EXISTS human_feedback (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id     TEXT NOT NULL,
    ai_type      TEXT NOT NULL,       -- scene|asr|ocr|label|keyframe
    ai_label     TEXT NOT NULL DEFAULT '',
    human_label  TEXT NOT NULL DEFAULT '',   -- 人工修正标签
    verdict      TEXT NOT NULL DEFAULT 'correct',  -- correct|partial|wrong
    comment      TEXT NOT NULL DEFAULT '',
    operator     TEXT NOT NULL DEFAULT '',
    created_time REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hf_asset ON human_feedback(asset_id);

CREATE TABLE IF NOT EXISTS broken_assets (
    asset_id     TEXT PRIMARY KEY,
    file_path    TEXT NOT NULL DEFAULT '',
    error_reason TEXT NOT NULL DEFAULT '',
    failed_time  REAL NOT NULL,
    stage        TEXT NOT NULL DEFAULT '',
    resolved     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_broken_resolved ON broken_assets(resolved);

CREATE TABLE IF NOT EXISTS asset_quality (
    asset_id     TEXT PRIMARY KEY,
    scene_score    INTEGER NOT NULL DEFAULT 0,   -- 0/10/20
    product_score  INTEGER NOT NULL DEFAULT 0,
    function_score INTEGER NOT NULL DEFAULT 0,
    value_score    INTEGER NOT NULL DEFAULT 0,
    business_score INTEGER NOT NULL DEFAULT 0,
    total_score    INTEGER NOT NULL DEFAULT 0,
    reviewer       TEXT NOT NULL DEFAULT '',
    reviewed_time  REAL,
    comment        TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS asset_status (
    asset_id     TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'REVIEW',
    source       TEXT NOT NULL DEFAULT 'system',  -- system|human
    updated_time REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status ON asset_status(status);

CREATE TABLE IF NOT EXISTS quality_report (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    report_name  TEXT NOT NULL,
    payload      TEXT NOT NULL DEFAULT '{}',
    created_time REAL NOT NULL
);
"""


class QualityValidationStore:
    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)

    def _connect(self):
        connection = sqlite3.connect(str(self.db_path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def ensure_schema(self) -> int:
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)
            row = connection.execute(
                "SELECT version FROM schema_version WHERE name=?", (SCHEMA_NAME,)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT OR REPLACE INTO schema_version(name,version) VALUES(?,?)",
                    (SCHEMA_NAME, SCHEMA_VERSION),
                )
            connection.commit()
        return SCHEMA_VERSION

    # ------------------------------------------------------------------
    # 人工反馈
    # ------------------------------------------------------------------

    def add_feedback(self, asset_id: str, ai_type: str, verdict: str,
                     ai_label: str = "", human_label: str = "",
                     comment: str = "", operator: str = "") -> int:
        if verdict not in (VERDICT_CORRECT, VERDICT_PARTIAL, VERDICT_WRONG):
            raise ValueError(f"非法评价: {verdict}")
        now = time.time()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "INSERT INTO human_feedback(asset_id,ai_type,ai_label,human_label,"
                "verdict,comment,operator,created_time) VALUES(?,?,?,?,?,?,?,?)",
                (asset_id, ai_type, ai_label, human_label, verdict,
                 comment, operator, now),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def feedback_stats(self) -> dict:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT ai_type, verdict, COUNT(*) FROM human_feedback "
                "GROUP BY ai_type, verdict"
            ).fetchall()
            total = connection.execute(
                "SELECT COUNT(*) FROM human_feedback").fetchone()[0]
        stats: dict = {"total": total, "by_type": {}}
        for r in rows:
            stats["by_type"].setdefault(r[0], {})[r[1]] = r[2]
        return stats

    def list_feedback(self, asset_id: str | None = None, limit: int = 200) -> list[dict]:
        with closing(self._connect()) as connection:
            if asset_id:
                rows = connection.execute(
                    "SELECT * FROM human_feedback WHERE asset_id=? "
                    "ORDER BY id DESC LIMIT ?", (asset_id, limit)).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM human_feedback ORDER BY id DESC LIMIT ?",
                    (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # 损坏素材隔离
    # ------------------------------------------------------------------

    def add_broken(self, asset_id: str, file_path: str, error_reason: str,
                   stage: str = "") -> None:
        now = time.time()
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO broken_assets(asset_id,file_path,error_reason,"
                "failed_time,stage,resolved) VALUES(?,?,?,?,?,0)",
                (asset_id, file_path, error_reason[:2000], now, stage),
            )
            connection.commit()

    def list_broken(self, resolved: int | None = None) -> list[dict]:
        with closing(self._connect()) as connection:
            if resolved is None:
                rows = connection.execute(
                    "SELECT * FROM broken_assets ORDER BY failed_time DESC").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM broken_assets WHERE resolved=? ORDER BY failed_time DESC",
                    (resolved,)).fetchall()
        return [dict(r) for r in rows]

    def count_broken(self) -> int:
        with closing(self._connect()) as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM broken_assets WHERE resolved=0").fetchone()[0])

    # ------------------------------------------------------------------
    # 质量评分（100 分制）
    # ------------------------------------------------------------------

    def score_asset(self, asset_id: str, scene: int, product: int, function: int,
                    value: int, business: int, reviewer: str = "",
                    comment: str = "") -> dict:
        for name, s in (("scene", scene), ("product", product),
                        ("function", function), ("value", value),
                        ("business", business)):
            if s not in (0, 10, 20):
                raise ValueError(f"{name} 评分必须为 0/10/20，收到 {s}")
        total = scene + product + function + value + business
        now = time.time()
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO asset_quality(asset_id,scene_score,product_score,"
                "function_score,value_score,business_score,total_score,reviewer,"
                "reviewed_time,comment) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (asset_id, scene, product, function, value, business, total,
                 reviewer, now, comment),
            )
            connection.commit()
        return {"asset_id": asset_id, "total": total}

    def quality_stats(self) -> dict:
        with closing(self._connect()) as connection:
            n = connection.execute("SELECT COUNT(*) FROM asset_quality").fetchone()[0]
            avg = connection.execute(
                "SELECT AVG(total_score) FROM asset_quality").fetchone()[0]
            by_score = connection.execute(
                "SELECT total_score, COUNT(*) FROM asset_quality GROUP BY total_score "
                "ORDER BY 1").fetchall()
        return {"reviewed": n, "avg_total": round(avg or 0, 1),
                "by_score": {r[0]: r[1] for r in by_score}}

    # ------------------------------------------------------------------
    # 素材状态
    # ------------------------------------------------------------------

    def set_asset_status(self, asset_id: str, status: str, source: str = "human") -> None:
        if status not in ASSET_STATUS:
            raise ValueError(f"非法状态: {status}")
        now = time.time()
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO asset_status(asset_id,status,source,updated_time) "
                "VALUES(?,?,?,?)",
                (asset_id, status, source, now),
            )
            connection.commit()

    def status_counts(self) -> dict:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) FROM asset_status GROUP BY status").fetchall()
        return {r[0]: r[1] for r in rows}

    # ------------------------------------------------------------------
    # 抽检
    # ------------------------------------------------------------------

    def sampled_assets(self, limit: int = 100, status: str = "REVIEW") -> list[dict]:
        """从未审核资产中随机抽取（带状态标记）。"""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT asset_id FROM assets WHERE asset_id NOT IN "
                "(SELECT asset_id FROM asset_quality) "
                "AND asset_id NOT IN (SELECT asset_id FROM asset_status WHERE status='BROKEN') "
                "ORDER BY RANDOM() LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # 报告
    # ------------------------------------------------------------------

    def save_report(self, report_name: str, payload: dict) -> int:
        import json
        now = time.time()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "INSERT INTO quality_report(report_name,payload,created_time) VALUES(?,?,?)",
                (report_name, json.dumps(payload, ensure_ascii=False), now),
            )
            connection.commit()
            return int(cursor.lastrowid)
