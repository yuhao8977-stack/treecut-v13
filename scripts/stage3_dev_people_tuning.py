# -*- coding: utf-8 -*-
"""Stage3 TRACK A — A2：People threshold DEV tuning（POST-REVIEW DEV TUNING DATA）。

允许：对 Stage3 60 重新运行 YOLO（此前仅 10 条预存输出）。
数据：Calibration333（333 人工真值）+ Stage3 60（人工真值，EXCLUDED 剔除）。
阈值网格：0.40/0.45/0.50/0.55/0.60/0.65/0.70。
优先避免为 100% recall 造成大量 FP；最终 threshold 冻结于 Stage3 DEV。
Fresh Holdout V1 不参与选择（仅 KNOWN BENCHMARK 参考）。
"""
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

GRID = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]


def f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def metrics(tp, fp, tn, fn):
    P = tp / (tp + fp) if (tp + fp) else 0.0
    R = tp / (tp + fn) if (tp + fn) else 0.0
    Sp = tn / (tn + fp) if (tn + fp) else 0.0
    acc = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) else 0.0
    ba = (R + Sp) / 2
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(P * 100, 1), "recall": round(R * 100, 1),
            "specificity": round(Sp * 100, 1), "f1": round(f1(P, R) * 100, 1),
            "accuracy": round(acc * 100, 1), "balanced_accuracy": round(ba * 100, 1),
            "n": tp + fp + tn + fn}


def main():
    from treecut.services.people_analyzer_v2 import PeoplePresenceAnalyzerV2

    # ---- 收集段集合与真值 ----
    cal = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = [s["segment_id"] for s in cal["segments"]]
    tman = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    t_sids = [s["segment_id"] for s in tman["segments"]]
    all_sids = cal_sids + t_sids

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    truth = {}
    for r in conn.execute("SELECT segment_id, people_presence FROM canonical_human_truth WHERE is_current=1"):
        truth[r["segment_id"]] = r["people_presence"]
    ph = ",".join("?" * len(t_sids))
    for r in conn.execute(f"SELECT segment_id, people_presence, review_status FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", t_sids):
        if r["review_status"] != "EXCLUDED":
            truth[r["segment_id"]] = r["people_presence"]
    conn.close()

    # ---- keyframes 查询 ----
    def kfs(sid):
        try:
            c2 = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
            c2.row_factory = sqlite3.Row
            fr = [r["image_path"] for r in c2.execute(
                "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY timestamp_ms LIMIT 8", (sid,))]
            c2.close()
            return fr
        except Exception:
            return []

    # ---- 重新运行 YOLO（POST-REVIEW DEV TUNING DATA）----
    print("重新对 Cal333+Stage3 运行 YOLO ...")
    az = PeoplePresenceAnalyzerV2()
    per_seg = {}
    for sid in all_sids:
        fr = kfs(sid)
        if fr:
            hits = az._yolo_frames(fr)
            per_seg[sid] = {"max_conf": max(hits) if hits else 0.0,
                            "frame_hit_count": len(hits), "frames_sampled": len(fr[:8])}
    az.unload()
    print("YOLO 推理完成:", len(per_seg), "段")

    # ---- 阈值网格（Cal333 ∪ Stage3，统一 DEV）----
    rows_all = []
    for sid in all_sids:
        t = truth.get(sid)
        if t in ("", "UNKNOWN", None):
            continue
        mc = per_seg.get(sid, {}).get("max_conf", 0.0)
        rows_all.append({"sid": sid, "truth_yes": t == "YES", "max_conf": mc,
                         "set": "CAL333" if sid in set(cal_sids) else "STAGE3"})
    print("有效真值段:", len(rows_all), "（CAL333:", sum(1 for r in rows_all if r['set']=='CAL333'),
          "STAGE3:", sum(1 for r in rows_all if r['set']=='STAGE3'), "）")

    grid_out = {}
    for thr in GRID:
        tp = fp = tn = fn = 0
        for r in rows_all:
            p_yes = r["max_conf"] >= thr
            if p_yes and r["truth_yes"]:
                tp += 1
            elif p_yes and not r["truth_yes"]:
                fp += 1
            elif not p_yes and not r["truth_yes"]:
                tn += 1
            else:
                fn += 1
        m = metrics(tp, fp, tn, fn)
        grid_out[str(thr)] = m
        print(f"conf={thr}: TP/FP/TN/FN={tp}/{fp}/{tn}/{fn} "
              f"P={m['precision']} R={m['recall']} Sp={m['specificity']} F1={m['f1']} "
              f"acc={m['accuracy']} bacc={m['balanced_accuracy']}")

    # 选择：F1 最高；平局取更高 specificity（避免 FP）
    best_thr = max(GRID, key=lambda t: (grid_out[str(t)]["f1"], grid_out[str(t)]["specificity"]))
    print(f"\n冻结 threshold = {best_thr}")

    # ---- 分集合对照 ----
    split = {}
    for sname, cond in (("CAL333", lambda r: r["set"] == "CAL333"),
                        ("STAGE3_DEV", lambda r: r["set"] == "STAGE3")):
        tp = fp = tn = fn = 0
        for r in rows_all:
            if not cond(r):
                continue
            p_yes = r["max_conf"] >= best_thr
            if p_yes and r["truth_yes"]:
                tp += 1
            elif p_yes and not r["truth_yes"]:
                fp += 1
            elif not p_yes and not r["truth_yes"]:
                tn += 1
            else:
                fn += 1
        split[sname] = metrics(tp, fp, tn, fn)
        print(f"[{sname}] conf={best_thr}: TP/FP/TN/FN={tp}/{fp}/{tn}/{fn} "
              f"P={split[sname]['precision']} R={split[sname]['recall']} F1={split[sname]['f1']}")

    out = {"manifest": "PEOPLE_ANALYZER_V2_DEV_EVAL",
           "scope": "POST-REVIEW DEV TUNING DATA（Cal333+Stage3 重新 YOLO 推理）；Fresh Holdout V1 不参与选择",
           "grid": grid_out, "frozen_threshold": best_thr,
           "split": split, "n_valid": len(rows_all),
           "note": "threshold 冻结于 Stage3 DEV；独立评估留待 FRESH_HOLDOUT_V2"}
    p = os.path.join(DATA_ROOT, "PEOPLE_ANALYZER_V2_DEV_EVAL.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)


if __name__ == "__main__":
    main()
