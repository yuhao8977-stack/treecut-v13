# -*- coding: utf-8 -*-
"""Phase A — C盘存储审计 + E盘/模型缓存审计（只读元数据，不读取凭证内容，禁止删除）。

产出到 reports/storage/（相对仓库根）：
  C_DRIVE_STORAGE_AUDIT_V1.json / .md
  TREECUT_REPO_DUPLICATE_AUDIT_V1.json
  TREECUT_MODEL_CACHE_AUDIT_V1.json
  STORAGE_ARCHITECTURE_V1.json
  TREECUT_STORAGE_MIGRATION_PLAN_V1.md
  C_DRIVE_CLEANUP_PLAN_V1.json（PENDING，不执行）
  *_MIGRATION_VALIDATION_V1.json（PENDING 模板）
  docs/TREECUT_STORAGE_ARCHITECTURE_REPORT_V1.md
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.stdout = type(sys.stdout)(
    sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "storage"
OUT.mkdir(parents=True, exist_ok=True)

HOME = Path(os.environ["USERPROFILE"])

AUDIT_PATHS = {
    "github": HOME / "github",
    ".treecut": HOME / ".treecut",
    ".cache": HOME / ".cache",
    ".modelscope": HOME / ".modelscope",
    ".ollama": HOME / ".ollama",
    ".dsh": HOME / ".dsh",
    "deepseek-harness": HOME / "deepseek-harness",
    "harness_workspace": HOME / "harness_workspace",
    "dsh_models": HOME / "dsh_models",
    "AppData_Local_Temp": HOME / "AppData" / "Local" / "Temp",
    "Desktop": HOME / "Desktop",
    "Downloads": HOME / "Downloads",
}
PER_PATH_BUDGET = 90.0  # 秒/路径


def dir_size(path: Path, budget: float) -> dict:
    """只统计大小/文件数（不读文件内容）；超预算返回 SCAN_TIMEOUT。"""
    total = 0
    count = 0
    start = time.time()
    try:
        for root, dirs, files in os.walk(str(path), followlinks=False):
            if time.time() - start > budget:
                return {"size_bytes": total, "file_count": count,
                        "status": "SCAN_TIMEOUT_PARTIAL"}
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                    count += 1
                except OSError:
                    pass
    except OSError as error:
        return {"size_bytes": total, "file_count": count, "status": f"ERR:{error}"}
    return {"size_bytes": total, "file_count": count, "status": "OK"}


def top_large_files(root: Path, threshold_mb: int = 50, cap: int = 200,
                    budget: float = 240.0) -> list[dict]:
    out = []
    start = time.time()
    try:
        for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
            if time.time() - start > budget:
                break
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
            for name in filenames:
                p = os.path.join(dirpath, name)
                try:
                    size = os.path.getsize(p)
                except OSError:
                    continue
                if size >= threshold_mb * 1024 * 1024:
                    try:
                        mtime = os.path.getmtime(p)
                    except OSError:
                        mtime = 0
                    out.append({"path": p, "size_bytes": size, "type": Path(p).suffix,
                                "modified": time.strftime("%Y-%m-%d", time.localtime(mtime))})
                    if len(out) >= cap:
                        return sorted(out, key=lambda x: -x["size_bytes"])
    except OSError:
        pass
    return sorted(out, key=lambda x: -x["size_bytes"])


def main() -> int:
    audit: dict = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "disks": {}, "paths": {}, "top_files": [], "top_dirs": [],
                   "e_treecut_candidates": [], "model_caches": {}}

    # 1) 磁盘可用空间
    for drive in ("C", "D", "E", "G", "Z"):
        try:
            usage = shutil.disk_usage(f"{drive}:\\")
            audit["disks"][drive] = {"free_gb": round(usage.free / 2**30, 1),
                                     "total_gb": round(usage.total / 2**30, 1)}
        except OSError:
            audit["disks"][drive] = None

    # 2) 目标路径大小
    for name, path in AUDIT_PATHS.items():
        if path.exists():
            info = dir_size(path, PER_PATH_BUDGET)
            audit["paths"][name] = {"path": str(path), **info,
                                    "size_gb": round(info["size_bytes"] / 2**30, 2)}
        else:
            audit["paths"][name] = {"path": str(path), "exists": False}

    # 3) C盘用户空间 Top 大文件
    audit["top_files"] = top_large_files(HOME)

    # 4) Top 大目录（首层 + 命名目录按大小排序）
    top_dirs = []
    for name, path in AUDIT_PATHS.items():
        if path.exists():
            info = audit["paths"].get(name, {})
            top_dirs.append({"name": name, "path": str(path),
                             "size_gb": info.get("size_gb", 0)})
    audit["top_dirs"] = sorted(top_dirs, key=lambda x: -x["size_gb"])

    # 5) E盘 TreeCut 候选（首层 + 常见位置；预算限制）
    e_candidates = []
    for base in ("E:\\",):
        try:
            for d in sorted(os.listdir(base)):
                p = Path(base) / d
                if p.is_dir() and ("树剪" in d or "TreeCut" in d or "treecut" in d.lower()):
                    info = dir_size(p, 60.0)
                    e_candidates.append({"path": str(p), **info,
                                         "size_gb": round(info["size_bytes"] / 2**30, 2)})
        except OSError:
            pass
    audit["e_treecut_candidates"] = e_candidates

    # 6) 模型缓存
    for name in (".modelscope", ".ollama", ".cache", "dsh_models"):
        p = HOME / name
        if p.exists():
            info = dir_size(p, 60.0)
            audit["model_caches"][name] = {"path": str(p), **info,
                                           "size_gb": round(info["size_bytes"] / 2**30, 2)}

    # 写 JSON
    (OUT / "C_DRIVE_STORAGE_AUDIT_V1.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    print("audit done. top dirs:")
    for d in audit["top_dirs"][:12]:
        print(f"  {d['name']:24s} {d['size_gb']:>10.2f} GB  {d['path']}")
    print("disks:", audit["disks"])
    print("e candidates:", [(c["path"], c["size_gb"]) for c in e_candidates])
    print("top files:", len(audit["top_files"]),
          "largest:", audit["top_files"][0] if audit["top_files"] else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
