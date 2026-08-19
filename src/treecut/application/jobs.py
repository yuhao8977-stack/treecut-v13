"""Persistent local production-job journal stored beside other TreeCut databases."""
from __future__ import annotations

from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
import time

from treecut.database import backup_before_migration, database_version


JOB_SCHEMA_VERSION = 1


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS production_jobs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    state TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_production_jobs_state ON production_jobs(state, updated_at);
"""


class JobJournal:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            old_version = database_version(path)
            self.migration_backup = backup_before_migration(
                path, old_version, JOB_SCHEMA_VERSION,
            )
            with self._connect() as connection:
                connection.executescript(SCHEMA)
                connection.execute(f"PRAGMA user_version={JOB_SCHEMA_VERSION}")
        except sqlite3.DatabaseError:
            # 任务记录库损坏时保留现场（改名备份）并重建，保证软件仍可启动。
            corrupt = path.with_name(
                f"{path.stem}.corrupt_{time.strftime('%Y%m%d_%H%M%S')}",
            )
            try:
                path.replace(corrupt)
            except OSError:
                path.unlink(missing_ok=True)
            self.migration_backup = None
            with self._connect() as connection:
                connection.executescript(SCHEMA)
                connection.execute(f"PRAGMA user_version={JOB_SCHEMA_VERSION}")

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def mark_interrupted(self, current_session: str) -> int:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE production_jobs SET state='failed',message='上次运行被中断',"
                "error='Interrupted: 软件或存储设备在任务完成前退出，请点击重试',updated_at=? "
                "WHERE state IN ('queued','running') AND session_id<>?",
                (now, current_session),
            )
            return int(cursor.rowcount)

    def save(self, job: dict, request: dict | None = None) -> None:
        now = time.time()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT request_json FROM production_jobs WHERE id=?", (job["id"],),
            ).fetchone()
            request_json = json.dumps(request, ensure_ascii=False) if request is not None else (
                existing["request_json"] if existing else "{}"
            )
            connection.execute(
                "INSERT INTO production_jobs(id,session_id,state,message,created_at,updated_at,"
                "request_json,result_json,error) VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET session_id=excluded.session_id,state=excluded.state,"
                "message=excluded.message,updated_at=excluded.updated_at,result_json=excluded.result_json,"
                "error=excluded.error",
                (job["id"], job["session_id"], job["state"], job["message"],
                 float(job["created_at"]), now, request_json,
                 json.dumps(job.get("result"), ensure_ascii=False) if job.get("result") is not None else None,
                 job.get("error")),
            )

    def get(self, job_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM production_jobs WHERE id=?", (job_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"], "session_id": row["session_id"], "state": row["state"],
            "message": row["message"], "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": row["error"], "request": json.loads(row["request_json"]),
        }

    def recent(self, limit: int = 100) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM production_jobs ORDER BY created_at DESC LIMIT ?", (max(0, limit),),
            ).fetchall()
        result = []
        for row in rows:
            result.append({
                "id": row["id"], "session_id": row["session_id"], "state": row["state"],
                "message": row["message"], "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "error": row["error"], "request": json.loads(row["request_json"]),
            })
        return result

    def import_legacy(self, legacy_path: Path) -> int:
        """Merge a legacy journal, keeping the newest record for duplicate ids."""
        if legacy_path.resolve() == self.path.resolve() or not legacy_path.is_file():
            return 0
        with closing(sqlite3.connect(legacy_path)) as source:
            source.row_factory = sqlite3.Row
            table = source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='production_jobs'"
            ).fetchone()
            rows = source.execute("SELECT * FROM production_jobs").fetchall() if table else []
        imported = 0
        with self._connect() as target:
            for row in rows:
                cursor = target.execute(
                    "INSERT INTO production_jobs(id,session_id,state,message,created_at,updated_at,"
                    "request_json,result_json,error) VALUES(?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET session_id=excluded.session_id,state=excluded.state,"
                    "message=excluded.message,created_at=excluded.created_at,updated_at=excluded.updated_at,"
                    "request_json=excluded.request_json,result_json=excluded.result_json,error=excluded.error "
                    "WHERE excluded.updated_at>production_jobs.updated_at",
                    tuple(row[name] for name in (
                        "id", "session_id", "state", "message", "created_at", "updated_at",
                        "request_json", "result_json", "error",
                    )),
                )
                imported += int(cursor.rowcount > 0)
        return imported


def open_job_journal(databases: Path) -> JobJournal:
    """One shared desktop/API history, with idempotent legacy import."""
    journal = JobJournal(databases / "jobs.db")
    journal.legacy_imported = sum(
        journal.import_legacy(databases / name)
        for name in ("desktop_jobs.db", "production_jobs.db")
    )
    return journal
