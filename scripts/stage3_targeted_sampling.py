# -*- coding: utf-8 -*-
"""Stage 3 STEP 10/11 — 全库候选发现 + TARGETED_REVIEW_STAGE3（~60 条）。

采样优先级（真缺口）：
  semantic action（高运动+组件证据）、people 难例、scene long-tail（非工厂）、
  material long-tail（实木等）、product variant
避免：FACTORY+ISLAND+岩板+SPEAKING 密集组合；与 canonical360+holdout30 隔离；同 asset 唯一。
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

MATERIAL_LT = ["实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃"]
FUNCTION_LT = ["水槽", "水吧", "嵌入电器", "办公", "就餐", "儿童安全"]
SCENE_LT = ["客户", "客厅", "卧室", "入户", "样板间", "安装", "展厅"]
ACTION_WORDS = ["拉出", "缩回", "打开抽屉", "关闭抽屉", "打开柜门", "插电", "水槽"]


def main():
    random.seed(20240829)
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # 排除：canonical360 + holdout30（按 segment 和 asset）
    excl_seg = {r[0] for r in conn.execute("SELECT segment_id FROM canonical_human_truth")}
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    excl_seg |= {s["segment_id"] for s in hold["strata"]}
    # 所有已用 asset（避免同 asset 近重复）
    used_asset = {r[0] for r in conn.execute(
        "SELECT DISTINCT asset_id FROM segments WHERE segment_id IN "
        "(SELECT segment_id FROM canonical_human_truth)")}
    used_asset |= {s["asset_id"] for s in hold["strata"]}
    print("排除段:", len(excl_seg), "| 排除 asset:", len(used_asset))

    cands = []
    for r in conn.execute(
            "SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms, s.duration_ms "
            "FROM segments s WHERE s.segment_id NOT IN "
            "(SELECT segment_id FROM canonical_human_truth)"
            " AND s.segment_id NOT IN (SELECT segment_id FROM fresh_holdout_human_review_v1)"):
        sid = r["segment_id"]
        if sid in excl_seg or r["asset_id"] in used_asset:
            continue
        asr = conn.execute("SELECT text_corrected FROM transcripts WHERE asset_id=? AND text_corrected IS NOT NULL",
                           (r["asset_id"],)).fetchall()
        asr_text = " ".join(x[0] for x in asr if x[0])[:600]
        ocr = conn.execute("SELECT text FROM ocr_text WHERE asset_id=? AND frame_timestamp_ms BETWEEN ? AND ? AND text IS NOT NULL",
                           (r["asset_id"], r["start_ms"], r["end_ms"])).fetchall()
        ocr_text = " ".join(x[0] for x in ocr if x[0])[:300]
        kf = conn.execute("SELECT COUNT(*) n FROM keyframes WHERE segment_id=?", (sid,)).fetchone()["n"]
        text = asr_text + " " + ocr_text
        cands.append({"segment_id": sid, "asset_id": r["asset_id"], "start_ms": r["start_ms"],
                      "end_ms": r["end_ms"], "duration_ms": r["duration_ms"],
                      "asr_len": len(asr_text), "ocr_len": len(ocr_text), "keyframes_n": kf,
                      "material_lt": [w for w in MATERIAL_LT if w in text],
                      "function_lt": [w for w in FUNCTION_LT if w in text],
                      "scene_lt": [w for w in SCENE_LT if w in text],
                      "action_words": [w for w in ACTION_WORDS if w in text]})
    print("候选池:", len(cands))

    def pick(pool, k, keyfn):
        picked, seen_a = [], set()
        pool = sorted(pool, key=lambda c: -len(keyfn(c)))
        for c in pool:
            if len(picked) >= k:
                break
            if c["asset_id"] in seen_a:
                continue
            picked.append(c)
            seen_a.add(c["asset_id"])
        return picked

    # 全局 asset 去重配额采样
    global_seen = set()
    action_pool = [c for c in cands if c["action_words"]]
    scene_pool = [c for c in cands if c["scene_lt"]]
    mat_pool = [c for c in cands if c["material_lt"]]
    fn_pool = [c for c in cands if c["function_lt"]]
    visual_pool = [c for c in cands if c["asr_len"] == 0 and c["ocr_len"] == 0]

    def pick_global(pool, k, keyfn):
        picked = []
        pool = sorted(pool, key=lambda c: -len(keyfn(c)))
        for c in pool:
            if len(picked) >= k:
                break
            if c["asset_id"] in global_seen:
                continue
            picked.append(c)
            global_seen.add(c["asset_id"])
        return picked

    items = []
    for pool, k, reason in ((action_pool, 15, "semantic_action"), (scene_pool, 10, "scene_longtail"),
                            (mat_pool, 10, "material_longtail"), (fn_pool, 10, "function_longtail"),
                            (visual_pool, 8, "pure_visual")):
        for c in pick_global(pool, k, lambda c: c["action_words"] + c["scene_lt"] + c["material_lt"] + c["function_lt"]):
            items.append({"segment_id": c["segment_id"], "asset_id": c["asset_id"],
                          "start_ms": c["start_ms"], "end_ms": c["end_ms"],
                          "duration_ms": c["duration_ms"], "asr_len": c["asr_len"],
                          "ocr_len": c["ocr_len"], "keyframes_n": c["keyframes_n"],
                          "selection_reason": reason,
                          "hits": c["action_words"] + c["scene_lt"] + c["material_lt"] + c["function_lt"]})
    # 动态补足到 60（随机，全局 asset 去重）
    rest = [c for c in cands if c["asset_id"] not in global_seen]
    random.shuffle(rest)
    for c in rest:
        if len(items) >= 60:
            break
        items.append({"segment_id": c["segment_id"], "asset_id": c["asset_id"],
                      "start_ms": c["start_ms"], "end_ms": c["end_ms"],
                      "duration_ms": c["duration_ms"], "asr_len": c["asr_len"],
                      "ocr_len": c["ocr_len"], "keyframes_n": c["keyframes_n"],
                      "selection_reason": "random_audit", "hits": []})
        global_seen.add(c["asset_id"])
    assert len(items) == 60, f"仍不足 60: {len(items)}"
    assert len({i["segment_id"] for i in items}) == 60
    assert len({i["asset_id"] for i in items}) == 60
    assert not ({i["segment_id"] for i in items} & excl_seg)

    out = {"manifest_version": "TARGETED_REVIEW_STAGE3",
           "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "note": ("Stage3 DEV/Calibration 扩展候选（60 条），非 Holdout；"
                    "允许用于 threshold/routing/prompt/model-selection；不得加入 FRESH_HOLDOUT_V1"),
           "guard": "DEV_ONLY; NOT_HOLDOUT",
           "composition": dict(Counter(i["selection_reason"] for i in items)),
           "segments": items}
    p = os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("TARGETED_REVIEW_STAGE3 ->", p, "| 60 条")
    print("composition:", out["composition"])
    print("hits:", dict(Counter(w for i in items for w in i["hits"]).most_common(15)))
    conn.close()


if __name__ == "__main__":
    main()
