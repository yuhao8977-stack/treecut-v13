# -*- coding: utf-8 -*-
"""Phase 3 STEP 11 — ActiveLearningSamplerV1 → TARGETED_REVIEW_BATCH_V1.json。

从 41814 - 300 已审段中挑选 60 条 unique Segment：
  40 coverage gap（非工厂/长尾材质/功能/组件/纯视觉）
  10 低证据/冲突
  10 random audit

纪律：
  - 不得假设素材库存在某类别：先 discover（ASR/OCR 关键词覆盖统计），
    类别不存在则如实报告，不伪造配额；
  - 与旧 300 不得 exact duplicate；同 asset 内避免 near duplicate（每 asset 至多 2 段）；
  - 比例配置化（GAP_RATIO/LOW_EVIDENCE_RATIO/RANDOM_RATIO）。
"""
import json
import os
import random
import sqlite3
import sys
from collections import Counter
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

# 配置化比例
GAP_RATIO, LOW_EV_RATIO, RANDOM_RATIO = 40, 10, 10

# 长尾 gap 类别（ASR/OCR 关键词）
GAP_KEYWORDS = {
    "material_longtail": ["实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃"],
    "function_longtail": ["轨道插座", "插座", "水槽", "水吧", "嵌入电器", "隐藏电器", "办公", "就餐"],
    "component_longtail": ["抽屉", "柜门", "台面", "电器"],
    "action_atomic": ["拉出", "缩回", "打开抽屉", "关闭抽屉", "打开柜门", "插电"],
    "scene_nonfactory": ["客户", "展厅", "安装", "家", "入户", "样板间"],
}
LOW_EV_WORDS = ["讲解", "演示", "伸缩", "收纳"]


def discover(conn) -> dict:
    """素材库类别存在性探索（asset 级 ASR + 帧级 OCR）。"""
    stats = {}
    for cat, words in GAP_KEYWORDS.items():
        n = 0
        for w in words:
            n += conn.execute(
                "SELECT COUNT(DISTINCT asset_id) FROM transcripts WHERE text_corrected LIKE ?",
                (f"%{w}%",)).fetchone()[0]
        stats[cat] = n
    no_asr_assets = conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT asset_id FROM assets) a "
        "WHERE NOT EXISTS (SELECT 1 FROM transcripts t WHERE t.asset_id=a.asset_id)").fetchone()[0]
    stats["no_asr_assets"] = no_asr_assets
    return stats


def main():
    random.seed(42)
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    reviewed = {r[0] for r in conn.execute(
        "SELECT target_id FROM human_annotations UNION SELECT segment_id FROM human_annotation_v2")}
    print("已审段:", len(reviewed), flush=True)

    # 候选池（未审段 + 元数据）
    cands = []
    for r in conn.execute(
            "SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms, s.duration_ms "
            "FROM segments s WHERE s.segment_id NOT IN "
            "(SELECT target_id FROM human_annotations) "
            "AND s.segment_id NOT IN (SELECT segment_id FROM human_annotation_v2)"):
        sid = r["segment_id"]
        # ASR（asset 级）与 OCR（段时间窗）文本
        asr = conn.execute(
            "SELECT text_corrected FROM transcripts WHERE asset_id=? AND text_corrected IS NOT NULL",
            (r["asset_id"],)).fetchall()
        asr_text = " ".join(x[0] for x in asr if x[0])[:800]
        ocr_rows = conn.execute(
            "SELECT text FROM ocr_text WHERE asset_id=? AND frame_timestamp_ms BETWEEN ? AND ? "
            "AND text IS NOT NULL", (r["asset_id"], r["start_ms"], r["end_ms"])).fetchall()
        ocr_text = " ".join(x[0] for x in ocr_rows if x[0])[:400]
        # keyframes 数量与运动粗估（用 sharpness 等已有元数据代替读取）
        kf = conn.execute(
            "SELECT COUNT(*) n, MAX(sharpness) s FROM keyframes WHERE segment_id=?",
            (sid,)).fetchone()
        cands.append({
            "segment_id": sid, "asset_id": r["asset_id"],
            "start_ms": r["start_ms"], "end_ms": r["end_ms"],
            "duration_ms": r["duration_ms"], "asr_len": len(asr_text),
            "ocr_len": len(ocr_text), "asr_text": asr_text[:200],
            "ocr_text": ocr_text[:150], "keyframes_n": kf["n"] if kf else 0,
        })
    print("候选池:", len(cands), flush=True)

    # ---- 打分 ----
    def score_gap(c):
        sc = 0
        hits = []
        text = (c["asr_text"] + " " + c["ocr_text"])
        for cat, words in GAP_KEYWORDS.items():
            for w in words:
                if w in text:
                    sc += 10
                    hits.append(w)
        if c["asr_len"] == 0 and c["ocr_len"] == 0:
            sc += 6  # 纯视觉无语言证据
            hits.append("no-asr-no-ocr")
        if c["keyframes_n"] >= 6:
            sc += 2
        return sc, sorted(set(hits))

    def score_low_ev(c):
        sc = 0
        for w in LOW_EV_WORDS:
            if w in c["asr_text"]:
                sc += 3
        if c["asr_len"] == 0 and c["ocr_len"] == 0:
            sc += 5
        return sc

    for c in cands:
        c["gap_score"], c["gap_hits"] = score_gap(c)
        c["low_ev_score"] = score_low_ev(c)

    # ---- 抽样（asset 去重：每 asset 至多 2 段；段内时间不重叠优先） ----
    def pick(pool, k, label):
        picked = []
        asset_cnt = Counter()
        pool = sorted(pool, key=lambda c: -c["gap_score"] if label != "random" else random.random())
        for c in pool:
            if len(picked) >= k:
                break
            if c["segment_id"] in {p["segment_id"] for p in picked}:
                continue
            if asset_cnt[c["asset_id"]] >= 2:
                continue
            # near-duplicate：同 asset 已选段时间窗重叠
            dup = False
            for p in picked:
                if p["asset_id"] == c["asset_id"] and not (
                        c["end_ms"] <= p["start_ms"] or c["start_ms"] >= p["end_ms"]):
                    dup = True
                    break
            if dup:
                continue
            picked.append(c)
            asset_cnt[c["asset_id"]] += 1
        return picked

    gap_pool = [c for c in cands if c["gap_score"] >= 6]
    low_pool = [c for c in cands if c["low_ev_score"] >= 3 and c["gap_score"] < 6]
    random_pool = cands

    gap_batch = pick(gap_pool, GAP_RATIO, "gap")
    low_batch = pick(low_pool, LOW_EV_RATIO, "low_evidence")
    # random 从剩余抽
    used = {c["segment_id"] for c in gap_batch + low_batch}
    random_batch = pick([c for c in random_pool if c["segment_id"] not in used],
                        RANDOM_RATIO, "random")

    batch = []
    for c in gap_batch:
        batch.append({**c, "selection_reason": "coverage_gap", "gap_hits": c["gap_hits"]})
    for c in low_batch:
        batch.append({**c, "selection_reason": "low_evidence",
                      "gap_hits": sorted(set(c["gap_hits"]) | set(LOW_EV_WORDS))})
    for c in random_batch:
        batch.append({**c, "selection_reason": "random_audit", "gap_hits": []})

    # 与旧 300 零重叠校验
    assert all(b["segment_id"] not in reviewed for b in batch), "与已审段重复！"

    discover_stats = discover(conn)
    out = {
        "manifest_version": "TARGETED_REVIEW_BATCH_V1",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ratios": {"coverage_gap": GAP_RATIO, "low_evidence": LOW_EV_RATIO,
                   "random_audit": RANDOM_RATIO},
        "total": len(batch),
        "composition": dict(Counter(b["selection_reason"] for b in batch)),
        "discover_stats": discover_stats,
        "dedup_policy": ("排除 300 已审段（exact）；同 asset 至多 2 段且时间窗不重叠（near-duplicate 规避）；"
                         "类别不存在不伪造配额"),
        "segments": [{"segment_id": b["segment_id"], "asset_id": b["asset_id"],
                      "start_ms": b["start_ms"], "end_ms": b["end_ms"],
                      "duration_ms": b["duration_ms"], "asr_len": b["asr_len"],
                      "ocr_len": b["ocr_len"], "keyframes_n": b["keyframes_n"],
                      "selection_reason": b["selection_reason"],
                      "hits": b["gap_hits"], "asr_excerpt": b["asr_text"][:80],
                      "ocr_excerpt": b["ocr_text"][:60]} for b in batch],
    }
    out_path = os.path.join(DATA_ROOT, "TARGETED_REVIEW_BATCH_V1.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("TARGETED_REVIEW_BATCH_V1 ->", out_path)
    print("total:", len(batch), "| composition:", out["composition"])
    print("素材库 discover:", json.dumps(discover_stats, ensure_ascii=False))
    print("gap hits 分布:", dict(Counter(w for b in gap_batch for w in b["gap_hits"])))
    conn.close()


if __name__ == "__main__":
    main()
