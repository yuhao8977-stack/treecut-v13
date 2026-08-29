# -*- coding: utf-8 -*-
"""Stage3 FINAL CONSOLIDATION — Holdout V2 正式 Near-Dup 审计。

Holdout V2 30 条 vs 全部已见（Cal333 + Stage3 60 + Mini18 + Holdout V1 30 + V2 内部）：
EXACT = cos>=0.999；NEAR = cos>=0.95 且全帧 pHash 最小 <=10；UNCERTAIN 记录。
"""
import json
import os
import sqlite3
import sys
import numpy as np
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")

COS_EXACT = 0.999
COS_NEAR = 0.95
PHASH_NEAR = 10
COS_UNC = 0.90


def main():
    v2 = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_MANIFEST_LOCK.json"), encoding="utf-8"))
    v2_sids = [s["segment_id"] for s in v2["strata"]]
    # 已见段
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    seen = {r[0] for r in conn.execute("SELECT segment_id FROM canonical_human_truth")}
    for f in ("TARGETED_REVIEW_STAGE3_V3_1.json", "TARGETED_REVIEW_STAGE3_MINI_V1.json"):
        m = json.load(open(os.path.join(DATA_ROOT, f), encoding="utf-8"))
        seen |= {s["segment_id"] for s in m["segments"]}
    h1 = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    seen |= {s["segment_id"] for s in h1["strata"]}
    seen -= set(v2_sids)
    conn.close()
    print("已见段:", len(seen), "HoldoutV2:", len(v2_sids))

    # embedding（V2 段新算；已见段用 npz 或现算）
    npz = np.load(os.path.join(DATA_ROOT, "STAGE3_FINAL_SEGMENT_EMBEDDINGS.npz"), allow_pickle=True)
    ref_sids = [str(s) for s in npz["sids"]]
    ref_emb = npz["embeddings"]
    ref_map = dict(zip(ref_sids, range(len(ref_sids))))

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
        if sid in ref_map:
            return ref_emb[ref_map[sid]]
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

    v2_embs = {s: embed(s) for s in v2_sids}
    v2_ph = {s: all_phash(s) for s in v2_sids}
    seen_emb = {}
    seen_ph = {}
    for sid in seen:
        e = embed(sid)
        if e is not None:
            seen_emb[sid] = e
            seen_ph[sid] = all_phash(sid)
    print("V2 emb:", len(v2_embs), "seen emb:", len(seen_emb))
    an.unload()

    cnt = Counter()
    details = []
    for sid in v2_sids:
        e = v2_embs[sid]
        if e is None:
            continue
        for osid, oe in seen_emb.items():
            cos = float(e @ oe)
            if cos < COS_UNC:
                continue
            d = min_hd(v2_ph[sid], seen_ph[osid])
            if cos >= COS_EXACT:
                cnt["EXACT"] += 1
                details.append((sid, osid, "EXACT", round(cos, 4), d))
            elif cos >= COS_NEAR and d is not None and d <= PHASH_NEAR:
                cnt["NEAR"] += 1
                details.append((sid, osid, "NEAR", round(cos, 4), d))
            else:
                cnt["UNCERTAIN"] += 1
    # V2 内部
    int_cnt = Counter()
    for i in range(len(v2_sids)):
        for j in range(i + 1, len(v2_sids)):
            e1, e2 = v2_embs[v2_sids[i]], v2_embs[v2_sids[j]]
            if e1 is None or e2 is None:
                continue
            cos = float(e1 @ e2)
            if cos < COS_UNC:
                continue
            d = min_hd(v2_ph[v2_sids[i]], v2_ph[v2_sids[j]])
            if cos >= COS_EXACT:
                int_cnt["EXACT"] += 1
            elif cos >= COS_NEAR and d is not None and d <= PHASH_NEAR:
                int_cnt["NEAR"] += 1
            else:
                int_cnt["UNCERTAIN"] += 1

    print("\nHoldoutV2 vs 全部已见:", dict(cnt))
    print("HoldoutV2 内部:", dict(int_cnt))
    for x in details[:5]:
        print("  ", x)
    ok = cnt.get("EXACT", 0) == 0 and cnt.get("NEAR", 0) == 0 and \
         int_cnt.get("EXACT", 0) == 0 and int_cnt.get("NEAR", 0) == 0
    out = {"manifest": "FRESH_HOLDOUT_V2_NEARDUP_AUDIT",
           "vs_all_seen_dev_holdout1": dict(cnt),
           "internal": dict(int_cnt),
           "pass": ok,
           "n_holdout_v2": len(v2_sids),
           "details": details[:10]}
    p = os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_NEARDUP_AUDIT.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p, "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
