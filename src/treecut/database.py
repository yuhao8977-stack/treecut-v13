"""Versioned SQLite migration helpers with same-drive recoverable backups."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import time
from contextlib import closing


def database_version(path: Path) -> int:
    if not path.is_file() or path.stat().st_size == 0:
        return 0
    with closing(sqlite3.connect(path)) as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


def has_user_tables(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    with closing(sqlite3.connect(path)) as connection:
        return bool(connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone())


def backup_before_migration(path: Path, old_version: int, new_version: int) -> Path | None:
    if old_version >= new_version or not has_user_tables(path):
        return None
    resolved = path.resolve()
    if resolved.is_symlink():
        raise RuntimeError(f"拒绝迁移符号链接数据库: {resolved}")
    backup_dir = resolved.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{resolved.stem}_schema{old_version}_to_{new_version}_{time.time_ns()}.db"
    with closing(sqlite3.connect(resolved)) as source:
        with closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
            destination.commit()
    return target


def verify_integrity(path: Path, quick: bool = False) -> str:
    """Return PRAGMA integrity_check result; 'ok' means the database is healthy."""
    if not path.is_file():
        return "missing"
    try:
        with closing(sqlite3.connect(path)) as connection:
            command = "PRAGMA quick_check" if quick else "PRAGMA integrity_check"  # treecut_quick_check_patch
            return str(connection.execute(command).fetchone()[0])
    except Exception as error:
        return f"error:{type(error).__name__}"
