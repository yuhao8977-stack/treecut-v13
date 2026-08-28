# -*- coding: utf-8 -*-
"""Phase 3 STEP 10 — THIRD_ADJUDICATION_V1.json（34 段 NEEDS_ADJUDICATION 裁决队列）。

生成队列（不自动启动审核窗口；等 Schema V2.1 UI 就绪后人工裁决）。
每段含：V1 人工 / V2 人工 / canonical current（合并参考）/ 冲突字段 / 裁决指引。
"""
import json
import os
import sqlite3
import sys
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

FIELDS = ["scene", "product", "material", "function", "action", "shot_type", "people_presence"]

conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

na = [r for r in conn.execute(
    "SELECT * FROM canonical_human_truth WHERE truth_source='NEEDS_ADJUDICATION'")]
v1_map = {r["target_id"]: r for r in conn.execute("SELECT * FROM human_annotations")}
v2_map = {r["segment_id"]: r for r in conn.execute("SELECT * FROM human_annotation_v2")}
seg_map = {r["segment_id"]: r for r in conn.execute(
    "SELECT segment_id, asset_id, start_ms, end_ms FROM segments")}

items = []
for r in na:
    sid = r["segment_id"]
    v1 = v1_map.get(sid)
    v2 = v2_map.get(sid)
    seg = seg_map.get(sid)
    # 冲突字段（canonical 合并参考 vs v1/v2 差异，简列）
    diffs = []
    for f in ("scene", "product", "function", "action", "shot_type"):
        a = (v1[f] or "").strip() if v1 else ""
        b = (v2[f] or "").strip() if v2 else ""
        if a and b and a != b:
            diffs.append({"field": f, "v1": a, "v2": b})
    items.append({
        "segment_id": sid,
        "asset_id": seg["asset_id"] if seg else "",
        "start_ms": seg["start_ms"] if seg else 0,
        "end_ms": seg["end_ms"] if seg else 0,
        "v1_human": {f: (v1[f] or "") for f in FIELDS} if v1 else None,
        "v2_human": {f: (v2[f] or "") for f in FIELDS} if v2 else None,
        "conflict_fields": diffs,
        "current_reference": {
            "scene_family": r["scene_family"], "scene_subtype": r["scene_subtype"],
            "product_family": r["product_family"], "product_variant": r["product_variant"],
            "material": r["material"], "component": r["component"],
            "function": r["function"], "action_group": r["action_group"],
            "atomic_action": r["atomic_action"], "shot_scale": r["shot_scale"],
            "shot_role": r["shot_role"], "people_presence": r["people_presence"],
        },
        "adjudication_note": ("请使用 ANNOTATION_DICTIONARY_V2_1 词典；隐藏 AI/V1/V2 答案；"
                              "保存为 Human V3；完成后 new_version() 升级 canonical 并保留历史"),
    })

out = {
    "manifest_version": "THIRD_ADJUDICATION_V1",
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "total": len(items),
    "dictionary": "ANNOTATION_DICTIONARY_V2_1",
    "policy": ("隐藏 AI 答案 / V1 答案 / V2 答案；用 V2.1 词典独立裁决；"
               "结果保存 Human V3 → canonical new_version（旧真值保留在 history）"),
    "segments": items,
}
p = os.path.join(DATA_ROOT, "THIRD_ADJUDICATION_V1.json")
with open(p, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("THIRD_ADJUDICATION_V1 ->", p, "| 34 段")
print("冲突字段统计:")
from collections import Counter
cc = Counter()
for it in items:
    for d in it["conflict_fields"]:
        cc[d["field"]] += 1
print(dict(cc))
conn.close()
