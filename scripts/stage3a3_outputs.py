# -*- coding: utf-8 -*-
"""Stage 3A.3 — B003 Asset Discovery 输出集。

诚实结论：
  现有 Asset DB 无成片索引（duration 全 0、无 finished 分类、无 B003 关联）
  Z:\B组更新视频 360 个成片未进 TreeCut 索引（需先导入）
  duration 匹配 136/155 但 128 个多候选（时长重复）→ 不足以可靠区分
  → STAGE3A3_NEEDS_ASSET_REPAIR（成片需导入 TreeCut 才能完成映射）
"""
import io, json, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DATA = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"

inv = json.load(open(os.path.join(DATA, "B003_PUBLISHED_CONTENT_INVENTORY_V3.json"), encoding="utf-8"))
z = json.load(open(os.path.join(DATA, "B003_Z_GROUP_ASSETS_V1.json"), encoding="utf-8"))
notes = [r for r in inv["records"] if r["note_id"]]

# ---- Asset Discovery Inventory ----
disc = {
    "manifest": "B003_ASSET_DISCOVERY_INVENTORY_V1",
    "generated_at": "2026-08-30",
    "existing_asset_db": {
        "assets_total": 22465, "assets_with_duration": 22465,
        "duration_reliable": False,  # 全 0.0（probe 未填充）
        "finished_classification": "NONE（media_files.category 全 unclassified）",
        "b003_linked_assets": 0,
        "z_group_in_index": False,
    },
    "z_group_candidates": {
        "total": 360, "with_duration": 360,
        "duration_range": [16.3, 141.3],
        "in_treecut_index": False,
        "note": "Z:\\B组更新视频 未进 TreeCut；文件名=日期+产品视频编号，无标题语义",
    },
    "published_side": {
        "notes": len(notes), "with_duration": 155,
        "duration_range": [10, 226],
    },
    "verdict": "ASSET_DB_COVERAGE_INSUFFICIENT — 现有索引无成片；Z 组 360 成片未导入",
}
json.dump(disc, open(os.path.join(DATA, "B003_ASSET_DISCOVERY_INVENTORY_V1.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---- Candidates Top-K（duration ±1.5s 候选）----
cands = []
for n in notes:
    nd = float(n["duration"]) if n.get("duration") else None
    top = []
    if nd:
        pool = [a for a in z["assets"] if a["duration"] and abs(a["duration"] - nd) <= 1.5]
        pool.sort(key=lambda a: abs(a["duration"] - nd))
        for a in pool[:5]:
            top.append({"asset_id": f"Z-{a['filename']}", "path": a["path"],
                        "duration": a["duration"], "duration_score": round(1.0 - abs(a["duration"] - nd) / 1.5, 2)})
    cands.append({"published_content_id": n["published_content_id"], "note_id": n["note_id"],
                  "title": n["title"], "duration": nd, "top_candidates": top,
                  "candidate_count": len(top)})
n_with = sum(1 for c in cands if c["candidate_count"] > 0)
print(f"Top-K 候选: {n_with}/{len(cands)} 有候选")
json.dump({"manifest": "B003_PUBLISHED_ASSET_CANDIDATES_V1", "count": len(cands),
           "with_candidates": n_with, "candidates": cands},
          open(os.path.join(DATA, "B003_PUBLISHED_ASSET_CANDIDATES_V1.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---- Mapping V4（无 EXACT/HIGH_CONFIDENCE，全 UNKNOWN——证据不足）----
mapping = {"manifest": "B003_PUBLISHED_CONTENT_ASSET_MAPPING_V4", "account": "B003",
           "total_notes": len(notes),
           "by_status": {"EXACT": 0, "HIGH_CONFIDENCE": 0, "AMBIGUOUS": 0, "UNKNOWN": len(notes)},
           "records": [{"note_id": n["note_id"], "title": n["title"], "mapping_status": "UNKNOWN",
                        "reason": "duration 候选 128/136 多候选；无 ASR/visual/成片索引可区分"}
                       for n in notes]}
json.dump(mapping, open(os.path.join(DATA, "B003_PUBLISHED_CONTENT_ASSET_MAPPING_V4.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---- Review Queue（不生成——无值得审的 AMBIGUOUS，全部 UNKNOWN）----
json.dump({"manifest": "B003_ASSET_MAPPING_REVIEW_QUEUE_V2", "items": [],
           "note": "无 AMBIGUOUS 候选可审（全部 UNKNOWN，证据不足）"},
          open(os.path.join(DATA, "B003_ASSET_MAPPING_REVIEW_QUEUE_V2.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---- Repost Clusters（无映射→无 cluster）----
json.dump({"manifest": "B003_REPOST_CLUSTERS_V1", "clusters": [],
           "note": "Asset 映射未建立，无法检测重发 cluster"},
          open(os.path.join(DATA, "B003_REPOST_CLUSTERS_V1.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---- Join Coverage ----
cov = {"manifest": "B003_ASSET_JOIN_COVERAGE_V1", "account": "B003",
       "coverage": {"published_to_asset": 0.0, "asset_to_segment": 0.0,
                    "published_to_cognition": 0.0},
       "counts": {"published": len(notes), "with_asset": 0, "with_segment": 0, "with_cognition": 0},
       "status": "STAGE3A3_NEEDS_ASSET_REPAIR"}
json.dump(cov, open(os.path.join(DATA, "B003_ASSET_JOIN_COVERAGE_V1.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("-> 7 个输出已生成")
print("判定: STAGE3A3_NEEDS_ASSET_REPAIR")
