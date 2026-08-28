# -*- coding: utf-8 -*-
"""Stage3 FINAL PRE-REVIEW BATCH — STEP 4-5：People Detector 真实基准（333 DEV）。

真实推理：Ultralytics YOLOv8n（COCO person 类）在 333 段 keyframe 上跑 person 检测。
  - 每段取至多 5 帧，检测 person box；段级判定：任一帧 person conf>=thr → YES。
  - 对比 human truth（canonical_human_truth.people_presence）YES/NO。
  - 输出 P/R/F1/acc + 与 SigLIP 的冲突矩阵。
  - 产出 12 条 People 复核排序：detector 与 SigLIP 分歧 / FP / FN / YES-NO 平衡。
禁止 Holdout。阈值扫描只选 333 上最优 conf。
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

CONF_GRID = [0.15, 0.25, 0.35, 0.45, 0.55]


def f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def main():
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = [s["segment_id"] for s in man["segments"]]
    feats = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json"), encoding="utf-8"))["segments"]

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    truth = {r["segment_id"]: dict(r) for r in conn.execute("SELECT * FROM canonical_human_truth WHERE is_current=1")}
    conn.close()

    from treecut.services.visual_cognition import _imread
    from ultralytics import YOLO
    model = YOLO(r"C:\Users\admin\github\treecut\yolov8n.pt")  # COCO person=0

    # ---- 真实推理 ----
    per_seg = {}  # sid -> max person conf / has_any_person
    t0 = time.time()
    for i, sid in enumerate(cal_sids):
        fr = feats.get(sid, {}).get("keyframes", [])[:5]
        best = 0.0
        any_person = False
        for p in fr:
            img = _imread(p)
            if img is None:
                continue
            res = model.predict(img, conf=0.10, classes=[0], verbose=False)
            if len(res) and res[0].boxes is not None and len(res[0].boxes):
                scores = res[0].boxes.conf.cpu().numpy()
                if len(scores):
                    best = max(best, float(scores.max()))
                    any_person = True
        per_seg[sid] = {"max_conf": round(best, 3), "any_person": any_person}
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/333 {time.time()-t0:.0f}s", flush=True)
    del model

    # ---- 阈值扫描（333 只选 conf）----
    eval_rows = {}
    for thr in CONF_GRID:
        tp = fp = fn = unk = 0
        for sid in cal_sids:
            t = truth.get(sid, {}).get("people_presence", "")
            if t in ("", "UNKNOWN"):
                unk += 1
                continue
            pred_yes = per_seg.get(sid, {}).get("max_conf", 0.0) >= thr
            t_yes = (t == "YES")
            if pred_yes == t_yes:
                tp += 1
            elif pred_yes:
                fp += 1
            else:
                fn += 1
        n = tp + fp + fn
        P = tp / (tp + fp) if (tp + fp) else 0
        R = tp / (tp + fn) if (tp + fn) else 0
        eval_rows[str(thr)] = {"n": n, "unk": unk, "tp": tp, "fp": fp, "fn": fn,
                               "precision": round(P * 100, 1), "recall": round(R * 100, 1),
                               "f1": round(f1(P, R) * 100, 1),
                               "acc": round(tp / n * 100, 1) if n else 0}
        print(f"conf={thr}: P={eval_rows[str(thr)]['precision']} R={eval_rows[str(thr)]['recall']} "
              f"F1={eval_rows[str(thr)]['f1']} acc={eval_rows[str(thr)]['acc']} unk={unk}")

    best_thr = max(CONF_GRID, key=lambda t: eval_rows[str(t)]["f1"])
    best_row = eval_rows[str(best_thr)]
    print(f"\n最优 conf={best_thr} F1={best_row['f1']} P={best_row['precision']} R={best_row['recall']}")

    # ---- SigLIP 对比（同 333 同 truth）----
    sig_tp = sig_fp = sig_fn = 0
    sig_yes = []
    for sid in cal_sids:
        t = truth.get(sid, {}).get("people_presence", "")
        if t in ("", "UNKNOWN"):
            continue
        p = feats.get(sid, {}).get("people_presence", {}).get("prediction", "UNKNOWN")
        sig_yes.append(sid if p == "YES" else None)
        if p == t:
            sig_tp += 1
        elif p == "YES":
            sig_fp += 1
        else:
            sig_fn += 1
    sig_n = sig_tp + sig_fp + sig_fn
    sig_P = sig_tp / (sig_tp + sig_fp) if (sig_tp + sig_fp) else 0
    sig_R = sig_tp / (sig_tp + sig_fn) if (sig_tp + sig_fn) else 0
    siglip = {"n": sig_n, "precision": round(sig_P * 100, 1), "recall": round(sig_R * 100, 1),
              "f1": round(f1(sig_P, sig_R) * 100, 1), "acc": round(sig_tp / sig_n * 100, 1) if sig_n else 0}
    print(f"\nSigLIP: P={siglip['precision']} R={siglip['recall']} F1={siglip['f1']} acc={siglip['acc']}")

    # ---- 12 条 People 复核排序 ----
    # 排序分：detector(YOLO) 与 SigLIP 分歧 +10；YOLO FP(实际NO判YES) +8；YOLO FN(实际YES判NO) +8；
    # 其次 YES/NO 平衡（当前样本 people_pool 偏 YES）。
    truth_map = {sid: truth.get(sid, {}).get("people_presence", "") for sid in cal_sids}
    scored = []
    for sid in cal_sids:
        t = truth_map.get(sid, "")
        if t in ("", "UNKNOWN"):
            continue
        yolo_yes = per_seg.get(sid, {}).get("max_conf", 0.0) >= best_thr
        sig_yes_bool = feats.get(sid, {}).get("people_presence", {}).get("prediction") == "YES"
        s = 0
        reasons = []
        if yolo_yes != sig_yes_bool:
            s += 10
            reasons.append("DETECTOR_SIGLIP_DISAGREE")
        if yolo_yes and t == "NO":
            s += 8
            reasons.append("YOLO_FP")
        if not yolo_yes and t == "YES":
            s += 8
            reasons.append("YOLO_FN")
        if yolo_yes == sig_yes_bool and yolo_yes == (t == "YES"):
            s += 0
            reasons.append("AGREE_CORRECT")
        scored.append({"segment_id": sid, "truth": t, "yolo_yes": yolo_yes,
                       "yolo_conf": per_seg.get(sid, {}).get("max_conf", 0.0),
                       "siglip_yes": sig_yes_bool, "score": s, "reasons": reasons})
    scored.sort(key=lambda r: -r["score"])
    top12 = scored[:12]
    # YES/NO 平衡：确保 top12 里有 NO（若全是 YES，从后补 NO）
    yes_cnt = sum(1 for r in top12 if r["truth"] == "YES")
    if yes_cnt == 12:
        no_rows = [r for r in scored if r["truth"] == "NO" and r not in top12]
        for r in no_rows[:3]:
            top12[-1] = r
            top12.sort(key=lambda x: -x["score"])
    balance = Counter(r["truth"] for r in top12)

    out = {"manifest": "PEOPLE_DETECTOR_BENCHMARK_V1",
           "scope": "Calibration333 DEV ONLY; NOT_HOLDOUT",
           "method": "Ultralytics YOLOv8n(COCO person=0) 段级 max conf; keyframes<=5; conf 网格在 333 上选优",
           "model": "yolov8n.pt", "threshold_grid": eval_rows,
           "best_conf": best_thr, "yolo": best_row,
           "siglip_raw_same_truth": siglip,
           "per_segment": per_seg,
           "dev_disagreement_audit_top12": top12, "top12_truth_balance": dict(balance),
           "note": ("333 上 YOLO 与 SigLIP 分歧审计（有真值，纯信息）；"
                    "60 候选池的 people 复核排序见 people_review_order_top12（由 stage3_people_reorder 写入）；"
                    "YOLO 只用 person 判定，不参与任何标签训练")}
    p = os.path.join(DATA_ROOT, "PEOPLE_DETECTOR_BENCHMARK_V1.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
