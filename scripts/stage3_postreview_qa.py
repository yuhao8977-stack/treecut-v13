# -*- coding: utf-8 -*-
"""Stage3 POST-REVIEW — STEP 14/15/16/17：Human QA 检查 + 开发门槛判定 + 下一步推荐。

STEP14：FLAG 异常（全 UNKNOWN、逻辑冲突、action_group 与 sequence 不一致等），不自动改真值。
STEP15：逐核心 action 开发门槛 READY_FOR_DEV / LIMITED / INSUFFICIENT_SAMPLE / ZERO_SUPPORT。
STEP16：是否还需人工审核（只看真实缺口）。
STEP17：下一阶段推荐（A 开发 / B 补最小批 / C 素材库缺口）。
"""
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

DEV_THRESHOLD = 10  # >=10 READY_FOR_DEV; 5-9 LIMITED; 1-4 INSUFFICIENT; 0 ZERO


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    man = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    man_sids = [s["segment_id"] for s in man["segments"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ph = ",".join("?" * len(man_sids))
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", man_sids)]
    cal = [dict(r) for r in conn.execute("SELECT * FROM canonical_human_truth WHERE is_current=1")]
    conn.close()
    man_by = {r["segment_id"]: r for r in rows}

    # ---- STEP 14: QA flags ----
    flags = []
    for r in rows:
        sid = r["segment_id"]
        multiset = {}
        for f in ("material_multi", "component_multi", "function_multi", "shot_role_multi"):
            v = jload(r.get(f))
            multiset[f] = v
        all_unk = all(x == ["UNKNOWN"] for x in multiset.values())
        all_empty = all(not x for x in multiset.values())
        # 全字段 UNKNOWN
        singles = [r.get(f) for f in ("scene_family", "product_family", "product_variant",
                                      "action_group", "people_presence")]
        if all(x in ("UNKNOWN", "") for x in singles) and all_unk:
            flags.append({"segment_id": sid, "type": "ALL_FIELDS_UNKNOWN"})
        # 多标签全选（超过人类合理上限：>6 标签）
        for f, v in multiset.items():
            if len(v) > 6:
                flags.append({"segment_id": sid, "type": "MULTILABEL_OVER_SELECT",
                              "field": f, "labels": v})
        # action_group 与 action_sequence 冲突
        grp = r.get("action_group", "")
        seq = jload(r.get("action_sequence"))
        grp2seq = {"SPEAKING": ["PERSON_SPEAKING"], "STATIC": ["STATIC_DISPLAY"],
                   "DRAWER": ["OPEN_DRAWER", "CLOSE_DRAWER", "OPEN_THEN_CLOSE_DRAWER"],
                   "EXTEND": ["PULL_OUT", "RETRACT"], "CABINET": ["OPEN_CABINET", "CLOSE_CABINET"]}
        if grp in grp2seq and seq and not any(a in grp2seq[grp] for a in seq):
            flags.append({"segment_id": sid, "type": "ACTION_GROUP_SEQ_MISMATCH",
                          "group": grp, "seq": seq})
        # product_family ISLAND 但 variant NOT_APPLICABLE 冲突
        if r.get("product_family") == "ISLAND" and r.get("product_variant") in ("NOT_APPLICABLE",):
            flags.append({"segment_id": sid, "type": "FAMILY_VARIANT_CONFLICT"})
    print("=== STEP 14: Human QA Flags ===")
    for f in flags:
        print("  ", f)
    print("  flags:", len(flags))

    # ---- STEP 15: Action 开发门槛（combined = 333 + 60）----
    cal_seq = Counter()
    for r in cal:
        for a in jload(r.get("action_sequence")):
            cal_seq[a] += 1
    s3_seq = Counter()
    for r in rows:
        for a in jload(r.get("action_sequence")):
            s3_seq[a] += 1
    actions = ["PERSON_SPEAKING", "PULL_OUT", "RETRACT", "OPEN_DRAWER", "CLOSE_DRAWER",
               "OPEN_CABINET", "CLOSE_CABINET", "OPERATE_SOCKET", "OPEN_SINK_COVER",
               "STATIC_DISPLAY", "OTHER"]
    print("\n=== STEP 15: Action 开发门槛（combined=333+60）===")
    dev_status = {}
    for a in actions:
        tot = cal_seq.get(a, 0) + s3_seq.get(a, 0)
        st = ("READY_FOR_DEV" if tot >= DEV_THRESHOLD else
              "LIMITED" if tot >= 5 else
              "INSUFFICIENT_SAMPLE" if tot >= 1 else "ZERO_SUPPORT")
        dev_status[a] = {"combined_support": tot, "status": st,
                         "from_333": cal_seq.get(a, 0), "from_60": s3_seq.get(a, 0)}
        print(f"  {a:18s} combined={tot:4d} ({cal_seq.get(a,0)}+{s3_seq.get(a,0)}) -> {st}")

    # Variant / Scene / Material 门槛
    print("\n=== Variant/Scene/Material 门槛 ===")
    extra_status = {}
    for name, field, cats in (
        ("FLOATING_ISLAND", "product_variant", ["FLOATING_ISLAND"]),
        ("FLOOR_ISLAND", "product_variant", ["FLOOR_ISLAND"]),
        ("CUSTOMER_HOME", "scene_family", ["CUSTOMER_HOME"]),
        ("SHOWROOM", "scene_family", ["SHOWROOM"]),
        ("INSTALLATION_SITE", "scene_family", ["INSTALLATION_SITE"]),
        ("实木", "material_multi", ["实木"]),
        ("奢石", "material_multi", ["奢石"]),
        ("大理石", "material_multi", ["大理石"]),
        ("不锈钢", "material_multi", ["不锈钢"]),
        ("玻璃", "material_multi", ["玻璃"])):
        def cnt(rs, f):
            c = Counter()
            for r in rs:
                if f == "material_multi":
                    for x in jload(r.get(f)):
                        c[x] += 1
                else:
                    v = r.get(f)
                    if v:
                        c[v] += 1
            return c
        tot = cnt(cal, field).get(cats[0], 0) + cnt(rows, field).get(cats[0], 0)
        st = ("READY_FOR_DEV" if tot >= DEV_THRESHOLD else
              "LIMITED" if tot >= 5 else
              "INSUFFICIENT_SAMPLE" if tot >= 1 else "ZERO_SUPPORT / LIBRARY_GAP")
        extra_status[name] = {"combined_support": tot, "status": st}
        print(f"  {name:20s} combined={tot} -> {st}")

    # ---- STEP 16: 是否还需人工审核 ----
    print("\n=== STEP 16: 人工审核需求 ===")
    gaps = {k: v for k, v in dev_status.items() if v["status"] in ("ZERO_SUPPORT", "INSUFFICIENT_SAMPLE")}
    gaps.update({k: v for k, v in extra_status.items() if v["status"].startswith(("ZERO", "INSUFFICIENT"))})
    need_batch = {k: v for k, v in gaps.items() if v["combined_support"] > 0}
    library_gap = {k: v for k, v in gaps.items() if v["combined_support"] == 0}
    verdict16 = ("无需再审，可进入开发" if not need_batch else
                 "需补最小 Targeted Batch（仅真实存在的少量缺口）")
    print("  仍缺(combined>0 但<10):", need_batch)
    print("  素材库缺口(combined=0):", library_gap)
    print("  =>", verdict16)

    # ---- STEP 17: 推荐 ----
    ready = {k: v for k, v in dev_status.items() if v["status"] == "READY_FOR_DEV"}
    if not library_gap and not need_batch:
        rec17 = "OPTION A: 数据足够，开发 PeoplePresenceAnalyzerV2 / SemanticActionAnalyzerV1 / Multi-label routing refinement"
    elif library_gap and not need_batch:
        rec17 = "OPTION C: 关键类别是素材库缺口（非标注问题）→ 标 LIBRARY_DATA_GAP，新增素材后再补"
    else:
        rec17 = "OPTION B: 先补最小人工 Batch（仅 need_batch 中 combined 1-9 的类别）"
    print("  下一步推荐:", rec17)

    out = {"manifest": "STAGE3_HUMAN_QA_FLAGS", "flags": flags, "flag_count": len(flags),
           "step15_action_dev_status": dev_status,
           "step15_extra_dev_status": extra_status,
           "step16_verdict": verdict16,
           "step16_need_batch": need_batch, "step16_library_gap": library_gap,
           "step17_recommendation": rec17,
           "dev_threshold": DEV_THRESHOLD}
    p = os.path.join(DATA_ROOT, "STAGE3_HUMAN_QA_FLAGS.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
