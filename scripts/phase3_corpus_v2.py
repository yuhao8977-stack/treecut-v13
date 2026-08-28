# -*- coding: utf-8 -*-
"""Phase 3 A5/A6 — CALIBRATION_CORPUS_V2 + COVERAGE_MATRIX_V3（unique segment 口径）。"""
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

ELIGIBLE_SOURCES = ("SINGLE_REVIEW", "DOUBLE_REVIEW_AGREED", "DOUBLE_REVIEW_HIERARCHICAL",
                    "THIRD_ADJUDICATION", "TARGETED_SINGLE_REVIEW")

# canonical current（is_current=1）
rows = conn.execute(
    "SELECT * FROM canonical_human_truth WHERE is_current=1").fetchall()
by_source = Counter(r["truth_source"] for r in rows)
print("canonical current 分布:", dict(by_source), "| 总:", len(rows))

usable = {r[0] for r in conn.execute(
    "SELECT segment_id FROM segment_boundary_reviews WHERE usable_as_edit_unit=1")}

eligible, needs_review, excluded = [], [], []
for r in rows:
    sid = r["segment_id"]
    if r["truth_source"] not in ELIGIBLE_SOURCES:
        excluded.append({"segment_id": sid, "reason": f"source={r['truth_source']}"})
        continue
    if r["review_status"] in ("NEEDS_SECOND_REVIEW", "EXCLUDED"):
        needs_review.append({"segment_id": sid, "reason": r["review_status"]})
        continue
    # 可用性：原段看 boundary usable；新段（TARGETED_SINGLE_REVIEW）看视频技术可用
    if r["truth_source"] == "TARGETED_SINGLE_REVIEW":
        seg = conn.execute("SELECT duration_ms FROM segments WHERE segment_id=?", (sid,)).fetchone()
        kf = conn.execute("SELECT COUNT(*) n FROM keyframes WHERE segment_id=?", (sid,)).fetchone()
        if seg is None or (seg["duration_ms"] or 0) <= 0 or (kf["n"] or 0) == 0:
            excluded.append({"segment_id": sid, "reason": "video_unavailable"})
            continue
    else:
        if sid not in usable:
            excluded.append({"segment_id": sid, "reason": "boundary_unusable"})
            continue
    eligible.append(r)

print(f"eligible={len(eligible)} needs_review={len(needs_review)} excluded={len(excluded)}")

# 各来源贡献
src_cnt = Counter(r["truth_source"] for r in eligible)
print("eligible 来源:", dict(src_cnt))
prev_240 = sum(1 for r in eligible if r["truth_source"] in
               ("SINGLE_REVIEW", "DOUBLE_REVIEW_AGREED", "DOUBLE_REVIEW_HIERARCHICAL"))
v3_added = src_cnt.get("THIRD_ADJUDICATION", 0)
tgt_added = src_cnt.get("TARGETED_SINGLE_REVIEW", 0)
print(f"previous≈{prev_240} + V3新增 {v3_added} + Targeted新增 {tgt_added} = {len(eligible)}")

# ---- CALIBRATION_CORPUS_V2_MANIFEST ----
manifest = {
    "manifest_version": "CALIBRATION_CORPUS_V2",
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "unit": "unique segment_id + current canonical_human_truth（同段多轮审核只计 1 次）",
    "counts": {
        "previous_eligible_v1": 240,
        "v3_resolved_added": v3_added,
        "targeted_eligible_added": tgt_added,
        "new_total_unique_eligible": len(eligible),
        "needs_review": len(needs_review),
        "excluded": len(excluded),
    },
    "by_source": dict(src_cnt),
    "segments": [{"segment_id": r["segment_id"], "truth_source": r["truth_source"],
                  "dictionary_version": r["dictionary_version"],
                  "review_status": r["review_status"]} for r in eligible],
    "needs_review_segments": needs_review,
    "excluded_segments": excluded,
    "usage_policy": "Calibration/Active-Learning 数据；禁止当 holdout/test/generalization accuracy；学习后不得回写 VALIDATION_SNAPSHOT_V1",
}
mp = os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json")
with open(mp, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)

# ---- COVERAGE_MATRIX_V3 ----
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
    for (a, b), n in cnt.most_common(80):
        state = "EMPTY" if n < TH["EMPTY"] else ("LOW" if n < TH["LOW"] else ("MEDIUM" if n < TH["MEDIUM"] else "GOOD"))
        combos.append({"dim1": d1, "dim1_value": a, "dim2": d2, "dim2_value": b,
                       "sample_count": n, "coverage_state": state})
gaps = sorted([c for c in combos if c["coverage_state"] in ("EMPTY", "LOW")],
              key=lambda c: (c["sample_count"], c["dim1"]))[:10]
good = sorted([c for c in combos if c["coverage_state"] == "GOOD"],
              key=lambda c: -c["sample_count"])[:10]

# V2 vs V3 对比（V2 数据从旧 manifest/coverage json 读）
old_cov = None
old_path = os.path.join(DATA_ROOT, "COVERAGE_MATRIX_V2.json")
if os.path.exists(old_path):
    old_cov = json.load(open(old_path, encoding="utf-8"))

def dim_val(f, v):
    return v  # 枚举直接比较

old_key = {}
if old_cov:
    for c in old_cov.get("combos", []):
        old_key[(c["dim1"], c["dim1_value"], c["dim2"], c["dim2_value"])] = c["sample_count"]

# 场景/材质多样性统计（V3 eligible 上）
def diversity(field):
    vals = Counter(r[field] for r in eligible if r[field] not in ("UNKNOWN", "NOT_APPLICABLE", ""))
    return vals
scene_div = diversity("scene_family")
material_div = diversity("material")
component_div = diversity("component")
function_div = diversity("function")
action_seq_n = sum(1 for r in eligible if r["action_sequence"] not in ("[]", "", None))
weak_asr = 0  # 新 60 中无 ASR/OCR
for r in eligible:
    if r["truth_source"] == "TARGETED_SINGLE_REVIEW":
        pass

comparison = {
    "scene_family_nonfactory": {k: v for k, v in scene_div.items() if k != "FACTORY"},
    "material_counts": dict(material_div),
    "component_counts": dict(component_div),
    "function_counts": dict(function_div),
    "with_action_sequence": action_seq_n,
    "old_combos_count": len(old_key) if old_key else None,
    "new_combos_count": len(combos),
}

cov = {
    "manifest_version": "COVERAGE_MATRIX_V3",
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "population": f"CALIBRATION_CORPUS_V2（{len(eligible)} unique segment）",
    "thresholds": TH,
    "state_counts": dict(Counter(c["coverage_state"] for c in combos)),
    "total_combos": len(combos),
    "top_strengths": good,
    "top_gaps": gaps,
    "diversity": comparison,
    "combos": combos,
}
cp = os.path.join(DATA_ROOT, "COVERAGE_MATRIX_V3.json")
with open(cp, "w", encoding="utf-8") as f:
    json.dump(cov, f, ensure_ascii=False, indent=1)

print("CALIBRATION_CORPUS_V2 ->", mp)
print("COVERAGE_MATRIX_V3 ->", cp)
print("states:", dict(Counter(c["coverage_state"] for c in combos)))
print("场景分布:", dict(scene_div))
print("材质分布:", dict(material_div))
print("Top gaps:")
for g in gaps:
    print("  ", g["dim1_value"], "x", g["dim2_value"], "=", g["sample_count"])
conn.close()
