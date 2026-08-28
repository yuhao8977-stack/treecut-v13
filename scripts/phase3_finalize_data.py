# -*- coding: utf-8 -*-
"""Phase 3 PART A — 94 条人工数据结算（写入 canonical_human_truth 新版本，保留历史）。

A2/A3: 34 条 V3 裁决 → canonical new_version(truth_version=2, truth_source=THIRD_ADJUDICATION)
  - HIGH/MEDIUM + REVIEWED/GOLD → resolved（更新 current）
  - LOW / NEEDS_SECOND_REVIEW → 保持 NEEDS_ADJUDICATION（不强行生成真值）
A4: 60 条 Targeted → canonical new_version(truth_source=TARGETED_SINGLE_REVIEW)
  - HIGH/MEDIUM + REVIEWED/GOLD + 非 EXCLUDED + 视频可用 → CALIBRATION_ELIGIBLE
  - 新样本无 boundary 记录（boundary 仅原 300），可用性改用技术指标（keyframes 存在 + duration>0）

禁止：自动学习、修改 AI 规则/权重/模型。
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
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

from treecut.services.canonical_truth import CanonicalTruthService

svc = CanonicalTruthService(DB)
conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

def jload(s):
    try:
        return json.loads(s) if s else []
    except Exception:
        return []

def v3_values(r):
    """human_annotation_v3 行 → new_version values（V2.1 结构）。"""
    return {
        "scene_family": r["scene_family"] or "UNKNOWN",
        "scene_subtype": r["scene_subtype"] or "UNKNOWN",
        "product_family": r["product_family"] or "UNKNOWN",
        "product_variant": r["product_variant"] or "UNKNOWN",
        "material": (jload(r["material_multi"]) or ["UNKNOWN"])[0] if r["material_multi"] not in ("[]", "") else "UNKNOWN",
        "component": (jload(r["component_multi"]) or ["UNKNOWN"])[0] if r["component_multi"] not in ("[]", "") else "UNKNOWN",
        "function": (jload(r["function_multi"]) or ["UNKNOWN"])[0] if r["function_multi"] not in ("[]", "") else "UNKNOWN",
        "action_group": r["action_group"] or "UNKNOWN",
        "atomic_action": (jload(r["action_sequence"]) or ["UNKNOWN"])[0] if r["action_sequence"] not in ("[]", "") else "UNKNOWN",
        "shot_scale": r["shot_scale"] or "UNKNOWN",
        "shot_role": (jload(r["shot_role_multi"]) or ["UNKNOWN"])[0] if r["shot_role_multi"] not in ("[]", "") else "UNKNOWN",
        "people_presence": r["people_presence"] or "UNKNOWN",
        "product_visibility": r["product_visibility"] or "UNKNOWN",
        "quality": r["quality"],
        "material_multi": jload(r["material_multi"]),
        "component_multi": jload(r["component_multi"]),
        "function_multi": jload(r["function_multi"]),
        "shot_role_multi": jload(r["shot_role_multi"]),
        "action_sequence": jload(r["action_sequence"]),
        "human_evidence_count": 3,  # V1+V2+V3
    }

def tgt_values(r):
    """targeted_human_review_v1 行 → new_version values。"""
    return {
        "scene_family": r["scene_family"] or "UNKNOWN",
        "scene_subtype": r["scene_subtype"] or "UNKNOWN",
        "product_family": r["product_family"] or "UNKNOWN",
        "product_variant": r["product_variant"] or "UNKNOWN",
        "material": (jload(r["material_multi"]) or ["UNKNOWN"])[0] if r["material_multi"] not in ("[]", "") else "UNKNOWN",
        "component": (jload(r["component_multi"]) or ["UNKNOWN"])[0] if r["component_multi"] not in ("[]", "") else "UNKNOWN",
        "function": (jload(r["function_multi"]) or ["UNKNOWN"])[0] if r["function_multi"] not in ("[]", "") else "UNKNOWN",
        "action_group": r["action_group"] or "UNKNOWN",
        "atomic_action": (jload(r["action_sequence"]) or ["UNKNOWN"])[0] if r["action_sequence"] not in ("[]", "") else "UNKNOWN",
        "shot_scale": r["shot_scale"] or "UNKNOWN",
        "shot_role": (jload(r["shot_role_multi"]) or ["UNKNOWN"])[0] if r["shot_role_multi"] not in ("[]", "") else "UNKNOWN",
        "people_presence": r["people_presence"] or "UNKNOWN",
        "product_visibility": r["product_visibility"] or "UNKNOWN",
        "quality": r["quality"],
        "material_multi": jload(r["material_multi"]),
        "component_multi": jload(r["component_multi"]),
        "function_multi": jload(r["function_multi"]),
        "shot_role_multi": jload(r["shot_role_multi"]),
        "action_sequence": jload(r["action_sequence"]),
        "human_evidence_count": 1,
    }

# ---- A3: 34 V3 ----
v3_rows = conn.execute("SELECT * FROM human_annotation_v3").fetchall()
resolved = []
still_needs = []
for r in v3_rows:
    ok_conf = r["human_confidence"] in ("HIGH", "MEDIUM")
    ok_status = r["review_status"] in ("REVIEWED", "GOLD")
    if ok_conf and ok_status:
        ver = svc.new_version(
            r["segment_id"], v3_values(r),
            truth_source="THIRD_ADJUDICATION", agreement_level="v3_adjudicated",
            human_confidence=r["human_confidence"], review_status=r["review_status"],
            dictionary_version="ANNOTATION_DICTIONARY_V2_1")
        resolved.append({"segment_id": r["segment_id"], "version": ver})
    else:
        still_needs.append({"segment_id": r["segment_id"],
                            "conf": r["human_confidence"], "status": r["review_status"]})
print(f"A3 V3 结算: resolved={len(resolved)} still_needs_review={len(still_needs)}")
for s in still_needs:
    print("  still:", s["segment_id"][:16], s["conf"], s["status"])

# ---- A4: 60 Targeted ----
tgt_rows = conn.execute("SELECT * FROM targeted_human_review_v1").fetchall()
tgt_eligible = []
tgt_excluded = []
for r in tgt_rows:
    ok_conf = r["human_confidence"] in ("HIGH", "MEDIUM")
    ok_status = r["review_status"] in ("REVIEWED", "GOLD")
    if r["review_status"] == "EXCLUDED":
        tgt_excluded.append({"segment_id": r["segment_id"], "reason": "EXCLUDED"})
        continue
    if not (ok_conf and ok_status):
        tgt_excluded.append({"segment_id": r["segment_id"],
                             "reason": f"conf={r['human_confidence']} status={r['review_status']}"})
        continue
    # 视频可用性（技术指标）：keyframes 存在 + duration>0
    seg = conn.execute("SELECT duration_ms FROM segments WHERE segment_id=?", (r["segment_id"],)).fetchone()
    kf = conn.execute("SELECT COUNT(*) n FROM keyframes WHERE segment_id=?", (r["segment_id"],)).fetchone()
    if seg is None or (seg["duration_ms"] or 0) <= 0 or (kf["n"] or 0) == 0:
        tgt_excluded.append({"segment_id": r["segment_id"], "reason": "video_unavailable"})
        continue
    ver = svc.new_version(
        r["segment_id"], tgt_values(r),
        truth_source="TARGETED_SINGLE_REVIEW", agreement_level="single",
        human_confidence=r["human_confidence"], review_status=r["review_status"],
        dictionary_version="ANNOTATION_DICTIONARY_V2_1")
    tgt_eligible.append({"segment_id": r["segment_id"], "version": ver})
print(f"A4 Targeted 结算: eligible={len(tgt_eligible)} excluded={len(tgt_excluded)}")
for e in tgt_excluded:
    print("  excl:", e)

print("version_stats:", svc.version_stats())
conn.close()

# 保存结算中间结果供报告
summary = {
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "v3_resolved": len(resolved),
    "v3_still_needs_review": still_needs,
    "targeted_eligible": len(tgt_eligible),
    "targeted_excluded": tgt_excluded,
}
with open(os.path.join(DATA_ROOT, "PHASE3_FINALIZATION_SUMMARY.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)
print("summary ->", os.path.join(DATA_ROOT, "PHASE3_FINALIZATION_SUMMARY.json"))
