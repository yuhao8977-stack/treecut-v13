# -*- coding: utf-8 -*-
"""Stage3 TRACK A — A3/A4/A5：SemanticActionAnalyzerV1 DEV 评估（333+60）。

对每段：SemanticActionAnalyzerV1（ASR/OCR/component/motion 多证据）→ action_sequence。
对照：人工 action_sequence（atomic，真值）。
输出逐 action：support / P / R / F1（atomic 级，A5：不得把 group 正确当 atomic 正确）。
component 证据用审核前冻结 SigLIP features（POST-REVIEW 前的 static_vision_v2 component 预测）。
"""
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

ATOMS = ["PERSON_SPEAKING", "PULL_OUT", "RETRACT", "OPEN_DRAWER", "CLOSE_DRAWER",
         "OPEN_CABINET", "CLOSE_CABINET", "OPERATE_SOCKET", "OPEN_SINK_COVER",
         "STATIC_DISPLAY", "OTHER"]


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
    az = SemanticActionAnalyzerV1()

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
    # ASR/OCR
    asr_map, ocr_map = {}, {}
    for r in conn.execute("SELECT asset_id, text_corrected FROM transcripts WHERE text_corrected IS NOT NULL"):
        asr_map.setdefault(r["asset_id"], []).append(r["text_corrected"])
    for r in conn.execute("SELECT asset_id, text FROM ocr_text WHERE text IS NOT NULL"):
        ocr_map.setdefault(r["asset_id"], []).append(r["text"])
    # keyframes
    kf_map = {}
    for r in conn.execute("SELECT segment_id, image_path FROM keyframes ORDER BY segment_id, timestamp_ms"):
        kf_map.setdefault(r["segment_id"], []).append(r["image_path"])
    # component（审核前冻结 SigLIP）
    feats = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json"), encoding="utf-8"))["segments"]
    conn.close()

    # ---- 逐段预测 ----
    per_atom = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "n": 0})
    n_valid = 0
    for sid in all_sids:
        tset = set(truth_seq.get(sid, []))
        if not tset:
            continue
        n_valid += 1
        fr = kf_map.get(sid, [])[:10]
        # asset 级 ASR/OCR
        seg_asset = None
        try:
            c2 = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
            seg_asset = c2.execute("SELECT asset_id FROM segments WHERE segment_id=?", (sid,)).fetchone()[0]
            c2.close()
        except Exception:
            pass
        asr_text = " ".join(asr_map.get(seg_asset or "", []))[:600]
        ocr_text = " ".join(ocr_map.get(seg_asset or "", []))[:300]
        comp = feats.get(sid, {}).get("component", {}).get("prediction", [])
        if not isinstance(comp, list):
            comp = []
        out = az.analyze(fr, asr_text=asr_text, ocr_text=ocr_text, component=comp)
        pset = set(out["action_sequence"])
        for a in ATOMS:
            t_hit = a in tset
            p_hit = a in pset
            if p_hit and t_hit:
                per_atom[a]["tp"] += 1
            elif p_hit and not t_hit:
                per_atom[a]["fp"] += 1
            elif t_hit and not p_hit:
                per_atom[a]["fn"] += 1
            if t_hit:
                per_atom[a]["n"] += 1

    # ---- 输出 ----
    print(f"有效段: {n_valid}")
    res = {}
    for a in ATOMS:
        s = per_atom[a]
        P = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) else 0
        R = s["tp"] / s["n"] if s["n"] else 0
        res[a] = {"support": s["n"], "tp": s["tp"], "fp": s["fp"], "fn": s["fn"],
                  "precision": round(P * 100, 1), "recall": round(R * 100, 1),
                  "f1": round(f1(P, R) * 100, 1)}
        print(f"  {a:18s} support={s['n']:4d} P={res[a]['precision']:5.1f} "
              f"R={res[a]['recall']:5.1f} F1={res[a]['f1']:5.1f}")

    out = {"manifest": "SEMANTIC_ACTION_ANALYZER_V1_DEV_EVAL",
           "scope": "Cal333+Stage3 DEV（atomic 级，非 group 冒充）",
           "n_valid": n_valid, "per_atom": res,
           "architecture": "rule-based state-change + ASR/OCR phrases + component hints + motion evidence(仅提示)",
           "status": "STAGE3_CANDIDATE_V1"}
    p = os.path.join(DATA_ROOT, "SEMANTIC_ACTION_ANALYZER_V1_DEV_EVAL.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)


if __name__ == "__main__":
    main()
