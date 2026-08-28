# -*- coding: utf-8 -*-
"""Stage 2 PRE-HOLDOUT GATE — 指标完整性 + Trivial Baseline + Ablation + Routing + Holdout 审计。

输出：FIELD_ABLATION_V1.json + 供报告使用的汇总数据。
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
                                        SHOT_SCALE_MAP, SHOT_ROLE_MAP, PEOPLE_MAP, ACTION_MAP)
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
        v = ACTION_MAP.get(raw); return v[1] if v else None
    return None


def main():
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    eligible = {s["segment_id"] for s in man["segments"]}
    truth_map = {r["segment_id"]: r for r in conn.execute(
        "SELECT * FROM canonical_human_truth WHERE is_current=1")}
    baseline_map = {r["target_id"]: r for r in conn.execute(
        "SELECT * FROM semantic_annotations WHERE status='candidate'")}
    sids = sorted(eligible)
    print("评估段:", len(sids), flush=True)

    # ---- Stage2 视觉（英文 prompt，GPU）----
    rt = VisionRuntimeProvider()
    an = StaticVisionAnalyzerV2(rt)
    t0 = time.time()
    rows = {}
    for i, sid in enumerate(sids):
        with sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True) as c:
            c.row_factory = sqlite3.Row
            frames = [r["image_path"] for r in c.execute(
                "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY timestamp_ms LIMIT 5", (sid,))]
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
            }
        bl = baseline_map.get(sid)
        baseline = {}
        for f, k in (("scene", "scene"), ("product", "product"), ("shot_scale", "shot_type"),
                     ("people", "people_presence"), ("material", "material"),
                     ("function", "function"), ("component", "function"),
                     ("shot_role", "shot_type")):
            baseline[f] = map_baseline(f, bl[k]) if bl else None
        rows[sid] = {"truth": truth_map[sid], "baseline": baseline, "stage2": cand2}
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(sids)} {time.time()-t0:.0f}s", flush=True)
    an.unload()
    print(f"Stage2 推理: {time.time()-t0:.0f}s", flush=True)

    TRUTH_KEY = {"scene": "scene_family", "product": "product_family", "shot_scale": "shot_scale",
                 "people": "people_presence", "material": "material", "component": "component",
                 "function": "function", "shot_role": "shot_role"}

    def f1(p, r):
        return 2 * p * r / (p + r) if (p + r) else 0.0

    # ---- 统一指标（single: accuracy/eff/cond/coverage/unk；multi: micro/macro/exact）----
    out = {"n": len(sids), "fields": {}}
    for field in ("scene", "product", "shot_scale", "people"):
        key = TRUTH_KEY[field]
        dist = Counter(r["truth"][key] for r in rows.values())
        majority = dist.most_common(1)[0]
        trivial = majority[1] / len(rows) * 100  # Always-majority accuracy
        res = {"trivial_accuracy": round(trivial, 1), "majority_class": majority[0],
               "truth_dist": dict(dist)}
        for which in ("baseline", "stage2"):
            tp = fp = fn = unk = 0
            for sid, r in rows.items():
                truth = r["truth"][key]
                if truth in ("", "UNKNOWN", "NOT_APPLICABLE", None):
                    continue
                pred = r[which].get(field)
                if pred in ("", "UNKNOWN", "NOT_APPLICABLE", None):
                    unk += 1
                    continue
                if pred == truth:
                    tp += 1
                else:
                    fp += 1
            # 单标签：真值类未命中 = 预测错误 + UNKNOWN；样本数 = tp+fp+unk
            fn = fp + unk
            hv = tp + fp + unk
            res[which] = {
                "accuracy": round(tp / hv * 100, 1) if hv else 0,
                "effective_correct_rate": round(tp / hv * 100, 1) if hv else 0,
                "conditional_accuracy": round(tp / (tp + fp) * 100, 1) if (tp + fp) else 0,
                "coverage": round((tp + fp) / hv * 100, 1) if hv else 0,
                "macro_f1": round(f1(tp / (tp + fp) if (tp + fp) else 0,
                                     tp / (tp + fn) if (tp + fn) else 0) * 100, 1),
                "unknown_rate": round(unk / hv * 100, 1) if hv else 0,
                "tp": tp, "fp": fp, "fn": fn, "unk": unk, "n_valid": hv}
        out["fields"][field] = res

    for field in ("material", "component", "function", "shot_role"):
        key = TRUTH_KEY[field]
        dist = Counter(r["truth"][key] for r in rows.values())
        majority = dist.most_common(1)[0]
        trivial = majority[1] / len(rows) * 100
        res = {"trivial_accuracy": round(trivial, 1), "majority_class": majority[0],
               "truth_dist": dict(dist), "per_class": {}}
        for which in ("baseline", "stage2"):
            tp = fp = fn = exact = valid = 0
            per = {}
            for sid, r in rows.items():
                truth = r["truth"][key]
                if truth in ("", "UNKNOWN", "NOT_APPLICABLE", None):
                    continue
                valid += 1
                ts = {truth}
                ps = set(r[which].get(field, []) or [])
                if ps == ts:
                    exact += 1
                for lab in ts:
                    if lab in ps: tp += 1
                    else:
                        fn += 1
                        per.setdefault(lab, {"tp": 0, "fp": 0, "fn": 0})["fn"] += 1
                for lab in ps - ts:
                    fp += 1
                    per.setdefault(lab, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
                for lab in ts & ps:
                    per.setdefault(lab, {"tp": 0, "fp": 0, "fn": 0})["tp"] += 1
            mp = tp / (tp + fp) if (tp + fp) else 0
            mr = tp / (tp + fn) if (tp + fn) else 0
            res[which] = {"micro_precision": round(mp * 100, 1), "micro_recall": round(mr * 100, 1),
                          "micro_f1": round(f1(mp, mr) * 100, 1),
                          "exact_set_match": round(exact / valid * 100, 1) if valid else 0,
                          "n_valid": valid}
            # per-class（用 stage2 或 baseline 的 per）
            if which == "stage2":
                res["per_class"] = {
                    lab: {"support": dist.get(lab, 0),
                          "precision": round(v["tp"] / (v["tp"] + v["fp"]) * 100, 1) if (v["tp"] + v["fp"]) else 0,
                          "recall": round(v["tp"] / (v["tp"] + v["fn"]) * 100, 1) if (v["tp"] + v["fn"]) else 0,
                          "f1": round(f1(v["tp"] / (v["tp"] + v["fp"]) if (v["tp"] + v["fp"]) else 0,
                                          v["tp"] / (v["tp"] + v["fn"]) if (v["tp"] + v["fn"]) else 0) * 100, 1),
                          "tp": v["tp"], "fp": v["fp"], "fn": v["fn"]}
                    for lab, v in per.items()}
        out["fields"][field] = res

    # ---- Always-岩板 trivial（material 专用）----
    mat = out["fields"]["material"]
    mat["trivial_always_岩板"] = {
        "note": "Always 预测[岩板] 的 microF1（真值 331/333 岩板时极高）",
        "micro_f1": round(f1(1.0, dist.get("岩板", 0) / len(rows)) * 100, 1),
    }

    with open(os.path.join(DATA_ROOT, "FIELD_ABLATION_V1.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("FIELD_ABLATION_V1.json ->", os.path.join(DATA_ROOT, "FIELD_ABLATION_V1.json"))
    for f, r in out["fields"].items():
        print(f"\n== {f} | trivial={r['trivial_accuracy']}% ({r['majority_class']})")
        for w in ("baseline", "stage2"):
            if w in r:
                m = r[w]
                if "micro_f1" in m:
                    print(f"  {w}: microF1={m['micro_f1']}% exact={m['exact_set_match']}% P={m['micro_precision']} R={m['micro_recall']} n={m['n_valid']}")
                else:
                    print(f"  {w}: acc={m['accuracy']}% eff={m['effective_correct_rate']}% cond={m['conditional_accuracy']}% cov={m['coverage']}% unk={m['unknown_rate']}% n={m['n_valid']}")
        if "per_class" in r:
            for lab, v in r["per_class"].items():
                flag = " INSUFFICIENT" if v["support"] < 5 else ""
                print(f"    {lab}: support={v['support']} P={v['precision']} R={v['recall']} F1={v['f1']}{flag}")
    conn.close()


if __name__ == "__main__":
    main()
