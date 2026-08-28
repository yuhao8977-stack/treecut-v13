# -*- coding: utf-8 -*-
"""Stage3 FINAL PRE-REVIEW BATCH — STEP 10-11：Visual Near-Duplicate 最终审计（两信号校准版）。

校准证据（STAGE3_FINAL_SEGMENT_EMBEDDINGS.npz，Calibration333 背景）：
  - 333 随机对余弦背景：p50≈0.80 p90≈0.87 p95≈0.89 p99≈0.91 max≈0.975
  - ⇒ 单一余弦阈值无法区分近邻与重复；采用两信号判定：
      NEAR_DUP（强）  ：cos ≥ 0.99（embedding 近恒等）
      NEAR_DUP（中）  ：cos ≥ 0.95 且 pHash(首帧 DCT8x8) 汉明 ≤ 10
      HOLD_OUT 泄漏  ：与 Holdout30 任一 cos ≥ 0.95 或 pHash ≤ 8（保守高召回）
分类：UNIQUE / NEAR_DUP_INTERNAL / NEAR_DUP_CALIBRATION / LEAK_RISK_HOLDOUT。
内部重复组保留 1 条（selection 顺序最先者），其余 DUPLICATE_DROPPED。
"""
import json
import os
import sqlite3
import sys
import numpy as np

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")

COS_STRONG = 0.99
COS_MED = 0.95
PHASH_MED = 10
COS_LEAK = 0.95
PHASH_LEAK = 8


def main():
    npz = np.load(os.path.join(DATA_ROOT, "STAGE3_FINAL_SEGMENT_EMBEDDINGS.npz"), allow_pickle=True)
    sids = [str(s) for s in npz["sids"]]
    emb = npz["embeddings"]
    sid2idx = {s: i for i, s in enumerate(sids)}

    cal = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = set(s["segment_id"] for s in cal["segments"])
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    hold_sids = set(s["segment_id"] for s in hold["strata"])
    v2 = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V2.json"), encoding="utf-8"))
    v2_items = v2["segments"]
    v2_sids = [s["segment_id"] for s in v2_items]

    feats = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json"), encoding="utf-8"))["segments"]

    # ---- 背景校准（333 随机对）----
    from treecut.services.visual_cognition import _imread
    import cv2
    rng = np.random.default_rng(0)
    ci = [sid2idx[s] for s in cal_sids if s in sid2idx]
    S = emb[ci] @ emb[ci].T
    n = len(ci)
    pairs = rng.integers(0, n, size=(20000, 2))
    pairs = pairs[pairs[:, 0] != pairs[:, 1]]
    bg = S[pairs[:, 0], pairs[:, 1]]
    bg_calib = {"n_pairs": len(bg), "p50": round(float(np.percentile(bg, 50)), 4),
                "p90": round(float(np.percentile(bg, 90)), 4),
                "p95": round(float(np.percentile(bg, 95)), 4),
                "p99": round(float(np.percentile(bg, 99)), 4),
                "max": round(float(bg.max()), 4)}

    phash_cache = {}

    def phash(sid):
        if sid in phash_cache:
            return phash_cache[sid]
        fr = feats.get(sid, {}).get("keyframes", [])
        if not fr:
            phash_cache[sid] = None
            return None
        img = _imread(fr[0])
        if img is None:
            phash_cache[sid] = None
            return None
        try:
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            g = cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA)
            g = np.float32(g)
            dct = cv2.dct(g)
            top = dct[:8, :8]
            med = np.median(top)
            phash_cache[sid] = (top > med).astype(np.uint8).flatten()
        except Exception:
            phash_cache[sid] = None
        return phash_cache[sid]

    def hamming(a, b):
        if a is None or b is None:
            return None
        return int(np.count_nonzero(a != b))

    # ---- 逐候选扫描 ----
    rows = []
    for sid in v2_sids:
        if sid not in sid2idx:
            rows.append({"segment_id": sid, "status": "NO_EMBEDDING", "matches": []})
            continue
        sim = emb[sid2idx[sid]] @ emb.T
        sim[sid2idx[sid]] = -1
        order = np.argsort(-sim)
        matches = []
        for j in order:
            if sim[j] < COS_MED - 0.02:
                break
            other = sids[j]
            if other not in cal_sids and other not in hold_sids and other not in set(v2_sids):
                continue
            ph = hamming(phash(sid), phash(other))
            relation = ("HOLDOUT" if other in hold_sids
                        else ("CALIBRATION" if other in cal_sids else "INTERNAL"))
            matches.append({"segment_id": other, "cosine": round(float(sim[j]), 4),
                            "phash_hamming": ph, "relation": relation})
            if len(matches) >= 8:
                break
        rows.append({"segment_id": sid, "status": "SCAN", "matches": matches})

    def classify(sid):
        m = rows[sid2row[sid]]["matches"]
        hold = [x for x in m if x["relation"] == "HOLDOUT"]
        cal = [x for x in m if x["relation"] == "CALIBRATION"]
        inter = [x for x in m if x["relation"] == "INTERNAL"]
        leak = [x for x in hold if x["cosine"] >= COS_LEAK or
                (x["phash_hamming"] is not None and x["phash_hamming"] <= PHASH_LEAK)]
        if leak:
            return "LEAK_RISK_HOLDOUT", leak
        strong_inter = [x for x in inter if x["cosine"] >= COS_STRONG]
        med_inter = [x for x in inter if x["cosine"] >= COS_MED and
                     x["phash_hamming"] is not None and x["phash_hamming"] <= PHASH_MED]
        if strong_inter or med_inter:
            return "NEAR_DUP_INTERNAL", (strong_inter or med_inter)[:3]
        strong_cal = [x for x in cal if x["cosine"] >= COS_STRONG]
        med_cal = [x for x in cal if x["cosine"] >= COS_MED and
                   x["phash_hamming"] is not None and x["phash_hamming"] <= PHASH_MED]
        if strong_cal or med_cal:
            return "NEAR_DUP_CALIBRATION", (strong_cal or med_cal)[:3]
        return "UNIQUE", []

    sid2row = {r["segment_id"]: i for i, r in enumerate(rows)}
    status = {}
    for r in rows:
        st, mm = classify(r["segment_id"])
        status[r["segment_id"]] = (st, mm)

    # ---- 内部重复组去重（保留 selection 序最先）----
    groups = {}
    for sid, (st, mm) in status.items():
        if st == "NEAR_DUP_INTERNAL":
            members = {sid} | {x["segment_id"] for x in mm}
            key = tuple(sorted(members))
            groups.setdefault(key, set()).add(sid)
    drop_internal = set()
    for members in groups.values():
        keep = min(members, key=lambda s: v2_sids.index(s) if s in v2_sids else 999)
        drop_internal |= (members - {keep})

    out_rows = []
    leak_risk = []
    for r in rows:
        sid = r["segment_id"]
        st, mm = status.get(sid, ("UNIQUE", []))
        dropped = "DUPLICATE_DROPPED" if (st == "NEAR_DUP_INTERNAL" and sid in drop_internal) else "KEEP"
        out_rows.append({"segment_id": sid, "near_duplicate_status": st, "keep": dropped,
                         "top_matches": mm})
        if st == "LEAK_RISK_HOLDOUT":
            leak_risk.append({"segment_id": sid, "holdout_dup": mm})

    counts = {}
    for st in ["UNIQUE", "NEAR_DUP_INTERNAL", "NEAR_DUP_CALIBRATION", "LEAK_RISK_HOLDOUT"]:
        counts[st] = sum(1 for r in out_rows if r["near_duplicate_status"] == st)

    res = {"manifest": "STAGE3_NEAR_DUP_FINAL_AUDIT",
           "scope": "60 V2 候选 × (60+333+30)；SigLIP 段级余弦 + pHash(DCT8x8)",
           "method": "两信号判定：cos>=0.99 或 (cos>=0.95 且 pHash<=10)；Holdout 泄漏: cos>=0.95 或 pHash<=8",
           "background_calibration_333": bg_calib,
           "thresholds": {"cos_strong": COS_STRONG, "cos_med": COS_MED, "phash_med": PHASH_MED,
                          "cos_leak": COS_LEAK, "phash_leak": PHASH_LEAK},
           "counts": counts, "dropped_internal": sorted(drop_internal),
           "leak_risk_holdout": leak_risk,
           "segments": out_rows}
    p = os.path.join(DATA_ROOT, "STAGE3_NEAR_DUP_FINAL_AUDIT.json")
    json.dump(res, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)
    print("bg:", bg_calib)
    print("counts:", counts)
    print("LEAK_RISK_HOLDOUT:", leak_risk)
    print("dropped internal:", sorted(drop_internal))


if __name__ == "__main__":
    main()
