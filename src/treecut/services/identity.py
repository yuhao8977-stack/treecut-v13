"""TreeCut AssetRepository / SegmentRepository — Canonical Identity 数据访问边界（Phase 1）。

Canonical 身份规则（架构宪法 2）：
  media_files.id   = 文件发现层 File Identity（仅文件定位/元数据/路径解析）
  assets.asset_id  = 视频资产唯一 Canonical Asset Identity（唯一 Source of Truth）
  segments.segment_id = 自动生产最小单位 / Shot Identity 基础

禁止：业务模块自行重复写 SQL；禁止使用 media_id 作为业务主键。

职责边界：
  AssetRepository  — asset 维度：取素材/解析 media/解析路径/列 segment/校验
  SegmentRepository— segment 维度：取镜头/回源 asset/解析路径/时间范围/校验
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


class AssetRepository:
    """Asset 数据访问（只读）。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _ro(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------

    def get_asset(self, asset_id: str) -> dict | None:
        with self._ro() as conn:
            row = conn.execute(
                "SELECT a.*, m.relative_path, m.media_type, s.path AS source_path "
                "FROM assets a LEFT JOIN media_files m ON m.id=a.media_id "
                "LEFT JOIN sources s ON s.id=m.source_id "
                "WHERE a.asset_id=?", (asset_id,)).fetchone()
        return dict(row) if row else None

    def resolve_media(self, asset_id: str) -> int | None:
        """asset_id → media_id（仅用于文件定位，不作业务主键）。"""
        with self._ro() as conn:
            row = conn.execute(
                "SELECT media_id FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
        return row["media_id"] if row else None

    def resolve_path(self, asset_id: str) -> str:
        """asset_id → 物理文件绝对路径。"""
        with self._ro() as conn:
            row = conn.execute(
                "SELECT m.relative_path, s.path AS source_path "
                "FROM assets a JOIN media_files m ON m.id=a.media_id "
                "JOIN sources s ON s.id=m.source_id "
                "WHERE a.asset_id=?", (asset_id,)).fetchone()
        if not row:
            return ""
        return str(Path(row["source_path"]) / row["relative_path"])

    def list_segments(self, asset_id: str) -> list[dict]:
        with self._ro() as conn:
            rows = conn.execute(
                "SELECT segment_id, start_ms, end_ms, duration_ms, scene_no, "
                "quality_score, algorithm_version FROM segments "
                "WHERE asset_id=? ORDER BY start_ms", (asset_id,)).fetchall()
        return [dict(r) for r in rows]

    def validate_asset(self, asset_id: str) -> dict:
        """资产校验：存在性 + 文件可达性。"""
        asset = self.get_asset(asset_id)
        if not asset:
            return {"valid": False, "asset_id": asset_id, "reason": "asset 不存在"}
        path = self.resolve_path(asset_id)
        exists = bool(path) and Path(path).exists()
        return {"valid": True, "asset_id": asset_id,
                "path": path, "path_exists": exists}


class SegmentRepository:
    """Segment 数据访问（只读）。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _ro(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------

    def get_segment(self, segment_id: str) -> dict | None:
        with self._ro() as conn:
            row = conn.execute(
                "SELECT * FROM segments WHERE segment_id=?", (segment_id,)).fetchone()
        return dict(row) if row else None

    def get_asset_id(self, segment_id: str) -> str | None:
        """segment_id → asset_id（Canonical 回溯第一跳）。"""
        with self._ro() as conn:
            row = conn.execute(
                "SELECT asset_id FROM segments WHERE segment_id=?",
                (segment_id,)).fetchone()
        return row["asset_id"] if row else None

    def resolve_source(self, segment_id: str) -> dict:
        """segment_id → {asset_id, media_id, path} 完整追溯链。"""
        with self._ro() as conn:
            row = conn.execute(
                "SELECT sg.segment_id, sg.asset_id, sg.start_ms, sg.end_ms, "
                "a.media_id, m.relative_path, s.path AS source_path "
                "FROM segments sg "
                "JOIN assets a ON a.asset_id=sg.asset_id "
                "JOIN media_files m ON m.id=a.media_id "
                "JOIN sources s ON s.id=m.source_id "
                "WHERE sg.segment_id=?", (segment_id,)).fetchone()
        if not row:
            return {"segment_id": segment_id, "found": False}
        return {
            "segment_id": segment_id, "found": True,
            "asset_id": row["asset_id"], "media_id": row["media_id"],
            "start_ms": row["start_ms"], "end_ms": row["end_ms"],
            "path": str(Path(row["source_path"]) / row["relative_path"]),
        }

    def resolve_time_range(self, segment_id: str) -> dict:
        seg = self.get_segment(segment_id)
        if not seg:
            return {"found": False}
        return {"found": True, "start_ms": seg["start_ms"],
                "end_ms": seg["end_ms"],
                "duration_ms": seg["duration_ms"]}

    def list_by_asset(self, asset_id: str) -> list[dict]:
        with self._ro() as conn:
            rows = conn.execute(
                "SELECT segment_id, start_ms, end_ms, duration_ms FROM segments "
                "WHERE asset_id=? ORDER BY start_ms", (asset_id,)).fetchall()
        return [dict(r) for r in rows]

    def validate_segment(self, segment_id: str) -> dict:
        """镜头校验：存在 + 时间合法 + 回源可达。"""
        seg = self.get_segment(segment_id)
        if not seg:
            return {"valid": False, "segment_id": segment_id, "reason": "segment 不存在"}
        issues = []
        if seg["start_ms"] >= seg["end_ms"]:
            issues.append("start_ms >= end_ms")
        if (seg["duration_ms"] or 0) <= 0:
            issues.append("duration_ms <= 0")
        src = self.resolve_source(segment_id)
        path_ok = src.get("found") and Path(src["path"]).exists()
        if not path_ok:
            issues.append("回源路径不可达")
        return {"valid": len(issues) == 0, "segment_id": segment_id,
                "asset_id": seg["asset_id"], "issues": issues,
                "path_exists": path_ok}
