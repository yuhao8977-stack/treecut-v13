"""TreeCut ShotUsageService — 镜头使用 Ledger（Phase 1 基础）。

宪法 8：素材使用必须有"记忆"。
本 Phase 仅建立 Schema 访问层（插入/查询/状态），
**不启用正式 reuse cooldown 算法**（Phase 6 才实现）。
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class ShotUsageService:
    """镜头使用记录服务（基础版）。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------

    def record_usage(self, segment_id: str, usage_type: str = "candidate",
                     production_id: str = "", account_id: str = "",
                     beat_id: str = "", template_id: str = "",
                     cooldown_until: float = 0.0) -> int:
        """记录一次镜头使用（usage_type: candidate|preview|rendered|published）。"""
        # 校验 segment 存在（不允许无效 segment 引用）
        conn = self._connect()
        seg = conn.execute(
            "SELECT segment_id FROM segments WHERE segment_id=?",
            (segment_id,)).fetchone()
        if seg is None:
            conn.close()
            raise ValueError(f"无效 segment_id: {segment_id}")
        now = time.time()
        cur = conn.execute(
            "SELECT usage_id, usage_count FROM shot_usage "
            "WHERE segment_id=? AND production_id=? AND usage_type=? AND status='active'",
            (segment_id, production_id, usage_type)).fetchone()
        if cur:
            conn.execute(
                "UPDATE shot_usage SET usage_count=usage_count+1, used_at=?, "
                "cooldown_until=? WHERE usage_id=?",
                (now, cooldown_until, cur["usage_id"]))
            uid = cur["usage_id"]
        else:
            cur2 = conn.execute(
                "INSERT INTO shot_usage(segment_id,production_id,account_id,beat_id,"
                "template_id,usage_type,used_at,usage_count,cooldown_until,status,created_at) "
                "VALUES(?,?,?,?,?,?,?,1,?, 'active', ?)",
                (segment_id, production_id, account_id, beat_id, template_id,
                 usage_type, now, cooldown_until, now))
            uid = cur2.lastrowid
        conn.commit()
        conn.close()
        return int(uid)

    def query_by_segment(self, segment_id: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM shot_usage WHERE segment_id=? ORDER BY used_at DESC",
            (segment_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def cancel(self, usage_id: int) -> None:
        conn = self._connect()
        conn.execute("UPDATE shot_usage SET status='cancelled' WHERE usage_id=?",
                     (usage_id,))
        conn.commit()
        conn.close()

    def usage_count(self, segment_id: str) -> int:
        conn = self._connect()
        row = conn.execute(
            "SELECT COALESCE(SUM(usage_count),0) n FROM shot_usage "
            "WHERE segment_id=? AND status='active'", (segment_id,)).fetchone()
        conn.close()
        return int(row["n"]) if row else 0

    def stats(self) -> dict:
        conn = self._connect()
        total = conn.execute("SELECT COUNT(*) FROM shot_usage").fetchone()[0]
        by_type = {r["usage_type"]: r["n"] for r in conn.execute(
            "SELECT usage_type, COUNT(*) n FROM shot_usage GROUP BY usage_type")}
        by_status = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) n FROM shot_usage GROUP BY status")}
        conn.close()
        return {"total": total, "by_type": by_type, "by_status": by_status}
