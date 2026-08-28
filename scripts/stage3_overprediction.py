# -*- coding: utf-8 -*-
"""Stage 3 STEP 0+1 — Stage2 基线快照 + Multi-label Overprediction Audit。

审计：Calibration333 + Holdout30 的 material/component/function/shot_role：
  human_avg_label_count vs prediction_avg_label_count、set size 分布、
  precision@prediction、overprediction_rate → 判定"高 label-in 是否因撒网"。
"""
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

MULTI = ["material", "component", "function", "shot_role"]


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    # ---- STEP 0 基线快照 ----
    snap = {
        "manifest_version": "STAGE2_BASELINE_SNAPSHOT",
        "bundle_id": "VISION_MODEL_BUNDLE_V1_1",
        "bundle_lock_sha256": "6c2ce081b9d2a1be",
        "prediction_sha256": "f5c7c5e70c0fa299",
        "human_truth_sha256": "f402a0104e28f591",
        "holdout_manifest_sha256": "31ae951d99f0e792",
        "fresh_holdout_key": {"product": 51.7, "scene": 24.1, "material": 23.2,
                              "component": 49.2, "function": 55.7, "shot_role": 37.3,
                              "people": 0.0, "action_group": 0.0},
        "guard": "V1 Holdout 永久 DO_NOT_TRAIN/DO_NOT_CALIBRATE；V2 独立验证须 FRESH_HOLDOUT_V2",
        "note": "Stage3 所有结果必须与 V1_1 比较；product_family 不得退化",
    }
    json.dump(snap, open(os.path.join(DATA_ROOT, "STAGE2_BASELINE_SNAPSHOT.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("[STEP0] STAGE2_BASELINE_SNAPSHOT 已冻结")

    # ---- Calibration333 human label sizes（canonical multi 列）----
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    sids333 = [s["segment_id"] for s in man["segments"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cal_human = {}
    for r in conn.execute("SELECT segment_id, material_multi, component_multi, function_multi, shot_role_multi FROM canonical_human_truth WHERE is_current=1"):
        if r["segment_id"] in set(sids333):
            cal_human[r["segment_id"]] = {f: len(jload(r[f"{f}_multi"])) for f in MULTI}
    conn.close()
    # Holdout30 human label sizes
    hl = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    ho30 = [s["segment_id"] for s in hl["strata"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ho_human = {r["segment_id"]: {f: len(jload(r[f"{f}_multi"])) for f in MULTI}
                for r in conn.execute("SELECT segment_id, material_multi, component_multi, function_multi, shot_role_multi FROM fresh_holdout_human_review_v1")}
    conn.close()
    # Holdout30 AI prediction set sizes（final routed）
    pred = json.load(open(os.path.join(DATA_ROOT, "HOLDOUT_AI_PREDICTIONS_V1.json"), encoding="utf-8"))
    ho_ai = {s["segment_id"]: {f: len(s["fields"].get(f, {}).get("final", []) or []) for f in MULTI}
             for s in pred["segments"]}

    # ---- Calibration333 AI prediction sizes（重跑 SigLIP）----
    print("[STEP1] 重跑 Calibration333 SigLIP 统计预测标签数...", flush=True)
    from treecut.services.vision_runtime import VisionRuntimeProvider
    from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2
    rt = VisionRuntimeProvider()
    an = StaticVisionAnalyzerV2(rt)
    cal_ai = {}
    t0 = time.time()
    for i, sid in enumerate(sids333):
        with sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True) as c:
            c.row_factory = sqlite3.Row
            fr = [r["image_path"] for r in c.execute(
                "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY timestamp_ms LIMIT 5", (sid,))]
        r2 = an.analyze(fr) if fr else {"error": "no_frames"}
        if "error" not in r2:
            cal_ai[sid] = {f: len(r2[f]["prediction"]) for f in MULTI}
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/333 {time.time()-t0:.0f}s", flush=True)
    an.unload()

    # ---- 统计 ----
    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M"), "fields": {}}
    for f in MULTI:
        def stat(sizes):
            vals = list(sizes.values())
            n = len(vals)
            avg = sum(vals) / n if n else 0
            med = sorted(vals)[n // 2] if n else 0
            p90 = sorted(vals)[int(n * 0.9)] if n else 0
            dist = dict(Counter(vals))
            return {"n": n, "avg": round(avg, 2), "median": med, "p90": p90,
                    "size_dist": {str(k): v for k, v in sorted(dist.items())},
                    "pct_1label": round(dist.get(1, 0) / n * 100, 1) if n else 0,
                    "pct_2plus": round(sum(v for k, v in dist.items() if k >= 2) / n * 100, 1) if n else 0,
                    "pct_4plus": round(sum(v for k, v in dist.items() if k >= 4) / n * 100, 1) if n else 0}
        cal_h = stat({s: cal_human.get(s, {}).get(f, 0) for s in sids333})
        cal_p = stat({s: cal_ai.get(s, {}).get(f, 0) for s in sids333})
        ho_h = stat({s: ho_human.get(s, {}).get(f, 0) for s in ho30})
        ho_p = stat({s: ho_ai.get(s, {}).get(f, 0) for s in ho30})
        over = round(ho_p["avg"] - ho_h["avg"], 2)
        out["fields"][f] = {
            "calibration_human": cal_h, "calibration_prediction": cal_p,
            "holdout_human": ho_h, "holdout_prediction": ho_p,
            "holdout_overprediction_avg_delta": over,
            "verdict": "OVERPREDICTION" if over > 1.0 else (
                "MILD" if over > 0.3 else "NO_OVERPREDICTION")}
        print(f"[{f}] cal human_avg={cal_h['avg']} pred_avg={cal_p['avg']} | ho human_avg={ho_h['avg']} pred_avg={ho_p['avg']} delta={over} {out['fields'][f]['verdict']}")
        print(f"    ho pred size_dist: {ho_p['size_dist']} | 1标签:{ho_p['pct_1label']}% 2+: {ho_p['pct_2plus']}% 4+: {ho_p['pct_4plus']}%")

    json.dump(out, open(os.path.join(DATA_ROOT, "MULTILABEL_OVERPREDICTION_AUDIT_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("-> MULTILABEL_OVERPREDICTION_AUDIT_V1.json")


if __name__ == "__main__":
    main()
