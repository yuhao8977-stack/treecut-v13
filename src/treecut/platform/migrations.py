"""TreeCut Migration 框架（Phase 0.4）。

正式迁移管理：
  - migrations/ 目录存放版本化迁移脚本（NNN_name.sql 或 .py）
  - schema_migrations 表记录 applied 迁移（version/name/git_commit/checksum/applied_at/status）
  - 只支持前向迁移，不删除现有表；rollback 依赖数据库备份

用法：
  from treecut.platform.migrations import MigrationManager
  mgr = MigrationManager(db_path)
  mgr.init()            # 建 schema_migrations 表 + 写入 baseline
  mgr.status()          # 查看已应用迁移
  mgr.apply_pending()   # 应用未执行的迁移
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

# schema_migrations 表定义
MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    version      TEXT NOT NULL UNIQUE,      -- 如 '0001'
    name         TEXT NOT NULL,             -- 迁移名
    git_commit   TEXT NOT NULL DEFAULT '',
    checksum     TEXT NOT NULL DEFAULT '',
    applied_at   REAL NOT NULL,
    status       TEXT NOT NULL DEFAULT 'applied',  -- applied|failed|rolled_back
    notes        TEXT NOT NULL DEFAULT ''
)
"""

# Phase 0 baseline：当前数据库所有已有 Schema 的基线记录
# （v13 各阶段通过 CREATE TABLE IF NOT EXISTS 累积出的 45 张表）
BASELINE_MIGRATION = {
    "version": "0001",
    "name": "baseline_v13_schema",
    "notes": (
        "Phase 0 baseline：冻结 v13.5.15 现有全部 Schema（45 表），"
        "包含 P1 资产/生命周期、P2 场景/关键帧/ASR/OCR、P2.5 任务、"
        "P2.7 质量验证、Brain 认知 6 表、Phase6 content_value 等。"
        "所有表由历史 CREATE TABLE IF NOT EXISTS 累积生成，本迁移仅登记基线。"
    ),
}


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class MigrationManager:
    """统一迁移管理：登记、应用、状态查询。"""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)
        self.migrations_dir = Path(__file__).resolve().parent.parent.parent.parent / "migrations"
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> dict:
        """建 schema_migrations 表 + 写入 baseline 记录（幂等）。"""
        with self._connect() as conn:
            conn.execute(MIGRATIONS_TABLE_SQL)
            # 检查 baseline 是否已存在
            row = conn.execute(
                "SELECT id FROM schema_migrations WHERE version=?",
                (BASELINE_MIGRATION["version"],)).fetchone()
            if row is None:
                payload = json.dumps(BASELINE_MIGRATION, ensure_ascii=False)
                conn.execute(
                    "INSERT INTO schema_migrations(version,name,git_commit,checksum,"
                    "applied_at,status,notes) VALUES(?,?,?,?,?,?,?)",
                    (BASELINE_MIGRATION["version"], BASELINE_MIGRATION["name"],
                     self._current_git_commit(), _checksum(payload),
                     time.time(), "applied", BASELINE_MIGRATION["notes"]))
            conn.commit()
        return self.status()

    def _current_git_commit(self) -> str:
        try:
            import subprocess
            # 仓库根 = 本文件 src/treecut/platform/ 向上 4 级
            repo = Path(__file__).resolve().parents[3]
            out = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=10)
            return out.stdout.strip() if out.returncode == 0 else ""
        except Exception:
            return ""

    def status(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT version, name, git_commit, checksum, applied_at, status, notes "
                "FROM schema_migrations ORDER BY version").fetchall()
        return [dict(r) for r in rows]

    def apply_pending(self) -> dict:
        """扫描 migrations/ 目录，应用版本号大于已应用的最新迁移。"""
        applied = {r["version"] for r in self.status()}
        files = sorted(self.migrations_dir.glob("*.sql"))
        results = []
        for f in files:
            version = f.stem.split("_", 1)[0]
            if version in applied:
                continue
            sql = f.read_text(encoding="utf-8")
            with self._connect() as conn:
                try:
                    conn.executescript(sql)
                    conn.execute(
                        "INSERT INTO schema_migrations(version,name,git_commit,checksum,"
                        "applied_at,status,notes) VALUES(?,?,?,?,?,?,?)",
                        (version, f.stem, self._current_git_commit(),
                         _checksum(sql), time.time(), "applied",
                         f"from {f.name}"))
                    conn.commit()
                    results.append({"version": version, "name": f.stem, "status": "applied"})
                except Exception as e:
                    conn.rollback()
                    results.append({"version": version, "name": f.stem,
                                    "status": "failed", "error": str(e)})
        return {"applied": results, "pending_remaining": len(files) - len(applied) - len(results)}

    def create_migration(self, name: str, sql: str) -> Path:
        """创建新迁移文件（自动编号）。"""
        applied = {r["version"] for r in self.status()}
        nxt = f"{int(max(applied, default='0000')) + 1:04d}"
        path = self.migrations_dir / f"{nxt}_{name}.sql"
        header = (f"-- Migration {nxt}: {name}\n"
                  f"-- git_commit: {self._current_git_commit()}\n"
                  f"-- checksum: {_checksum(sql)}\n\n")
        path.write_text(header + sql, encoding="utf-8")
        return path
