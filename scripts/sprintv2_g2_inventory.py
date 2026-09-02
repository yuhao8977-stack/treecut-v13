# -*- coding: utf-8 -*-
"""G2: 候选清单(严格池13642 × 动作关键词) — 干净实现。"""
import json, sqlite3, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)

STRICT = ("r.source_role IN ('PRODUCTION_CLEAN_RAW','PRODUCTION_CLEAN_SEMI') "
          "AND r.review_status!='REJECTED' "
          "AND (r.review_status='APPROVED' OR (r.burned_subtitle_present='ABSENT' "
          "AND r.platform_watermark_present='ABSENT' AND r.unrelated_overlay_present='ABSENT' "
          "AND r.old_title_overlay_present='ABSENT' AND r.brand_overlay_present='ABSENT'))")

ACTION_KW = {
    "EXTEND": ["伸缩", "变宽", "延伸"],
    "RETRACT": ["收起", "收起来", "缩回"],
    "DRAWER_OPEN": ["抽屉拉开", "薄抽收纳", "薄抽", "拉开"],
    "SOCKET_INSERT": ["插座插拔", "轨道插座", "插上"],
    "CABINET_OPEN": ["柜门", "开门"],
    "STORAGE_PUT_IN": ["放入", "收纳"],
    "POWER_USE": ["火锅", "煮茶", "烧水"],
    "PRODUCT_MOVE": ["移动", "挪"],
}

cand = {}
for act, kws in ACTION_KW.items():
    like = " OR ".join(["mf.relative_path LIKE ?"] * len(kws))
    args = [f"%{k}%" for k in kws]
    rows = c.execute(
        f"""SELECT DISTINCT mf.id, mf.source_id, mf.relative_path
            FROM media_files mf
            WHERE mf.source_id IN (1,2,4) AND mf.extension='.mp4' AND ({like})
            AND mf.id IN (SELECT r.entity_id FROM b007_source_role_v1 r
                          WHERE r.entity_kind='media_file' AND {STRICT})
            LIMIT 300""", args).fetchall()
    items = []
    for mid, sid, rel in rows:
        folder = rel.split("\\")[0] if "\\" in rel else ""
        items.append({"media_id": mid, "source_id": sid, "folder_hint": folder, "rel": rel[:130]})
    cand[act] = items
    print(f"{act}: {len(items)}")

json.dump(cand, open(OUT / "_g2_inventory.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("inventory saved")
