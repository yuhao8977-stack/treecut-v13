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
        "SELECT target_id FROM human_annotations UNION SELECT segment_id FROM human_annotation_v2"
        " UNION SELECT segment_id FROM human_annotation_v3"
        " UNION SELECT segment_id FROM targeted_human_review_v1")}
    print("已审段(含 V3/Targeted):", len(reviewed), flush=True)

    # 候选池（未审段 + 元数据）
    cands = []
    for r in conn.execute(
            "SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms, s.duration_ms "
            "FROM segments s WHERE s.segment_id NOT IN "
            "(SELECT target_id FROM human_annotations) "
            "AND s.segment_id NOT IN (SELECT segment_id FROM human_annotation_v2)"
            " AND s.segment_id NOT IN (SELECT segment_id FROM human_annotation_v3)"
            " AND s.segment_id NOT IN (SELECT segment_id FROM targeted_human_review_v1)"):
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

    # ---- 保留已审核条目（同 asset 只留 1 条；已审数据在库不丢，清单去重） ----
    old_path = os.path.join(DATA_ROOT, "TARGETED_REVIEW_BATCH_V1.json")
    kept = []
    if os.path.exists(old_path):
        old = json.load(open(old_path, encoding="utf-8")).get("segments", [])
        kept_raw = [s for s in old if s["segment_id"] in reviewed]
        seen_a = set()
        for s in kept_raw:
            if s["asset_id"] not in seen_a:
                kept.append(s)
                seen_a.add(s["asset_id"])
    kept_assets = {k["asset_id"] for k in kept}
    print(f"保留已审条目(asset 去重): {len(kept)}（已审数据全部在库不丢）", flush=True)

    # ---- 抽样（asset 严格去重：每 asset 至多 1 段 + 排除 kept asset） ----
    def pick(pool, k, label):
        picked = []
        asset_seen = set(kept_assets)
        pool = sorted(pool, key=lambda c: -c["gap_score"] if label != "random" else random.random())
        for c in pool:
            if len(picked) >= k:
                break
            if c["segment_id"] in {p["segment_id"] for p in picked}:
                continue
            if c["asset_id"] in asset_seen:
                continue  # 同一素材严格只取 1 段（修复：杜绝相邻段 ±3s 上下文重叠）
            picked.append(c)
            asset_seen.add(c["asset_id"])
        return picked

    gap_pool = [c for c in cands if c["gap_score"] >= 6]
    low_pool = [c for c in cands if c["low_ev_score"] >= 3 and c["gap_score"] < 6]
    random_pool = cands

    # 动态目标：总 60 = kept + 新段（优先 gap，其次 low，最后 random）
    target = 60 - len(kept)
    gap_target = min(GAP_RATIO, target)
    low_target = min(LOW_EV_RATIO, max(0, target - gap_target))
    random_target = max(0, target - gap_target - low_target)
    print(f"采样目标: gap {gap_target} + low {low_target} + random {random_target}（新段共 {target}）", flush=True)

    gap_batch = pick(gap_pool, gap_target, "gap")
    low_batch = pick(low_pool, low_target, "low_evidence")
    # random 从剩余抽
    used = {c["segment_id"] for c in gap_batch + low_batch}
    random_batch = pick([c for c in random_pool if c["segment_id"] not in used],
                        random_target, "random")

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

    # ---- 合并 kept + 新段 = 60；严格校验 ----
    all_items = kept + batch
    print(f"新清单总数: {len(all_items)}", flush=True)
    # 严格校验：segment 唯一 + asset 唯一
    assert len({s["segment_id"] for s in all_items}) == len(all_items), "segment 重复！"
    dup_asset = [a for a, n in Counter(s["asset_id"] for s in all_items).items() if n > 1]
    assert not dup_asset, f"asset 重复（修复后不应出现）: {dup_asset}"

    discover_stats = discover(conn)
    out = {
        "manifest_version": "TARGETED_REVIEW_BATCH_V1",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "revision": "rev2-fix-asset-dedup",
        "fix_note": ("rev2 修复：同一 asset 严格只取 1 段（旧版允许 2 段相邻段，"
                     "±3s 上下文重叠导致观感重复）。保留已审条目，补足 60 条新段。"),
        "ratios": {"coverage_gap": GAP_RATIO, "low_evidence": LOW_EV_RATIO,
                   "random_audit": RANDOM_RATIO},
        "total": len(all_items),
        "kept_already_reviewed": len(kept),
        "composition": dict(Counter(b["selection_reason"] for b in all_items)),
        "discover_stats": discover_stats,
        "dedup_policy": ("排除全部已审段（300+V3 34+Targeted 已审）；同一 asset 严格 1 段；"
                         "类别不存在不伪造配额"),
        "segments": [{"segment_id": b["segment_id"], "asset_id": b["asset_id"],
                      "start_ms": b["start_ms"], "end_ms": b["end_ms"],
                      "duration_ms": b["duration_ms"], "asr_len": b["asr_len"],
                      "ocr_len": b["ocr_len"], "keyframes_n": b["keyframes_n"],
                      "selection_reason": b["selection_reason"],
                      "gap_hits": b.get("gap_hits") or b.get("hits", []),
                      "asr_excerpt": (b.get("asr_text") or b.get("asr_excerpt") or "")[:80],
                      "ocr_excerpt": (b.get("ocr_text") or b.get("ocr_excerpt") or "")[:60]} for b in all_items],
    }
    out_path = os.path.join(DATA_ROOT, "TARGETED_REVIEW_BATCH_V1.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("TARGETED_REVIEW_BATCH_V1(rev2) ->", out_path)
    print("total:", len(all_items), "| kept:", len(kept), "| 新段:", len(batch))
    print("composition:", out["composition"])
    print("素材库 discover:", json.dumps(discover_stats, ensure_ascii=False))
    print("gap hits 分布:", dict(Counter(w for b in all_items if b["selection_reason"] == "coverage_gap" for w in b["gap_hits"])))
    conn.close()


if __name__ == "__main__":
    main()
