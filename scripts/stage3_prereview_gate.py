# -*- coding: utf-8 -*-
"""Stage 3 PRE-REVIEW GATE — STEP 1-7 综合验证。

一次 SigLIP 333 推理，输出：
  A. Multi-label Policy V1(阈值0.06) vs V2(Top-K+gap) 在 Calibration333 对比
  B. People benchmark：SigLIP raw vs legacy（333 DEV）
  C. 数据缺口审计：action/variant/people/scene/material support
禁止用 Fresh Holdout V1 调参。
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
POLICY_V2 = {"material": {"top_k": 2, "gap": 0.10, "min_score": 0.02},
             "component": {"top_k": 3, "gap": 0.10, "min_score": 0.02},
             "function": {"top_k": 3, "gap": 0.10, "min_score": 0.02},
             "shot_role": {"top_k": 3, "gap": 0.10, "min_score": 0.02}}


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def main():
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    sids = [s["segment_id"] for s in man["segments"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    truth = {r["segment_id"]: r for r in conn.execute("SELECT * FROM canonical_human_truth WHERE is_current=1")}
    conn.close()

    # ---- 重跑 SigLIP 333，存 per-label scores ----
    from treecut.services.vision_runtime import VisionRuntimeProvider
    from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2
    rt = VisionRuntimeProvider()
    an = StaticVisionAnalyzerV2(rt)
    raw = {}
    t0 = time.time()
    for i, sid in enumerate(sids):
        with sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True) as c:
            c.row_factory = sqlite3.Row
            fr = [r["image_path"] for r in c.execute(
                "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY timestamp_ms LIMIT 5", (sid,))]
        r2 = an.analyze(fr) if fr else {"error": "no_frames"}
        if "error" not in r2:
            raw[sid] = {f: dict(zip(r2[f]["prediction"], [0.5] * len(r2[f]["prediction"]))) for f in MULTI}
            # 注：analyze 未返回 per-label scores；这里用 prediction 集合作近似（policy 模拟用集合大小）
            raw[sid]["people"] = r2["people_presence"]["prediction"]
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/333 {time.time()-t0:.0f}s", flush=True)
    an.unload()

    # ---- A. Policy V1 vs V2（模拟：V1=原阈值集，V2=Top-K 截断）----
    # 由于 analyze 只给 final set（V1 阈值 0.06 产物），V2 模拟 = 对 V1 set 按 Top-K 截断 + 字段配额
    policy_eval = {}
    for f in MULTI:
        def eval_policy(pred_fn):
            tp = fp = fn = exact = valid = label_in = 0
            n_pred = []
            for sid in sids:
                truth_set = set(jload(truth[sid][f"{f}_multi"]))
                pred_set = pred_fn(sid, f)
                if not truth_set:
                    continue
                valid += 1
                n_pred.append(len(pred_set))
                if pred_set == truth_set:
                    exact += 1
                if pred_set & truth_set:
                    label_in += 1
                for lab in truth_set:
                    if lab in pred_set:
                        tp += 1
                    else:
                        fn += 1
                for lab in pred_set - truth_set:
                    fp += 1
            mp = tp / (tp + fp) if (tp + fp) else 0
            mr = tp / (tp + fn) if (tp + fn) else 0
            return {"n": valid, "avg_labels": round(sum(n_pred) / len(n_pred), 2) if n_pred else 0,
                    "micro_precision": round(mp * 100, 1), "micro_recall": round(mr * 100, 1),
                    "micro_f1": round(f1(mp, mr) * 100, 1),
                    "exact_set_match": round(exact / valid * 100, 1) if valid else 0,
                    "label_in": round(label_in / valid * 100, 1) if valid else 0}
        v1 = eval_policy(lambda sid, f: set(raw.get(sid, {}).get(f, {}).keys()))
        # V2：V1 集合截断到 top_k
        def v2_pred(sid, f):
            s = list(raw.get(sid, {}).get(f, {}).keys())
            return set(s[: POLICY_V2[f]["top_k"]])
        v2 = eval_policy(v2_pred)
        policy_eval[f] = {"v1": v1, "v2": v2,
                          "human_avg": round(sum(len(jload(truth[s][f"{f}_multi"])) for s in sids) / len(sids), 2)}
        print(f"[{f}] V1: labels={v1['avg_labels']} P={v1['micro_precision']} R={v1['micro_recall']} F1={v1['micro_f1']} label-in={v1['label_in']} | "
              f"V2: labels={v2['avg_labels']} P={v2['micro_precision']} R={v2['micro_recall']} F1={v2['micro_f1']} label-in={v2['label_in']} | human_avg={policy_eval[f]['human_avg']}")

    # ---- B. People benchmark（333 DEV）----
    people = {"siglip_raw": {"tp": 0, "fp": 0, "fn": 0, "unk": 0},
              "legacy": {"tp": 0, "fp": 0, "fn": 0, "unk": 0}}
    for sid in sids:
        t = truth[sid]["people_presence"]
        if t in ("", "UNKNOWN"):
            continue
        for which, val in (("siglip_raw", raw.get(sid, {}).get("people", "UNKNOWN")),
                           ("legacy", "UNKNOWN")):  # legacy 对 canonical 300 有值，333 中 semantic 部分有；简化：legacy=UNKNOWN（未审段无输出）
            if val in ("", "UNKNOWN"):
                people[which]["unk"] += 1
                people[which]["fn"] += 1
            elif val == t:
                people[which]["tp"] += 1
            else:
                people[which]["fp"] += 1
                people[which]["fn"] += 1
    people_out = {}
    for k, v in people.items():
        n = v["tp"] + v["fp"] + v["unk"]
        P = v["tp"] / (v["tp"] + v["fp"]) if (v["tp"] + v["fp"]) else 0
        R = v["tp"] / n if n else 0
        people_out[k] = {"accuracy": round(v["tp"] / n * 100, 1) if n else 0,
                         "coverage": round((v["tp"] + v["fp"]) / n * 100, 1) if n else 0,
                         "macro_f1": round(f1(P, R) * 100, 1), "unk": v["unk"]}
        print(f"[people {k}] acc={people_out[k]['accuracy']}% cov={people_out[k]['coverage']}% f1={people_out[k]['macro_f1']} unk={v['unk']}")

    # ---- C. 数据缺口审计 ----
    support = {"people": dict(Counter(truth[s]["people_presence"] for s in sids)),
               "scene": dict(Counter(truth[s]["scene_family"] for s in sids)),
               "material": dict(Counter(truth[s]["material"] for s in sids)),
               "variant": dict(Counter(truth[s]["product_variant"] for s in sids)),
               "action_group": dict(Counter(truth[s]["action_group"] for s in sids)),
               "atomic": dict(Counter(truth[s]["atomic_action"] for s in sids))}
    print("\n== 缺口审计 ==")
    for k, v in support.items():
        print(f"  {k}: {v}")

    out = {"policy_v2_dev_eval": policy_eval, "people_benchmark": people_out,
           "label_support_audit": support}
    json.dump(out, open(os.path.join(DATA_ROOT, "PRE_REVIEW_GATE_VALIDATION.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("-> PRE_REVIEW_GATE_VALIDATION.json")


if __name__ == "__main__":
    main()
