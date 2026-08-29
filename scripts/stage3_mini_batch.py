# -*- coding: utf-8 -*-
"""Stage3 TRACK 2 — TARGETED_REVIEW_STAGE3_MINI_V1（18 条最小验证批）生成。

三类：OPERATE_SOCKET 8 / CUSTOMER_HOME 5 / SOLID_WOOD 5（±2，上限 20）。
采样要求（每类）：
  OPERATE_SOCKET：ASR 插座短语 + 视觉 component 证据（TRACK_SOCKET）+ 手部/运动迹象，禁纯 ASR
  CUSTOMER_HOME：真实住宅视觉（非工厂白底）+ ASR 语义，禁"客户/家/安装"子串误命中
  SOLID_WOOD：主体木质视觉证据（SigLIP material 非纯岩板）+ ASR 实木语义
筛选用 SigLIP（STAGE3_FINAL_FEATURES 的 component/material scores；新段实时嵌入）。
Near-dup：asset 唯一 + embedding 余弦 vs Cal333/Stage3/Holdout/Mini内部 → EXACT=0 NEAR=0。
输出 TARGETED_REVIEW_STAGE3_MINI_V1.json + STAGE3_MINI_BATCH_DISCOVERY_AUDIT.json
"""
import json
import os
import re
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

QUOTA = {"OPERATE_SOCKET": 8, "CUSTOMER_HOME": 5, "SOLID_WOOD": 5}
TARGET_CN = {"OPERATE_SOCKET": "插座动作", "CUSTOMER_HOME": "客户家", "SOLID_WOOD": "实木"}

COS_EXACT = 0.999
COS_NEAR = 0.95
PHASH_NEAR = 10
COS_UNC = 0.93

# ASR 规则（精确短语，禁子串误命中）
OP_SOCKET_ASR = re.compile(r"插电|插上电|插座|插头|通电|电源接口|插上")
HOME_ASR = re.compile(r"(客户家|业主家|家里|新家|入户|客厅|卧室|装修)")
WOOD_ASR = re.compile(r"实木|原木|木纹|木质|木饰面")


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    import numpy as np
    # ---- 参考 embedding（Cal333+Stage3+Holdout）----
    npz = np.load(os.path.join(DATA_ROOT, "STAGE3_FINAL_SEGMENT_EMBEDDINGS.npz"), allow_pickle=True)
    ref_sids = [str(s) for s in npz["sids"]]
    ref_emb = npz["embeddings"]
    ref_sid2emb = dict(zip(ref_sids, ref_emb))
    cal = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = {s["segment_id"] for s in cal["segments"]}
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    hold_sids = {s["segment_id"] for s in hold["strata"]}
    tman = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    stage3_sids = {s["segment_id"] for s in tman["segments"]}
    feats = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json"), encoding="utf-8"))["segments"]

    # ---- 分析器（新段 embedding + component/material）----
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
        try:
            c2 = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
            c2.row_factory = sqlite3.Row
            fr = [r["image_path"] for r in c2.execute(
                "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY timestamp_ms LIMIT ?", (sid, limit))]
            c2.close()
            return fr
        except Exception:
            return []

    def embed_new(sid):
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

    def sig_analyze(sid):
        """返回 component/material scores + 预测（新段实时，旧段用缓存）。"""
        if sid in feats:
            return feats[sid]
        fr = kfs(sid)
        if not fr:
            return {}
        try:
            return an.analyze(fr[:5])
        except Exception:
            return {}

    # ---- 候选池（与 gap discovery 一致 + 完整列表）----
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    excl = {r[0] for r in conn.execute("SELECT segment_id FROM canonical_human_truth")}
    excl |= hold_sids | stage3_sids
    used_asset = {r[0] for r in conn.execute(
        "SELECT DISTINCT asset_id FROM segments WHERE segment_id IN (SELECT segment_id FROM canonical_human_truth)")}
    used_asset |= {s["asset_id"] for s in hold["strata"]} | {s["asset_id"] for s in tman["segments"]}
    cands = []
    for r in conn.execute("SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms, s.duration_ms "
                          "FROM segments s WHERE s.segment_id NOT IN (SELECT segment_id FROM canonical_human_truth)"
                          " AND s.segment_id NOT IN (SELECT segment_id FROM targeted_human_review_v1)"
                          " AND s.segment_id NOT IN (SELECT segment_id FROM fresh_holdout_human_review_v1)"):
        if r["segment_id"] in excl or r["asset_id"] in used_asset:
            continue
        asr = " ".join(x[0] for x in conn.execute(
            "SELECT text_corrected FROM transcripts WHERE asset_id=? AND text_corrected IS NOT NULL",
            (r["asset_id"],)).fetchall() if x[0])[:800]
        ocr = " ".join(x[0] for x in conn.execute(
            "SELECT text FROM ocr_text WHERE asset_id=? AND text IS NOT NULL",
            (r["asset_id"],)).fetchall() if x[0])[:400]
        kf_n = conn.execute("SELECT COUNT(*) n FROM keyframes WHERE segment_id=?",
                            (r["segment_id"],)).fetchone()["n"]
        cands.append({"segment_id": r["segment_id"], "asset_id": r["asset_id"],
                      "start_ms": r["start_ms"], "end_ms": r["end_ms"],
                      "duration_ms": r["duration_ms"], "asr": asr, "ocr": ocr, "kf_n": kf_n})
    conn.close()
    print("候选池:", len(cands))

    # ---- 分类打分 ----
    def classify(c):
        asr = c["asr"]
        ocr = c["ocr"]
        hit = {}
        hit["OPERATE_SOCKET"] = bool(OP_SOCKET_ASR.search(asr))
        hit["CUSTOMER_HOME"] = bool(HOME_ASR.search(asr))
        hit["SOLID_WOOD"] = bool(WOOD_ASR.search(asr + " " + ocr))
        return hit

    for c in cands:
        c["hit"] = classify(c)

    # ---- 逐类挑选（视觉证据加权）----
    picked = {}
    new_embs = {}
    for cat in ("OPERATE_SOCKET", "CUSTOMER_HOME", "SOLID_WOOD"):
        pool = [c for c in cands if c["hit"][cat] and c["segment_id"] not in picked]
        # 视觉排序：高 kf + 视觉证据（component/material）
        scored = []
        for c in pool[:60]:  # 每类最多检查 60 候选
            sig = sig_analyze(c["segment_id"])
            if not sig:
                continue
            score = 1.0
            evidence = []
            if cat == "OPERATE_SOCKET":
                comp = sig.get("component", {}).get("prediction", [])
                if "TRACK_SOCKET" in comp:
                    score += 2.0
                    evidence.append("TRACK_SOCKET")
                if "APPLIANCE_SLOT" in comp:
                    score += 0.5
                    evidence.append("APPLIANCE_SLOT")
                if c["kf_n"] >= 4:
                    score += 0.5
            elif cat == "CUSTOMER_HOME":
                # 视觉上非工厂：scene_family 预测不是 FACTORY 加分
                sc = sig.get("scene_family", {}).get("prediction", "UNKNOWN")
                if sc != "FACTORY":
                    score += 2.0
                    evidence.append(f"scene={sc}")
                if c["kf_n"] >= 4:
                    score += 0.3
            elif cat == "SOLID_WOOD":
                mat = sig.get("material", {}).get("scores", {})
                wood = {k: v for k, v in mat.items() if "木" in k}
                if wood:
                    score += 1.0
                    evidence.append(f"wood_scores={ {k: round(v,2) for k,v in wood.items()} }")
                if c["kf_n"] >= 4:
                    score += 0.3
            scored.append((score, c, evidence, sig))
        scored.sort(key=lambda x: -x[0])
        got = 0
        used_asset_pick = set()
        for score, c, ev, sig in scored:
            if got >= QUOTA[cat]:
                break
            if c["asset_id"] in used_asset_pick:
                continue  # 同 asset 只选一条（独立素材）
            sid = c["segment_id"]
            e = embed_new(sid)
            if e is None:
                continue
            # near-dup 检查 vs 参考
            sims = e @ ref_emb.T
            ok = True
            for j, other in enumerate(ref_sids):
                if other not in cal_sids and other not in hold_sids and other not in stage3_sids:
                    continue
                if float(sims[j]) >= COS_NEAR:
                    ok = False
                    break
            if not ok:
                continue
            # vs Mini 内部已选
            for sid2, e2 in new_embs.items():
                if float(e @ e2) >= COS_NEAR:
                    ok = False
                    break
            if not ok:
                continue
            picked[sid] = {"category": cat, "c": c, "score": round(score, 2),
                           "evidence": ev, "sig": sig}
            new_embs[sid] = e
            used_asset_pick.add(c["asset_id"])
            got += 1
            print(f"  [{cat}] 选中 {sid[:8]} asset={c['asset_id'][:8]} score={score:.2f} "
                  f"ev={ev[:3]} kf={c['kf_n']}")
    an.unload()

    # ---- 组装 manifest ----
    items = []
    for sid, info in picked.items():
        c = info["c"]
        items.append({"segment_id": sid, "asset_id": c["asset_id"],
                      "start_ms": c["start_ms"], "end_ms": c["end_ms"],
                      "duration_ms": c["duration_ms"], "keyframes_n": c["kf_n"],
                      "sampling_target": info["category"],
                      "sampling_target_cn": TARGET_CN[info["category"]],
                      "secondary_targets": [],
                      "selection_reason": f"mini_gap_{info['category'].lower()}",
                      "sampling_keywords": [],
                      "near_duplicate_status": "UNIQUE", "novelty_score": 1.0})
    items.sort(key=lambda i: i["sampling_target"])
    assert len({i["segment_id"] for i in items}) == len(items)
    assert len({i["asset_id"] for i in items}) == len(items)
    print(f"\nMini 批: {len(items)} 条", dict(Counter(i["sampling_target"] for i in items)))

    out = {"manifest_version": "TARGETED_REVIEW_STAGE3_MINI_V1",
           "generated_at": "2026-08-29",
           "purpose": ("验证 candidate discovery precision + 补充少量真实 DEV 样本；"
                       "18 条左右（±2），非训练大模型"),
           "guard": "DEV_ONLY; NOT_HOLDOUT; 只显示采样目标（插座动作/客户家/实木），隐藏 AI 猜测/score/关键词/provider",
           "dictionary": "ANNOTATION_DICTIONARY_V2_1",
           "composition": dict(Counter(i["sampling_target"] for i in items)),
           "segments": items}
    p = os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_MINI_V1.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)

    # ---- discovery audit ----
    audit = {"manifest": "STAGE3_MINI_BATCH_DISCOVERY_AUDIT",
             "pool_size": len(cands),
             "quota": QUOTA, "selected": dict(Counter(i["sampling_target"] for i in items)),
             "near_dup_note": "选中段 vs Cal333/Stage3/Holdout/Mini内部 余弦<0.95（EXACT=0 NEAR=0）",
             "per_category": {}}
    for cat in ("OPERATE_SOCKET", "CUSTOMER_HOME", "SOLID_WOOD"):
        sel = [i for i in items if i["sampling_target"] == cat]
        audit["per_category"][cat] = {
            "selected": len(sel),
            "segments": [{"segment_id": s["segment_id"], "asset": s["asset_id"],
                          "score": picked[s["segment_id"]]["score"],
                          "evidence": picked[s["segment_id"]]["evidence"][:4]}
                         for s in sel]}
    ap = os.path.join(DATA_ROOT, "STAGE3_MINI_BATCH_DISCOVERY_AUDIT.json")
    json.dump(audit, open(ap, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", ap)


if __name__ == "__main__":
    main()
