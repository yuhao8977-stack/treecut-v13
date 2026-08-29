# -*- coding: utf-8 -*-
"""FRESH_HOLDOUT_V2 FINAL EVAL — STEP 1：Human Truth 冻结 + JOIN 校验。"""
import hashlib
import io
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    man = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_MANIFEST_LOCK.json"), encoding="utf-8"))
    man_sids = [s["segment_id"] for s in man["strata"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ph = ",".join("?" * len(man_sids))
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM fresh_holdout_human_review_v1 WHERE segment_id IN ({ph})", man_sids)]
    conn.close()

    db_sids = [r["segment_id"] for r in rows]
    missing = [s for s in man_sids if s not in set(db_sids)]
    extra = [r for r in db_sids if r not in set(man_sids)]
    dup = [s for s in set(man_sids) if man_sids.count(s) > 1]
    join = {"manifest_count": len(man_sids), "human_count": len(rows),
            "missing": missing, "extra": extra, "duplicate": dup,
            "pass": not missing and not extra and not dup}
    status_c = dict(Counter(r["review_status"] for r in rows))
    conf_c = dict(Counter(r["human_confidence"] for r in rows))
    dict_c = dict(Counter(r["dictionary_version"] for r in rows))
    print("JOIN:", join["pass"], "| status:", status_c, "| conf:", conf_c, "| dict:", dict_c)

    # Human Lock
    by = {r["segment_id"]: r for r in rows}
    segs = []
    for sid in sorted(man_sids):
        r = by[sid]
        segs.append({"segment_id": sid,
                     "scene_family": r["scene_family"], "scene_subtype": r["scene_subtype"],
                     "product_family": r["product_family"], "product_variant": r["product_variant"],
                     "material": jload(r["material_multi"]), "component": jload(r["component_multi"]),
                     "function": jload(r["function_multi"]), "action_group": r["action_group"],
                     "action_sequence": jload(r["action_sequence"]), "shot_scale": r["shot_scale"],
                     "shot_role": jload(r["shot_role_multi"]), "people_presence": r["people_presence"],
                     "product_visibility": r["product_visibility"], "quality": r.get("quality"),
                     "human_confidence": r["human_confidence"], "review_status": r["review_status"],
                     "comment": r.get("comment", ""), "stratum": next(
                         s["stratum"] for s in man["strata"] if s["segment_id"] == sid)})
    payload = {"manifest": "FRESH_HOLDOUT_V2", "dictionary_version": "ANNOTATION_DICTIONARY_V2_1",
               "segments": segs}
    canon = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    human_sha = hashlib.sha256(canon).hexdigest()
    lock = {"manifest_version": "FRESH_HOLDOUT_V2_HUMAN_LOCK",
            "frozen_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "manifest_sha256": man["manifest_sha256"],
            "human_truth_sha256": human_sha,
            "count": len(segs), "status": status_c, "confidence": conf_c,
            "dictionary_version": dict_c,
            "guard": "DO_NOT_OVERWRITE; DO_NOT_TRAIN; DO_NOT_CALIBRATE; 修订走 revision/adjudication",
            "segments": segs}
    p = os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_HUMAN_LOCK.json")
    json.dump(lock, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)
    print("human_truth_sha256:", human_sha)


if __name__ == "__main__":
    main()
