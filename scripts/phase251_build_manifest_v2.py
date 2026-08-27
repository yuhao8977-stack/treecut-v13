# -*- coding: utf-8 -*-
"""Phase 2.5.1 — 重建 CALIBRATION_CORPUS_V1_MANIFEST_V2 + COVERAGE_MATRIX_V2（修正版）。

唯一口径：一个 segment_id 只计一次。
训练单位 = canonical_human_truth 非冲突/非排除 ∩ boundary usable==1。
旧 COVERAGE_MATRIX_V1.json 标记 DEPRECATED_FOR_DOUBLE_COUNT_RISK（不删除）。
"""
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

# ---- 记录数（annotation records，保留口径） ----
v1_records = conn.execute("SELECT COUNT(*) n FROM human_annotations WHERE target_type='segment'").fetchone()["n"]
v2_records = conn.execute("SELECT COUNT(*) n FROM human_annotation_v2").fetchone()["n"]
FIELDS = ["scene", "product", "material", "function", "action", "shot_type", "people_presence"]
def complete(r):
    return all((r[f] or "").strip() not in ("", "UNKNOWN", "未知") for f in FIELDS)
# 合格记录（纯字段完整口径）
v1_ok = sum(1 for r in conn.execute("SELECT * FROM human_annotations") if complete(r))
v2_ok = sum(1 for r in conn.execute("SELECT * FROM human_annotation_v2")
            if complete(r) and r["review_status"] in ("REVIEWED", "GOLD")
            and r["human_confidence"] in ("HIGH", "MEDIUM"))
# 旧 Phase2.5 资格口径（字段完整 + boundary usable）→ 对齐用户 274/58/332
usable = {r[0] for r in conn.execute(
    "SELECT segment_id FROM segment_boundary_reviews WHERE usable_as_edit_unit=1")}
v1_old_ok = sum(1 for r in conn.execute("SELECT * FROM human_annotations")
                if complete(r) and r["target_id"] in usable)
v2_old_ok = sum(1 for r in conn.execute("SELECT * FROM human_annotation_v2")
                if complete(r) and r["review_status"] in ("REVIEWED", "GOLD")
                and r["human_confidence"] in ("HIGH", "MEDIUM") and r["segment_id"] in usable)

# ---- 唯一 segment 口径（canonical_human_truth） ----
rows = {r["segment_id"]: r for r in conn.execute("SELECT * FROM canonical_human_truth")}
all_sids = sorted(rows)
by_source = Counter(r["truth_source"] for r in rows.values())

canon_eligible = [r for r in rows.values() if r["truth_source"] in
                  ("SINGLE_REVIEW", "DOUBLE_REVIEW_AGREED", "DOUBLE_REVIEW_HIERARCHICAL")]
needs_review = [r for r in rows.values() if r["truth_source"] == "NEEDS_ADJUDICATION"]
canon_excluded = [r for r in rows.values() if r["truth_source"] == "EXCLUDED"]

# 训练单位 = canonical eligible ∩ boundary usable
eligible = [r for r in canon_eligible if r["segment_id"] in usable]
boundary_blocked = [r for r in canon_eligible if r["segment_id"] not in usable]
excluded_all = canon_excluded + boundary_blocked
assert len(eligible) + len(needs_review) + len(excluded_all) == len(all_sids), "300 校验失败"

# ---- Manifest V2 ----
training_units = []
for r in eligible:
    training_units.append({
        "segment_id": r["segment_id"],
        "canonical_human_truth": {
            "scene_family": r["scene_family"], "scene_subtype": r["scene_subtype"],
            "product_family": r["product_family"], "product_variant": r["product_variant"],
            "material": r["material"], "component": r["component"],
            "function": r["function"], "action_group": r["action_group"],
            "atomic_action": r["atomic_action"], "shot_scale": r["shot_scale"],
            "shot_role": r["shot_role"], "people_presence": r["people_presence"],
            "product_visibility": r["product_visibility"], "quality": r["quality"],
        },
        "truth_source": r["truth_source"], "agreement_level": r["agreement_level"],
        "human_evidence_count": r["human_evidence_count"],
        "human_confidence": r["human_confidence"],
        "review_status": r["review_status"],
        "dictionary_version": r["dictionary_version"],
    })

manifest_v2 = {
    "manifest_version": "CALIBRATION_CORPUS_V1_MANIFEST_V2",
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "scope_fix": (
        "V1 manifest 的 332 是 annotation_records（含同一 segment 的 v1+v2 两条记录 + "
        "24 条 boundary 不可用段记录），非独立 segment。V2 唯一 segment 口径："
        "一个 segment_id 只出现一次，且训练单位要求 boundary usable==1。"),
    "counts": {
        "annotation_records": {
            "v1_records": v1_records, "v2_records": v2_records,
            "combined_records": v1_records + v2_records,
            "v1_eligible_records_old_rule": v1_old_ok,
            "v2_eligible_records_old_rule": v2_old_ok,
            "combined_eligible_records_old_rule": v1_old_ok + v2_old_ok,
            "v1_complete_records_field_only": v1_ok,
            "v2_complete_records_field_only": v2_ok,
        },
        "unique_segments": len(all_sids),
        "eligible_unique_segments": len(eligible),
        "needs_review_unique_segments": len(needs_review),
        "excluded_unique_segments": len(excluded_all),
        "by_truth_source": dict(by_source),
    },
    "evidence": {
        "single_review": sum(1 for r in eligible if r["truth_source"] == "SINGLE_REVIEW"),
        "double_review_agreed": sum(1 for r in eligible if r["truth_source"] == "DOUBLE_REVIEW_AGREED"),
        "double_review_hierarchical": sum(1 for r in eligible if r["truth_source"] == "DOUBLE_REVIEW_HIERARCHICAL"),
    },
    "training_units": training_units,
    "needs_adjudication_segments": [r["segment_id"] for r in needs_review],
    "excluded_segments": [r["segment_id"] for r in excluded_all],
    "boundary_blocked_segments": [r["segment_id"] for r in boundary_blocked],
    "usage_policy": (
        "每个训练单位 = 1 segment_id + 1 canonical_human_truth；"
        "同 segment 的 v1+v2 双审不构成两个样本；"
        "NEEDS_ADJUDICATION（34）/ EXCLUDED（26：2 无真值 + 24 boundary 不可用）不进训练；"
        "canonical truth 来自 VALIDATION_SNAPSHOT_V1 逻辑子集，学习后不得回写快照。"),
}
mp = os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V1_MANIFEST_V2.json")
with open(mp, "w", encoding="utf-8") as f:
    json.dump(manifest_v2, f, ensure_ascii=False, indent=1)

# ---- Coverage V2（unique segment，canonical truth 源，eligible 240） ----
TH = {"EMPTY": 0, "LOW": 5, "MEDIUM": 20, "GOOD": 50}
dims = [("scene_family", "product_family"), ("product_family", "material"),
        ("scene_family", "action_group"), ("product_family", "function"),
        ("scene_family", "shot_scale"), ("material", "function"),
        ("scene_family", "material"), ("product_family", "action_group")]
combos = []
for d1, d2 in dims:
    cnt = Counter()
    for r in eligible:
        v1v, v2v = r[d1], r[d2]
        if v1v in ("UNKNOWN", "NOT_APPLICABLE", "") or v2v in ("UNKNOWN", "NOT_APPLICABLE", ""):
            continue
        cnt[(v1v, v2v)] += 1
    for (a, b), n in cnt.most_common(60):
        state = "EMPTY" if n < TH["EMPTY"] else ("LOW" if n < TH["LOW"] else ("MEDIUM" if n < TH["MEDIUM"] else "GOOD"))
        combos.append({"dim1": d1, "dim1_value": a, "dim2": d2, "dim2_value": b,
                       "sample_count": n, "coverage_state": state})
gaps = sorted([c for c in combos if c["coverage_state"] in ("EMPTY", "LOW")],
              key=lambda c: (c["sample_count"], c["dim1"]))[:10]
good = sorted([c for c in combos if c["coverage_state"] == "GOOD"],
              key=lambda c: -c["sample_count"])[:10]

# ---- 旧 V1 coverage 对比（维度/值映射） ----
DIM_MAP = {"scene": "scene_family", "product": "product_family",
           "material": "material", "function": "function",
           "action": "action_group", "shot_type": "shot_scale"}
VAL_MAP = {
    "scene": {"工厂": "FACTORY", "展厅": "SHOWROOM", "客户家": "CUSTOMER_HOME"},
    "product": {"岛台": "ISLAND", "伸缩岛台": "ISLAND", "悬浮岛台": "ISLAND",
                "落地岛台": "ISLAND", "吧台": "BAR", "餐边柜": "SIDEBOARD", "茶桌": "DINING_TABLE"},
    "action": {"讲解/演示": "SPEAKING", "拉出/展开": "EXTEND", "收纳/关闭": "EXTEND", "其他": "OTHER"},
    "shot_type": {"全景": "WIDE", "中景": "MEDIUM", "近景": "CLOSE", "特写": "CLOSE_UP"},
}
old_path = os.path.join(DATA_ROOT, "COVERAGE_MATRIX_V1.json")
old_key = {}
if os.path.exists(old_path):
    old = json.load(open(old_path, encoding="utf-8"))
    for c in old.get("combos", []):
        d1 = DIM_MAP.get(c["dim1"], c["dim1"])
        d2 = DIM_MAP.get(c["dim2"], c["dim2"])
        v1 = VAL_MAP.get(c["dim1"], {}).get(c["dim1_value"], c["dim1_value"])
        v2 = VAL_MAP.get(c["dim2"], {}).get(c["dim2_value"], c["dim2_value"])
        old_key[(d1, v1, d2, v2)] = c["sample_count"]
comparison = []
for c in combos:
    o = old_key.get((c["dim1"], c["dim1_value"], c["dim2"], c["dim2_value"]))
    if o is not None:
        comparison.append({"dim1": c["dim1"], "dim1_value": c["dim1_value"],
                           "dim2": c["dim2"], "dim2_value": c["dim2_value"],
                           "old_records_count": o, "new_unique_count": c["sample_count"],
                           "double_count_risk": o - c["sample_count"]})
comparison.sort(key=lambda x: -x["double_count_risk"])

cov_v2 = {
    "manifest_version": "COVERAGE_MATRIX_V2",
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "population": f"canonical_human_truth 唯一 segment（eligible {len(eligible)}，boundary usable）",
    "deprecates": "COVERAGE_MATRIX_V1 → DEPRECATED_FOR_DOUBLE_COUNT_RISK（未删除）",
    "double_count_note": (
        "旧 V1 声明人口 332 条 annotation records，实际组合计数已按 segment set 去重为 291 段，"
        "故组合值对未因 v1+v2 双计放大；但 291 中混入 51 个不可训练段"
        "（34 NEEDS_ADJUDICATION + 17 boundary 不可用），导致 GOOD 覆盖虚高。"
        "V2 只统计可训练唯一段（240），每段只计一次。"),
    "old_vs_new_population": {
        "old_eligible_records": 332,
        "old_unique_segments": 291,
        "old_unusable_segments": 51,
        "new_trainable_unique_segments": len(eligible),
        "reduced_by": 291 - len(eligible),
    },
    "thresholds": TH,
    "state_counts": dict(Counter(c["coverage_state"] for c in combos)),
    "total_combos": len(combos),
    "top_strengths": good,
    "top_gaps": gaps,
    "v1_vs_v2_comparison": comparison[:20],
    "combos": combos,
}
cp = os.path.join(DATA_ROOT, "COVERAGE_MATRIX_V2.json")
with open(cp, "w", encoding="utf-8") as f:
    json.dump(cov_v2, f, ensure_ascii=False, indent=1)

print("MANIFEST_V2:", os.path.basename(mp))
print("  records: v1", v1_records, "v2", v2_records, "combined", v1_records + v2_records)
print("  old-rule eligible records: v1", v1_old_ok, "+ v2", v2_old_ok, "=", v1_old_ok + v2_old_ok)
print("  unique:", len(all_sids), "| eligible(training):", len(eligible),
      "| needs_review:", len(needs_review), "| excluded:", len(excluded_all),
      " (no-truth", len(canon_excluded), "+ boundary", len(boundary_blocked), ")")
print("  evidence: single", sum(1 for r in eligible if r["truth_source"] == "SINGLE_REVIEW"),
      "agreed", sum(1 for r in eligible if r["truth_source"] == "DOUBLE_REVIEW_AGREED"))
print("COVERAGE_V2:", os.path.basename(cp), "| combos:", len(combos),
      "| states:", dict(Counter(c["coverage_state"] for c in combos)))
for c in comparison[:8]:
    print("  cmp:", c["dim1_value"], "x", c["dim2_value"], "| old:", c["old_records_count"],
          "new:", c["new_unique_count"], "| 膨胀:", c["double_count_risk"])
conn.close()
