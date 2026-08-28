# -*- coding: utf-8 -*-
"""Stage3 MODEL DEV — 口径修正：STAGE3_POST_REVIEW_LABEL_SUPPORT.json 的 Calibration333
改为严格 manifest 交集（360→333），并重算 combined_dev 与 Action 门槛。"""
import json
import os
import sqlite3
import sys
from collections import Counter

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
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    man_sids = {s["segment_id"] for s in man["segments"]}
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    all_cur = [dict(r) for r in conn.execute("SELECT * FROM canonical_human_truth WHERE is_current=1")]
    cal333 = [r for r in all_cur if r["segment_id"] in man_sids]

    # Stage3 60（EXCLUDED 1 条剔除：a678c4b5 人工标废弃）
    tman = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    t_sids = [s["segment_id"] for s in tman["segments"]]
    ph = ",".join("?" * len(t_sids))
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", t_sids)]
    conn.close()
    rows = [r for r in rows if r["review_status"] != "EXCLUDED"]
    print(f"Cal333={len(cal333)} Stage3有效={len(rows)}（EXCLUDED 剔除）")

    def single(rs, f):
        return dict(Counter(r.get(f) for r in rs if r.get(f)))

    def multi(rs, f):
        return dict(Counter(l for r in rs for l in jload(r.get(f))))

    support = {}
    for f in SINGLE:
        support[f] = {"calibration333": single(cal333, f), "stage3_60": single(rows, f)}
    for f in MULTI:
        support[f] = {"calibration333": multi(cal333, f), "stage3_60": multi(rows, f)}
    support["_action_sequence"] = {"calibration333": multi(cal333, "action_sequence"),
                                   "stage3_60": multi(rows, "action_sequence")}

    combined = {}
    for f in SINGLE + MULTI + ["_action_sequence"]:
        m = Counter(support[f]["calibration333"])
        for k, v in support[f]["stage3_60"].items():
            m[k] += v
        combined[f] = dict(m)
    support["combined_dev"] = combined

    # 修正后 Action 门槛
    dev = {}
    for a in ["PERSON_SPEAKING", "PULL_OUT", "RETRACT", "OPEN_DRAWER", "CLOSE_DRAWER",
              "OPEN_CABINET", "CLOSE_CABINET", "OPERATE_SOCKET", "OPEN_SINK_COVER",
              "STATIC_DISPLAY", "OTHER"]:
        tot = combined["_action_sequence"].get(a, 0)
        dev[a] = {"combined_support": tot, "status": (
            "READY_FOR_DEV" if tot >= 10 else "LIMITED" if tot >= 5 else
            "INSUFFICIENT_SAMPLE" if tot >= 1 else "ZERO_SUPPORT")}

    p = os.path.join(DATA_ROOT, "STAGE3_POST_REVIEW_LABEL_SUPPORT.json")
    data = json.load(open(p, encoding="utf-8"))
    data["support"] = support
    data["action_dev_status_corrected"] = dev
    data["integrity_note"] = ("口径修正：Calibration333 严格按 manifest 333 段交集 "
                              "（原 360 全表含 27 段早期批次，已剔除）；"
                              "Stage3 EXCLUDED 1 条剔除；多标签为 label occurrence")
    data["integrity_audit_ref"] = "SUPPORT_COUNT_INTEGRITY_AUDIT.json"
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("-> 已修正", p)
    print("FACTORY:", combined["scene_family"].get("FACTORY"))
    print("岩板 occurrence:", combined["material_multi"].get("岩板"))
    print("Action 门槛:")
    for k, v in dev.items():
        print(f"  {k:18s} {v['combined_support']:4d} {v['status']}")


if __name__ == "__main__":
    main()
