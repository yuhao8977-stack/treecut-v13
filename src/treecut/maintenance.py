"""One-stop data backup and safe output cleanup (recycle-bin based)."""
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from treecut.platform.paths import RuntimePaths


def backup_data(paths: RuntimePaths, destination: Path) -> Path:
    """Copy databases and settings into a timestamped backup folder."""
    target = destination / f"treecut_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for source in sorted((paths.databases / "backups").parent.glob("*.db")):
        if source.is_file():
            shutil.copy2(source, target / source.name)
            copied += 1
    settings = paths.data_root / "config" / "settings.json"
    if settings.is_file():
        shutil.copy2(settings, target / "settings.json")
    if copied == 0 and not (target / "settings.json").is_file():
        raise RuntimeError("没有找到可备份的数据文件")
    return target


def _trash(path: Path) -> None:
    escaped = str(path).replace("'", "''")
    script = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("
        f"'{escaped}', 'OnlyErrorDialogs', 'SendToRecycleBin')"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, check=False, timeout=180,
        )
    except Exception as error:
        raise RuntimeError(f"无法调用回收站（{type(error).__name__}）：{path}") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"无法安全删除（移入回收站失败）：{path} {detail}")


def cleanup_outputs(paths: RuntimePaths, keep: int = 20) -> list[str]:
    """Move oldest project folders to the recycle bin, keeping the newest N."""
    projects = paths.output / "projects"
    if not projects.is_dir():
        return []
    entries = sorted(
        (item for item in projects.iterdir() if item.is_dir() and not item.is_symlink()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    removed: list[str] = []
    for stale in entries[keep:]:
        _trash(stale)
        removed.append(stale.name)
    return removed


def restore_data(paths: RuntimePaths, backup_dir: Path) -> list[str]:
    """Restore databases from a backup folder (current data is backed up first)."""
    backup_dir = Path(backup_dir)
    if not backup_dir.is_dir():
        raise RuntimeError(f"备份目录不存在: {backup_dir}")
    guard = backup_data(paths, paths.databases / "restore_guard")
    restored = []
    for name in ("materials.db", "jobs.db", "desktop_jobs.db", "feedback.db"):
        source = backup_dir / name
        if source.is_file():
            shutil.copy2(source, paths.databases / name)
            restored.append(name)
    if not restored:
        raise RuntimeError("备份目录里没有可恢复的数据库文件")
    return restored + [f"当前数据已临时备份到 {guard.name}"]


def auto_backup(paths: RuntimePaths, keep: int = 7) -> Path:
    """Create a timestamped backup and prune old automatic backups."""
    target = backup_data(paths, paths.data_root / "backups" / "auto")
    auto_root = paths.data_root / "backups" / "auto"
    entries = sorted(
        (item for item in auto_root.glob("treecut_backup_*") if item.is_dir()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for stale in entries[keep:]:
        try:
            _trash(stale)
        except Exception:
            pass
    return target


def export_project(project_dir: Path, destination: Path) -> Path:
    """Copy one production project folder to a chosen destination."""
    project_dir = Path(project_dir)
    destination = Path(destination)
    if not project_dir.is_dir():
        raise RuntimeError(f"项目目录不存在: {project_dir}")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / project_dir.name
    if target.exists():
        raise RuntimeError(f"目标位置已存在同名项目: {target}")
    shutil.copytree(project_dir, target)
    return target


def export_tags_csv(paths: RuntimePaths, output: Path) -> Path:
    """Export material id/path/tags to a UTF-8 CSV for editing or backup."""
    import sqlite3
    from contextlib import closing
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(paths.databases / "materials.db")) as connection:
        rows = connection.execute(
            "SELECT m.id, s.path || '\\' || m.relative_path, "
            "(SELECT GROUP_CONCAT(tag, '、') FROM "
            "(SELECT tag FROM media_tags t WHERE t.media_id=m.id ORDER BY t.rowid)) "
            "FROM media_files m JOIN sources s ON s.id=m.source_id ORDER BY m.id"
        ).fetchall()
    lines = ["media_id\tpath\ttags"]
    for media_id, path, tags in rows:
        lines.append(f"{media_id}\t{path}\t{tags or ''}")
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def import_tags_csv(paths: RuntimePaths, source: Path) -> int:
    """Import media_id\\tpath\\ttags rows; unknown media ids are skipped."""
    import sqlite3
    from treecut.library import Catalog
    catalog = Catalog(paths.databases / "materials.db")
    text = Path(source).read_text(encoding="utf-8")
    imported = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("media_id"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        try:
            media_id = int(parts[0])
        except ValueError:
            continue
        tags = [tag.strip() for tag in parts[2].replace("、", ",").split(",") if tag.strip()]
        try:
            catalog.set_tags(media_id, tags)
            imported += 1
        except (KeyError, ValueError):
            continue
    return imported


def _recent_jobs_summary(db_path: Path, limit: int = 20) -> list[dict]:
    """Read the latest production jobs without opening the database for writing."""
    import json
    import sqlite3
    if not db_path.is_file():
        return []
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                "SELECT id,state,message,created_at,updated_at,error "
                "FROM production_jobs ORDER BY updated_at DESC LIMIT ?", (limit,),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows]
    except Exception as error:
        return [{"error": f"{type(error).__name__}: {error}"}]


def _database_health(paths: RuntimePaths) -> dict[str, str]:
    from treecut.database import verify_integrity
    health: dict[str, str] = {}
    for name in ("materials.db", "jobs.db", "desktop_jobs.db", "feedback.db"):
        health[name] = verify_integrity(paths.databases / name, quick=True)  # treecut_quick_check_patch
    return health


def _media_count(paths: RuntimePaths) -> int:
    import sqlite3
    from contextlib import closing
    try:
        with closing(sqlite3.connect(f"file:{paths.databases / 'materials.db'}?mode=ro",
                                     uri=True, timeout=5)) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM media_files").fetchone()[0])
    except Exception:
        return -1


def _free_gb(paths: RuntimePaths):
    import shutil
    try:
        return round(shutil.disk_usage(paths.data_root).free / 2**30, 2)
    except OSError as error:
        return f"unavailable: {error}"


def _log_tail(paths: RuntimePaths, lines: int = 30) -> list[str]:
    log = paths.logs / "treecut.log"
    if not log.is_file():
        return []
    try:
        return log.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return []


def treecut_version(paths: RuntimePaths) -> str:
    """Read the single version source (pyproject.toml) so updates bump it too."""
    try:
        pyproject = paths.install_root / "pyproject.toml"
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("version"):
                return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "13.5.10"


def collect_diagnostic_report(paths: RuntimePaths) -> dict:
    """Full status report used by the offline diagnostic bundle."""
    import platform
    import sys

    capabilities: dict = {}
    try:
        from treecut.platform.capabilities import detect_capabilities
        capabilities = detect_capabilities(paths).to_dict()
    except Exception as error:
        capabilities = {"error": f"{type(error).__name__}: {error}"}

    logs_included: list[str] = []
    if paths.logs.is_dir():
        for entry in sorted(paths.logs.glob("*")):
            if (entry.is_file() and entry.suffix.lower() in (".log", ".json")
                    and entry.stat().st_size <= 5 * 1024 * 1024):
                logs_included.append(entry.name)

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "treecut_version": treecut_version(paths),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "install_root": str(paths.install_root),
        "data_root": str(paths.data_root),
        "data_drive_free_gb": _free_gb(paths),
        "capabilities": capabilities,
        "database_health": _database_health(paths),
        "media_count": _media_count(paths),
        "recent_jobs": _recent_jobs_summary(paths.databases / "jobs.db"),
        "logs_included": logs_included,
    }


def collect_light_status(paths: RuntimePaths) -> dict:
    """Cheap periodic status snapshot for the remote agent (no heavy imports)."""
    import platform
    import sys

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "treecut_version": treecut_version(paths),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "data_drive_free_gb": _free_gb(paths),
        "database_health": _database_health(paths),
        "media_count": _media_count(paths),
        "recent_jobs": _recent_jobs_summary(paths.databases / "jobs.db"),
        "log_tail": _log_tail(paths),
    }


def export_diagnostic_bundle(paths: RuntimePaths, destination: Path) -> Path:
    """Collect logs, health checks, and environment info into one portable zip.

    The bundle is small and safe to copy back to the development computer so the
    state of an installed machine can be analyzed without remote access.
    """
    import json
    import zipfile

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle = destination / f"treecut_diagnostic_{stamp}.zip"
    report = collect_diagnostic_report(paths)

    root_prefix = "treecut_diagnostic/"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(root_prefix + "report.json",
                         json.dumps(report, ensure_ascii=False, indent=2))
        settings = paths.data_root / "config" / "settings.json"
        if settings.is_file():
            archive.write(settings, root_prefix + "config/settings.json")
        verification = paths.data_root / "model_verification.json"
        if verification.is_file():
            archive.write(verification, root_prefix + "model_verification.json")
        if paths.logs.is_dir():
            for name in report["logs_included"]:
                archive.write(paths.logs / name, root_prefix + "logs/" + name)
    return bundle


def wipe_user_data(paths: RuntimePaths) -> list[str]:
    """Delete user data (databases, materials, output, logs, caches); keep config.

    Used by remote wipe/uninstall commands. Only touches paths under data_root.
    """
    import shutil
    removed: list[str] = []
    for directory in (paths.databases, paths.materials, paths.output, paths.cache,
                      paths.logs, paths.temp):
        if not directory.is_dir() or directory.is_symlink():
            continue
        for entry in directory.iterdir():
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
                removed.append(str(entry))
            except OSError:
                pass
        directory.mkdir(parents=True, exist_ok=True)
    return removed
