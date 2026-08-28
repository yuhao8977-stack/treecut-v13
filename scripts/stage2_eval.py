# -*- coding: utf-8 -*-
"""Stage 2 STEP 19 — 333 Calibration 三路 Benchmark。

对比：
  baseline  : rules+clip-v1（semantic_annotations 映射 V2 枚举）
  stage1    : Stage1 multimodal（visual_cognition.py opencv-heuristic-v0.1 fused）
  stage2    : StaticVisionAnalyzerV2（SigLIP base, GPU cuda:0 fp16）

指标：单值(coverage/cond/effective/macroF1/UNKNOWN)、多标签(micro/macro/exact)、action(group/seq)。
输出：<data_root>/PHASE3_STAGE2_EVAL.json
"""
import json
import os
import sqlite3
import sys
import time
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

from treecut.services.schema_v2 import (SCENE_MAP, PRODUCT_MAP, FUNCTION_MAP,
                                        SHOT_SCALE_MAP, SHOT_ROLE_MAP, PEOPLE_MAP)
from treecut.services.vision_runtime import VisionRuntimeProvider
from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2


def map_baseline(field, raw):
    raw = (raw or "").strip()
    if raw in ("", "UNKNOWN", "未知"):
        return None
    if field == "scene":
        v = SCENE_MAP.get(raw); return v[0] if v else None
    if field == "product":
        v = PRODUCT_MAP.get(raw); return v[0] if v else None
    if field == "shot_scale":
        return SHOT_SCALE_MAP.get(raw)
    if field == "people":
        return PEOPLE_MAP.get(raw.lower())
    if field == "material":
        return raw if raw in ("岩板", "实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃") else None
    if field == "function":
        v = FUNCTION_MAP.get(raw); return v[1] if v else None
    if field == "component":
        v = FUNCTION_MAP.get(raw); return v[0] if v else None
    if field == "shot_role":
        return SHOT_ROLE_MAP.get(raw)
    if field == "action":
        from treecut.services.schema_v2 import ACTION_MAP
        v = ACTION_MAP.get(raw); return v[1] if v else None
    return None


def main():
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # 333 eligible（manifest rec-v1）
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    eligible = {s["segment_id"] for s in man["segments"]}
    segs = [r for r in conn.execute(
        "SELECT segment_id, asset_id, start_ms, end_ms FROM segments WHERE segment_id IN "
        "(SELECT segment_id FROM canonical_human_truth WHERE is_current=1)")]
    segs = [r for r in segs if r["segment_id"] in eligible]
    print("评估段:", len(segs), flush=True)
    truth_map = {r["segment_id"]: r for r in conn.execute(
        "SELECT * FROM canonical_human_truth WHERE is_current=1")}
    baseline_map = {r["target_id"]: r for r in conn.execute(
        "SELECT * FROM semantic_annotations WHERE status='candidate'")}
    conn.close()

    # Stage2 analyzer（GPU，一次加载）
    rt = VisionRuntimeProvider()
    an = StaticVisionAnalyzerV2(rt)
    t0 = time.time()
    rows = []
    for i, s in enumerate(segs):
        sid = s["segment_id"]
        # frames
        with sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True) as c:
            c.row_factory = sqlite3.Row
            frames = [r["image_path"] for r in c.execute(
                "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY timestamp_ms LIMIT 5", (sid,))]
        # stage2
        try:
            r2 = an.analyze(frames) if frames else {"error": "no_frames"}
        except Exception as e:
            r2 = {"error": str(e)[:100]}
        cand2 = {}
        if "error" not in r2:
            cand2 = {
                "scene": r2["scene_family"]["prediction"], "product": r2["product_family"]["prediction"],
                "shot_scale": r2["shot_scale"]["prediction"], "people": r2["people_presence"]["prediction"],
                "material": r2["material"]["prediction"], "component": r2["component"]["prediction"],
                "function": r2["function"]["prediction"], "shot_role": r2["shot_role"]["prediction"],
                "action_group": "UNKNOWN", "action_sequence": [],
            }
        # baseline
        bl = baseline_map.get(sid)
        baseline = {}
        for f, k in (("scene", "scene"), ("product", "product"), ("shot_scale", "shot_type"),
                     ("people", "people_presence"), ("material", "material"),
                     ("function", "function"), ("component", "function"),
                     ("shot_role", "shot_type"), ("action", "action")):
            baseline[f] = map_baseline(f, bl[k]) if bl else None
        t = truth_map[sid]
        rows.append({
            "segment_id": sid,
            "truth": {f: t[f] for f in ("scene_family", "product_family", "shot_scale",
                                        "people_presence", "material", "component", "function",
                                        "shot_role", "action_group", "atomic_action")},
            "baseline": baseline,
            "stage2": cand2,
        })
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(segs)} elapsed {time.time()-t0:.0f}s", flush=True)
    an.unload()
    print(f"Stage2 推理总耗时 {time.time()-t0:.0f}s, 平均 {(time.time()-t0)/len(segs):.1f}s/段", flush=True)

    # ---------------- metrics ----------------
    TRUTH_KEY = {"scene": "scene_family", "product": "product_family", "shot_scale": "shot_scale",
                 "people": "people_presence", "material": "material", "component": "component",
                 "function": "function", "shot_role": "shot_role"}

    def f1(p, r):
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def eval_single(rows, which, field):
        key = TRUTH_KEY[field]
        tp = fp = fn = unk = 0
        for r in rows:
            truth = r["truth"][key]
            if truth in ("", "UNKNOWN", "NOT_APPLICABLE", None):
                continue
            pred = r[which].get(field)
            if pred in ("", "UNKNOWN", "NOT_APPLICABLE", None):
                unk += 1; fn += 1; continue
            if pred == truth: tp += 1
            else: fp += 1; fn += 1
        hv = tp + fp + fn
        ans = tp + fp
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        return {"coverage": round(ans / hv * 100, 1) if hv else 0,
                "conditional_accuracy": round(tp / ans * 100, 1) if ans else 0,
                "effective_correct_rate": round(tp / hv * 100, 1) if hv else 0,
                "macro_f1": round(f1(prec, rec) * 100, 1), "unknown_rate": round(unk / hv * 100, 1) if hv else 0,
                "n": hv}

    def eval_multi(rows, which, field):
        key = TRUTH_KEY[field]
        tp = fp = fn = exact = valid = 0
        for r in rows:
            tv = r["truth"][key]
            if tv in ("", "UNKNOWN", "NOT_APPLICABLE", None):
                continue
            valid += 1
            ts = {tv}; ps = set(r[which].get(field, []) or [])
            if ps == ts: exact += 1
            for lab in ts:
                if lab in ps: tp += 1
                else: fn += 1
            for lab in ps - ts: fp += 1
        mp = tp / (tp + fp) if (tp + fp) else 0.0
        mr = tp / (tp + fn) if (tp + fn) else 0.0
        return {"micro_precision": round(mp * 100, 1), "micro_recall": round(mr * 100, 1),
                "micro_f1": round(f1(mp, mr) * 100, 1), "exact_set_match": round(exact / valid * 100, 1) if valid else 0,
                "n": valid}

    metrics = {}
    for f in ("scene", "product", "shot_scale", "people"):
        metrics[f] = {"baseline": eval_single(rows, "baseline", f),
                      "stage2": eval_single(rows, "stage2", f)}
    for f in ("material", "component", "function", "shot_role"):
        metrics[f] = {"baseline": eval_multi(rows, "baseline", f),
                      "stage2": eval_multi(rows, "stage2", f)}
    # action（stage2 未做时序 → 记录占位）
    metrics["action"] = {"note": "stage2 本轮未含 Temporal Action（STEP 11 单独交付）"}

    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M"), "n_segments": len(rows),
           "stage2_model": "siglip-base-patch16-224",
           "stage2_avg_seconds": round((time.time() - t0) / len(segs), 1),
           "metrics": metrics, "rows": rows,
           "note": ("333 = CALIBRATION_CORPUS_V2（DEV/Calibration 数据，非 holdout；"
                    "成绩为 dev-set performance，禁止称泛化准确率）")}
    with open(os.path.join(DATA_ROOT, "PHASE3_STAGE2_EVAL.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n== metrics (baseline vs stage2) ==")
    for f, m in metrics.items():
        if f == "action":
            print(f, m); continue
        b, s = m["baseline"], m["stage2"]
        if f in ("scene", "product", "shot_scale", "people"):
            print(f"{f:12s} base eff={b['effective_correct_rate']}% | stage2 eff={s['effective_correct_rate']}% cov={s['coverage']}% unk={s['unknown_rate']}%")
        else:
            print(f"{f:12s} base microF1={b['micro_f1']}% | stage2 microF1={s['micro_f1']}% exact={s['exact_set_match']}%")


if __name__ == "__main__":
    main()
