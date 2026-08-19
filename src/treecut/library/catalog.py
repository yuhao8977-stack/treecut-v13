"""Incremental, removable-drive-safe media catalog."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import time
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.analysis_version import ANALYSIS_PIPELINE_VERSION
from treecut.media.source_discovery import (
    AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, DriveInfo,
    discover_drives, volume_identity,
)
from treecut.platform.paths import RuntimePaths
from treecut.database import backup_before_migration, database_version


CATALOG_SCHEMA_VERSION = 3


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    volume_id TEXT NOT NULL DEFAULT '',
    relative_root TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'folder',
    label TEXT NOT NULL DEFAULT '',
    online INTEGER NOT NULL DEFAULT 1,
    last_seen REAL,
    last_scan REAL,
    file_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS media_files (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    media_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    modified_ns INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    available INTEGER NOT NULL DEFAULT 1,
    discovered_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(source_id, relative_path)
);
CREATE INDEX IF NOT EXISTS idx_media_fingerprint ON media_files(fingerprint);
CREATE INDEX IF NOT EXISTS idx_media_available_type ON media_files(available, media_type);
CREATE TABLE IF NOT EXISTS analysis_jobs (
    id INTEGER PRIMARY KEY,
    media_id INTEGER NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL DEFAULT 'full_analysis',
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    result_json TEXT NOT NULL DEFAULT '{}',
    analysis_version TEXT NOT NULL DEFAULT '',
    stale_reason TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(media_id, task_type)
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON analysis_jobs(status, updated_at);
CREATE TABLE IF NOT EXISTS media_tags (
    media_id INTEGER NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY(media_id, tag)
);
"""


@dataclass(frozen=True)
class ScanResult:
    source: str
    online: bool
    total: int = 0
    added: int = 0
    changed: int = 0
    unchanged: int = 0
    missing: int = 0
    duplicates: int = 0
    errors: int = 0
    error_details: tuple[dict, ...] = ()
    stopped_early: bool = False
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _media_type(extension: str) -> str | None:
    if extension in VIDEO_EXTENSIONS:
        return "video"
    if extension in AUDIO_EXTENSIONS:
        return "audio"
    if extension in IMAGE_EXTENSIONS:
        return "image"
    return None


def _fingerprint(path: Path, size: int) -> str:
    """Fast content fingerprint using size plus first/last 1 MiB."""
    digest = hashlib.sha256()
    digest.update(str(size).encode("ascii"))
    with path.open("rb") as stream:
        digest.update(stream.read(1024 * 1024))
        if size > 1024 * 1024:
            stream.seek(max(0, size - 1024 * 1024))
            digest.update(stream.read(1024 * 1024))
    return digest.hexdigest()


class Catalog:
    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            paths = RuntimePaths.discover()
            paths.ensure()
            db_path = paths.databases / "materials.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        old_version = database_version(self.db_path)
        self.migration_backup = backup_before_migration(
            self.db_path, old_version, CATALOG_SCHEMA_VERSION
        )
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(sources)")}
            if "volume_id" not in columns:
                connection.execute("ALTER TABLE sources ADD COLUMN volume_id TEXT NOT NULL DEFAULT ''")
            if "relative_root" not in columns:
                connection.execute("ALTER TABLE sources ADD COLUMN relative_root TEXT NOT NULL DEFAULT ''")
            media_columns = {row["name"] for row in connection.execute("PRAGMA table_info(media_files)")}
            if "category" not in media_columns:
                connection.execute("ALTER TABLE media_files ADD COLUMN category TEXT NOT NULL DEFAULT 'unclassified'")
            if "category_source" not in media_columns:
                connection.execute("ALTER TABLE media_files ADD COLUMN category_source TEXT NOT NULL DEFAULT ''")
            job_columns = {row["name"] for row in connection.execute("PRAGMA table_info(analysis_jobs)")}
            if "analysis_version" not in job_columns:
                connection.execute(
                    "ALTER TABLE analysis_jobs ADD COLUMN analysis_version TEXT NOT NULL DEFAULT ''"
                )
            if "stale_reason" not in job_columns:
                connection.execute(
                    "ALTER TABLE analysis_jobs ADD COLUMN stale_reason TEXT NOT NULL DEFAULT ''"
                )
            now = time.time()
            cursor = connection.execute(
                "UPDATE analysis_jobs SET status='not_applicable',attempts=0,"
                "error='This full-analysis job only supports video media.',stale_reason='',updated_at=? "
                "WHERE media_id IN (SELECT id FROM media_files WHERE media_type<>'video') "
                "AND status<>'not_applicable'",
                (now,),
            )
            self.non_video_jobs_retired = int(cursor.rowcount)
            connection.execute(
                "INSERT INTO analysis_jobs(media_id,status,attempts,error,result_json,created_at,updated_at) "
                "SELECT m.id,'pending',0,'','{}',?,? FROM media_files m "
                "WHERE m.available=1 AND m.media_type='video' "
                "AND NOT EXISTS (SELECT 1 FROM analysis_jobs j WHERE j.media_id=m.id)",
                (now, now),
            )
            cursor = connection.execute(
                "UPDATE analysis_jobs SET status='pending',attempts=0,error='',"
                "stale_reason=?,updated_at=? WHERE status='success' AND analysis_version<>? "
                "AND media_id IN (SELECT id FROM media_files WHERE media_type='video')",
                (
                    f"分析管线已升级：旧版本需要重新分析，目标版本 {ANALYSIS_PIPELINE_VERSION}",
                    now,
                    ANALYSIS_PIPELINE_VERSION,
                ),
            )
            self.stale_jobs_requeued = int(cursor.rowcount)
            connection.execute(f"PRAGMA user_version={CATALOG_SCHEMA_VERSION}")

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

    def add_source(self, path: str | Path, kind: str = "folder", label: str = "") -> int:
        normalized = str(Path(path).resolve())
        _, volume_id, relative_root = volume_identity(normalized)
        online = int(Path(normalized).is_dir())
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO sources(path,volume_id,relative_root,kind,label,online,last_seen) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(path) DO UPDATE SET kind=excluded.kind,label=excluded.label,"
                "volume_id=excluded.volume_id,relative_root=excluded.relative_root,online=excluded.online,"
                "last_seen=CASE WHEN excluded.online=1 THEN excluded.last_seen ELSE last_seen END",
                (normalized, volume_id, relative_root, kind, label, online, now),
            )
            row = connection.execute("SELECT id FROM sources WHERE path=?", (normalized,)).fetchone()
            return int(row["id"])

    def list_sources(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT s.id,s.path,s.volume_id,s.relative_root,s.kind,s.label,s.online,s.last_seen,"
                "s.last_scan,s.file_count,"
                "(SELECT COUNT(*) FROM media_files m WHERE m.source_id=s.id AND m.available=1) available_files,"
                "(SELECT COUNT(*) FROM analysis_jobs j JOIN media_files m ON m.id=j.media_id "
                " WHERE m.source_id=s.id AND j.status='failed') failed_jobs "
                "FROM sources s ORDER BY s.path"
            ).fetchall()
        return [dict(row) for row in rows]

    def list_media(self, status: str | None = None, limit: int = 500) -> list[dict]:
        if limit < 0 or limit > 5000:
            raise ValueError("素材列表数量必须在 0 到 5000 之间")
        allowed = {"pending", "retry", "running", "success", "failed", "not_applicable"}
        if status is not None and status not in allowed:
            raise ValueError(f"不支持的分析状态: {status}")
        where = "AND j.status=?" if status else ""
        params = (status, limit) if status else (limit,)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT m.id media_id,m.relative_path,m.media_type,m.category,m.category_source,"
                "m.available,m.size_bytes,m.fingerprint,s.path source_path,s.online source_online,"
                "j.id job_id,j.status,j.attempts,j.error,j.analysis_version,j.stale_reason,j.updated_at,"
                "(SELECT GROUP_CONCAT(tag, ',') FROM "
                "(SELECT tag FROM media_tags t WHERE t.media_id=m.id ORDER BY t.rowid)) tags "
                "FROM media_files m JOIN sources s ON s.id=m.source_id "
                "LEFT JOIN analysis_jobs j ON j.media_id=m.id "
                "WHERE 1=1 " + where + " ORDER BY j.updated_at DESC,m.id LIMIT ?",
                params,
            ).fetchall()
        return [dict(row) | {
            "absolute_path": str(Path(row["source_path"]) / row["relative_path"]),
            "tags": tuple((row["tags"] or "").split(",")) if row["tags"] else (),
        } for row in rows]

    def set_tags(self, media_id: int, tags) -> None:
        cleaned = []
        for tag in tags:
            value = str(tag).strip()
            if not value or len(value) > 20:
                raise ValueError(f"标签必须是非空且不超过 20 个字符: {tag!r}")
            if value not in cleaned:
                cleaned.append(value)
        if len(cleaned) > 20:
            raise ValueError("单个素材最多 20 个标签")
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM media_files WHERE id=?", (media_id,),
            ).fetchone()
            if exists is None:
                raise KeyError(f"素材不存在: {media_id}")
            connection.execute("DELETE FROM media_tags WHERE media_id=?", (media_id,))
            connection.executemany(
                "INSERT INTO media_tags(media_id, tag) VALUES(?,?)",
                [(media_id, tag) for tag in cleaned],
            )

    def retry_analysis(self, media_id: int) -> int:
        now = time.time()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT m.media_type,m.available,s.online,j.id job_id FROM media_files m "
                "JOIN sources s ON s.id=m.source_id LEFT JOIN analysis_jobs j ON j.media_id=m.id "
                "WHERE m.id=?", (media_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"素材不存在: {media_id}")
            if row["media_type"] != "video":
                raise ValueError("当前完整分析只支持视频素材")
            if not row["available"] or not row["online"]:
                raise RuntimeError("素材文件或所在硬盘当前离线")
            if row["job_id"] is None:
                cursor = connection.execute(
                    "INSERT INTO analysis_jobs(media_id,status,attempts,error,result_json,created_at,updated_at) "
                    "VALUES(?,'pending',0,'','{}',?,?)", (media_id, now, 0),
                )
                return int(cursor.lastrowid)
            connection.execute(
                "UPDATE analysis_jobs SET status='pending',attempts=0,error='',stale_reason='用户手动重新分析',"
                "updated_at=? WHERE id=?", (now, row["job_id"]),
            )
            return int(row["job_id"])

    def set_category(self, media_id: int, category: str) -> None:
        from treecut.library.classification import CATEGORY_RULES
        allowed = {*CATEGORY_RULES, "unclassified"}
        if category not in allowed:
            raise ValueError(f"不支持的素材分类: {category}")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE media_files SET category=?,category_source='user_override',updated_at=? WHERE id=?",
                (category, time.time(), media_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"素材不存在: {media_id}")

    def refresh_online_status(self) -> list[dict]:
        now = time.time()
        with self._connect() as connection:
            rows = connection.execute("SELECT id,path FROM sources").fetchall()
            for row in rows:
                online = int(Path(row["path"]).is_dir())
                connection.execute(
                    "UPDATE sources SET online=?,last_seen=CASE WHEN ?=1 THEN ? ELSE last_seen END WHERE id=?",
                    (online, online, now, row["id"]),
                )
                if not online:
                    connection.execute("UPDATE media_files SET available=0 WHERE source_id=?", (row["id"],))
        return self.list_sources()

    def relink_sources(self, drives: list[DriveInfo] | None = None) -> list[dict]:
        """Update stored paths when Windows assigns a known volume a new drive letter."""
        drives = drives if drives is not None else discover_drives()
        roots = {drive.volume_id: drive.root for drive in drives if drive.accessible}
        now = time.time()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id,path,volume_id,relative_root FROM sources WHERE volume_id<>''"
            ).fetchall()
            for row in rows:
                root = roots.get(row["volume_id"])
                if not root:
                    continue
                candidate = str((Path(root) / row["relative_root"]).resolve())
                if candidate == row["path"] or not Path(candidate).is_dir():
                    continue
                conflict = connection.execute(
                    "SELECT id FROM sources WHERE path=? AND id<>?", (candidate, row["id"])
                ).fetchone()
                if conflict:
                    continue
                connection.execute(
                    "UPDATE sources SET path=?,online=1,last_seen=? WHERE id=?",
                    (candidate, now, row["id"]),
                )
        return self.refresh_online_status()

    def scan(self, source: str | Path, kind: str = "folder", label: str = "",
             max_files: int = 500_000) -> ScanResult:
        if max_files < 1:
            raise ValueError("扫描文件上限必须大于 0")
        started = time.perf_counter()
        root = Path(source).resolve()
        source_id = self.add_source(root, kind=kind, label=label)
        if not root.is_dir():
            self.refresh_online_status()
            return ScanResult(str(root), online=False, seconds=round(time.perf_counter() - started, 3))

        with self._connect() as connection:
            existing = {
                row["relative_path"]: row
                for row in connection.execute(
                    "SELECT relative_path,size_bytes,modified_ns,fingerprint FROM media_files WHERE source_id=?",
                    (source_id,),
                )
            }
            seen: set[str] = set()
            added = changed = unchanged = errors = total = 0
            error_details: list[dict] = []
            stopped_early = False
            now = time.time()
            for current, directories, files in os.walk(root, followlinks=False):
                directories[:] = [
                    name for name in directories
                    if not (Path(current) / name).is_symlink()
                    and name.lower() not in {"$recycle.bin", "system volume information", "windows", "program files", "program files (x86)"}
                ]
                for name in files:
                    path = Path(current) / name
                    extension = path.suffix.lower()
                    media_type = _media_type(extension)
                    if media_type is None:
                        continue
                    if total >= max_files:
                        stopped_early = True
                        break
                    total += 1
                    relative = str(path.relative_to(root))
                    seen.add(relative)
                    try:
                        stat = path.stat()
                        old = existing.get(relative)
                        if old and old["size_bytes"] == stat.st_size and old["modified_ns"] == stat.st_mtime_ns:
                            unchanged += 1
                            connection.execute(
                                "UPDATE media_files SET available=1,updated_at=? WHERE source_id=? AND relative_path=?",
                                (now, source_id, relative),
                            )
                            continue
                        fingerprint = _fingerprint(path, stat.st_size)
                        connection.execute(
                            "INSERT INTO media_files(source_id,relative_path,media_type,extension,size_bytes,modified_ns,"
                            "fingerprint,available,discovered_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) "
                            "ON CONFLICT(source_id,relative_path) DO UPDATE SET media_type=excluded.media_type,"
                            "extension=excluded.extension,size_bytes=excluded.size_bytes,modified_ns=excluded.modified_ns,"
                            "fingerprint=excluded.fingerprint,available=1,updated_at=excluded.updated_at",
                            (source_id, relative, media_type, extension, stat.st_size, stat.st_mtime_ns,
                             fingerprint, 1, now, now),
                        )
                        if old:
                            changed += 1
                        else:
                            added += 1
                        media_id = connection.execute(
                            "SELECT id FROM media_files WHERE source_id=? AND relative_path=?",
                            (source_id, relative),
                        ).fetchone()["id"]
                        if media_type == "video":
                            connection.execute(
                                "INSERT INTO analysis_jobs(media_id,status,attempts,error,result_json,created_at,updated_at) "
                                "VALUES(?,'pending',0,'','{}',?,?) ON CONFLICT(media_id,task_type) DO UPDATE SET "
                            "status='pending',attempts=0,error='',result_json='{}',analysis_version='',"
                            "stale_reason='素材文件发生变化',updated_at=excluded.updated_at",
                                (media_id, now, now),
                            )
                    except OSError as error:
                        errors += 1
                        if len(error_details) < 50:
                            error_details.append({
                                "path": str(path),
                                "type": type(error).__name__,
                                "message": str(error),
                            })

                if stopped_early:
                    break

            missing_paths = set() if stopped_early else set(existing) - seen
            if not stopped_early and missing_paths:
                connection.executemany(
                    "UPDATE media_files SET available=0,updated_at=? WHERE source_id=? AND relative_path=?",
                    [(now, source_id, relative) for relative in missing_paths],
                )
            connection.execute(
                "UPDATE sources SET online=1,last_seen=?,last_scan=?,"
                "file_count=CASE WHEN ?=1 THEN file_count ELSE ? END WHERE id=?",
                (now, now, int(stopped_early), total, source_id),
            )
            duplicates = connection.execute(
                "SELECT COALESCE(SUM(c-1),0) AS duplicates FROM ("
                "SELECT COUNT(*) c FROM media_files WHERE available=1 GROUP BY fingerprint HAVING COUNT(*)>1)"
            ).fetchone()["duplicates"]

        return ScanResult(
            source=str(root), online=True, total=total, added=added, changed=changed,
            unchanged=unchanged, missing=len(missing_paths), duplicates=int(duplicates),
            errors=errors, error_details=tuple(error_details), stopped_early=stopped_early,
            seconds=round(time.perf_counter() - started, 3),
        )

    def stats(self) -> dict:
        with self._connect() as connection:
            source_count = connection.execute("SELECT COUNT(*) n FROM sources").fetchone()["n"]
            online_sources = connection.execute("SELECT COUNT(*) n FROM sources WHERE online=1").fetchone()["n"]
            files = connection.execute(
                "SELECT media_type,COUNT(*) n,SUM(size_bytes) bytes FROM media_files WHERE available=1 GROUP BY media_type"
            ).fetchall()
            duplicates = connection.execute(
                "SELECT COALESCE(SUM(c-1),0) n FROM (SELECT COUNT(*) c FROM media_files WHERE available=1 "
                "GROUP BY fingerprint HAVING COUNT(*)>1)"
            ).fetchone()["n"]
        return {
            "sources": source_count,
            "online_sources": online_sources,
            "available": {row["media_type"]: {"count": row["n"], "bytes": row["bytes"]} for row in files},
            "duplicates": int(duplicates),
        }

    def pending_jobs(self, limit: int = 100) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT j.id,j.media_id,j.task_type,j.status,j.attempts,s.path source_path,m.relative_path,"
                "m.media_type,m.fingerprint FROM analysis_jobs j "
                "JOIN media_files m ON m.id=j.media_id JOIN sources s ON s.id=m.source_id "
                "WHERE j.status IN ('pending','retry') AND m.media_type='video' "
                "AND m.available=1 AND s.online=1 "
                "ORDER BY CASE WHEN j.status='retry' THEN 0 ELSE 1 END,j.updated_at,j.id LIMIT ?", (limit,),
            ).fetchall()
        return [dict(row) | {"absolute_path": str(Path(row["source_path"]) / row["relative_path"])} for row in rows]

    def recover_interrupted_jobs(self) -> int:
        """Return jobs abandoned by a previous analysis process to the retry queue."""
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE analysis_jobs SET status='retry',"
                "error='Interrupted: 上次分析进程在完成前退出',updated_at=? "
                "WHERE status='running' AND media_id IN "
                "(SELECT id FROM media_files WHERE media_type='video')", (now,),
            )
            return int(cursor.rowcount)

    def claim_job(self, media_id: int | None = None) -> dict | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            selected = "AND m.id=? " if media_id is not None else ""
            params = (media_id,) if media_id is not None else ()
            row = connection.execute(
                "SELECT j.id,j.media_id,j.task_type,j.attempts,s.path source_path,m.relative_path,m.media_type "
                "FROM analysis_jobs j JOIN media_files m ON m.id=j.media_id "
                "JOIN sources s ON s.id=m.source_id WHERE j.status IN ('pending','retry') "
                "AND m.media_type='video' AND m.available=1 AND s.online=1 "
                + selected + "ORDER BY j.updated_at,j.id LIMIT 1", params
            ).fetchone()
            if row is None:
                return None
            now = time.time()
            connection.execute(
                "UPDATE analysis_jobs SET status='running',attempts=attempts+1,updated_at=? WHERE id=?",
                (now, row["id"]),
            )
            result = dict(row)
            result["attempts"] += 1
            result["absolute_path"] = str(Path(row["source_path"]) / row["relative_path"])
            return result

    def complete_job(self, job_id: int, result: dict, category: str = "unclassified",
                     category_source: str = "model",
                     analysis_version: str = ANALYSIS_PIPELINE_VERSION) -> None:
        now = time.time()
        with self._connect() as connection:
            row = connection.execute("SELECT media_id FROM analysis_jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(f"分析任务不存在: {job_id}")
            connection.execute(
                "UPDATE analysis_jobs SET status='success',error='',result_json=?,analysis_version=?,"
                "stale_reason='',updated_at=? WHERE id=?",
                (json.dumps(result, ensure_ascii=False), analysis_version, now, job_id),
            )
            connection.execute(
                "UPDATE media_files SET category=?,category_source=? WHERE id=?",
                (category, category_source, row["media_id"]),
            )

    def enrich_job_result(self, job_id: int, additions: dict, category: str | None = None,
                          category_source: str | None = None) -> None:
        """Merge verified later-stage evidence without discarding probe/frame results."""
        now = time.time()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT media_id,status,result_json FROM analysis_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"分析任务不存在：{job_id}")
            if row["status"] != "success":
                raise RuntimeError(f"只能补充已成功任务，当前状态：{row['status']}")
            result = json.loads(row["result_json"] or "{}")
            result.update(additions)
            connection.execute(
                "UPDATE analysis_jobs SET result_json=?,updated_at=? WHERE id=?",
                (json.dumps(result, ensure_ascii=False), now, job_id),
            )
            if category is not None:
                connection.execute(
                    "UPDATE media_files SET category=?,category_source=? WHERE id=?",
                    (category, category_source or "vision_model", row["media_id"]),
                )

    def fail_job(self, job_id: int, error: str, max_attempts: int = 3) -> str:
        now = time.time()
        with self._connect() as connection:
            row = connection.execute("SELECT attempts FROM analysis_jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(f"分析任务不存在: {job_id}")
            status = "failed" if row["attempts"] >= max_attempts else "retry"
            connection.execute(
                "UPDATE analysis_jobs SET status=?,error=?,updated_at=? WHERE id=?",
                (status, error[:2000], now, job_id),
            )
            return status

    def job_stats(self) -> dict:
        with self._connect() as connection:
            rows = connection.execute("SELECT status,COUNT(*) n FROM analysis_jobs GROUP BY status").fetchall()
        return {row["status"]: row["n"] for row in rows}

    def referenced_frame_directories(self) -> set[str]:
        """Return frame directories still referenced by any preserved analysis result."""
        referenced: set[str] = set()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT result_json FROM analysis_jobs WHERE result_json<>'' AND result_json<>'{}'"
            ).fetchall()
        for row in rows:
            try:
                frames = (json.loads(row["result_json"]) or {}).get("frames") or []
            except (TypeError, json.JSONDecodeError):
                continue
            for frame in frames:
                path = frame.get("path") if isinstance(frame, dict) else frame
                if path:
                    referenced.add(str(Path(path).parent.resolve()))
        return referenced
