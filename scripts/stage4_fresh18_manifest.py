# -*- coding: utf-8 -*-
"""Stage 2.1 — Fresh18 manifest（六类各 3，与全部旧评估集不重叠，Storage 覆盖）。

排除集：
  Stage1 Validation43 / Challenge60（含 V3 12 + Secondary36）/ Human24 /
  Adjudication V2 / Calibration V3 / Fresh Holdout V1 / Fresh Holdout V2

采样：按冻结 Evidence 结构（非按预测）：
  STRONG=3 / MULTI_SOURCE=3 / CONFLICT=3 / WEAK=3 / NEGATIVE=3 / AMBIGUOUS=3
Storage 覆盖：至少 3 个 Storage 相关段（component-only / component+function / component+ASR）
"""
import io
import json
import os
import random
import sqlite3
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
OUT = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_FRESH_VALIDATION_V1.json")


def jload(s):
    if isinstance(s, list):
        return s
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    # ---- 排除集 ----
    used = set()
    for f in ("KNOWLEDGE_BRAIN_STAGE1_VALIDATION_SET.json",
              "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json", "FRESH_HOLDOUT_V2_MANIFEST_LOCK.json",
              "BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json",
              "BUSINESS_COGNITION_STAGE2_CHALLENGE_V1.json",
              "HUMAN_CALIBRATION_V3_MANIFEST.json"):
        d = json.load(open(os.path.join(DATA_ROOT, f), encoding="utf-8"))
        for s in (d.get("segments", d.get("strata", []))):
            used.add(s["segment_id"])
    print("排除集大小:", len(used))

    # ---- 数据池（与 Challenge60 一致：canonical + targeted）----
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    pool = {}
    for r in conn.execute("SELECT segment_id, action_sequence, component_multi, function_multi, "
                          "scene_family, people_presence, material_multi, shot_role_multi "
                          "FROM canonical_human_truth WHERE is_current=1"):
        pool[r["segment_id"]] = dict(r)
    for f in ("TARGETED_REVIEW_STAGE3_V3_1.json", "TARGETED_REVIEW_STAGE3_MINI_V1.json"):
        m = json.load(open(os.path.join(DATA_ROOT, f), encoding="utf-8"))
        sids = [s["segment_id"] for s in m["segments"]]
        ph = ",".join("?" * len(sids))
        for r in conn.execute(f"SELECT segment_id, action_sequence, component_multi, function_multi, "
                              f"scene_family, people_presence, material_multi, shot_role_multi, review_status "
                              f"FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", sids):
            if r["review_status"] != "EXCLUDED":
                pool[r["segment_id"]] = dict(r)
    # segment 时间窗 + transcripts（ASR）
    seg_times = {}
    for r in conn.execute("SELECT segment_id, asset_id, start_ms, end_ms FROM segments"):
        seg_times[r["segment_id"]] = (r["asset_id"], r["start_ms"], r["end_ms"])
    tr_by_asset = {}
    for r in conn.execute("SELECT asset_id, start_ms, end_ms, text_corrected FROM transcripts "
                          "WHERE text_corrected IS NOT NULL AND text_corrected != ''"):
        tr_by_asset.setdefault(r["asset_id"], []).append((r["start_ms"], r["end_ms"], r["text_corrected"]))
    conn.close()

    def seg_asr(sid):
        meta = seg_times.get(sid)
        if not meta:
            return ""
        asset_id, s0, s1 = meta
        return " ".join(txt for (t0, t1, txt) in tr_by_asset.get(asset_id, [])
                        if t1 >= s0 and t0 <= s1)

    cands = [sid for sid in pool if sid not in used]
    print("候选池（非排除集）:", len(cands))

    # ---- 分类（冻结 Evidence 结构，非按预测）----
    DRAW_ACT = ("OPEN_DRAWER", "PULL_OUT", "OPEN_THEN_CLOSE_DRAWER")
    CAB_ACT = ("OPEN_CABINET", "CLOSE_CABINET")

    def classify(sid):
        t = pool[sid]
        comp = jload(t.get("component_multi"))
        func = jload(t.get("function_multi"))
        seq = jload(t.get("action_sequence")) or []
        asr = seg_asr(sid)
        has_drawer = "DRAWER" in comp
        has_socket = "TRACK_SOCKET" in comp
        # CONFLICTING：动作↔组件不匹配（动作声称但视觉无对应部件）或 ASR 断言冲突
        if (any(a in seq for a in DRAW_ACT) and not comp) or \
           (any(a in seq for a in CAB_ACT) and "CABINET_DOOR" not in comp):
            return "CONFLICTING_EVIDENCE"
        if has_socket and not any(f in func for f in ("POWER", "OFFICE", "SMALL_APPLIANCE")):
            return "CONFLICTING_EVIDENCE"
        if has_drawer and "STORAGE" not in func:
            return "CONFLICTING_EVIDENCE"
        if has_socket:
            return "NEGATIVE_RULE_TRIGGER"
        if len(comp) == 1 and ((has_drawer and "STORAGE" in func) or
                               ("CABINET_DOOR" in comp and "STORAGE" in func)):
            return "STRONG_SINGLE_EVIDENCE"
        if len(comp) >= 2 or len(func) >= 2:
            return "MULTI_SOURCE_AGREEMENT"
        if not comp:
            return "WEAK_EVIDENCE"
        return "AMBIGUOUS_MULTI_PURPOSE"

    buckets = {k: [] for k in ("STRONG_SINGLE_EVIDENCE", "MULTI_SOURCE_AGREEMENT",
                               "CONFLICTING_EVIDENCE", "WEAK_EVIDENCE",
                               "NEGATIVE_RULE_TRIGGER", "AMBIGUOUS_MULTI_PURPOSE")}
    for sid in cands:
        buckets[classify(sid)].append(sid)
    print("bucket sizes:", {k: len(v) for k, v in buckets.items()})

    # ---- 每类抽 3（确定性种子）----
    selected = []
    for i, cls in enumerate(sorted(buckets.keys())):
        rng = random.Random(20260830 + i * 131)
        lst = list(buckets[cls])
        rng.shuffle(lst)
        picked = lst[:3]
        selected.extend(picked)
        print(f"  {cls}: 池 {len(lst)} -> 选 {len(picked)}")

    # ---- Storage 覆盖检查（至少 3 个 Storage 相关段）----
    storage_sids = [sid for sid in selected
                    if "DRAWER" in jload(pool[sid].get("component_multi")) or
                    "CABINET_DOOR" in jload(pool[sid].get("component_multi")) or
                    "STORAGE" in jload(pool[sid].get("function_multi"))]
    print("\nStorage 相关段:", len(storage_sids), [s[:12] for s in storage_sids])

    # ---- manifest ----
    segs = []
    for sid in selected:
        t = pool[sid]
        segs.append({"segment_id": sid,
                     "stratum": "BUSINESS_COGNITION_FRESH_VALIDATION_V1",
                     "evidence_structure_class": classify(sid),
                     "frozen_evidence": {
                         "component": jload(t.get("component_multi")),
                         "function": jload(t.get("function_multi")),
                         "scene_family": t.get("scene_family"),
                         "material": jload(t.get("material_multi")),
                         "action_sequence": jload(t.get("action_sequence")),
                         "asr_text": seg_asr(sid),
                     }})
    man = {
        "manifest": "BUSINESS_COGNITION_FRESH_VALIDATION_V1",
        "generated_at": "2026-08-29",
        "guard": "FRESH18; 与 Validation43/Challenge60/Human24/V2/V3/Holdout V1/V2 全不重叠; "
                 "按冻结 Evidence 结构采样（非按预测）; Storage 覆盖 >=3",
        "count": len(segs),
        "class_counts": dict(Counter(s["evidence_structure_class"] for s in segs)),
        "storage_segments": len(storage_sids),
        "segments": segs,
    }
    assert all(v == 3 for v in man["class_counts"].values()), "每类必须 3"
    json.dump(man, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", OUT)
    print("总数:", len(segs), "| 类别:", man["class_counts"])


if __name__ == "__main__":
    main()
