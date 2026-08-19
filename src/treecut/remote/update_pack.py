"""Build, verify, and safely apply incremental update packages."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
import zipfile
from pathlib import Path


INCLUDE_DIRS = ("src", "scripts")
INCLUDE_FILES = (
    "pyproject.toml",
    "assets/icon.ico",
    "assets/knowledge/protected_words.json",
    "assets/knowledge/素材标签库.json",
    "启动树剪v13.cmd",
    "检查树剪安装.cmd",
    "启动树剪本地接口.cmd",
    "导出诊断包.cmd",
    "启动远程管理端.cmd",
    "远程助手客户端.cmd",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def make_update_package(install_root: Path, version: str, notes: str, output: Path,
                        include_dirs: tuple[str, ...] = INCLUDE_DIRS,
                        include_files: tuple[str, ...] = INCLUDE_FILES,
                        force: bool = False) -> Path:
    """Zip the current code files with a manifest of per-file sha256 hashes."""
    root = Path(install_root).resolve()
    entries: list[dict] = []
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for directory in include_dirs:
            base = root / directory
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*")):
                if (not path.is_file() or "__pycache__" in path.parts
                        or path.suffix in (".pyc", ".pyo")):
                    continue
                relative = _relative(path, root)
                entries.append({"path": relative, "sha256": _sha256_file(path)})
                archive.write(path, f"files/{relative}")
        for name in include_files:
            path = root / name
            if path.is_file():
                entries.append({"path": name, "sha256": _sha256_file(path)})
                archive.write(path, f"files/{name}")
    manifest = {
        "version": version,
        "notes": notes,
        "force": bool(force),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": entries,
    }
    with zipfile.ZipFile(output, "a") as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return output


def read_manifest(package: Path) -> dict:
    with zipfile.ZipFile(package) as archive:
        return json.loads(archive.read("manifest.json").decode("utf-8"))


def verify_package(package: Path, install_root: Path) -> list[str]:
    """Return a list of problems; empty means the package is safe to apply."""
    problems: list[str] = []
    root = Path(install_root).resolve()
    try:
        manifest = read_manifest(package)
    except Exception as error:
        return [f"无法读取更新清单：{type(error).__name__}"]
    if not isinstance(manifest.get("files"), list) or not manifest["files"]:
        return ["更新包没有任何文件"]
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        seen: set[str] = set()
        for item in manifest.get("files", []):
            relative = str(item.get("path", ""))
            if relative in seen:
                problems.append(f"重复文件：{relative}")
                continue
            seen.add(relative)
            target = (root / relative).resolve()
            if not str(target).startswith(str(root)):
                problems.append(f"不安全路径：{relative}")
                continue
            member = f"files/{relative}"
            if member not in names:
                problems.append(f"缺少文件：{relative}")
                continue
            digest = hashlib.sha256()
            with archive.open(member) as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b""):
                    digest.update(chunk)
            if digest.hexdigest() != str(item.get("sha256", "")):
                problems.append(f"校验不匹配：{relative}")
    return problems


def apply_update(install_root: Path, package: Path, *,
                 smoke_command: list[str] | None = None,
                 env: dict | None = None) -> dict:
    """Apply a verified package; roll back every changed file on any failure."""
    root = Path(install_root).resolve()
    problems = verify_package(package, root)
    if problems:
        return {"ok": False, "error": "校验失败：" + "；".join(problems)}
    manifest = read_manifest(package)
    backup_dir = root / "runtime_data" / "updates" / f"backup_{time.strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    changed: list[tuple[Path, Path]] = []
    try:
        with zipfile.ZipFile(package) as archive:
            for item in manifest["files"]:
                relative = str(item["path"])
                target = (root / relative).resolve()
                if not str(target).startswith(str(root)):
                    raise RuntimeError(f"不安全路径：{relative}")
                target.parent.mkdir(parents=True, exist_ok=True)
                backup = backup_dir / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    shutil.copy2(target, backup)
                target.write_bytes(archive.read(f"files/{relative}"))
                changed.append((target, backup))
        if smoke_command:
            result = subprocess.run(
                smoke_command, capture_output=True, check=False, timeout=180, env=env,
            )
            if result.returncode != 0:
                detail = result.stderr.decode("utf-8", errors="replace").strip()[:500]
                raise RuntimeError(f"更新后自检失败：{detail or '无错误信息'}")
        return {
            "ok": True,
            "version": manifest["version"],
            "changed": len(changed),
            "backup": str(backup_dir),
        }
    except Exception as error:
        for target, backup in changed:
            try:
                if backup.exists():
                    shutil.copy2(backup, target)
                else:
                    target.unlink(missing_ok=True)
            except OSError:
                pass
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}
