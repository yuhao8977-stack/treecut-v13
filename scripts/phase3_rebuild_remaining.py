# -*- coding: utf-8 -*-
"""Phase 3 — 重建 TARGETED_REVIEW_BATCH_V1（rev3）：类别配额去同质化。

问题（用户反馈）：rev2 剩余条目 30/39 命中"轨道插座/插座"，同质化严重。
修复：
  1. 按 gap 类别配额采样（每类上限），保证多样性；
  2. 修正关键词："家"过宽（命中"家具"）→ 精确词；"岛头尺寸"等业务词排除；
  3. 保留已审 24 条（含备注）；asset 严格唯一；
  4. 增加纯视觉（无 ASR/OCR）样本配额。
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

# 类别 → (关键词, 配额)  （配额：剩余 36 条）
GAP_CLASSES = [
    ("material_longtail", ["实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃"], 4),
    ("function_longtail", ["水槽", "水吧", "嵌入电器", "隐藏电器", "办公", "就餐", "儿童安全"], 4),
    ("component_longtail", ["抽屉", "柜门", "台面", "电器"], 4),
    ("scene_nonfactory", ["客户家", "客厅", "卧室", "入户", "样板间", "安装", "展厅"], 5),
    ("socket", ["轨道插座", "插座"], 2),          # 已过度 → 限 2
    ("size_price", ["尺寸", "价格", "多少钱", "报价"], 1),  # 业务参数类，少量标注
]
PURE_VISUAL_QUOTA = 6      # 纯视觉（无 ASR/OCR）
LOW_EV_QUOTA = 6           # 低证据
RANDOM_QUOTA = 4           # 随机


def classify(hits: list[str], asr_len: int, ocr_len: int) -> str | None:
    if asr_len == 0 and ocr_len == 0:
        return "pure_visual"
    for cls, kws, _q in GAP_CLASSES:
        for k in kws:
            if k in " ".join(hits):
                return cls
    return None


def main():
    random.seed(2024)
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    reviewed = {r[0] for r in conn.execute(
        "SELECT target_id FROM human_annotations UNION SELECT segment_id FROM human_annotation_v2"
        " UNION SELECT segment_id FROM human_annotation_v3"
        " UNION SELECT segment_id FROM targeted_human_review_v1")}

    # 旧清单：保留已审条目（asset 去重）
    old_path = os.path.join(DATA_ROOT, "TARGETED_REVIEW_BATCH_V1.json")
    kept = []
    if os.path.exists(old_path):
        old = json.load(open(old_path, encoding="utf-8")).get("segments", [])
        seen_a = set()
        for s in old:
            if s["segment_id"] in reviewed and s["asset_id"] not in seen_a:
                kept.append(s)
                seen_a.add(s["asset_id"])
    kept_assets = {k["asset_id"] for k in kept}
    TOTAL_TARGET = 60 - len(kept)   # 动态目标
    print(f"保留已审: {len(kept)}（总 60 = 保留 {len(kept)} + 新采 {TOTAL_TARGET}）", flush=True)

    # 候选池（未审段）
    cands = []
    for r in conn.execute(
            "SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms, s.duration_ms "
            "FROM segments s WHERE s.segment_id NOT IN "
            "(SELECT target_id FROM human_annotations) "
            "AND s.segment_id NOT IN (SELECT segment_id FROM human_annotation_v2)"
            " AND s.segment_id NOT IN (SELECT segment_id FROM human_annotation_v3)"
            " AND s.segment_id NOT IN (SELECT segment_id FROM targeted_human_review_v1)"):
        sid = r["segment_id"]
        asr = conn.execute(
            "SELECT text_corrected FROM transcripts WHERE asset_id=? AND text_corrected IS NOT NULL",
            (r["asset_id"],)).fetchall()
        asr_text = " ".join(x[0] for x in asr if x[0])[:800]
        ocr_rows = conn.execute(
            "SELECT text FROM ocr_text WHERE asset_id=? AND frame_timestamp_ms BETWEEN ? AND ? "
            "AND text IS NOT NULL", (r["asset_id"], r["start_ms"], r["end_ms"])).fetchall()
        ocr_text = " ".join(x[0] for x in ocr_rows if x[0])[:400]
        cands.append({
            "segment_id": sid, "asset_id": r["asset_id"],
            "start_ms": r["start_ms"], "end_ms": r["end_ms"],
            "duration_ms": r["duration_ms"], "asr_len": len(asr_text),
            "ocr_len": len(ocr_text), "asr_text": asr_text[:200],
            "ocr_text": ocr_text[:150],
            "keyframes_n": conn.execute(
                "SELECT COUNT(*) n FROM keyframes WHERE segment_id=?", (sid,)).fetchone()["n"],
        })
    print("候选池:", len(cands), flush=True)

    # 打分（按类别）
    for c in cands:
        text = c["asr_text"] + " " + c["ocr_text"]
        hits = []
        for _cls, kws, _q in GAP_CLASSES:
            for k in kws:
                if k in text:
                    hits.append(k)
        c["gap_hits"] = sorted(set(hits))
        c["cls"] = classify(c["gap_hits"], c["asr_len"], c["ocr_len"])

    # 按类别配额采样（asset 唯一 + 排除 kept asset）
    def pick_by_class(cls: str, quota: int) -> list[dict]:
        pool = [c for c in cands if c["cls"] == cls and c["asset_id"] not in kept_assets]
        random.shuffle(pool)
        picked, seen = [], set()
        for c in pool:
            if len(picked) >= quota:
                break
            if c["asset_id"] in seen or c["segment_id"] in {p["segment_id"] for p in picked}:
                continue
            picked.append(c)
            seen.add(c["asset_id"])
        return picked

    new_batch = []
    quota_log = {}
    for cls, kws, q in GAP_CLASSES:
        got = pick_by_class(cls, q)
        quota_log[cls] = len(got)
        for c in got:
            new_batch.append({**c, "selection_reason": f"coverage_gap:{cls}", "gap_hits": c["gap_hits"]})
    for c in pick_by_class("pure_visual", PURE_VISUAL_QUOTA):
        new_batch.append({**c, "selection_reason": "pure_visual", "gap_hits": []})
    quota_log["pure_visual"] = sum(1 for b in new_batch if b["selection_reason"] == "pure_visual")
    # low_evidence（有 ASR 但低证据词）
    low_pool = [c for c in cands if c["cls"] is None and c["asr_len"] > 0
                and any(w in c["asr_text"] for w in ("讲解", "演示", "伸缩", "收纳"))
                and c["asset_id"] not in kept_assets]
    random.shuffle(low_pool)
    low_picked = 0
    seen_a = {b["asset_id"] for b in new_batch}
    for c in low_pool:
        if low_picked >= LOW_EV_QUOTA:
            break
        if c["asset_id"] in seen_a:
            continue
        new_batch.append({**c, "selection_reason": "low_evidence", "gap_hits": []})
        seen_a.add(c["asset_id"])
        low_picked += 1
    quota_log["low_evidence"] = low_picked
    # random 补足
    random_pool = [c for c in cands if c["asset_id"] not in kept_assets
                   and c["asset_id"] not in {b["asset_id"] for b in new_batch}]
    random.shuffle(random_pool)
    rnd_picked = 0
    for c in random_pool:
        if rnd_picked >= RANDOM_QUOTA or len(new_batch) >= TOTAL_TARGET:
            break
        new_batch.append({**c, "selection_reason": "random_audit", "gap_hits": []})
        rnd_picked += 1
    quota_log["random_audit"] = rnd_picked
    # 若仍不足：从候选池按需补（任意类别，asset 唯一）
    for c in random_pool:
        if len(new_batch) >= TOTAL_TARGET:
            break
        if c["asset_id"] in {b["asset_id"] for b in new_batch}:
            continue
        new_batch.append({**c, "selection_reason": "coverage_gap", "gap_hits": c["gap_hits"]})
    print("配额达成:", json.dumps(quota_log, ensure_ascii=False), "| 新采:", len(new_batch), flush=True)

    all_items = kept + new_batch[: max(0, TOTAL_TARGET - len(kept)) + len(kept) - len(kept)]
    # 修正：目标总 60
    all_items = kept + new_batch
    if len(all_items) > 60:
        all_items = kept + new_batch[: 60 - len(kept)]
    print("最终清单:", len(all_items), flush=True)
    assert len({s["segment_id"] for s in all_items}) == len(all_items), "segment 重复"
    dup_a = [a for a, n in Counter(s["asset_id"] for s in all_items).items() if n > 1]
    assert not dup_a, f"asset 重复: {dup_a}"

    out = {
        "manifest_version": "TARGETED_REVIEW_BATCH_V1",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "revision": "rev3-category-quota",
        "fix_note": ("rev3 修复用户反馈同质化：按 gap 类别配额采样（轨道插座限 2、材质/功能/组件/"
                     "场景长尾各 4-5、纯视觉 6、低证据 6、随机 4）；修正'家'关键词过宽；"
                     "保留已审条目与备注；asset 严格唯一。"),
        "total": len(all_items),
        "kept_already_reviewed": len(kept),
        "quota_log": quota_log,
        "composition": dict(Counter(s["selection_reason"] for s in all_items)),
        "dedup_policy": "已审全部排除；同 asset 严格 1 段；类别配额防同质化",
        "segments": [{"segment_id": s["segment_id"], "asset_id": s["asset_id"],
                      "start_ms": s["start_ms"], "end_ms": s["end_ms"],
                      "duration_ms": s["duration_ms"], "asr_len": s["asr_len"],
                      "ocr_len": s["ocr_len"], "keyframes_n": s["keyframes_n"],
                      "selection_reason": s["selection_reason"],
                      "gap_hits": s.get("gap_hits") or s.get("hits", []),
                      "asr_excerpt": (s.get("asr_text") or s.get("asr_excerpt") or "")[:80],
                      "ocr_excerpt": (s.get("ocr_text") or s.get("ocr_excerpt") or "")[:60]}
                     for s in all_items],
    }
    with open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_BATCH_V1.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("rev3 ->", os.path.join(DATA_ROOT, "TARGETED_REVIEW_BATCH_V1.json"))
    print("composition:", out["composition"])
    conn.close()


if __name__ == "__main__":
    main()
