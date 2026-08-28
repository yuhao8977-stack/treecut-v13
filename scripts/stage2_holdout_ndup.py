# -*- coding: utf-8 -*-
"""Stage 2 STEP 9 — Holdout vs Calibration 视觉近重复审计（embedding 相似度）。

每个 segment 取代表帧（keyframes 中段帧）→ SigLIP image embedding →
Holdout30 vs Calibration333 两两 cosine 相似度；>0.92 判 near_duplicate（候选），
>0.97 判 exact_duplicate（视觉级）。
"""
import json
import os
import sqlite3
import sys
import time

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

import numpy as np
from treecut.services.vision_runtime import VisionRuntimeProvider
from treecut.services.visual_cognition import _imread


def main():
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_CANDIDATES.json"), encoding="utf-8"))
    hold_sids = [s["segment_id"] for s in hold["segments"]]
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = [s["segment_id"] for s in man["segments"]]
    print("holdout:", len(hold_sids), "| calibration:", len(cal_sids), flush=True)

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    def rep_frame(sid):
        r = conn.execute(
            "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY ABS(timestamp_ms - "
            "(SELECT (MAX(timestamp_ms)+MIN(timestamp_ms))/2 FROM keyframes WHERE segment_id=?)) LIMIT 1",
            (sid, sid)).fetchone()
        return r["image_path"] if r else None

    # SigLIP embedding（复用 static_vision_v2 的 image embedding 逻辑）
    from transformers import AutoModel, AutoProcessor
    import torch
    rt = VisionRuntimeProvider()
    mdl = AutoModel.from_pretrained("google/siglip-base-patch16-224",
                                    cache_dir=str(rt.info.models_dir)).to("cuda:0").half().eval()
    proc = AutoProcessor.from_pretrained("google/siglip-base-patch16-224",
                                         cache_dir=str(rt.info.models_dir))

    def embed(sids):
        paths = [rep_frame(s) for s in sids]
        imgs = []
        ok = []
        for sid, p in zip(sids, paths):
            img = _imread(p) if p else None
            if img is not None:
                imgs.append(img)
                ok.append(sid)
        if not imgs:
            return {}, []
        inp = proc(images=imgs, return_tensors="pt").to("cuda:0")
        with torch.no_grad():
            o = mdl.get_image_features(**inp)
            e = o.pooler_output if hasattr(o, "pooler_output") else o
        e = e.float().cpu().numpy()
        e = e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)
        return {sid: vec for sid, vec in zip(ok, e)}, ok

    h_emb, h_ok = embed(hold_sids)
    c_emb, c_ok = embed(cal_sids)
    print("embeddings:", len(h_emb), "hold /", len(c_emb), "cal", flush=True)

    exact, near, uncert = [], [], []
    hmat = np.stack([h_emb[s] for s in h_ok])
    cmat = np.stack([c_emb[s] for s in c_ok])
    sim = hmat @ cmat.T
    for i, hs in enumerate(h_ok):
        row = sim[i]
        for j, cs in enumerate(c_ok):
            s = float(row[j])
            if s > 0.97:
                exact.append({"holdout": hs, "calibration": cs, "sim": round(s, 4)})
            elif s > 0.92:
                near.append({"holdout": hs, "calibration": cs, "sim": round(s, 4)})
            elif s > 0.88:
                uncert.append({"holdout": hs, "calibration": cs, "sim": round(s, 4)})
    out = {"method": "SigLIP image embedding cosine (representative frame)",
           "exact_duplicate(>0.97)": exact, "near_duplicate(>0.92)": near,
           "uncertain(>0.88)": uncert[:20], "counts": {
               "exact": len(exact), "near": len(near), "uncertain": len(uncert)}}
    p = os.path.join(DATA_ROOT, "HOLDOUT_NEAR_DUP_AUDIT.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("counts:", out["counts"])
    for e_ in exact[:5]:
        print("  EXACT:", e_["holdout"][:12], "~", e_["calibration"][:12], e_["sim"])
    for n_ in near[:5]:
        print("  NEAR:", n_["holdout"][:12], "~", n_["calibration"][:12], n_["sim"])
    conn.close()


if __name__ == "__main__":
    main()
