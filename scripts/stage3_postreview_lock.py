# -*- coding: utf-8 -*-
"""Stage3 POST-REVIEW — STEP 1/2/3：冻结校验 + Human Truth Lock + 全字段 support 对比。

严格按 manifest.segment_id JOIN（非 UI 顺序/index）。
输出 missing/extra/duplicate 必须全 0；生成 HUMAN_LOCK（human_truth_sha256）；
再统计 60 条真实 label support 并与 Calibration333 对比。
"""
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

SINGLE = ["scene_family", "scene_subtype", "product_family", "product_variant",
          "action_group", "shot_scale", "people_presence", "product_visibility"]
MULTI = ["material_multi", "component_multi", "function_multi", "shot_role_multi"]


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    man = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    man_sids = [s["segment_id"] for s in man["segments"]]
    man_sha = man.get("manifest_sha256", "（sidecar 见 .sha256 文件）")

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ph = ",".join("?" * len(man_sids))
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", man_sids)]
    cal_rows = [dict(r) for r in conn.execute(
        "SELECT * FROM canonical_human_truth WHERE is_current=1")]
    conn.close()

    # ---- STEP 1: JOIN 校验 ----
    db_sids = [r["segment_id"] for r in rows]
    missing = [s for s in man_sids if s not in set(db_sids)]
    extra = [r for r in db_sids if r not in set(man_sids)]
    dup_m = [s for s in set(man_sids) if man_sids.count(s) > 1]
    dup_db = [s for s in set(db_sids) if db_sids.count(s) > 1]
    join = {"manifest_count": len(man_sids), "manifest_unique": len(set(man_sids)),
            "human_count": len(rows), "human_unique": len(set(db_sids)),
            "missing": missing, "extra": extra,
            "duplicate_manifest": dup_m, "duplicate_human": dup_db,
            "join_pass": (not missing and not extra and not dup_m and not dup_db)}

    status_c = dict(Counter(r["review_status"] for r in rows))
    conf_c = dict(Counter(r["human_confidence"] for r in rows))
    dict_c = dict(Counter(r["dictionary_version"] for r in rows))
    needs_review = sum(1 for r in rows if r["review_status"] == "NEEDS_SECOND_REVIEW")
    print("JOIN:", join["join_pass"], "| status:", status_c, "| conf:", conf_c,
          "| dict:", dict_c, "| needs_review(DB):", needs_review)

    # ---- STEP 2: Human Truth Lock ----
    # 按 segment_id 固定排序，构建规范记录
    by_sid = {r["segment_id"]: r for r in rows}
    lock_segments = []
    for sid in sorted(man_sids):
        r = by_sid[sid]
        lock_segments.append({
            "segment_id": sid,
            "scene_family": r["scene_family"], "scene_subtype": r["scene_subtype"],
            "product_family": r["product_family"], "product_variant": r["product_variant"],
            "material": jload(r["material_multi"]), "component": jload(r["component_multi"]),
            "function": jload(r["function_multi"]), "action_group": r["action_group"],
            "action_sequence": jload(r["action_sequence"]), "shot_scale": r["shot_scale"],
            "shot_role": jload(r["shot_role_multi"]), "people_presence": r["people_presence"],
            "product_visibility": r["product_visibility"], "quality": r.get("quality"),
            "human_confidence": r["human_confidence"], "review_status": r["review_status"],
            "comment": r.get("comment", ""), "operator": r.get("operator", ""),
        })
    truth_payload = {
        "manifest": "TARGETED_REVIEW_STAGE3_V3_1",
        "manifest_sha256": man_sha,
        "dictionary_version": "ANNOTATION_DICTIONARY_V2_1",
        "segments": lock_segments,
    }
    canon = json.dumps(truth_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    human_sha = hashlib.sha256(canon).hexdigest()
    lock = {
        "manifest_version": "TARGETED_REVIEW_STAGE3_V3_1_HUMAN_LOCK",
        "frozen_at": "2026-08-28",
        "manifest_sha256": man_sha,
        "human_truth_sha256": human_sha,
        "count": len(lock_segments),
        "review_status_distribution": status_c,
        "human_confidence_distribution": conf_c,
        "dictionary_version": dict_c,
        "guard": "DO_NOT_OVERWRITE; 修订必须走 revision/adjudication，禁止直接覆盖历史 Human Truth",
        "segments": lock_segments,
    }
    lp = os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1_HUMAN_LOCK.json")
    json.dump(lock, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("HUMAN_LOCK ->", lp)
    print("human_truth_sha256:", human_sha)

    # ---- STEP 3: 全字段 support：60 vs Cal333 ----
    def single_support(rows, field):
        return dict(Counter(r[field] for r in rows if r.get(field)))

    def multi_support(rows, field):
        c = Counter()
        for r in rows:
            for lab in jload(r.get(field)):
                c[lab] += 1
        return dict(c)

    support = {}
    for f in SINGLE:
        support[f] = {"stage3_60": single_support(rows, f),
                      "calibration333": single_support(cal_rows, f)}
    for f in MULTI:
        support[f] = {"stage3_60": multi_support(rows, f),
                      "calibration333": multi_support(cal_rows, f)}
    support["_action_sequence"] = {"stage3_60": multi_support(rows, "action_sequence"),
                                   "calibration333": multi_support(cal_rows, "action_sequence")}

    # 合并 support（combined_dev = 60 + 333，仅同类 label 求和）
    combined = {}
    for f in SINGLE + MULTI + ["_action_sequence"]:
        merged = Counter(support[f]["calibration333"])
        for k, v in support[f]["stage3_60"].items():
            merged[k] += v
        combined[f] = dict(merged)
    support["combined_dev"] = combined

    sp = os.path.join(DATA_ROOT, "STAGE3_POST_REVIEW_LABEL_SUPPORT.json")
    out = {"manifest": "STAGE3_POST_REVIEW_LABEL_SUPPORT",
           "join": join, "status": status_c, "confidence": conf_c,
           "dictionary": dict_c, "needs_review_db": needs_review,
           "human_truth_sha256": human_sha,
           "support": support}
    json.dump(out, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", sp)
    for f in SINGLE:
        print(f"[{f}] 60:", support[f]["stage3_60"])
    for f in MULTI + ["_action_sequence"]:
        print(f"[{f}] 60:", support[f]["stage3_60"])


if __name__ == "__main__":
    main()
