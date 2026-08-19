"""P1: Video-level asset table with stable asset_id and probe metadata.

Builds on the Catalog's media_files/analysis_jobs but adds the
第二阶段总指令 §C2/C3/C4 requirements:
- asset_id: UUID + content fingerprint (not bare filename)
- full SHA256 fingerprint (大文件分块) for exact duplicate detection
- ffprobe metadata: duration / width / height / fps / codec / bitrate
- P0-P1: 断点续跑 task statuses with retry/checkpoint
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.library.catalog import Catalog
from treecut.library.hash_utils import full_sha256, quick_fingerprint

ASSETS_SCHEMA_VERSION = 1

ASSETS_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,          -- uuid4 hex (stable identity)
    media_id INTEGER NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
    fingerprint_quick TEXT NOT NULL,    -- size+head/tail sha256 (scan dedup)
    fingerprint_full TEXT NOT NULL,     -- full streaming sha256 (exact dup)
    file_size INTEGER NOT NULL,
    duration REAL DEFAULT 0,
    width INTEGER DEFAULT 0,
    height INTEGER DEFAULT 0,
    fps REAL DEFAULT 0,
    video_codec TEXT DEFAULT '',
    audio_codec TEXT DEFAULT '',
    bitrate REAL DEFAULT 0,
    has_audio INTEGER DEFAULT 0,
    probe_status TEXT DEFAULT 'pending', -- pending/running/done/failed/skipped
    probe_attempts INTEGER DEFAULT 0,
    probe_error TEXT DEFAULT '',
    probe_version TEXT DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assets_media ON assets(media_id);
CREATE INDEX IF NOT EXISTS idx_assets_full_hash ON assets(fingerprint_full);
CREATE INDEX IF NOT EXISTS idx_assets_quick_hash ON assets(fingerprint_quick);
CREATE TABLE IF NOT EXISTS asset_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    media_id INTEGER NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL,
    current INTEGER NOT NULL DEFAULT 1,
    UNIQUE(source_id, relative_path)
);
CREATE INDEX IF NOT EXISTS idx_locations_asset ON asset_locations(asset_id);
"""


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    media_id: int
    fingerprint_quick: str
    fingerprint_full: str
    file_size: int
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    bitrate: float
    has_audio: bool
    probe_status: str
    probe_error: str
    probe_version: str
    probe_attempts: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class AssetsManager:
    """Asset-level management layered over Catalog's media_files."""

    def __init__(self, catalog: Catalog | None = None, max_probe_attempts: int = 3):
        self.catalog = catalog or Catalog()
        self.db_path = self.catalog.db_path
        self.max_probe_attempts = max_probe_attempts
        with self._connect() as connection:
            connection.executescript(ASSETS_SCHEMA)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(assets)")}
            if "probe_attempts" not in columns:
                connection.execute(
                    "ALTER TABLE assets ADD COLUMN probe_attempts INTEGER DEFAULT 0"
                )
            connection.execute(f"PRAGMA user_version={ASSETS_SCHEMA_VERSION}")

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

    def ensure_asset(self, media_id: int, absolute_path: str) -> AssetRecord:
        """Create an asset row for a media file if missing. Probe stays pending."""
        now = time.time()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM assets WHERE media_id=?", (media_id,)
            ).fetchone()
            if existing is not None:
                return AssetRecord(**dict(existing))
            path = Path(absolute_path)
            size = path.stat().st_size
            quick = quick_fingerprint(path, size)
            asset_id = uuid.uuid4().hex
            connection.execute(
                "INSERT INTO assets(asset_id,media_id,fingerprint_quick,fingerprint_full,file_size,"
                "probe_status,probe_error,probe_version,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (asset_id, media_id, quick, quick, size, 'pending', '', '', now, now),
            )
            row = connection.execute(
                "SELECT * FROM assets WHERE media_id=?", (media_id,)
            ).fetchone()
            return AssetRecord(**dict(row))

    def recover_interrupted_probes(self) -> int:
        """Return probes left 'running' by a crashed previous process to pending.

        断点续跑（第二阶段 §7）：Windows 重启或程序崩溃后，把 stuck running
        收回为 pending（attempts 保留，仍受 max_probe_attempts 限制）。
        """
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE assets SET probe_status='pending',probe_error="
                "'Interrupted: 上次采集进程在完成前退出',updated_at=? "
                "WHERE probe_status='running'",
                (now,),
            )
            return int(cursor.rowcount)

    def ensure_all_video_assets(self) -> int:
        """Create asset rows for all available video media that lack one.

        P1.1 内容身份协调：
        - 同一内容（quick fingerprint 相同）只允许一个 canonical asset_id。
        - 文件移动/改名/重复副本 → 复用已有 asset_id，位置记录到 asset_locations。
        - 不更新主 media_id 指针（保留首次关联），新位置通过 asset_locations 追踪。
        """
        now = time.time()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT m.id media_id,m.relative_path,s.path source_path,s.id source_id "
                "FROM media_files m JOIN sources s ON s.id=m.source_id "
                "WHERE m.media_type='video' AND m.available=1 AND s.online=1 "
                "AND NOT EXISTS (SELECT 1 FROM assets a WHERE a.media_id=m.id)"
            ).fetchall()
            created = 0
            for row in rows:
                abs_path = str(Path(row["source_path"]) / row["relative_path"])
                try:
                    size = Path(abs_path).stat().st_size
                except OSError:
                    continue
                quick = quick_fingerprint(abs_path, size)
                # 内容身份协调：quick 已归属某 asset → 复用（移动/改名/重复副本）
                existing = connection.execute(
                    "SELECT asset_id FROM assets WHERE fingerprint_quick=? LIMIT 1",
                    (quick,),
                ).fetchone()
                if existing is not None:
                    # 记录位置（幂等），不新建 asset，不动主 media_id
                    connection.execute(
                        "INSERT INTO asset_locations(asset_id,source_id,relative_path,media_id,"
                        "first_seen,last_seen,current) VALUES(?,?,?,?,?,?,1) "
                        "ON CONFLICT(source_id,relative_path) DO UPDATE SET "
                        "asset_id=excluded.asset_id,media_id=excluded.media_id,"
                        "last_seen=excluded.last_seen,current=1",
                        (existing["asset_id"], row["source_id"], row["relative_path"],
                         row["media_id"], now, now),
                    )
                    # 旧位置标记为非当前（移动/改名后旧路径不再 current）
                    connection.execute(
                        "UPDATE asset_locations SET current=0 WHERE asset_id=? "
                        "AND NOT (source_id=? AND relative_path=?)",
                        (existing["asset_id"], row["source_id"], row["relative_path"]),
                    )
                    created += 0
                    continue
                asset_id = uuid.uuid4().hex
                connection.execute(
                    "INSERT INTO assets(asset_id,media_id,fingerprint_quick,fingerprint_full,file_size,"
                    "probe_status,probe_error,probe_version,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (asset_id, row["media_id"], quick, quick, size, 'pending', '', '', now, now),
                )
                connection.execute(
                    "INSERT INTO asset_locations(asset_id,source_id,relative_path,media_id,"
                    "first_seen,last_seen,current) VALUES(?,?,?,?,?,?,1)",
                    (asset_id, row["source_id"], row["relative_path"], row["media_id"], now, now),
                )
                created += 1
            return created

    def pending_probes(self, limit: int = 100) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT a.*,m.relative_path,s.path source_path,m.media_type,m.available,m.fingerprint "
                "FROM assets a JOIN media_files m ON m.id=a.media_id JOIN sources s ON s.id=m.source_id "
                "WHERE a.probe_status IN ('pending','failed') AND a.probe_attempts<? "
                "AND m.media_type='video' AND m.available=1 AND s.online=1 ORDER BY a.updated_at LIMIT ?",
                (self.max_probe_attempts, limit),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["absolute_path"] = str(Path(item["source_path"]) / item["relative_path"])
            result.append(item)
        return result

    def claim_probe(self, media_id: int | None = None) -> dict | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            selected = "AND a.media_id=? " if media_id is not None else ""
            params = (media_id,) if media_id is not None else ()
            row = connection.execute(
                "SELECT a.*,m.relative_path,s.path source_path FROM assets a "
                "JOIN media_files m ON m.id=a.media_id JOIN sources s ON s.id=m.source_id "
                "WHERE a.probe_status IN ('pending','failed') AND a.probe_attempts<? "
                "AND m.media_type='video' AND m.available=1 AND s.online=1 " + selected +
                "ORDER BY a.updated_at LIMIT 1",
                (self.max_probe_attempts, *params),
            ).fetchone()
            if row is None:
                return None
            now = time.time()
            connection.execute(
                "UPDATE assets SET probe_status='running',probe_attempts=probe_attempts+1,updated_at=? "
                "WHERE media_id=?",
                (now, row["media_id"]),
            )
            item = dict(row)
            item["absolute_path"] = str(Path(item["source_path"]) / item["relative_path"])
            return item

    def complete_probe(self, media_id: int, probe: dict, probe_version: str = "ffprobe-v1") -> None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "UPDATE assets SET duration=?,width=?,height=?,fps=?,video_codec=?,audio_codec=?,"
                "bitrate=?,has_audio=?,probe_status='done',probe_error='',probe_version=?,updated_at=? "
                "WHERE media_id=?",
                (probe.get("duration", 0), probe.get("width", 0), probe.get("height", 0),
                 probe.get("fps", 0), probe.get("video_codec", ""), probe.get("audio_codec") or "",
                 probe.get("bitrate", 0), int(probe.get("has_audio", 0)), probe_version, now, media_id),
            )

    def fail_probe(self, media_id: int, error: str) -> None:
        """Mark probe failed; skip permanently once attempts exceed the cap."""
        now = time.time()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT probe_attempts FROM assets WHERE media_id=?", (media_id,)
            ).fetchone()
            attempts = row["probe_attempts"] if row else 0
            status = "skipped" if attempts >= self.max_probe_attempts else "failed"
            connection.execute(
                "UPDATE assets SET probe_status=?,probe_error=?,updated_at=? WHERE media_id=?",
                (status, error[:2000], now, media_id),
            )

    def needs_full_hash(self, media_id: int) -> bool:
        """P1.1 §八: Full SHA256 仅用于疑似重复/高价值/后台。

        判断：该 asset 的 quick fingerprint 是否与其它 asset 相同（疑似重复），
        或该文件是大文件（>200MB，高价值校验）。否则跳过 full hash，
        避免为 3TB 素材全量顺序读盘。
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT a.fingerprint_quick, a.file_size FROM assets a WHERE media_id=?",
                (media_id,),
            ).fetchone()
            if row is None:
                return False
            quick = row["fingerprint_quick"]
            size = row["file_size"] or 0
            if quick and quick != "0" * 64:
                count = connection.execute(
                    "SELECT COUNT(*) n FROM assets WHERE fingerprint_quick=?",
                    (quick,),
                ).fetchone()["n"]
                if count > 1:
                    return True
            return size >= 200 * 1024 * 1024  # >=200MB 高价值校验

    def finalize_fingerprint(self, media_id: int, absolute_path: str,
                             force: bool = False) -> bool:
        """Compute the full streaming SHA256 (P1 dedup).

        P1.1 分层哈希：默认仅当疑似重复/大文件才计算；force=True 强制。
        返回是否实际计算。
        """
        if not force and not self.needs_full_hash(media_id):
            return False
        now = time.time()
        full = full_sha256(absolute_path)
        with self._connect() as connection:
            connection.execute(
                "UPDATE assets SET fingerprint_full=?,updated_at=? WHERE media_id=?",
                (full, now, media_id),
            )
        return True

    def stats(self) -> dict:
        with self._connect() as connection:
            total = connection.execute("SELECT COUNT(*) n FROM assets").fetchone()["n"]
            by_status = {
                row["probe_status"]: row["n"]
                for row in connection.execute(
                    "SELECT probe_status,COUNT(*) n FROM assets GROUP BY probe_status"
                ).fetchall()
            }
            duplicates = connection.execute(
                "SELECT COALESCE(SUM(c-1),0) n FROM (SELECT COUNT(*) c FROM assets "
                "GROUP BY fingerprint_full HAVING COUNT(*)>1 AND fingerprint_full<>'')"
            ).fetchone()["n"]
            with_meta = connection.execute(
                "SELECT COUNT(*) n FROM assets WHERE probe_status='done'"
            ).fetchone()["n"]
        return {
            "total": total,
            "probe_status": by_status,
            "probed_with_metadata": with_meta,
            "exact_duplicates": int(duplicates),
        }

    def list_assets(self, limit: int = 200, probed_only: bool = False) -> list[dict]:
        where = "AND a.probe_status='done'" if probed_only else ""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT a.*,m.relative_path,s.path source_path, "
                "COALESCE((SELECT l.relative_path FROM asset_locations l "
                "          WHERE l.asset_id=a.asset_id AND l.current=1 LIMIT 1), "
                "         m.relative_path) current_relative_path, "
                "COALESCE((SELECT sl.path FROM asset_locations l2 "
                "          JOIN sources sl ON sl.id=l2.source_id "
                "          WHERE l2.asset_id=a.asset_id AND l2.current=1 LIMIT 1), "
                "         s.path) current_source_path "
                "FROM assets a "
                "JOIN media_files m ON m.id=a.media_id JOIN sources s ON s.id=m.source_id "
                "WHERE 1=1 " + where + " ORDER BY a.updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["relative_path"] = item["current_relative_path"] or item["relative_path"]
            item["source_path"] = item["current_source_path"] or item["source_path"]
            item["absolute_path"] = str(Path(item["source_path"]) / item["relative_path"])
            result.append(item)
        return result
