#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CALIBRATION WAVE — 候选发现 + 独立性查重 + A3 污染检查（只读）。

池: G1 eligible X1 mp4 − (A3_CANDIDATES.excluded_known_ids ∪ A3 17 候选媒体 ∪ A3 家族文件夹)。
分桶: EXTEND(伸缩) / INTERFERENCE(抽屉/插座/腿运动/人动) / STATIC(空镜/讲解) / RETRACT(ASR 收回, 可能不足)。
仅 CANDIDATE(非真值)；每组给 > 需要量，人工评审页选择。
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
A3C = json.loads((OUT / "TREECUT_MMVV_A3_CANDIDATES.json").read_text(encoding="utf-8"))
sys.stdout.reconfigure(encoding="utf-8")

EXCLUDED = set(A3C["excluded_known_ids"])
A3_IDS = {c["media_id"] for c in A3C["candidates"]}
# A3 家族文件夹级排除（取候选第二段 client 文件夹）
A3_FAM = set()
for c in A3C["candidates"]:
    p = c["relative_path"]
    parts = p.split("\\")
    A3_FAM.add(parts[1] if len(parts) > 1 else parts[0])


def fam_key(rel: str) -> str:
    parts = rel.split("\\")
    return parts[1] if len(parts) > 1 else parts[0]


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    base = """
        SELECT mf.id, mf.relative_path, a.duration
        FROM media_files mf
        JOIN b007_source_role_v1 r ON r.entity_id=mf.id AND r.entity_kind='media_file'
        LEFT JOIN assets a ON a.media_id=mf.id
        WHERE mf.extension='.mp4'
          AND r.source_role IN ('PRODUCTION_CLEAN_RAW','PRODUCTION_CLEAN_SEMI')
          AND r.review_status!='REJECTED'
          AND (r.review_status='APPROVED'
               OR (r.burned_subtitle_present!='PRESENT' AND r.platform_watermark_present!='PRESENT'
                   AND r.old_title_overlay_present!='PRESENT' AND r.brand_overlay_present!='PRESENT'
                   AND r.unrelated_overlay_present!='PRESENT'
                   AND r.burned_subtitle_present!='UNCERTAIN' AND r.platform_watermark_present!='UNCERTAIN'
                   AND r.old_title_overlay_present!='UNCERTAIN' AND r.brand_overlay_present!='UNCERTAIN'
                   AND r.unrelated_overlay_present!='UNCERTAIN'))
          AND mf.id NOT IN ({ex})
    """
    excl_sql = ",".join(str(x) for x in sorted(EXCLUDED | A3_IDS)) or "0"

    def fetch(like_sql):
        q = base.format(ex=excl_sql) + " AND (" + like_sql + ")"
        return [{"media_id": r[0], "path": r[1], "fam": fam_key(r[1]), "dur": r[2]}
                for r in cur.execute(q, ())]

    def dedup_by_family(items, want):
        """家族去重后取 want 个（时长列可能缺失，不设门槛；抽帧时实测时长）"""
        seen = {}
        for it in sorted(items, key=lambda x: -(x["dur"] or 0)):
            if it["fam"] in A3_FAM or it["media_id"] in A3_IDS:
                continue
            if it["fam"] not in seen:
                seen[it["fam"]] = it
            if len(seen) >= want:
                break
        return list(seen.values())[:want]

    extend = fetch("mf.relative_path LIKE '%伸缩%' OR mf.relative_path LIKE '%可拉伸%' OR mf.relative_path LIKE '%拉出%'")
    drawer = fetch("mf.relative_path LIKE '%抽屉%' AND (mf.relative_path LIKE '%打开%' OR mf.relative_path LIKE '%抽拉%')")
    socket = fetch("mf.relative_path LIKE '%轨道插座%' AND (mf.relative_path LIKE '%调%' OR mf.relative_path LIKE '%插%')")
    leg = fetch("(mf.relative_path LIKE '%伸缩脚%' OR mf.relative_path LIKE '%亚克力伸缩%' OR mf.relative_path LIKE '%岩板腿%')")
    stat = fetch("(mf.relative_path LIKE '%空镜%' OR mf.relative_path LIKE '%讲解%') AND mf.relative_path NOT LIKE '%伸缩%'")
    retr = fetch("mf.relative_path LIKE '%收回%'")
    print("raw hits -> extend", len(extend), "drawer", len(drawer), "socket", len(socket),
          "leg", len(leg), "stat", len(stat), "retr", len(retr))
    # ASR 检索“收回”（transcripts/fts 按 asset 键控；asset->media 经 assets.media_id）
    asr_retr = []
    try:
        q = base.format(ex=excl_sql) + """ AND mf.id IN (
            SELECT a.media_id FROM assets a
            JOIN transcripts t ON t.asset_id=a.asset_id
            WHERE (t.text_raw LIKE '%收回%' OR t.text_raw LIKE '%收回去%' OR t.text_raw LIKE '%缩回%'))"""
        asr_retr = [{"media_id": r[0], "path": r[1], "fam": fam_key(r[1]), "dur": r[2]}
                    for r in cur.execute(q, ())]
    except Exception as e:
        print("asr_retr err:", e)

    proposal = {
        "EXTEND": dedup_by_family(extend, 7),
        "INTERFERENCE_DRAWER": dedup_by_family(drawer, 4),
        "INTERFERENCE_SOCKET": dedup_by_family(socket, 4),
        "INTERFERENCE_LEG": dedup_by_family(leg, 4),
        "STATIC": dedup_by_family(stat, 4),
        "RETRACT_PATH": dedup_by_family(retr, 3),
        "RETRACT_ASR": dedup_by_family(asr_retr, 3),
    }
    n = sum(len(v) for v in proposal.values())
    doc = {"experiment": "MMVV_POSTA3_CALIBRATION_MANIFEST_V1",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "note": ("仅候选(非真值)。排除 = A3_CANDIDATES.excluded_known_ids ∪ A3 17 候选媒体 "
                    "∪ A3 家族文件夹(第二段)。人工评审页决定 ACTION GT。"),
           "excluded_known_count": len(EXCLUDED), "a3_candidate_ids_excluded": len(A3_IDS),
           "a3_family_folders_excluded": sorted(A3_FAM)[:20],
           "pools_queried": {"extend_hits": len(extend), "drawer_hits": len(drawer),
                             "socket_hits": len(socket), "leg_hits": len(leg),
                             "static_hits": len(stat), "retr_path": len(retr), "retr_asr": len(asr_retr)},
           "proposals": {k: [{"media_id": i["media_id"], "path": i["path"], "family": i["fam"],
                              "duration_s": i["dur"]} for i in v]
                         for k, v in proposal.items() if v},
           "proposal_total": n}
    out = OUT / "TREECUT_POSTA3_CALIBRATION_MANIFEST_V1.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("proposal total:", n)
    for k, v in proposal.items():
        print(f"  {k}: {len(v)}  ", [i['media_id'] for i in v])
    # A3 污染自检
    bad = [i["media_id"] for v in proposal.values() for i in v if i["media_id"] in (EXCLUDED | A3_IDS)]
    print("A3/known contamination in proposals:", bad if bad else "NONE")
    con.close()


if __name__ == "__main__":
    main()
