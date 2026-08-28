# -*- coding: utf-8 -*-
"""Stage3 POST-REVIEW — STEP 6/7：People Detector 难例诊断（仅用审核前已保存输出）。

约束：只用审核前已保存的 YOLO（PEOPLE_DETECTOR_BENCHMARK_V1.people_review_order_top12）
与 SigLIP（STAGE3_FINAL_FEATURES.people_presence）输出，禁止重新推理/改阈值（防 post-hoc）。
A. 全部 60（SigLIP 49 段有输出；YOLO 仅 10 段有输出，如实标注覆盖）
B. PEOPLE targeted subset（22 段）
C. YOLO×SigLIP disagreement subset
统一称 Targeted Hard-case Diagnostic Performance，不作泛化 accuracy。
"""
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")


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
    man = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    man_sids = [s["segment_id"] for s in man["segments"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ph = ",".join("?" * len(man_sids))
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", man_sids)]
    conn.close()
    truth = {r["segment_id"]: r["people_presence"] for r in rows}

    feats = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json"), encoding="utf-8"))["segments"]
    bench = json.load(open(os.path.join(DATA_ROOT, "PEOPLE_DETECTOR_BENCHMARK_V1.json"), encoding="utf-8"))
    yolo_out = {r["segment_id"]: r for r in bench.get("people_review_order_top12", [])}
    people_target = {s["segment_id"] for s in man["segments"] if s["sampling_target"] == "PEOPLE"}

    def sig_yes(sid):
        return feats.get(sid, {}).get("people_presence", {}).get("prediction") == "YES"

    def yolo_yes(sid):
        r = yolo_out.get(sid)
        return r["yolo_yes"] if r else None

    def eval_set(sids, pred_fn, label):
        tp = fp = tn = fn = unk = 0
        for sid in sids:
            t = truth.get(sid)
            if t in ("", "UNKNOWN", None):
                unk += 1
                continue
            p = pred_fn(sid)
            if p is None:
                unk += 1
                continue
            t_yes = (t == "YES")
            if p and t_yes:
                tp += 1
            elif p and not t_yes:
                fp += 1
            elif not p and not t_yes:
                tn += 1
            else:
                fn += 1
        m = metrics(tp, fp, tn, fn)
        m["unknown_skipped"] = unk
        print(f"[{label}] n={m['n']} unk={unk} TP/FP/TN/FN={tp}/{fp}/{tn}/{fn} "
              f"P={m['precision']} R={m['recall']} Sp={m['specificity']} F1={m['f1']} "
              f"acc={m['accuracy']} bacc={m['balanced_accuracy']}")
        return m

    out = {"manifest": "STAGE3_PEOPLE_HARDCASE_EVAL",
           "note": ("仅使用审核前已保存输出（YOLO=people_review_order_top12 预存，SigLIP=STAGE3_FINAL_FEATURES）；"
                    "未重新推理/未调阈值；结果为 Targeted Hard-case Diagnostic，非泛化 accuracy"),
           "coverage": {"yolo_saved_in_v31": sum(1 for s in man_sids if s in yolo_out),
                        "siglip_saved_in_v31": sum(1 for s in man_sids if s in feats),
                        "people_target_count": len(people_target)}}

    # A. 全部 60
    sig_all = eval_set(man_sids, sig_yes, "A. SigLIP 全部60")
    yolo_all = eval_set(man_sids, yolo_yes, "A. YOLO  全部60")
    out["A_all_60"] = {"siglip": sig_all, "yolo": yolo_all}

    # B. PEOPLE targeted subset
    pt = list(people_target)
    sig_pt = eval_set(pt, sig_yes, "B. SigLIP PEOPLE子集22")
    yolo_pt = eval_set(pt, yolo_yes, "B. YOLO  PEOPLE子集22")
    out["B_people_subset"] = {"siglip": sig_pt, "yolo": yolo_pt}

    # C. YOLO×SigLIP disagreement（审核前记录的 12 条，10 条在 V3_1）
    dis = [s for s in man_sids if s in yolo_out and yolo_yes(s) != sig_yes(s)]
    print("\nC. YOLO×SigLIP disagreement in V3_1:", len(dis), "条")
    for sid in dis:
        print(f"   {sid[:8]} truth={truth.get(sid)} yolo={yolo_yes(sid)} sig={sig_yes(sid)}")
    yolo_dis = eval_set(dis, yolo_yes, "C. YOLO  disagreement子集")
    sig_dis = eval_set(dis, sig_yes, "C. SigLIP disagreement子集")
    out["C_disagreement_subset"] = {"count": len(dis),
                                    "segments": [{"segment_id": s, "truth": truth.get(s),
                                                  "yolo_yes": yolo_yes(s), "siglip_yes": sig_yes(s)} for s in dis],
                                    "yolo": yolo_dis, "siglip": sig_dis}

    # STEP 7: 对比汇总（全部基于审核前输出）
    out["step7_summary"] = {
        "yolo_all60": yolo_all, "siglip_all60": sig_all,
        "verdict": ("PeoplePresenceAnalyzerV2 候选成立" if
                    (yolo_all["f1"] >= 70 or yolo_pt["f1"] >= 70)
                    else "PeoplePresenceAnalyzerV2 证据不足"),
        "note": "决策依据为审核前冻结输出；阈值/路由若调整须另开 DEV tuning，禁止 post-hoc"}
    p = os.path.join(DATA_ROOT, "STAGE3_PEOPLE_HARDCASE_EVAL.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
