# -*- coding: utf-8 -*-
"""Stage3 FINAL PRE-REVIEW BATCH — 特征转储（一次 SigLIP 推理，服务多个下游审计）。

对 333 Calibration + 30 Holdout + 60 V2 候选 = 423 段：
  - 每段 mean segment embedding（至多 5 帧，L2 归一）→ npz（near-dup / 相似度用）
  - 每段 4 个多标签字段全 label scores（Policy V1/V2/变体模拟用）
  - 每段 7 个单值字段预测
  - 每段 keyframe 路径（People Detector / 人工复核用）

禁止用 Holdout 调参 —— 本脚本只产出特征，不调参。
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

MULTI = ["material", "component", "function", "shot_role"]
SINGLE = ["scene_family", "scene_subtype", "product_family",
          "product_variant", "shot_scale", "people_presence", "product_visibility"]


def main():
    from treecut.services.vision_runtime import VisionRuntimeProvider
    from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2

    # ---- 收集段集合 ----
    cal = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = [s["segment_id"] for s in cal["segments"]]
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    hold_sids = [s["segment_id"] for s in hold["strata"]]
    v2 = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V2.json"), encoding="utf-8"))
    v2_sids = [s["segment_id"] for s in v2["segments"]]
    all_sids = list(dict.fromkeys(cal_sids + hold_sids + v2_sids))
    print(f"段: cal={len(cal_sids)} hold={len(hold_sids)} v2={len(v2_sids)} union={len(all_sids)}")

    # ---- keyframe 路径 ----
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    frames = {}
    for r in conn.execute(
            "SELECT segment_id, image_path FROM keyframes ORDER BY segment_id, timestamp_ms"):
        frames.setdefault(r["segment_id"], []).append(r["image_path"])
    conn.close()
    print("有 keyframe 的段:", sum(1 for s in all_sids if frames.get(s)))

    # ---- 单次 SigLIP ----
    rt = VisionRuntimeProvider()
    an = StaticVisionAnalyzerV2(rt)
    an._ensure_model()
    import numpy as np
    import torch
    for f in an.LABEL_PROMPTS:
        for lab in an.LABEL_PROMPTS[f]:
            an._text_embedding(f, lab)  # 预热 text embedding 缓存

    out = {}
    embs = {}
    t0 = time.time()
    for i, sid in enumerate(all_sids):
        fr = frames.get(sid, [])[:5]
        if not fr:
            out[sid] = {"error": "no_frames"}
            continue
        from treecut.services.visual_cognition import _imread
        imgs = [im for im in (_imread(p) for p in fr) if im is not None]
        if not imgs:
            out[sid] = {"error": "no_frames_decoded"}
            continue
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
        mean_ie = ie.mean(axis=0)
        mean_ie = mean_ie / (np.linalg.norm(mean_ie) + 1e-9)
        embs[sid] = mean_ie
        rec = {"keyframes": fr[:5], "frame_evidence": len(ie)}
        for f in SINGLE:
            rec[f] = an._classify_single_emb(f, ie)
        for f in MULTI:
            rec[f] = an._classify_multi_emb(f, ie)
        out[sid] = rec
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(all_sids)} {time.time()-t0:.0f}s", flush=True)
    an.unload()

    # ---- 写盘 ----
    npz = os.path.join(DATA_ROOT, "STAGE3_FINAL_SEGMENT_EMBEDDINGS.npz")
    sids = sorted(embs.keys())
    arr = np.stack([embs[s] for s in sids])
    np.savez_compressed(npz, sids=np.array(sids, dtype=object), embeddings=arr)
    js = {"generated_at": time.strftime("%Y-%m-%d %H:%M"),
          "note": "FINAL PRE-REVIEW BATCH 特征转储；仅 DEV 分析，非调参（Holdout 只产出特征不参与策略选择）",
          "segments": {k: out[k] for k in sids if k in out},
          "count": len(sids)}
    jp = os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json")
    json.dump(js, open(jp, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"-> {jp} ({len(sids)} 段) / {npz}")
    print("耗时 %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
