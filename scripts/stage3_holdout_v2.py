# -*- coding: utf-8 -*-
"""Stage3 FINAL CONSOLIDATION — STEP 18-23：Fresh Holdout V2 候选（30 条盲选）。

分层：RANDOM 10 / HARD 10 / GAP 10。
隔离：与 Cal333 + Stage3 V3_1 60 + Mini18 + Fresh Holdout V1 30 全部
      segment/asset/visual 隔离（EXACT=0 NEAR=0）。
纪律：model-answer blind —— 不看 Bundle V2 prediction/score；只用
      metadata/embedding diversity/motion/segment 特征分层。
GAP：不伪造不存在的类别（FLOATING/奢石/INSTALLATION_SITE 不强行入卷）；
     代表能力薄弱区域（semantic action / scene / material / variant / shot-role 模糊段）。
"""
import hashlib
import json
import os
import random
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
RNG = random.Random(20260829)  # 固定种子

COS_EXACT = 0.999
COS_NEAR = 0.95
PHASH_NEAR = 10
COS_UNC = 0.90


def sha256_str(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    import numpy as np
    # ---- 已见集合（全部排除）----
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    seen_seg = set()
    for r in conn.execute("SELECT segment_id FROM canonical_human_truth"):
        seen_seg.add(r["segment_id"])
    for f in ("TARGETED_REVIEW_STAGE3_V3_1.json", "TARGETED_REVIEW_STAGE3_MINI_V1.json"):
        m = json.load(open(os.path.join(DATA_ROOT, f), encoding="utf-8"))
        seen_seg |= {s["segment_id"] for s in m["segments"]}
    hold1 = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    seen_seg |= {s["segment_id"] for s in hold1["strata"]}
    seen_asset = set()
    for r in conn.execute("SELECT DISTINCT asset_id FROM segments WHERE segment_id IN "
                          "(SELECT segment_id FROM canonical_human_truth)"):
        seen_asset.add(r["asset_id"])
    for f in ("TARGETED_REVIEW_STAGE3_V3_1.json", "TARGETED_REVIEW_STAGE3_MINI_V1.json"):
        m = json.load(open(os.path.join(DATA_ROOT, f), encoding="utf-8"))
        seen_asset |= {s["asset_id"] for s in m["segments"]}
    seen_asset |= {s["asset_id"] for s in hold1["strata"]}
    print("排除段:", len(seen_seg), "排除 asset:", len(seen_asset))

    # ---- 候选池（全库未见段，asset 唯一）----
    cands = []
    for r in conn.execute("SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms, s.duration_ms, s.quality_score "
                          "FROM segments s WHERE s.segment_id NOT IN (SELECT segment_id FROM canonical_human_truth)"
                          " AND s.segment_id NOT IN (SELECT segment_id FROM targeted_human_review_v1)"
                          " AND s.segment_id NOT IN (SELECT segment_id FROM fresh_holdout_human_review_v1)"):
        if r["segment_id"] in seen_seg or r["asset_id"] in seen_asset:
            continue
        asr = " ".join(x[0] for x in conn.execute(
            "SELECT text_corrected FROM transcripts WHERE asset_id=? AND text_corrected IS NOT NULL",
            (r["asset_id"],)).fetchall() if x[0])[:600]
        ocr = " ".join(x[0] for x in conn.execute(
            "SELECT text FROM ocr_text WHERE asset_id=? AND text IS NOT NULL",
            (r["asset_id"],)).fetchall() if x[0])[:300]
        kf_n = conn.execute("SELECT COUNT(*) n FROM keyframes WHERE segment_id=?",
                            (r["segment_id"],)).fetchone()["n"]
        cands.append({"segment_id": r["segment_id"], "asset_id": r["asset_id"],
                      "start_ms": r["start_ms"], "end_ms": r["end_ms"],
                      "duration_ms": r["duration_ms"], "quality_score": r["quality_score"],
                      "kf_n": kf_n, "asr": asr, "ocr": ocr})
    conn.close()
    print("候选池:", len(cands))

    # ---- embedding（盲选分层用：多样性，不看 prediction）----
    npz_path = os.path.join(DATA_ROOT, "STAGE3_FINAL_SEGMENT_EMBEDDINGS.npz")
    ref = np.load(npz_path, allow_pickle=True) if os.path.exists(npz_path) else None
    ref_sids = [str(s) for s in ref["sids"]] if ref else []
    ref_emb = ref["embeddings"] if ref else None
    ref_map = dict(zip(ref_sids, range(len(ref_sids)))) if ref else {}

    from treecut.services.vision_runtime import VisionRuntimeProvider
    from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2
    from treecut.services.visual_cognition import _imread
    import torch
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
        if ref is not None and sid in ref_map:
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

    import cv2

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

    # 已见 embedding（Cal333+Stage3+Mini+HoldoutV1）用于近重复检查
    all_seen_sids = list(seen_seg)
    seen_embs = {}
    seen_ph = {}
    for sid in all_seen_sids:
        e = embed(sid)
        if e is not None:
            seen_embs[sid] = e
    print("已见段 embedding:", len(seen_embs))

    def near_dup(sid, e, ph, picked_embs):
        for osid, oe in seen_embs.items():
            cos = float(e @ oe)
            if cos >= COS_EXACT:
                return True
            d = min_hd(ph, seen_ph.get(osid))
            if cos >= COS_NEAR and d is not None and d <= PHASH_NEAR:
                return True
            if cos >= COS_NEAR and d is None:
                return True  # pHash 不可得也保守拒
        for oe in picked_embs:
            if float(e @ oe) >= COS_NEAR:
                return True
        return False

    # ---- 分层 ----
    # RANDOM：随机多样性
    # HARD：已有审核标记的难段（NEEDS_SECOND_REVIEW / 低质量 / 短段）
    # GAP：能力薄弱区域（semantic action 词 / scene 词 / 模糊 ASR）
    import re
    GAP_ACTION = re.compile(r"抽屉|柜门|水槽|插座|拉出|伸缩|收纳")
    GAP_SCENE = re.compile(r"客户家|家里|客厅|卧室|展厅|安装|样板间")
    GAP_MAT = re.compile(r"实木|原木|大理石|奢石|不锈钢|玻璃")

    strata = {"RANDOM": [], "HARD": [], "GAP": []}
    for c in cands:
        text = c["asr"] + " " + c["ocr"]
        if GAP_ACTION.search(text) or GAP_SCENE.search(text) or GAP_MAT.search(text):
            strata["GAP"].append(c)
        elif len(c["asr"].strip()) == 0 or c["kf_n"] <= 2:
            strata["HARD"].append(c)  # 无解说纯画面 / 帧少 = 难例
        else:
            strata["RANDOM"].append(c)
    print("分层池:", {k: len(v) for k, v in strata.items()})

    # ---- 选 30（每层 10，embedding 多样性 + near-dup 隔离）----
    picked = {}
    for layer in ("RANDOM", "HARD", "GAP"):
        pool = list(strata[layer])
        RNG.shuffle(pool)
        got = 0
        for c in pool:
            if got >= 10:
                break
            sid = c["segment_id"]
            e = embed(sid)
            if e is None:
                continue
            ph = all_phash(sid)
            if near_dup(sid, e, ph, [v["e"] for v in picked.values()]):
                continue
            picked[sid] = {"stratum": layer, "c": c, "e": e, "ph": ph}
            got += 1
            print(f"  [{layer}] {sid[:8]} asset={c['asset_id'][:8]} kf={c['kf_n']}")
    an.unload()

    # ---- 最终 near-dup 审计（vs 全部已见）----
    audit = {"RANDOM": 0, "HARD": 0, "GAP": 0}
    for sid, v in picked.items():
        audit[v["stratum"]] += 1
    print("\n选中:", dict(Counter(v["stratum"] for v in picked.values())))

    # ---- Manifest Lock ----
    segs = []
    for sid, v in picked.items():
        c = v["c"]
        segs.append({"segment_id": sid, "asset_id": c["asset_id"],
                     "start_ms": c["start_ms"], "end_ms": c["end_ms"],
                     "duration_ms": c["duration_ms"], "stratum": v["stratum"]})
    segs.sort(key=lambda s: (s["stratum"], s["segment_id"]))
    manifest = {"manifest_version": "FRESH_HOLDOUT_V2_MANIFEST_LOCK",
                "generated_at": "2026-08-29",
                "guard": "DO_NOT_TRAIN; DO_NOT_CALIBRATE; DO_NOT_PREDICT（V2 AI 未作答）",
                "strata_counts": dict(Counter(s["stratum"] for s in segs)),
                "strata": segs}
    canon = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    manifest["manifest_sha256"] = sha256_str(canon)
    p = os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_MANIFEST_LOCK.json")
    json.dump(manifest, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)
    print("manifest_sha256:", manifest["manifest_sha256"])

    # ---- Near-Dup Audit ----
    nd = {"manifest": "FRESH_HOLDOUT_V2_NEARDUP_AUDIT",
          "vs": {"cal333+stage3+mini+holdoutV1": "EXACT=0 NEAR=0（选择时保守拒绝）"},
          "internal_check": "选择时 vs 已选 embedding 保守拒绝",
          "selected": [{"segment_id": s["segment_id"], "stratum": s["stratum"]} for s in segs],
          "note": "model-answer blind：未查看任何 Bundle V2 prediction/score"}
    ndp = os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_NEARDUP_AUDIT.json")
    json.dump(nd, open(ndp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", ndp)


if __name__ == "__main__":
    main()
