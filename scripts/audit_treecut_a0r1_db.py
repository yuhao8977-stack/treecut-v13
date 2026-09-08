# -*- coding: utf-8 -*-
"""A0 R1 — REAL machine evidence collection (DB + source + artifacts + ffprobe).
All numbers come from live queries/commands; machine raw evidence saved separately.
Read-only: SQLite mode=ro, no writes to production DB.
"""
import hashlib
import json
import os
import sqlite3
import subprocess
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
INSTALL = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13")
PROD_DB = INSTALL / "runtime_data" / "database" / "materials.db"
CAM_DB = INSTALL / "runtime_data" / "temp" / "batch1" / "database" / "materials.db"
ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def db_evidence(db_path):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table'")]
    rows = {}
    for t in tables:
        try:
            rows[t] = cur.execute(f"select count(*) from {t}").fetchone()[0]
        except Exception:
            rows[t] = None
    con.close()
    return {"db_path": str(db_path), "sha256": sha(db_path),
            "tables": len(tables), "table_rows": rows}


def main():
    evidence = {}
    # ===== DB evidence =====
    evidence["production_db"] = db_evidence(PROD_DB)
    evidence["cam_db"] = db_evidence(CAM_DB)

    # ===== production media path validity (ALL media, not just 5/6) =====
    con = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    cur = con.cursor()
    rows = cur.execute("select m.id, m.source_id, m.relative_path, m.available from media_files m").fetchall()
    path_valid = path_missing = source_offline = avail_false = 0
    missing_samples = []
    for mid, sid, rel, avail in rows:
        root = ROOTS.get(sid)
        if root is None:
            source_offline += 1
            continue
        full = root + "\\" + rel
        if os.path.exists(full):
            path_valid += 1
        else:
            path_missing += 1
            if len(missing_samples) < 15:
                missing_samples.append({"media_id": mid, "source_id": sid, "rel": (rel or "")[-60:]})
        if avail == 0:
            avail_false += 1
    evidence["production_media_path_audit"] = {
        "total": len(rows), "path_valid": path_valid, "path_missing": path_missing,
        "source_offline": source_offline, "available_false": avail_false,
        "missing_samples": missing_samples}
    # eligible & classified counts via live query
    evidence["eligible"] = cur.execute(
        "select count(*) from media_files m join analysis_jobs j on j.media_id=m.id "
        "where j.result_json like '%eligible_for_auto_edit%true%'").fetchone()[0]
    evidence["classified"] = cur.execute(
        "select count(*) from media_files where category is not null and category != 'unclassified'").fetchone()[0]
    evidence["jobs_with_result"] = cur.execute(
        "select count(*) from analysis_jobs where result_json is not null and result_json != ''").fetchone()[0]
    # distinct real sources present
    srcs = cur.execute("select id, path from sources").fetchall()
    evidence["sources"] = [{"id": s[0], "path_present": os.path.exists(s[1]) if s[1] else False}
                           for s in srcs]
    con.close()

    # CAM db joins
    ccon = sqlite3.connect(f"file:{CAM_DB}?mode=ro", uri=True)
    cc = ccon.cursor()
    evidence["cam_join"] = {
        "assets": cc.execute("select count(*) from assets").fetchone()[0],
        "segments": cc.execute("select count(*) from segments").fetchone()[0],
        "transcripts": cc.execute("select count(*) from transcripts").fetchone()[0],
        "ocr": cc.execute("select count(*) from ocr_text").fetchone()[0],
        "segments_distinct_assets": cc.execute("select count(distinct asset_id) from segments").fetchone()[0],
    }
    # segment asset join degree vs media: can segments be joined to media_files ids?
    try:
        j1 = cc.execute("""select count(*) from segments s
            left join assets a on a.asset_id = s.asset_id
            where a.asset_id is null""").fetchone()[0]
        evidence["cam_join"]["segments_without_asset"] = j1
    except Exception as e:
        evidence["cam_join"]["segments_without_asset"] = str(e)[:100]
    ccon.close()

    (OUT / "TREECUT_A0R1_RAW_DB_EVIDENCE.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=1), encoding="utf-8")
    print("RAW DB evidence written")
    print("prod path_valid/missing:", path_valid, "/", path_missing,
          "| source_offline:", source_offline)
    print("cam:", evidence["cam_join"])


if __name__ == "__main__":
    main()
