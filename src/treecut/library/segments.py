"""P2: Segment-level asset data — segments / keyframes / transcripts / ocr_text.

全部通过 asset_id 关联（Canonical Asset Registry 原则），
不重复创建"视频身份"。阶段状态由 asset_processing_state 管理，
本模块只存分析结果数据。
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from treecut.library.assets import AssetsManager

P2_SCHEMA_VERSION = 1

P2_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS segments (
    segment_id TEXT PRIMARY KEY,          -- uuid4 hex
    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    scene_no INTEGER NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    quality_score REAL DEFAULT 0,
    algorithm_version TEXT DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_segments_asset ON segments(asset_id, scene_no);

CREATE TABLE IF NOT EXISTS keyframes (
    frame_id TEXT PRIMARY KEY,
    segment_id TEXT NOT NULL REFERENCES segments(segment_id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    image_path TEXT NOT NULL,
    sharpness REAL DEFAULT 0,
    brightness REAL DEFAULT 0,
    selected INTEGER DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_keyframes_segment ON keyframes(segment_id);
CREATE INDEX IF NOT EXISTS idx_keyframes_asset ON keyframes(asset_id);

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL,
    segment_id TEXT,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    text_raw TEXT NOT NULL,
    text_corrected TEXT DEFAULT '',
    language TEXT DEFAULT '',
    confidence REAL DEFAULT 0,
    model_name TEXT DEFAULT '',
    model_version TEXT DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transcripts_asset ON transcripts(asset_id);

CREATE TABLE IF NOT EXISTS ocr_text (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL,
    frame_id TEXT,
    frame_timestamp_ms INTEGER,
    text TEXT NOT NULL,
    bbox TEXT DEFAULT '',
    subtitle_flag INTEGER DEFAULT 0,
    coverage REAL DEFAULT 0,
    confidence REAL DEFAULT 0,
    ocr_model TEXT DEFAULT '',
    ocr_model_version TEXT DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ocr_asset ON ocr_text(asset_id);
"""


class SegmentStore:
    """P2 分析结果存取（segments/keyframes/transcripts/ocr_text）。"""

    def __init__(self, assets: AssetsManager | None = None):
        self.assets = assets or AssetsManager()
        self.db_path = self.assets.db_path
        with self._connect() as connection:
            connection.executescript(P2_SCHEMA)
            connection.execute(f"PRAGMA user_version={P2_SCHEMA_VERSION}")

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

    # ---------------- segments ----------------

    def save_segments(self, asset_id: str, segments: list[dict],
                      algorithm_version: str = "scenedetect-contentdetector") -> int:
        """Replace segments for an asset (idempotent by asset+scene_no)."""
        now = time.time()
        with self._connect() as connection:
            connection.execute("DELETE FROM segments WHERE asset_id=?", (asset_id,))
            for seg in segments:
                sid = seg.get("segment_id") or uuid.uuid4().hex
                start = int(seg.get("start_ms", 0))
                end = int(seg.get("end_ms", 0))
                connection.execute(
                    "INSERT INTO segments(segment_id,asset_id,scene_no,start_ms,end_ms,"
                    "duration_ms,quality_score,algorithm_version,created_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (sid, asset_id, int(seg.get("scene_no", 0)), start, end,
                     max(0, end - start), float(seg.get("quality_score", 0)),
                     algorithm_version, now),
                )
        return len(segments)

    def list_segments(self, asset_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM segments WHERE asset_id=? ORDER BY scene_no", (asset_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def count_segments(self, asset_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) n FROM segments WHERE asset_id=?", (asset_id,)
            ).fetchone()
        return row["n"] if row else 0

    # ---------------- keyframes ----------------

    def save_keyframes(self, asset_id: str, keyframes: list[dict]) -> int:
        now = time.time()
        with self._connect() as connection:
            for kf in keyframes:
                connection.execute(
                    "INSERT INTO keyframes(frame_id,segment_id,asset_id,timestamp_ms,"
                    "image_path,sharpness,brightness,selected,created_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (kf.get("frame_id") or uuid.uuid4().hex,
                     kf["segment_id"], asset_id, int(kf.get("timestamp_ms", 0)),
                     kf["image_path"], float(kf.get("sharpness", 0)),
                     float(kf.get("brightness", 0)), int(kf.get("selected", 1)), now),
                )
        return len(keyframes)

    def list_keyframes(self, asset_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM keyframes WHERE asset_id=? ORDER BY timestamp_ms", (asset_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    # ---------------- transcripts ----------------

    def save_transcript(self, asset_id: str, transcript: dict) -> int:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO transcripts(asset_id,segment_id,start_ms,end_ms,text_raw,"
                "text_corrected,language,confidence,model_name,model_version,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (asset_id, transcript.get("segment_id"), int(transcript.get("start_ms", 0)),
                 int(transcript.get("end_ms", 0)), transcript.get("text_raw", ""),
                 transcript.get("text_corrected", ""), transcript.get("language", ""),
                 float(transcript.get("confidence", 0)), transcript.get("model_name", ""),
                 transcript.get("model_version", ""), now),
            )
            return connection.total_changes

    def list_transcripts(self, asset_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM transcripts WHERE asset_id=? ORDER BY start_ms", (asset_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def full_transcript(self, asset_id: str) -> str:
        """合并全文（供检索/标签使用）。"""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT GROUP_CONCAT(text_corrected, '') text FROM transcripts "
                "WHERE asset_id=? AND text_corrected<>''",
                (asset_id,),
            ).fetchone()
            if row and row["text"]:
                return row["text"]
            row2 = connection.execute(
                "SELECT GROUP_CONCAT(text_raw, '') text FROM transcripts WHERE asset_id=?",
                (asset_id,),
            ).fetchone()
        return row2["text"] if row2 else ""

    # ---------------- ocr ----------------

    def save_ocr(self, asset_id: str, ocr_items: list[dict]) -> int:
        now = time.time()
        with self._connect() as connection:
            for item in ocr_items:
                connection.execute(
                    "INSERT INTO ocr_text(asset_id,frame_id,frame_timestamp_ms,text,bbox,"
                    "subtitle_flag,coverage,confidence,ocr_model,ocr_model_version,created_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (asset_id, item.get("frame_id"), int(item.get("frame_timestamp_ms", 0)),
                     item.get("text", ""), item.get("bbox", ""),
                     int(item.get("subtitle_flag", 0)), float(item.get("coverage", 0)),
                     float(item.get("confidence", 0)), item.get("ocr_model", "rapidocr"),
                     item.get("ocr_model_version", ""), now),
                )
        return len(ocr_items)

    def list_ocr(self, asset_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ocr_text WHERE asset_id=? ORDER BY frame_timestamp_ms", (asset_id,)
            ).fetchall()
        return [dict(row) for row in rows]
