# -*- coding: utf-8 -*-
"""A0 R1 — REAL path validity using sources.path (correct mapping). Read-only."""
import hashlib
import json
import os
import sqlite3
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DB = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\database\materials.db")


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    src_path = {r[0]: r[1] for r in cur.execute("select id, path from sources")}
    rows = cur.execute(
        "select m.id, m.source_id, m.relative_path, m.category, "
        "(select count(*) from analysis_jobs j where j.media_id=m.id and j.result_json like '%eligible_for_auto_edit%true%') "
        "from media_files m").fetchall()
    total = len(rows)
    valid = missing = 0
    eligible_valid = eligible_missing = 0
    video_ext = (".mp4", ".mov", ".avi", ".mkv", ".m4v")
    missing_video = []
    for mid, sid, rel, cat, elig in rows:
        base = src_path.get(sid)
        if not base:
            continue
        full = os.path.join(base, rel or "")
        ex = os.path.exists(full)
        if ex:
            valid += 1
            if elig:
                eligible_valid += 1
            # video-type check
            if rel and rel.lower().endswith(video_ext) and elig:
                pass
        else:
            missing += 1
            if elig:
                eligible_missing += 1
            if rel and rel.lower().endswith(video_ext) and len(missing_video) < 20:
                missing_video.append({"mid": mid, "src": sid, "rel": (rel or "")[-60:], "eligible": bool(elig)})
    # eligible video count total
    elig_video = cur.execute(
        "select count(*) from media_files m where m.relative_path like '%.mp4' or m.relative_path like '%.mov' "
        "or m.relative_path like '%.avi' or m.relative_path like '%.mkv' or m.relative_path like '%.m4v'").fetchone()[0]
    con.close()
    res = {"total": total, "path_valid": valid, "path_missing": missing,
           "eligible_total": eligible_valid + eligible_missing,
           "eligible_valid": eligible_valid, "eligible_missing": eligible_missing,
           "video_media_total_approx": elig_video,
           "missing_video_samples": missing_video,
           "note": "using real sources.path (D:/E: local dirs); previous A0 used wrong \\X1 mapping -> corrected",
           "sha256_db": hashlib.sha256(Path(DB).read_bytes()).hexdigest()}
    (OUT / "TREECUT_A0R1_PATH_VALIDITY_CORRECTED.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
