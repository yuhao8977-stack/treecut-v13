# -*- coding: utf-8 -*-
"""Stage3 TRACK 2 — Mini 批 near-dup 最终审计（vs Cal333/Stage3/Holdout/内部）。

EXACT = cos>=0.999；NEAR = cos>=0.95 且全帧 pHash 最小 <=10；Holdout 泄漏 = cos>=0.95（保守）。
"""
import json
import os
import sqlite3
import sys
import numpy as np
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

COS_EXACT = 0.999
COS_NEAR = 0.95
PHASH_NEAR = 10
COS_LEAK = 0.95


def main():
    mini = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_MINI_V1.json"), encoding="utf-8"))
    mini_sids = [s["segment_id"] for s in mini["segments"]]
    npz = np.load(os.path.join(DATA_ROOT, "STAGE3_FINAL_SEGMENT_EMBEDDINGS.npz"), allow_pickle=True)
    ref_sids = [str(s) for s in npz["sids"]]
    ref_emb = npz["embeddings"]
    ref_sid2emb = dict(zip(ref_sids, ref_emb))
    cal = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = {s["segment_id"] for s in cal["segments"]}
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    hold_sids = {s["segment_id"] for s in hold["strata"]}
    tman = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    s3_sids = {s["segment_id"] for s in tman["segments"]}

    # Mini 段 embedding（存于 discovery audit？未存 → 重新算；此处从 features/npz 取，新段需推理）
    from treecut.services.vision_runtime import VisionRuntimeProvider
    from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2
    from treecut.services.visual_cognition import _imread
    import torch
    import cv2
    rt = VisionRuntimeProvider()
    an = StaticVisionAnalyzerV2(rt)
    an._ensure_model()
    for f in an.LABEL_PROMPTS:
        for lab in an.LABEL_PROMPTS[f]:
            an._text_embedding(f, lab)

    def kfs(sid, limit=8):
        c2 = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
        c2.row_factory = sqlite3.Row
        fr = [r["image_path"] for r in c2.execute(
            "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY timestamp_ms LIMIT ?", (sid, limit))]
        c2.close()
        return fr

    def embed(sid):
        if sid in ref_sid2emb:
            return ref_sid2emb[sid]
        fr = kfs(sid)
        imgs = [im for im in (_imread(p) for p in fr) if im is not None]
        if not imgs:
            return None
        inp = an._proc(images=imgs, return_tensors="pt")
        dev = an.runtime.device
        if dev.startswith("cuda"):
            inp = {k: v.to(dev) for k, v in inp.items()}
        with torch.no_grad():
            o = an._model.get_image_features(**inp)
        if hasattr(o, "pooler_output"):
            o = o.pooler_output
        ie = o.cpu().float().numpy()
        ie = ie / (np.linalg.norm(ie, axis=1, keepdims=True) + 1e-9)
        m = ie.mean(axis=0)
        return m / (np.linalg.norm(m) + 1e-9)

    def all_phash(sid):
        out = []
        for p in kfs(sid):
            im = _imread(p)
            if im is None:
                continue
            try:
                g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
                g = cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA)
                dct = cv2.dct(np.float32(g))
                top = dct[:8, :8]
                out.append((top > np.median(top)).astype(np.uint8).flatten())
            except Exception:
                pass
        return out

    def min_hd(pa, pb):
        if not pa or not pb:
            return None
        return min(int(np.count_nonzero(a != b)) for a in pa for b in pb)

    mini_embs = {s: embed(s) for s in mini_sids}
    mini_ph = {s: all_phash(s) for s in mini_sids}
    ref_ph_cache = {}

    def ref_ph(sid):
        if sid not in ref_ph_cache:
            ref_ph_cache[sid] = all_phash(sid)
        return ref_ph_cache[sid]

    def audit(ref_set, label):
        cnt = Counter()
        details = []
        for sid in mini_sids:
            e = mini_embs[sid]
            if e is None:
                continue
            for other in ref_set:
                if other == sid or other not in ref_sid2emb:
                    continue
                cos = float(e @ ref_sid2emb[other])
                if cos < 0.90:
                    continue
                d = min_hd(mini_ph[sid], ref_ph(other))
                if cos >= COS_EXACT:
                    cnt["EXACT"] += 1
                    details.append((sid, other, "EXACT", round(cos, 4), d))
                elif cos >= COS_NEAR and d is not None and d <= PHASH_NEAR:
                    cnt["NEAR"] += 1
                    details.append((sid, other, "NEAR", round(cos, 4), d))
                elif cos >= COS_NEAR and label == "HOLD":
                    cnt["NEAR"] += 1  # Holdout 保守泄漏
                    details.append((sid, other, "HOLD_LEAK", round(cos, 4), d))
                else:
                    cnt["UNCERTAIN"] += 1
        print(f"{label}: {dict(cnt)}")
        if details:
            for d in details[:5]:
                print("   ", d)
        return dict(cnt)

    res = {
        "vs_calibration333": audit(cal_sids, "CAL"),
        "vs_stage3_60": audit(s3_sids, "STAGE3"),
        "vs_holdout30": audit(hold_sids, "HOLD"),
        "internal": audit(set(mini_sids), "INT"),
    }
    an.unload()
    out = {"manifest": "STAGE3_MINI_BATCH_FINAL_NEARDUP",
           "mini_count": len(mini_sids), "result": res,
           "pass": all(v.get("EXACT", 0) == 0 and v.get("NEAR", 0) == 0 for v in res.values())}
    p = os.path.join(DATA_ROOT, "STAGE3_MINI_BATCH_FINAL_NEARDUP.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p, "PASS" if out["pass"] else "FAIL")


if __name__ == "__main__":
    main()
