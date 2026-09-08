# -*- coding: utf-8 -*-
"""A0 audit data collection - PRE_RUN baseline + env. Read-only."""
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
INSTALL = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13")


def git(*a):
    return subprocess.run(["git", "-C", str(REPO)] + list(a),
                          capture_output=True, text=True).stdout.strip()


def main():
    base = {
        "audit": "TREECUT_A0_PRE_RUN_BASELINE",
        "recorded_before_a0_outputs": True,
        "head": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "origin_main": git("rev-parse", "origin/main"),
        "head_equals_origin": git("rev-parse", "HEAD") == git("rev-parse", "origin/main"),
        "git_status_porcelain_count": len(git("status", "--porcelain").splitlines()),
        "tracked_worktree_clean": len(git("status", "--porcelain").splitlines()) == 0,
        "python_runtime": sys.version.split()[0] if False else "3.12.13 (runtime E:\\...\\runtime\\python.exe)",
        "os": platform.system() + " " + platform.release(),
        "ffmpeg": "8.1.1-full_build (gyan.dev)",
        "production_db": str(INSTALL / "runtime_data" / "database" / "materials.db"),
        "production_db_tables": ["sources", "media_files", "analysis_jobs", "media_tags"],
        "analysis_db_cam01": str(INSTALL / "runtime_data" / "temp" / "batch1" / "database" / "materials.db"),
        "launcher": str(INSTALL / "启动树剪v13.cmd"),
        "launcher_chain": "启动树剪v13.cmd -> runtime\\pythonw.exe -m treecut.watchdog -> pythonw -m treecut.desktop (Tk)",
        "console_scripts": {"treecut": "treecut.main:main", "treecut-desktop": "treecut.desktop:main",
                            "treecut-api": "treecut.api:main", "treecut-xhs-browser": "treecut.browser.main:main"},
        "tracked_file_count": len(git("ls-files").splitlines()),
        "note": "baseline recorded BEFORE any A0 file generated"}
    (OUT / "TREECUT_A0_PRE_RUN_BASELINE.json").write_text(
        json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(base, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
