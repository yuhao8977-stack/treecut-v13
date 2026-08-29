# -*- coding: utf-8 -*-
"""Stage3 TRACK 3 — SemanticActionAnalyzerV2 DEV 评估（vs V1）。

对照：V1（规则基）与 V2（对象状态变化）在同一 Cal333+Stage3 段上的 atomic 级 P/R/F1。
重点：OPEN_DRAWER / CLOSE_DRAWER / OPEN_CABINET / CLOSE_CABINET / PULL_OUT / RETRACT。
目标：至少 3 个真 semantic action F1>=30（且非 OTHER/STATIC_DISPLAY/PERSON_SPEAKING）。
"""
import json
import os
import sqlite3
import sys
from collections import defaultdict

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

ATOMS = ["PERSON_SPEAKING", "PULL_OUT", "RETRACT", "OPEN_DRAWER", "CLOSE_DRAWER",
         "OPEN_CABINET", "CLOSE_CABINET", "OPERATE_SOCKET", "OPEN_SINK_COVER",
         "STATIC_DISPLAY", "OTHER"]
KEY_ACTIONS = ["OPEN_DRAWER", "CLOSE_DRAWER", "OPEN_CABINET", "CLOSE_CABINET",
               "PULL_OUT", "RETRACT"]


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def main():
    from treecut.services.semantic_action_v1 import SemanticActionAnalyzerV1
    from treecut.services.semantic_action_v2 import SemanticActionAnalyzerV2
    az1 = SemanticActionAnalyzerV1()
    az2 = SemanticActionAnalyzerV2()

    cal = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = [s["segment_id"] for s in cal["segments"]]
    tman = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    t_sids = [s["segment_id"] for s in tman["segments"]]
    all_sids = cal_sids + t_sids

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    truth_seq = {}
    for r in conn.execute("SELECT segment_id, action_sequence FROM canonical_human_truth WHERE is_current=1"):
        truth_seq[r["segment_id"]] = jload(r["action_sequence"])
    ph = ",".join("?" * len(t_sids))
    for r in conn.execute(f"SELECT segment_id, action_sequence, review_status FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", t_sids):
        if r["review_status"] != "EXCLUDED":
            truth_seq[r["segment_id"]] = jload(r["action_sequence"])
    asr_map, ocr_map = {}, {}
    for r in conn.execute("SELECT asset_id, text_corrected FROM transcripts WHERE text_corrected IS NOT NULL"):
        asr_map.setdefault(r["asset_id"], []).append(r["text_corrected"])
    for r in conn.execute("SELECT asset_id, text FROM ocr_text WHERE text IS NOT NULL"):
        ocr_map.setdefault(r["asset_id"], []).append(r["text"])
    kf_map = {}
    for r in conn.execute("SELECT segment_id, image_path FROM keyframes ORDER BY segment_id, timestamp_ms"):
        kf_map.setdefault(r["segment_id"], []).append(r["image_path"])
    feats = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json"), encoding="utf-8"))["segments"]
    seg_asset = {}
    for r in conn.execute("SELECT segment_id, asset_id FROM segments"):
        seg_asset[r["segment_id"]] = r["asset_id"]
    conn.close()

    def run(az, tag):
        per = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "n": 0})
        n_valid = 0
        # 只评估含关键动作真值的段（V2 状态变化评估聚焦 6 类，减少耗时）
        focus_sids = [sid for sid in all_sids
                      if set(truth_seq.get(sid, [])) & set(KEY_ACTIONS)]
        print(f"  [{tag}] 关键动作段: {len(focus_sids)}")
        for sid in focus_sids:
            tset = set(truth_seq.get(sid, []))
            if not tset:
                continue
            n_valid += 1
            fr = kf_map.get(sid, [])[:10]
            if len(fr) < 3:
                continue
            asr = " ".join(asr_map.get(seg_asset.get(sid, ""), []))[:600]
            ocr = " ".join(ocr_map.get(seg_asset.get(sid, ""), []))[:300]
            comp = feats.get(sid, {}).get("component", {}).get("prediction", [])
            if not isinstance(comp, list):
                comp = []
            if tag == "v1":
                out = az1.analyze(fr, asr_text=asr, ocr_text=ocr, component=comp)
            else:
                out = az2.analyze(fr, component=comp, asr_text=asr, ocr_text=ocr)
            pset = set(out["action_sequence"])
            for a in ATOMS:
                t_hit, p_hit = a in tset, a in pset
                if p_hit and t_hit:
                    per[a]["tp"] += 1
                elif p_hit and not t_hit:
                    per[a]["fp"] += 1
                elif t_hit and not p_hit:
                    per[a]["fn"] += 1
                if t_hit:
                    per[a]["n"] += 1
        res = {}
        for a in ATOMS:
            s = per[a]
            P = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) else 0
            R = s["tp"] / s["n"] if s["n"] else 0
            res[a] = {"support": s["n"], "tp": s["tp"], "fp": s["fp"], "fn": s["fn"],
                      "precision": round(P * 100, 1), "recall": round(R * 100, 1),
                      "f1": round(f1(P, R) * 100, 1)}
        return res, n_valid

    r1, n1 = run(az1, "v1")
    r2, n2 = run(az2, "v2")
    az2.unload()

    print(f"有效段: V1={n1} V2={n2}")
    print(f"{'action':20s} {'V1 P':>6s} {'V1 R':>6s} {'V1 F1':>6s} | {'V2 P':>6s} {'V2 R':>6s} {'V2 F1':>6s} | dF1")
    summary = {}
    for a in ATOMS:
        v1, v2 = r1[a], r2[a]
        d = v2["f1"] - v1["f1"]
        summary[a] = {"v1": v1, "v2": v2, "delta_f1": round(d, 1)}
        print(f"  {a:18s} {v1['precision']:6.1f} {v1['recall']:6.1f} {v1['f1']:6.1f} | "
              f"{v2['precision']:6.1f} {v2['recall']:6.1f} {v2['f1']:6.1f} | {d:+.1f}")

    # 目标判定：至少 3 个 KEY_ACTIONS F1>=30
    ready = [a for a in KEY_ACTIONS if r2[a]["f1"] >= 30]
    print(f"\nV2 关键动作 F1>=30: {ready} ({len(ready)}/6)")
    print("目标达成:", len(ready) >= 3)

    out = {"manifest": "SEMANTIC_ACTION_ANALYZER_V2_DEV_EVAL",
           "scope": "Cal333+Stage3 DEV（atomic 级，对照 V1）",
           "n_valid": {"v1": n1, "v2": n2},
           "per_atom": summary,
           "key_actions_ready": ready,
           "goal_met_3_of_6_f1_30": len(ready) >= 3,
           "note": "V2 对象状态变化（SigLIP 状态描述 + 运动几何提示）；ASR 仅补充"}
    p = os.path.join(DATA_ROOT, "SEMANTIC_ACTION_ANALYZER_V2_DEV_EVAL.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)


if __name__ == "__main__":
    main()
