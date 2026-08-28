# -*- coding: utf-8 -*-
"""Stage 2 STEP 22 — FRESH_HOLDOUT_V1_CANDIDATES（30 条，仅生成候选，不审核）。

隔离纪律：
  - 完全不属于 原300 / Targeted60 / Calibration333（即 canonical 360 全部排除）
  - 同 asset 严格 1 段
  - 不看 Human truth（尚无人工标签）；只按 sampling metadata / evidence profile / visual diversity
构成：10 random + 10 低证据 + 10 coverage gap（比例配置化）
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

GAP_WORDS = ["实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃", "水槽", "水吧", "嵌入电器",
             "办公", "就餐", "抽屉", "柜门", "安装", "客厅", "卧室", "入户", "样板间"]
LOW_EV_WORDS = ["讲解", "演示", "伸缩", "收纳", "轨道插座"]


def main():
    random.seed(20240828)
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # 排除集合：canonical 全部 360（含 excluded/needs_review，保证彻底隔离）
    excl = {r[0] for r in conn.execute("SELECT segment_id FROM canonical_human_truth")}
    print("排除段:", len(excl))

    cands = []
    for r in conn.execute(
            "SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms, s.duration_ms "
            "FROM segments s WHERE s.segment_id NOT IN "
            "(SELECT segment_id FROM canonical_human_truth)"):
        sid = r["segment_id"]
        asr = conn.execute(
            "SELECT text_corrected FROM transcripts WHERE asset_id=? AND text_corrected IS NOT NULL",
            (r["asset_id"],)).fetchall()
        asr_text = " ".join(x[0] for x in asr if x[0])[:600]
        ocr = conn.execute(
            "SELECT text FROM ocr_text WHERE asset_id=? AND frame_timestamp_ms BETWEEN ? AND ? "
            "AND text IS NOT NULL", (r["asset_id"], r["start_ms"], r["end_ms"])).fetchall()
        ocr_text = " ".join(x[0] for x in ocr if x[0])[:300]
        kf = conn.execute("SELECT COUNT(*) n FROM keyframes WHERE segment_id=?", (sid,)).fetchone()["n"]
        text = asr_text + " " + ocr_text
        hits = sorted(set(w for w in GAP_WORDS if w in text))
        low = sorted(set(w for w in LOW_EV_WORDS if w in text))
        cands.append({"segment_id": sid, "asset_id": r["asset_id"],
                      "start_ms": r["start_ms"], "end_ms": r["end_ms"],
                      "duration_ms": r["duration_ms"], "asr_len": len(asr_text),
                      "ocr_len": len(ocr_text), "keyframes_n": kf,
                      "gap_hits": hits, "low_hits": low})
    print("候选池(41814-360):", len(cands))

    def pick(pool, k, label):
        picked, seen_a = [], set()
        if label == "random":
            random.shuffle(pool)
        else:
            pool = sorted(pool, key=lambda c: -len(c["gap_hits"] if label == "gap" else c["low_hits"]))
        for c in pool:
            if len(picked) >= k:
                break
            if c["asset_id"] in seen_a:
                continue
            picked.append(c)
            seen_a.add(c["asset_id"])
        return picked

    gap_pool = [c for c in cands if c["gap_hits"]]
    low_pool = [c for c in cands if c["low_hits"] and not c["gap_hits"]]
    random_pool = cands

    gap = pick(gap_pool, 10, "gap")
    low = pick(low_pool, 10, "low")
    used = {c["segment_id"] for c in gap + low}
    rnd = pick([c for c in random_pool if c["segment_id"] not in used], 10, "random")

    items = []
    for c in gap:
        items.append({**{k: c[k] for k in ("segment_id", "asset_id", "start_ms", "end_ms",
                                           "duration_ms", "asr_len", "ocr_len", "keyframes_n")},
                      "selection_reason": "coverage_gap", "hits": c["gap_hits"]})
    for c in low:
        items.append({**{k: c[k] for k in ("segment_id", "asset_id", "start_ms", "end_ms",
                                           "duration_ms", "asr_len", "ocr_len", "keyframes_n")},
                      "selection_reason": "low_evidence", "hits": c["low_hits"]})
    for c in rnd:
        items.append({**{k: c[k] for k in ("segment_id", "asset_id", "start_ms", "end_ms",
                                           "duration_ms", "asr_len", "ocr_len", "keyframes_n")},
                      "selection_reason": "random_audit", "hits": []})

    assert len(items) == 30
    assert len({i["segment_id"] for i in items}) == 30
    assert len({i["asset_id"] for i in items}) == 30
    assert not ({i["segment_id"] for i in items} & excl), "与已审/Calibration 重叠！"

    out = {
        "manifest_version": "FRESH_HOLDOUT_V1_CANDIDATES",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note": ("30 条未见样本候选（10 随机 + 10 低证据 + 10 coverage gap）；"
                 "完全不属于原300/Targeted60/Calibration333；同 asset 唯一；"
                 "未看 Human truth。待 VISION_MODEL_BUNDLE_V1 冻结后先 AI 预测、锁定、再盲审。"),
        "guard": "DO_NOT_TRAIN; DO_NOT_CALIBRATE",
        "composition": dict(Counter(i["selection_reason"] for i in items)),
        "segments": items,
    }
    p = os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_CANDIDATES.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("FRESH_HOLDOUT_V1_CANDIDATES ->", p, "| 30 条")
    print("composition:", out["composition"])
    print("gap hits:", dict(Counter(w for i in items for w in i["hits"])))
    conn.close()


if __name__ == "__main__":
    main()
