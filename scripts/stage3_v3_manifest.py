# -*- coding: utf-8 -*-
"""Stage3 FINAL PRE-REVIEW BATCH — STEP 12-14：TARGETED_REVIEW_STAGE3_V3 冻结。

输入：V2 60 条 + 各审计输出（near-dup 两信号 / people reorder / action support / policy 裁定）。
流程：
  1. near-dup 过滤：INTERNAL 组留 1（其余 DUPLICATE_DROPPED）；LEAK_RISK_HOLDOUT 必须替换；
  2. 动态配额（优先级 Action > People > Variant > Scene > Material > PureVisual，总量 ~60）：
     - Action 重平衡：稀缺原子优先（OPEN_DRAWER/OPEN_SINK_COVER/PULL_OUT），RETRACT 封顶；
       CLOSE_CABINET/OPERATE_SOCKET 无候选 → LIBRARY_CANDIDATE_GAP 如实报告，不伪造；
     - People：YOLO×SigLIP 分歧 top12（跳过 dropped/leak，从后补）；
     - Variant：EXTENDABLE 已足（199）不补；STANDARD/FLOATING/FLOOR 无发现不伪造 → 回流；
     - Scene/Material：关键词误命中审计（"家"子串等），弱候选降权；
     - PureVisual 保留。
  3. novelty_score：UNIQUE=1.0 / NEAR_DUP_CALIBRATION=0.6 / 内部去重=0；动作稀缺 +0.05；
  4. manifest_sha256 + DEV_ONLY/NOT_HOLDOUT + deprecates V2。
盲审契约：manifest 只含采样目标/原因/关键词，绝不含任何 AI 预测/分数/证据。
"""
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

TOTAL = 60
ACTION_KW = ["打开抽屉", "关闭抽屉", "打开柜门", "关闭柜门", "插电", "插座", "水槽盖",
             "打开水槽", "拉出", "抽出", "伸缩拉出", "收回", "收纳", "抽屉", "柜门", "伸缩"]
VARIANT_KW = ["悬浮", "落地", "标准", "固定", "伸缩", "拉出"]
SCENE_KW = ["客户", "客厅", "卧室", "入户", "样板间", "安装", "展厅"]
MATERIAL_KW = ["实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃"]
PEOPLE_KW = ["师傅", "安装师傅", "讲解", "介绍", "演示"]

# 原子动作稀缺性（333 支持量越低越优先）
ATOMIC_PRIORITY = {
    "OPEN_DRAWER": 5, "CLOSE_DRAWER": 4, "OPEN_CABINET": 4, "CLOSE_CABINET": 5,
    "OPERATE_SOCKET": 5, "OPEN_SINK_COVER": 3, "PULL_OUT": 2, "RETRACT": 1,
}
ACTION_KEYWORDS = {
    "OPEN_DRAWER": ["打开抽屉", "拉抽屉", "抽出抽屉"],
    "CLOSE_DRAWER": ["关闭抽屉", "关抽屉", "推进抽屉", "关上抽屉"],
    "OPEN_CABINET": ["打开柜门", "打开柜子", "开柜门"],
    "CLOSE_CABINET": ["关闭柜门", "关柜门", "关上柜子"],
    "OPERATE_SOCKET": ["插电", "插座", "插头", "通电"],
    "OPEN_SINK_COVER": ["水槽盖", "打开水槽", "掀开水槽", "水槽"],
    "PULL_OUT": ["拉出", "抽出", "拉伸", "伸缩拉出"],
    "RETRACT": ["收回", "缩回", "收纳"],
}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    v2 = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V2.json"), encoding="utf-8"))
    items = v2["segments"]
    nd = json.load(open(os.path.join(DATA_ROOT, "STAGE3_NEAR_DUP_FINAL_AUDIT.json"), encoding="utf-8"))
    nd_status = {r["segment_id"]: r for r in nd["segments"]}
    bench = json.load(open(os.path.join(DATA_ROOT, "PEOPLE_DETECTOR_BENCHMARK_V1.json"), encoding="utf-8"))
    people_order = bench.get("people_review_order_top12", [])
    pol = json.load(open(os.path.join(DATA_ROOT, "MULTILABEL_POLICY_V2_FINAL_EVAL.json"), encoding="utf-8"))
    support = json.load(open(os.path.join(DATA_ROOT, "STAGE3_ACTION_CANDIDATE_SUPPORT.json"), encoding="utf-8"))
    atomic_support = support["atomic_support_in_333"]

    # ---- 1. near-dup 过滤 ----
    dropped = set(nd["dropped_internal"])
    leak = {r["segment_id"] for r in nd["leak_risk_holdout"]}
    keep = [i for i in items if i["segment_id"] not in dropped and i["segment_id"] not in leak]
    print(f"V2={len(items)} 去重后={len(keep)} dropped={len(dropped)} leak={len(leak)}")

    # ---- 2. 候选池生成（供回流，逻辑同 V2 sampling）----
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    excl = {r[0] for r in conn.execute("SELECT segment_id FROM canonical_human_truth")}
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    excl |= {s["segment_id"] for s in hold["strata"]}
    used_asset = {r[0] for r in conn.execute(
        "SELECT DISTINCT asset_id FROM segments WHERE segment_id IN (SELECT segment_id FROM canonical_human_truth)")}
    used_asset |= {s["asset_id"] for s in hold["strata"]}
    used_asset |= {i.get("asset_id", "") for i in items if i.get("asset_id")}
    used_seg = {i["segment_id"] for i in items}
    cands = []
    for r in conn.execute("SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms, s.duration_ms "
                          "FROM segments s WHERE s.segment_id NOT IN (SELECT segment_id FROM canonical_human_truth)"
                          " AND s.segment_id NOT IN (SELECT segment_id FROM fresh_holdout_human_review_v1)"):
        sid = r["segment_id"]
        if sid in used_seg or sid in excl or r["asset_id"] in used_asset:
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
                      "text": text})
    conn.close()
    print("回流候选池:", len(cands))

    # ---- 3. 分类与排序 ----
    def classify(c):
        text = c["text"]
        action = []
        for atomic, kws in ACTION_KEYWORDS.items():
            if any(kw in text for kw in kws):
                action.append(atomic)
        variant = [w for w in VARIANT_KW if w in text]
        scene = [w for w in SCENE_KW if w in text]
        material = [w for w in MATERIAL_KW if w in text]
        people = [w for w in PEOPLE_KW if w in text]
        return {"action": action, "variant": variant, "scene": scene,
                "material": material, "people": people,
                "pure_visual": c["asr_len"] == 0 and c["ocr_len"] == 0}

    def action_score(a):
        return sum(ATOMIC_PRIORITY.get(x, 0) for x in a)

    for c in cands:
        c["cls"] = classify(c)

    def seg_set(lst):
        return {i["segment_id"] for i in lst}

    # ---- 4. 类别划分（基于 V2 的 primary_target）----
    def cat(i):
        t = i.get("primary_target", "")
        if t == "SEMANTIC_ACTION" or i.get("selection_reason") == "semantic_action":
            return "action"
        if t == "PEOPLE" or i.get("selection_reason") == "people":
            return "people"
        if i.get("selection_reason") == "product_variant":
            return "variant"
        if i.get("selection_reason") == "scene_longtail":
            return "scene"
        if i.get("selection_reason") == "material_longtail":
            return "material"
        return "visual"

    by_cat = defaultdict(list)
    for i in keep:
        by_cat[cat(i)].append(i)

    # ---- 5. Action 重平衡（保留稀缺原子优先，RETRACT 封顶，总量 <=20）----
    action_items = by_cat["action"]
    action_atomic = {}
    for i in action_items:
        text = " ".join(i.get("hits", []))
        mat = []
        for atomic, kws in ACTION_KEYWORDS.items():
            if any(kw in text for kw in kws):
                mat.append(atomic)
        action_atomic[i["segment_id"]] = mat or ["ACTION_KEYWORD_MISS"]
    rare = [i for i in action_items if any(a in ("OPEN_DRAWER", "CLOSE_DRAWER", "OPEN_CABINET",
                                                 "CLOSE_CABINET", "OPERATE_SOCKET", "OPEN_SINK_COVER")
                                           for a in action_atomic[i["segment_id"]])]
    pullout = [i for i in action_items if "PULL_OUT" in action_atomic[i["segment_id"]]]
    retract = [i for i in action_items if "RETRACT" in action_atomic[i["segment_id"]]]
    miss = [i for i in action_items if action_atomic[i["segment_id"]] == ["ACTION_KEYWORD_MISS"]]
    rare.sort(key=lambda i: -max(ATOMIC_PRIORITY.get(a, 0) for a in action_atomic[i["segment_id"]]))
    pullout.sort(key=lambda i: -len(action_atomic[i["segment_id"]]))
    action_keep = (rare[:10] + pullout[:6] + retract[:3] + miss[:1])[:20]
    action_keep_ids = seg_set(action_keep)
    reflow_action = [i for i in action_items if i["segment_id"] not in action_keep_ids]
    print(f"Action: 原{len(action_items)} -> 保留{len(action_keep)} (rare={len(rare)} pullout={len(pullout)} "
          f"retract={len(retract)} miss={len(miss)}) 回流={len(reflow_action)}")

    # ---- 6. People：按检测分歧 top12 排序（保留 12）----
    people_items = by_cat["people"]
    order_rank = {r["segment_id"]: idx for idx, r in enumerate(people_order)}
    people_items.sort(key=lambda i: order_rank.get(i["segment_id"], 999))
    people_keep = people_items[:12]
    people_keep_ids = seg_set(people_keep)
    reflow_people = [i for i in people_items if i["segment_id"] not in people_keep_ids]
    print(f"People: 原{len(people_items)} -> 保留{len(people_keep)} 回流={len(reflow_people)}")

    # ---- 7. Variant/Scene/Material 质量门 ----
    def keep_if_any(lst, kws):
        out, drop = [], []
        for i in lst:
            if any(w in " ".join(i.get("hits", [])) for w in kws):
                out.append(i)
            else:
                drop.append(i)
        return out, drop

    var_real, var_drop = keep_if_any(by_cat["variant"], ("标准", "悬浮", "落地", "固定"))
    scene_real, scene_drop = keep_if_any(by_cat["scene"], ("客户", "客厅", "卧室", "入户", "样板间", "安装", "展厅"))
    mat_real, mat_drop = keep_if_any(by_cat["material"], ("实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃"))
    print(f"Variant: {len(var_real)}/{len(by_cat['variant'])} | Scene: {len(scene_real)}/{len(by_cat['scene'])} | "
          f"Material: {len(mat_real)}/{len(by_cat['material'])}")

    # ---- 8. 组装（不重复添加）----
    keep = []
    seen_ids = set()
    for grp in (action_keep, people_keep, var_real, scene_real, mat_real, by_cat["visual"]):
        for i in grp:
            if i["segment_id"] in seen_ids:
                continue
            seen_ids.add(i["segment_id"])
            keep.append(i)
    print(f"组装后: {len(keep)} / {TOTAL}")

    # ---- 9. 回流补足（优先稀缺 action，再 people；被质量门剔除的 variant/scene/material 不再回流）----
    reflow_pool = reflow_action + reflow_people
    reflow_pool.sort(key=lambda i: (0 if cat(i) == "action" else 1,
                                    0 if cat(i) == "people" else 1,
                                    -len(i.get("hits", []))))
    while len(keep) < TOTAL and reflow_pool:
        i = reflow_pool.pop(0)
        if i["segment_id"] in seen_ids:
            continue
        seen_ids.add(i["segment_id"])
        keep.append(i)
    cands_ranked = sorted(cands, key=lambda c: (-action_score(c["cls"]["action"]),
                                                 -len(c["cls"]["people"])))
    used_assets_final = {i.get("asset_id", "") for i in keep}
    while len(keep) < TOTAL and cands_ranked:
        c = cands_ranked.pop(0)
        if c["segment_id"] in seen_ids or c["asset_id"] in used_assets_final:
            continue
        seen_ids.add(c["segment_id"])
        used_assets_final.add(c["asset_id"])
        keep.append({"segment_id": c["segment_id"], "asset_id": c["asset_id"],
                     "start_ms": c["start_ms"], "end_ms": c["end_ms"],
                     "duration_ms": c["duration_ms"], "asr_len": c["asr_len"],
                     "ocr_len": c["ocr_len"], "keyframes_n": c["keyframes_n"],
                     "selection_reason": "reflow_audit", "primary_target": "SEMANTIC_ACTION",
                     "secondary_targets": ["PEOPLE"], "hits": []})
    # 超额截断（保持优先级）
    if len(keep) > TOTAL:
        pri = lambda i: (0 if cat(i) == "action" else 1 if cat(i) == "people" else 2)
        keep = sorted(keep, key=pri)[:TOTAL]
    print(f"总计: {len(keep)} / 目标 {TOTAL}")

    # ---- 8. 组装 V3 条目 ----
    seg_rows = []
    for i in keep:
        sid = i["segment_id"]
        ndr = nd_status.get(sid, {})
        nst = ndr.get("near_duplicate_status", "UNIQUE")
        novelty = {"UNIQUE": 1.0, "NEAR_DUP_CALIBRATION": 0.6,
                   "NEAR_DUP_INTERNAL": 0.0, "LEAK_RISK_HOLDOUT": 0.0}.get(nst, 0.5)
        if i.get("primary_target") == "SEMANTIC_ACTION":
            text = " ".join(i.get("hits", []))
            atomic = [a for a, kws in ACTION_KEYWORDS.items() if any(kw in text for kw in kws)]
            if atomic and any(a in ("OPEN_DRAWER", "CLOSE_DRAWER", "OPEN_CABINET",
                                    "CLOSE_CABINET", "OPERATE_SOCKET") for a in atomic):
                novelty = min(1.0, novelty + 0.05)
        seg_rows.append({
            "segment_id": sid, "asset_id": i.get("asset_id", ""),
            "start_ms": i.get("start_ms", 0), "end_ms": i.get("end_ms", 0),
            "duration_ms": i.get("duration_ms", 0),
            "keyframes_n": i.get("keyframes_n", 0),
            "sampling_target": i.get("primary_target", "SEMANTIC_ACTION"),
            "sampling_target_cn": {"SEMANTIC_ACTION": "动作", "PEOPLE": "人物",
                                   "PRODUCT_VARIANT": "变体", "SCENE": "场景",
                                   "MATERIAL": "材质", "PURE_VISUAL": "纯视觉"}.get(
                                       i.get("primary_target", ""), "动作"),
            "secondary_targets": i.get("secondary_targets", []),
            "selection_reason": i.get("selection_reason", ""),
            "sampling_keywords": i.get("hits", []),
            "near_duplicate_status": nst,
            "novelty_score": round(novelty, 2),
        })

    assert len({r["segment_id"] for r in seg_rows}) == len(seg_rows)
    assert len({r["asset_id"] for r in seg_rows}) == len(seg_rows), "asset 重复！"

    composition = dict(Counter(r["sampling_target"] for r in seg_rows))
    multi = sum(1 for r in seg_rows if r["secondary_targets"])
    out = {"manifest_version": "TARGETED_REVIEW_STAGE3_V3",
           "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "deprecates": "TARGETED_REVIEW_STAGE3_V2.json（SUPERSEDED_PRE_REVIEW_BATCH，保留）",
           "note": ("FINAL PRE-REVIEW BATCH 冻结；near-dup 两信号过滤 + people 真检测排序 + "
                    "action 原子化 + 诚实长尾；DEV/Calibration 扩展，非 Holdout"),
           "guard": "DEV_ONLY; NOT_HOLDOUT; 盲审: 隐藏一切 AI 预测/分数/证据，仅显示采样目标",
           "policy_final": pol["summary"],
           "composition": composition, "multi_target_count": multi,
           "library_candidate_gap": support["library_candidate_gap"],
           "segments": seg_rows}
    p = os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 冻结：写盘后计算 sha256（存独立 sidecar，保证文件自洽可校验）
    h = sha256(p)
    sidecar = os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3.sha256")
    json.dump({"manifest": "TARGETED_REVIEW_STAGE3_V3", "sha256": h,
               "note": "冻结指纹；校验: sha256sum -c 或对照本文件"},
              open(sidecar, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p, "| 总条数:", len(seg_rows), "| multi-target:", multi)
    print("sha256:", h, "->", sidecar)
    print("composition:", composition)
    print("库缺口:", json.dumps(support["library_candidate_gap"], ensure_ascii=False))

    # 标记 V2 为 SUPERSEDED
    v2["superseded_by"] = "TARGETED_REVIEW_STAGE3_V3"
    v2["superseded_reason"] = "SUPERSEDED_PRE_REVIEW_BATCH（near-dup 过滤 / people 检测排序 / action 原子化）"
    json.dump(v2, open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V2.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("V2 已标记 SUPERSEDED")


if __name__ == "__main__":
    main()
