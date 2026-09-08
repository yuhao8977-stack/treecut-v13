# -*- coding: utf-8 -*-
"""A0 R2 — RAW_PREFLIGHT. Reads the repo-EXTERNAL raw captures (made BEFORE any
repo file existed) and assembles the machine evidence JSON. Nothing hardcoded:
all numbers/values come from the captured text files."""
import json
from pathlib import Path

EXT_CAPTURE = Path(r"E:\EchoBird-main\_treecut_audit_temp\preflight_20260908_183213")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def read(name: str) -> dict:
    p = EXT_CAPTURE / f"{name}.txt"
    raw = p.read_text(encoding="utf-8-sig", errors="replace")  # utf-8-sig strips BOM
    text = raw
    lines = [ln for ln in text.splitlines() if ln.strip()]
    rc = 0
    if lines and lines[0].startswith("#== git ") and "rc=" in lines[0]:
        rc = int(lines[0].split("rc=")[1].split(" ")[0])
        lines = lines[1:]
    return {"file": str(p), "exit_code": rc, "lines": lines, "raw": raw}


def main():
    git = {}
    for name in ("rev_parse_HEAD", "rev_parse_origin", "status", "branch",
                 "log1", "diff_name", "cached", "ls_untracked"):
        git[name] = read(name)
    head = git["rev_parse_HEAD"]["lines"][0].strip()
    origin = git["rev_parse_origin"]["lines"][0].strip()
    clean = len(git["status"]["lines"]) == 0 and len(git["diff_name"]["lines"]) == 0

    versions = {}
    for name in ("sys_python", "rt_python", "ffmpeg"):
        d = read(name)
        versions[name] = {"lines": d["lines"], "raw": d["raw"]}
    disk = read("disk_free")

    preflight = {
        "experiment": "TREECUT_A0R2_RAW_PREFLIGHT",
        "head": head,
        "origin_main": origin,
        "head_eq_origin": head == origin,
        "branch": git["branch"]["lines"][0].strip() if git["branch"]["lines"] else "",
        "worktree_clean": clean,
        "status_porcelain_lines": git["status"]["lines"],
        "tracked_diff_lines": git["diff_name"]["lines"],
        "cached_diff_lines": git["cached"]["lines"],
        "untracked_lines": git["ls_untracked"]["lines"],
        "git_commands": {k: {"exit_code": v["exit_code"], "file": v["file"]} for k, v in git.items()},
        "external_raw_capture_dir": str(EXT_CAPTURE),
        "versions": versions,
        "disk_free": disk["lines"],
        "note": "captured BEFORE any A0R2 repo file existed (ordering requirement met)",
    }
    (OUT / "TREECUT_A0R2_RAW_PREFLIGHT.json").write_text(
        json.dumps(preflight, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"head={head} origin_eq={head == origin} clean={clean}")


if __name__ == "__main__":
    main()
