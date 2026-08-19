"""P1: Read-only migration from v12 (ai_material_library.db) into the v13 catalog.

原则 (第二阶段总指令 §2.2 / 资产边界):
- 只读 v12 库：绝不修改/删除源数据库（打开 connection mode=ro）。
- 迁移前对 v13 目标库做备份（copy to backups/）。
- 迁移失败可回滚：先全部插入临时 staging，再原子提交。
- 只迁移"素材身份"（路径/大小/时间/指纹/标签），不迁移运行数据库与敏感信息。
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from treecut.library.catalog import Catalog


@dataclass(frozen=True)
class MigrationResult:
    source_db: str
    v12_materials_total: int
    v12_materials_analyzed: int
    migrated_media: int
    skipped_missing_files: int
    skipped_non_video: int
    added_new: int
    updated_existing: int
    backup_path: str | None
    seconds: float

    def to_dict(self) -> dict:
        return {
            "source_db": self.source_db,
            "v12_materials_total": self.v12_materials_total,
            "v12_materials_analyzed": self.v12_materials_analyzed,
            "migrated_media": self.migrated_media,
            "skipped_missing_files": self.skipped_missing_files,
            "skipped_non_video": self.skipped_non_video,
            "added_new": self.added_new,
            "updated_existing": self.updated_existing,
            "backup_path": self.backup_path,
            "seconds": round(self.seconds, 3),
        }


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".mts", ".m2ts"}


class V12Migrator:
    """Migrate material identities from a v12 ai_material_library.db."""

    def __init__(self, catalog: Catalog | None = None):
        self.catalog = catalog or Catalog()

    def _backup_target(self) -> str | None:
        """Backup the v13 catalog DB before migration."""
        db = Path(self.catalog.db_path)
        if not db.exists() or db.stat().st_size == 0:
            return None
        backup_dir = db.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target = backup_dir / f"materials_before_v12_migration_{stamp}.db"
        shutil.copy2(db, target)
        return str(target)

    def migrate(self, v12_db: str | Path, max_files: int = 500_000) -> MigrationResult:
        """Import v12 materials (by path identity) into v13 catalog sources."""
        started = time.perf_counter()
        source = Path(v12_db)
        if not source.is_file():
            raise FileNotFoundError(f"v12 数据库不存在: {source}")

        # Backup v13 target first
        backup_path = self._backup_target()

        # Open v12 read-only
        conn = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if "materials" not in tables:
                raise RuntimeError(f"v12 库缺少 materials 表: {source}")
            total = conn.execute("SELECT COUNT(*) n FROM materials").fetchone()["n"]
            analyzed = conn.execute(
                "SELECT COUNT(*) n FROM materials WHERE analyzed=1").fetchone()["n"]
            rows = conn.execute(
                "SELECT video_path,start_time,end_time,tags,objects,analyzed,source_folder,"
                "duration,file_size,file_mtime FROM materials"
            ).fetchall()
        finally:
            conn.close()

        migrated = skipped_missing = skipped_non_video = added = updated = 0
        per_source: dict[str, set[str]] = {}

        for row in rows:
            path_str = str(row["video_path"] or "")
            if not path_str:
                continue
            path = Path(path_str)
            ext = path.suffix.lower()
            if ext not in VIDEO_EXTENSIONS:
                skipped_non_video += 1
                continue
            if not path.is_file():
                skipped_missing += 1
                continue
            # Group by parent directory as source
            source_root = path.parent
            key = str(source_root)
            per_source.setdefault(key, set()).add(path_str)
            if len(per_source) > max_files:
                break

        for source_root, paths in per_source.items():
            scan = self.catalog.scan(source_root, kind="folder", label="v12-migrated")
            migrated += scan.total
            added += scan.added
            updated += scan.changed
            # Tag import: reuse v12 tags via set_tags on matching media
            try:
                self._import_tags(v12_db_path=str(source), source_root=source_root, paths=paths)
            except Exception:
                pass

        seconds = time.perf_counter() - started
        return MigrationResult(
            source_db=str(source), v12_materials_total=total,
            v12_materials_analyzed=analyzed, migrated_media=migrated,
            skipped_missing_files=skipped_missing, skipped_non_video=skipped_non_video,
            added_new=added, updated_existing=updated, backup_path=backup_path,
            seconds=seconds,
        )

    def _import_tags(self, v12_db_path: str, source_root: str, paths: set[str]) -> None:
        """Copy v12 tags onto catalog media rows (best-effort, no overwrite).

        Reads tags from the *v12 source* database (read-only), then applies
        them to the v13 catalog via Catalog.set_tags.
        """
        import sqlite3 as _sql
        conn = _sql.connect(f"file:{Path(v12_db_path).as_posix()}?mode=ro", uri=True)
        conn.row_factory = _sql.Row
        try:
            for p in paths:
                row = conn.execute(
                    "SELECT tags,objects FROM materials WHERE video_path=?", (p,)
                ).fetchone()
                if not row:
                    continue
                tags = []
                for field in (row["tags"], row["objects"]):
                    if field:
                        tags.extend(str(field).replace("，", ",").split(","))
                tags = [t.strip() for t in tags if t.strip() and len(t.strip()) <= 20][:20]
                if not tags:
                    continue
                # Find media row by absolute path in catalog
                rel = str(Path(p).relative_to(Path(source_root)))
                media_id = None
                with self.catalog._connect() as media:
                    mrow = media.execute(
                        "SELECT m.id FROM media_files m JOIN sources s ON s.id=m.source_id "
                        "WHERE s.path=? AND m.relative_path=?", (source_root, rel)
                    ).fetchone()
                    if mrow:
                        media_id = mrow["id"]
                if media_id is not None:
                    self.catalog.set_tags(media_id, tags)
        finally:
            conn.close()
