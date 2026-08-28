# -*- coding: utf-8 -*-
"""Stage3 FINAL PRE-REVIEW BATCH — STEP 6-8：Action 原子化候选支持审计 + Variant 回流。

对 60 条 V2 候选逐条给出：
  - action_reason：ASR/OCR 命中的动作关键词 → 映射到原子动作（OPEN_DRAWER/CLOSE_DRAWER/OPEN_CABINET/
    CLOSE_CABINET/OPERATE_SOCKET/OPEN_SINK_COVER/PULL_OUT/RETRACT）
  - existing_support：该原子动作在 canonical_human_truth(333 当前真值) 中的条数
  - potential_post_review_support：若本条人工确认 → 支持量 +1
  - LIBRARY_CANDIDATE_GAP：candidate=0 的原子动作 → 若候选池中命中该原子则列 GAP_CLOSED_CANDIDATE，
    否则 GAP_UNCOVERED（回流配额时优先补）。
Variant：EXTENDABLE 已 184 无需补；STANDARD/FLOATING/FLOOR 若发现=0 则不伪造配额 → 回流 Action/People。
"""
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

# ASR/OCR 关键词 → 原子动作
ACTION_KEYWORDS = {
    "OPEN_DRAWER": ["打开抽屉", "拉抽屉", "抽屉拉开", "抽出抽屉"],
    "CLOSE_DRAWER": ["关闭抽屉", "关抽屉", "抽屉推回", "推进抽屉", "关上抽屉"],
    "OPEN_CABINET": ["打开柜门", "打开柜子", "开柜门", "开柜"],
    "CLOSE_CABINET": ["关闭柜门", "关柜门", "关上柜子", "合上柜门"],
    "OPERATE_SOCKET": ["插电", "插座", "插头", "通电", "插上电"],
    "OPEN_SINK_COVER": ["水槽盖", "打开水槽", "掀开水槽", "水槽"],
    "PULL_OUT": ["拉出", "抽出", "拉伸", "伸缩拉出"],
    "RETRACT": ["收回", "缩回", "推回原位", "收纳"],
}
# 宽松映射（动作组级，供 reasoning）
ACTION_GROUP_MAP = {
    "OPEN_DRAWER": "DRAWER", "CLOSE_DRAWER": "DRAWER",
    "OPEN_CABINET": "CABINET", "CLOSE_CABINET": "CABINET",
    "OPERATE_SOCKET": "SOCKET", "OPEN_SINK_COVER": "SINK",
    "PULL_OUT": "EXTEND", "RETRACT": "EXTEND",
}


def main():
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # 333 当前真值的原子动作支持
    support = Counter()
    for r in conn.execute(
            "SELECT atomic_action FROM canonical_human_truth WHERE is_current=1 AND atomic_action IS NOT NULL AND atomic_action != ''"):
        support[r["atomic_action"]] += 1
    group_support = Counter()
    for r in conn.execute(
            "SELECT action_group FROM canonical_human_truth WHERE is_current=1 AND action_group IS NOT NULL AND action_group != ''"):
        group_support[r["action_group"]] += 1
    conn.close()
    print("原子动作支持:", dict(support))
    print("动作组支持:", dict(group_support))

    v2 = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V2.json"), encoding="utf-8"))
    items = v2["segments"]

    atomic_pool = defaultdict(list)  # atomic -> [candidate segments]
    rows = []
    for it in items:
        sid = it["segment_id"]
        # 用 V2 hits（ASR/OCR 关键词）+ OCR 原文做二次映射
        hits = " ".join(it.get("hits", []))
        matched = []
        for atomic, kws in ACTION_KEYWORDS.items():
            if any(kw in hits for kw in kws):
                matched.append(atomic)
        # 无精确关键词但命中动作组关键词
        loose = []
        if any(k in hits for k in ("抽屉", "柜", "水槽", "插座", "拉出", "伸缩")):
            for atomic, kws in ACTION_KEYWORDS.items():
                if any(k in hits for k in kws):
                    loose.append(atomic)
        matched = sorted(set(matched)) or sorted(set(loose))
        for a in matched:
            atomic_pool[a].append(sid)
        row = {"segment_id": sid, "asset_id": it.get("asset_id", ""),
               "selection_reason": it.get("selection_reason", ""),
               "action_reason": (matched or ["ACTION_KEYWORD_MISS"]),
               "existing_support": {a: support[a] for a in matched},
               "potential_post_review_support": {a: support[a] + 1 for a in matched},
               "raw_hits": it.get("hits", [])}
        rows.append(row)

    # 库缺口：333 中支持=0 的原子动作
    all_atomics = ["OPEN_DRAWER", "CLOSE_DRAWER", "OPEN_CABINET", "CLOSE_CABINET",
                   "OPERATE_SOCKET", "OPEN_SINK_COVER", "PULL_OUT", "RETRACT"]
    gap = {}
    for a in all_atomics:
        if support[a] == 0:
            covered = atomic_pool.get(a, [])
            gap[a] = {"library_support": 0,
                      "candidate_count": len(covered),
                      "candidates": covered[:5],
                      "status": "GAP_CLOSED_CANDIDATE" if covered else "GAP_UNCOVERED"}
    print("\n库缺口:", json.dumps(gap, ensure_ascii=False, indent=1))

    # Variant 回流：检查 V2 variant 配额发现量与 333 支持
    variant_pool_count = len({r["asset_id"] for r in rows if r["selection_reason"] == "product_variant"})
    variant_333 = Counter()
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    for r in conn.execute(
            "SELECT product_variant FROM canonical_human_truth WHERE is_current=1 AND product_variant IS NOT NULL AND product_variant != ''"):
        variant_333[r["product_variant"]] += 1
    conn.close()
    variant_audit = {k: v for k, v in variant_333.items()}

    out = {"manifest": "STAGE3_ACTION_CANDIDATE_SUPPORT",
           "scope": "60 V2 候选逐条；support=canonical_human_truth(333 当前真值)",
           "atomic_support_in_333": dict(support),
           "action_group_support_in_333": dict(group_support),
           "candidates": rows,
           "library_candidate_gap": gap,
           "action_keyword_hit_summary": dict(Counter(
               a for r in rows for a in r["action_reason"] if a != "ACTION_KEYWORD_MISS")),
           "variant_support_in_333": variant_audit,
           "variant_v2_candidates_selected": variant_pool_count,
           "variant_reflow_note": ("EXTENDABLE 支持充足(184)；STANDARD/FLOATING/FLOOR 若发现=0 "
                                   "不伪造配额 → 回流 Action/People 配额。")}
    p = os.path.join(DATA_ROOT, "STAGE3_ACTION_CANDIDATE_SUPPORT.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
