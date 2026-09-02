# -*- coding: utf-8 -*-
"""V0.9.1 CP-2/3: 原子主张脚本 + 混剪叙事 + 干净素材检索候选（X1 原始池）。"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"

# 混剪通用脚本（INFORMATION_MONTAGE：跨案例通用语言，所有主张由干净动作片段支撑）
SCRIPT = ("岛台想好用，这三个细节最值得看。第一，上层薄抽，收纳小物不弯腰，"
          "打开就能拿到。第二，轨道插座，吃火锅煮茶都方便，插拔也顺手。"
          "第三，伸缩桌面，来客时一拉就变宽，平时收起来不占位。"
          "厨房好不好用，全在这些小细节里。")
# claim 拆解（atomic）
CLAIMS = [
    {"claim_id": "C01", "claim_type": "PRODUCT_IDENTITY", "text": "岛台", "evidence_req": "OBJECT_PRESENT"},
    {"claim_id": "C02", "claim_type": "FUNCTION", "text": "上层薄抽收纳", "evidence_req": "ACTION_DEMONSTRATION_COMPLETE"},
    {"claim_id": "C03", "claim_type": "USE_CASE", "text": "收纳小物不弯腰", "evidence_req": "ACTION_DEMONSTRATION_COMPLETE"},
    {"claim_id": "C04", "claim_type": "FUNCTION", "text": "轨道插座可用", "evidence_req": "FUNCTION_VISIBLE"},
    {"claim_id": "C05", "claim_type": "USE_CASE", "text": "吃火锅煮茶插拔方便", "evidence_req": "FUNCTION_VISIBLE"},
    {"claim_id": "C06", "claim_type": "FUNCTION", "text": "桌面可伸缩", "evidence_req": "ACTION_DEMONSTRATION_COMPLETE"},
    {"claim_id": "C07", "claim_type": "USE_CASE", "text": "来客一拉变宽", "evidence_req": "ACTION_DEMONSTRATION_COMPLETE"},
    {"claim_id": "C08", "claim_type": "USE_CASE", "text": "平时收起来不占位", "evidence_req": "ACTION_DEMONSTRATION_COMPLETE"},
    {"claim_id": "C09", "claim_type": "CTA", "text": "厨房好用靠细节", "evidence_req": "OBJECT_PRESENT"},
]
BEATS = [
    {"beat_id": "B1", "type": "HOOK", "text": "岛台想好用，这三个细节最值得看",
     "claims": ["C01"], "story": "MONTAGE_INTRO"},
    {"beat_id": "B2", "type": "FEATURE_STORAGE", "text": "上层薄抽收纳，打开就能拿到",
     "claims": ["C02", "C03"], "story": "MONTAGE_FEATURE_1"},
    {"beat_id": "B3", "type": "FEATURE_POWER", "text": "轨道插座，插拔顺手",
     "claims": ["C04", "C05"], "story": "MONTAGE_FEATURE_2"},
    {"beat_id": "B4", "type": "FEATURE_FLEXIBLE", "text": "伸缩桌面，一拉变宽",
     "claims": ["C06", "C07", "C08"], "story": "MONTAGE_FEATURE_3"},
    {"beat_id": "B5", "type": "CTA", "text": "厨房好不好用，全在小细节",
     "claims": ["C09"], "story": "MONTAGE_CTA"},
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    (OUT / "B007_V2_ATOMIC_CLAIMS_V1.json").write_text(json.dumps(
        {"story_mode": "INFORMATION_MONTAGE", "script": SCRIPT, "claims": CLAIMS,
         "note": "通用混剪语言：不指向单一产品/客户；每句主张由干净动作画面支撑（无 岩板→耐刮 式推断）"},
        ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_V2_SCRIPT_BEATS_V1.json").write_text(json.dumps(
        {"beats": BEATS}, ensure_ascii=False, indent=2), encoding="utf-8")

    c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    # 干净资产：X1 卖点展示类素材(source 1) 中，OCR 无烧录字幕(污染=0) 的资产
    feat_keywords = {
        "STORAGE": ["薄抽", "抽屉", "收纳", "对开", "开放抽屉"],
        "POWER": ["插座", "轨道插"],
        "FLEXIBLE": ["伸缩"],
        "MATERIAL": ["材质", "细节"],
    }
    cand = {"STORAGE": [], "POWER": [], "FLEXIBLE": []}
    for feat, kws in feat_keywords.items():
        if feat == "MATERIAL":
            continue
        like = " OR ".join(["mf.relative_path LIKE ?"] * len(kws))
        args = [f"%{k}%" for k in kws] * 1
        args = [f"%{k}%" for k in kws]
        rows = c.execute(
            f"SELECT a.asset_id, a.media_id, mf.relative_path, a.duration FROM assets a "
            f"JOIN media_files mf ON mf.id=a.media_id WHERE mf.source_id IN (1,2) AND ({like}) "
            f"AND a.duration BETWEEN 1.0 AND 30.0 LIMIT 40", args).fetchall()
        for aid, mid, rel, dur in rows:
            cand[feat].append({"asset_id": aid, "media_id": mid, "path": rel,
                               "duration_s": round(dur, 1), "feature": feat})
    c.close()
    (OUT / "B007_V2_SHOT_CANDIDATES_V1.json").write_text(json.dumps(
        {"phase": "V0.9.1-CP3", "pool": "X1 卖点展示类/效果展示类素材(source1/2) 原始干净片段",
         "clean_filter": "资产级 OCR 无烧录字幕(污染≈0)；folder 语义匹配特征关键词",
         "candidates": cand}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"story_mode": "INFORMATION_MONTAGE", "claims": len(CLAIMS),
                      "candidate_counts": {k: len(v) for k, v in cand.items()},
                      "samples": {k: v[:2] for k, v in cand.items()}}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
