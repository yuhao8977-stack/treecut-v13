# -*- coding: utf-8 -*-
"""Phase B1 — 安全 Temp 清理（只删明确过期 stale，占用/近期 SKIP，不强杀程序）。"""
import json
import os
import sys
import time
from pathlib import Path

sys.stdout = type(sys.stdout)(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

TEMP = Path(os.environ["USERPROFILE"]) / "AppData" / "Local" / "Temp"
STALE_DAYS = 7  # 仅删除超过 7 天未修改的条目


def size_of(path: Path) -> int:
    if path.is_file():
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    total = 0
    for r, _ds, fs in os.walk(path):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return total


def main() -> int:
    before = 0
    deleted = 0
    skipped_locked = 0
    skipped_recent = 0
    skipped_other = 0
    deleted_count = 0
    skipped_paths = []
    now = time.time()
    stale_sec = STALE_DAYS * 86400

    for entry in sorted(os.scandir(TEMP), key=lambda e: e.name.lower()):
        p = Path(entry.path)
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            skipped_other += 1
            continue
        age = now - mtime
        sz = size_of(p)
        before += sz
        if age < stale_sec:
            skipped_recent += 1
            if len(skipped_paths) < 20:
                skipped_paths.append({"path": str(p), "reason": "recent", "size_gb": round(sz / 2**30, 2)})
            continue
        try:
            if p.is_dir():
                import shutil
                shutil.rmtree(p)
            else:
                p.unlink()
            deleted += sz
            deleted_count += 1
        except OSError:
            skipped_locked += 1
            if len(skipped_paths) < 40:
                skipped_paths.append({"path": str(p), "reason": "locked/in-use", "size_gb": round(sz / 2**30, 2)})

    result = {
        "temp_dir": str(TEMP),
        "stale_threshold_days": STALE_DAYS,
        "bytes_before": before,
        "bytes_deleted": deleted,
        "bytes_skipped": before - deleted,
        "deleted_entries": deleted_count,
        "skipped_recent": skipped_recent,
        "skipped_locked_or_other": skipped_locked + skipped_other,
        "deleted_gb": round(deleted / 2**30, 2),
        "skipped_gb": round((before - deleted) / 2**30, 2),
        "skipped_samples": skipped_paths,
    }
    out = Path(r"C:\Users\admin\github\treecut-v13\reports\storage\TEMP_CLEANUP_RESULT_V1.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
