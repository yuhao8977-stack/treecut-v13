# -*- coding: utf-8 -*-
"""Stage 3 STEP 8-13 — TARGETED_REVIEW_STAGE3_V2（60 条，对齐 Stage3 核心缺口）。

配额：Action 20 / People 12 / Variant 10 / Scene 8 / Material 6 / PureVisual+Random 4
multi-target：primary_target + secondary_targets[]（同一段可服务多目标）
诚实长尾：requested/discovered/selected；发现不足则回流 Action/People/Variant。
near-dup：排除 canonical360+holdout30；同 asset 唯一；visual near-dup 标注待复核。
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

ACTION_W = ["打开抽屉", "关闭抽屉", "打开柜门", "插电", "水槽", "收纳", "抽屉"]
VARIANT_W = ["悬浮", "落地", "标准", "固定", "伸缩", "拉出"]
SCENE_W = ["客户", "客厅", "卧室", "入户", "样板间", "安装", "展厅", "家"]
MATERIAL_W = ["实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃"]
PEOPLE_W = ["师傅", "安装师傅", "讲解", "介绍", "演示"]


def main():
    random.seed(20240830)
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    excl_seg = {r[0] for r in conn.execute("SELECT segment_id FROM canonical_human_truth")}
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    excl_seg |= {s["segment_id"] for s in hold["strata"]}
    used_asset = {r[0] for r in conn.execute(
        "SELECT DISTINCT asset_id FROM segments WHERE segment_id IN (SELECT segment_id FROM canonical_human_truth)")}
    used_asset |= {s["asset_id"] for s in hold["strata"]}
    print("排除段:", len(excl_seg), "asset:", len(used_asset))

    cands = []
    for r in conn.execute("SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms, s.duration_ms "
                          "FROM segments s WHERE s.segment_id NOT IN (SELECT segment_id FROM canonical_human_truth)"
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
                      "action": [w for w in ACTION_W if w in text],
                      "variant": [w for w in VARIANT_W if w in text],
                      "scene": [w for w in SCENE_W if w in text],
                      "material": [w for w in MATERIAL_W if w in text],
                      "people": [w for w in PEOPLE_W if w in text],
                      "pure_visual": len(asr_text) == 0 and len(ocr_text) == 0})
    print("候选池:", len(cands))

    seen = set()

    def pick_global(pool, k, scorefn):
        picked = []
        pool = sorted(pool, key=lambda c: -scorefn(c))
        for c in pool:
            if len(picked) >= k:
                break
            if c["asset_id"] in seen:
                continue
            picked.append(c)
            seen.add(c["asset_id"])
        return picked

    # 配额（基于 Gate 缺口审计调整）：
    #   action 20：聚焦抽屉/柜门/插座/水槽（DRAWER 11/OPEN_DRAWER 3/CLOSE_DRAWER 1/CABINET 0/SOCKET 0/SINK 1 严重不足）
    #   people 12：YES 237 主导，需补 NO + 模型冲突（平衡）
    #   variant 6：EXTENDABLE 已 184，补 标准/悬浮/落地（发现不足回流）
    #   scene 6 / material 5：诚实发现（素材极缺则回流）
    #   visual+random 11：补足
    action_pool = [c for c in cands if c["action"]]
    people_pool = [c for c in cands if c["people"] or c["action"]]
    variant_pool = [c for c in cands if c["variant"] and any(w in "".join(c["variant"]) for w in ("悬浮", "落地", "标准", "固定"))]
    scene_pool = [c for c in cands if c["scene"]]
    mat_pool = [c for c in cands if c["material"]]
    visual_pool = [c for c in cands if c["pure_visual"]]

    # requested / discovered / selected 诚实记录
    report = {}
    items = []
    for name, pool, k, reason, prim, sec in (
            ("action", action_pool, 20, "semantic_action", "SEMANTIC_ACTION", ["PEOPLE"]),
            ("people", people_pool, 12, "people", "PEOPLE", ["SEMANTIC_ACTION"]),
            ("variant", variant_pool, 6, "product_variant", "PRODUCT_VARIANT", []),
            ("scene", scene_pool, 6, "scene_longtail", "SCENE", []),
            ("material", mat_pool, 5, "material_longtail", "MATERIAL", []),
            ("visual", visual_pool, 11, "pure_visual", "PEOPLE", ["SEMANTIC_ACTION"])):
        disc = len({c["asset_id"] for c in pool})
        got = pick_global(pool, k, lambda c: len(c["action"]) + len(c["variant"]) + len(c["people"]) + len(c["scene"]) + len(c["material"]))
        report[name] = {"requested": k, "discovered": disc, "selected": len(got)}
        for c in got:
            targets = [prim] + sec
            items.append({"segment_id": c["segment_id"], "asset_id": c["asset_id"],
                          "start_ms": c["start_ms"], "end_ms": c["end_ms"],
                          "duration_ms": c["duration_ms"], "asr_len": c["asr_len"],
                          "ocr_len": c["ocr_len"], "keyframes_n": c["keyframes_n"],
                          "selection_reason": reason, "primary_target": prim,
                          "secondary_targets": sec, "hits": c["action"] + c["variant"] + c["scene"] + c["material"] + c["people"]})
        print(f"  {name}: requested={k} discovered={disc} selected={len(got)}")

    # 回流：如果总量 <60（长尾不足），补 Action/People/Variant 或随机
    rest = [c for c in cands if c["asset_id"] not in seen]
    random.shuffle(rest)
    for c in rest:
        if len(items) >= 60:
            break
        items.append({"segment_id": c["segment_id"], "asset_id": c["asset_id"],
                      "start_ms": c["start_ms"], "end_ms": c["end_ms"],
                      "duration_ms": c["duration_ms"], "asr_len": c["asr_len"],
                      "ocr_len": c["ocr_len"], "keyframes_n": c["keyframes_n"],
                      "selection_reason": "random_audit", "primary_target": "SEMANTIC_ACTION",
                      "secondary_targets": ["PEOPLE"], "hits": []})
        seen.add(c["asset_id"])
    # 截断到 60
    items = items[:60]
    assert len({i["segment_id"] for i in items}) == len(items)
    assert len({i["asset_id"] for i in items}) == len(items)

    multi_target = sum(1 for i in items if i["secondary_targets"])
    out = {"manifest_version": "TARGETED_REVIEW_STAGE3_V2",
           "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "deprecates": "TARGETED_REVIEW_STAGE3.json（DEPRECATED_CANDIDATE_BATCH_V1，保留）",
           "note": "对齐 Stage3 核心缺口；DEV/Calibration 扩展（非 Holdout）；multi-target 提高单次审核价值",
           "guard": "DEV_ONLY; NOT_HOLDOUT; 隐藏 AI 猜测, 仅显示采样目标",
           "quota_report": report, "multi_target_count": multi_target,
           "composition": dict(Counter(i["selection_reason"] for i in items)),
           "segments": items}
    p = os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V2.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("TARGETED_REVIEW_STAGE3_V2 ->", p, "|", len(items), "条 | multi-target:", multi_target)
    print("composition:", out["composition"])
    conn.close()


if __name__ == "__main__":
    main()
