"""P2.5: TaskStore — analysis_tasks table + atomic claim (BEGIN IMMEDIATE).

旁路设计：本模块只新增 analysis_tasks / schema_version 两张表，绝不修改
任何既有表结构；旧 --p2-run / asset_processing_state 逻辑保持原样。
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path

from treecut.database import backup_before_migration

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
SCHEMA_NAME = "analysis_tasks"

# 任务类型（与 Worker 分片对应）
TASK_TYPES = ("vision", "asr", "ocr", "full", "segment", "embedding")

# 状态
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
ALL_STATUSES = {STATUS_PENDING, STATUS_PROCESSING, STATUS_COMPLETED,
                STATUS_FAILED, STATUS_SKIPPED}

DEFAULT_MAX_RETRY = 3
STALE_AFTER_SECONDS = 1800.0  # processing 超过 30 分钟视为失联可回收

SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_tasks (
    task_id       TEXT PRIMARY KEY,
    asset_id      TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    task_type     TEXT NOT NULL,
    stages        TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',
    worker_id     TEXT NOT NULL DEFAULT '',
    priority      INTEGER NOT NULL DEFAULT 0,
    retry_count   INTEGER NOT NULL DEFAULT 0,
    attempt       INTEGER NOT NULL DEFAULT 0,
    error         TEXT NOT NULL DEFAULT '',
    created_time  REAL NOT NULL,
    started_time  REAL,
    finished_time REAL
);
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_status
    ON analysis_tasks(status, priority DESC, created_time);
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_asset
    ON analysis_tasks(asset_id);

CREATE TABLE IF NOT EXISTS schema_version (
    name    TEXT PRIMARY KEY,
    version INTEGER NOT NULL
);
"""


class TaskStore:
    """analysis_tasks 的创建/领取/完成/恢复。线程安全（每调用独立连接+事务）。"""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)

    # ------------------------------------------------------------------
    # 连接与 schema
    # ------------------------------------------------------------------

    def _connect(self):
        connection = sqlite3.connect(str(self.db_path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def ensure_schema(self) -> int:
        """CREATE TABLE IF NOT EXISTS + schema_version 记录。幂等、可重入。"""
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
            elif row["version"] < SCHEMA_VERSION:
                # 未来版本升级点：在此追加 ALTER 逻辑
                connection.execute(
                    "UPDATE schema_version SET version=? WHERE name=?",
                    (SCHEMA_VERSION, SCHEMA_NAME),
                )
            connection.commit()
        return SCHEMA_VERSION

    def schema_status(self) -> dict:
        """返回 schema_version 表内容（多模块各自版本互不覆盖）。"""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT name,version FROM schema_version ORDER BY name"
            ).fetchall()
        return {row["name"]: row["version"] for row in rows}

    def migrate_if_needed(self) -> Path | None:
        """迁移前备份（仅当 analysis_tasks 表不存在且库非空时）。"""
        backup = backup_before_migration(self.db_path, 0, SCHEMA_VERSION)
        self.ensure_schema()
        return backup

    # ------------------------------------------------------------------
    # 任务创建（幂等）
    # ------------------------------------------------------------------

    def create_task(self, asset_id: str, task_type: str, stages: str = "",
                    priority: int = 0) -> bool:
        """创建单个任务；同一 (asset_id, task_type) 已存在则跳过。返回是否新建。"""
        if task_type not in TASK_TYPES:
            raise ValueError(f"非法任务类型: {task_type}")
        now = time.time()
        task_id = f"p25_{uuid.uuid4().hex}"
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO analysis_tasks"
                "(task_id,asset_id,task_type,stages,status,worker_id,priority,"
                "retry_count,attempt,error,created_time,started_time,finished_time) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, asset_id, task_type, stages, STATUS_PENDING, "", priority,
                 0, 0, "", now, None, None),
            )
            connection.commit()
            return cursor.rowcount > 0

    def create_tasks(self, items: list[dict], task_type: str,
                     stages: str = "", priority: int = 0) -> int:
        """批量创建；已存在的 (asset_id, task_type) 自动跳过。返回新建数。"""
        created = 0
        with closing(self._connect()) as connection:
            for item in items:
                asset_id = item["asset_id"] if isinstance(item, dict) else item
                now = time.time()
                task_id = f"p25_{uuid.uuid4().hex}"
                cursor = connection.execute(
                    "INSERT OR IGNORE INTO analysis_tasks"
                    "(task_id,asset_id,task_type,stages,status,worker_id,priority,"
                    "retry_count,attempt,error,created_time,started_time,finished_time) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (task_id, asset_id, task_type, stages, STATUS_PENDING, "", priority,
                     0, 0, "", now, None, None),
                )
                created += int(cursor.rowcount > 0)
            connection.commit()
        return created

    def has_pending(self, task_type: str = "") -> bool:
        with closing(self._connect()) as connection:
            if task_type:
                row = connection.execute(
                    "SELECT 1 FROM analysis_tasks WHERE status='pending' AND task_type=? LIMIT 1",
                    (task_type,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT 1 FROM analysis_tasks WHERE status='pending' LIMIT 1"
                ).fetchone()
        return row is not None

    def pending_count(self, task_type: str = "") -> int:
        with closing(self._connect()) as connection:
            if task_type:
                return int(connection.execute(
                    "SELECT COUNT(*) n FROM analysis_tasks WHERE status='pending' AND task_type=?",
                    (task_type,),
                ).fetchone()["n"])
            return int(connection.execute(
                "SELECT COUNT(*) n FROM analysis_tasks WHERE status='pending'"
            ).fetchone()["n"])

    # ------------------------------------------------------------------
    # 原子领取（防双领核心）
    # ------------------------------------------------------------------

    def claim_task(self, worker_id: str, task_type: str = "",
                   stages: str = "", max_retry: int = DEFAULT_MAX_RETRY) -> dict | None:
        """原子领取一个 pending 任务。

        BEGIN IMMEDIATE 串行化写事务；UPDATE 带 status='pending' 条件 + rowcount
        校验，任何并发下同一任务只会被一个 Worker 领走。
        """
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                where = "t.status='pending' AND t.retry_count<=?"
                params: list = [max_retry]
                if task_type:
                    where += " AND t.task_type=?"
                    params.append(task_type)
                if stages:
                    where += " AND (t.stages=? OR t.stages='')"
                    params.append(stages)
                row = connection.execute(
                    f"SELECT t.task_id,t.asset_id,t.task_type,t.stages,t.priority,"
                    f"a.media_id,m.relative_path,s.path AS source_path,"
                    f"m.available,s.online "
                    f"FROM analysis_tasks t "
                    f"JOIN assets a ON a.asset_id=t.asset_id "
                    f"JOIN media_files m ON m.id=a.media_id "
                    f"JOIN sources s ON s.id=m.source_id "
                    f"WHERE {where} AND m.available=1 AND s.online=1 "
                    f"ORDER BY t.priority DESC,t.created_time LIMIT 1",
                    params,
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return None
                now = time.time()
                cursor = connection.execute(
                    "UPDATE analysis_tasks SET status=?,worker_id=?,started_time=?,"
                    "attempt=attempt+1 WHERE task_id=? AND status='pending'",
                    (STATUS_PROCESSING, worker_id, now, row["task_id"]),
                )
                if cursor.rowcount != 1:
                    connection.rollback()
                    return None
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        item = dict(row)
        item["absolute_path"] = str(Path(row["source_path"]) / row["relative_path"])
        return item

    # ------------------------------------------------------------------
    # 完成 / 失败 / 跳过
    # ------------------------------------------------------------------

    def complete_task(self, task_id: str, result_count: int = 0) -> None:
        now = time.time()
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE analysis_tasks SET status=?,finished_time=?,error='' WHERE task_id=?",
                (STATUS_COMPLETED, now, task_id),
            )
            connection.commit()

    def skip_task(self, task_id: str, reason: str = "") -> None:
        now = time.time()
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE analysis_tasks SET status=?,finished_time=?,error=? WHERE task_id=?",
                (STATUS_SKIPPED, now, reason[:500], task_id),
            )
            connection.commit()

    def fail_task(self, task_id: str, error: str, retryable: bool = True,
                  max_retry: int = DEFAULT_MAX_RETRY) -> None:
        now = time.time()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT retry_count FROM analysis_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            retry_count = row["retry_count"] if row else 0
            if retryable and retry_count < max_retry:
                connection.execute(
                    "UPDATE analysis_tasks SET status=?,worker_id='',started_time=NULL,"
                    "retry_count=?,error=?,finished_time=NULL WHERE task_id=?",
                    (STATUS_PENDING, retry_count + 1, error[:500], task_id),
                )
            else:
                connection.execute(
                    "UPDATE analysis_tasks SET status=?,finished_time=?,error=? WHERE task_id=?",
                    (STATUS_FAILED, now, error[:500], task_id),
                )
            connection.commit()

    # ------------------------------------------------------------------
    # 断点恢复
    # ------------------------------------------------------------------

    def recover_stale(self, max_age_seconds: float = STALE_AFTER_SECONDS) -> int:
        """processing 超时（Worker 崩溃/被 kill）→ 回收为 pending，attempt+1。"""
        cutoff = time.time() - max_age_seconds
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE analysis_tasks SET status='pending',worker_id='',started_time=NULL,"
                "retry_count=retry_count+1,error='recovered: worker 失联超时' "
                "WHERE status='processing' AND started_time<?",
                (cutoff,),
            )
            connection.commit()
            return int(cursor.rowcount)

    def recover_all_processing(self) -> int:
        """启动时兜底：把所有 processing（含刚被 kill 的）交还 pending。"""
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE analysis_tasks SET status='pending',worker_id='',started_time=NULL,"
                "retry_count=retry_count+1,error='recovered: 进程启动回收' "
                "WHERE status='processing'"
            )
            connection.commit()
            return int(cursor.rowcount)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT status,COUNT(*) n FROM analysis_tasks GROUP BY status"
            ).fetchall()
            by_type = connection.execute(
                "SELECT task_type,status,COUNT(*) n FROM analysis_tasks "
                "GROUP BY task_type,status"
            ).fetchall()
        statuses = {row["status"]: row["n"] for row in rows}
        return {
            "total": sum(statuses.values()),
            "by_status": statuses,
            "by_type": {
                f"{r['task_type']}/{r['status']}": r["n"] for r in by_type
            },
        }
