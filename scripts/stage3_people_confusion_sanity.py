# -*- coding: utf-8 -*-
"""Stage3 FINAL PRE-REVIEW SANITY — People 混淆矩阵最终核验（纯离线，不改预测）。

从已存储的 per_segment(max_conf) + canonical truth + STAGE3_FINAL_FEATURES(SigLIP) 重建
完整 4 元混淆矩阵，逐 conf 输出 TP/FP/TN/FN 并校验 TP+FP+TN+FN = 有效样本数。
公式：
  precision = TP/(TP+FP)
  recall    = TP/(TP+FN)
  specificity = TN/(TN+FP)
  f1        = 2PR/(P+R)
  accuracy  = (TP+TN)/(TP+FP+TN+FN)
  balanced_accuracy = (recall+specificity)/2
输出 YES/NO/UNKNOWN support，修正 PEOPLE_DETECTOR_BENCHMARK_V1.json。
不得修改预测本身，只修 evaluation。
"""
import json
import os
import sqlite3
import sys

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

CONF_GRID = [0.15, 0.25, 0.35, 0.45, 0.55]


def f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def main():
    bench = json.load(open(os.path.join(DATA_ROOT, "PEOPLE_DETECTOR_BENCHMARK_V1.json"), encoding="utf-8"))
    per_seg = bench["per_segment"]
    feats = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json"), encoding="utf-8"))["segments"]
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = [s["segment_id"] for s in man["segments"]]

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    truth = {r["segment_id"]: dict(r) for r in conn.execute("SELECT * FROM canonical_human_truth WHERE is_current=1")}
    conn.close()

    # ---- support ----
    support = {"YES": 0, "NO": 0, "UNKNOWN": 0}
    for sid in cal_sids:
        t = truth.get(sid, {}).get("people_presence", "")
        support[t if t in support else "UNKNOWN"] += 1
    n_valid = support["YES"] + support["NO"]
    print(f"support: YES={support['YES']} NO={support['NO']} UNKNOWN={support['UNKNOWN']} n_valid={n_valid}")

    def confusion(pred_yes_fn):
        tp = fp = tn = fn = 0
        for sid in cal_sids:
            t = truth.get(sid, {}).get("people_presence", "")
            if t in ("", "UNKNOWN"):
                continue
            p_yes = pred_yes_fn(sid)
            t_yes = (t == "YES")
            if p_yes and t_yes:
                tp += 1
            elif p_yes and not t_yes:
                fp += 1
            elif not p_yes and not t_yes:
                tn += 1
            else:
                fn += 1
        assert tp + fp + tn + fn == n_valid, f"混淆矩阵和 {tp+fp+tn+fn} != {n_valid}"
        P = tp / (tp + fp) if (tp + fp) else 0.0
        R = tp / (tp + fn) if (tp + fn) else 0.0
        Sp = tn / (tn + fp) if (tn + fp) else 0.0
        acc = (tp + tn) / (tp + fp + tn + fn)
        ba = (R + Sp) / 2
        return {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
                "precision": round(P * 100, 1), "recall": round(R * 100, 1),
                "specificity": round(Sp * 100, 1), "f1": round(f1(P, R) * 100, 1),
                "accuracy": round(acc * 100, 1), "balanced_accuracy": round(ba * 100, 1),
                "sum_check": tp + fp + tn + fn}

    # ---- YOLO per conf ----
    grid = {}
    for thr in CONF_GRID:
        grid[str(thr)] = confusion(lambda sid, t=thr: per_seg.get(sid, {}).get("max_conf", 0.0) >= t)
        r = grid[str(thr)]
        print(f"conf={thr}: TP={r['tp']} FP={r['fp']} TN={r['tn']} FN={r['fn']} "
              f"P={r['precision']} R={r['recall']} Sp={r['specificity']} F1={r['f1']} "
              f"acc={r['accuracy']} bacc={r['balanced_accuracy']} sum={r['sum_check']}")

    # ---- 阈值选择：仅 Calibration333（无 Holdout），以 F1 最优 ----
    best_thr = max(CONF_GRID, key=lambda t: grid[str(t)]["f1"])
    print(f"\nF1 最优 conf={best_thr}（仅 Calibration333 选择）")

    # ---- SigLIP 同真值 ----
    sig = confusion(lambda sid: feats.get(sid, {}).get("people_presence", {}).get("prediction") == "YES")
    print(f"SigLIP: TP={sig['tp']} FP={sig['fp']} TN={sig['tn']} FN={sig['fn']} "
          f"P={sig['precision']} R={sig['recall']} Sp={sig['specificity']} F1={sig['f1']} "
          f"acc={sig['accuracy']} bacc={sig['balanced_accuracy']}")

    # ---- 回写（保留 per_segment / reorder / 元数据，只修 evaluation）----
    best_row = grid[str(best_thr)]
    bench["threshold_grid"] = {k: v for k, v in grid.items()}
    bench["best_conf"] = best_thr
    bench["yolo"] = dict(best_row, conf=best_thr)
    bench["siglip_raw_same_truth"] = sig
    bench["support"] = support
    bench["eval_note"] = ("混淆矩阵 4 元重建（TP/FP/TN/FN，sum=n_valid）；"
                          "旧版把 TN 计入 TP 导致 precision 被高估为 accuracy；"
                          "threshold 仅 Calibration333 选择，未用 Holdout。")
    bench["formulas"] = {
        "precision": "TP/(TP+FP)", "recall": "TP/(TP+FN)",
        "specificity": "TN/(TN+FP)", "f1": "2PR/(P+R)",
        "accuracy": "(TP+TN)/(TP+FP+TN+FN)",
        "balanced_accuracy": "(recall+specificity)/2"}
    p = os.path.join(DATA_ROOT, "PEOPLE_DETECTOR_BENCHMARK_V1.json")
    json.dump(bench, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("-> 已修正", p)
    print(f"最终 best_conf={best_thr} TP/FP/TN/FN = {best_row['tp']}/{best_row['fp']}/"
          f"{best_row['tn']}/{best_row['fn']}")


if __name__ == "__main__":
    main()
