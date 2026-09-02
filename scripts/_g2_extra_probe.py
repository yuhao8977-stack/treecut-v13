# -*- coding: utf-8 -*-
import json, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
STRICT = ("r.source_role IN ('PRODUCTION_CLEAN_RAW','PRODUCTION_CLEAN_SEMI') AND r.review_status!='REJECTED' "
          "AND (r.review_status='APPROVED' OR (r.burned_subtitle_present='ABSENT' "
          "AND r.platform_watermark_present='ABSENT' AND r.unrelated_overlay_present='ABSENT' "
          "AND r.old_title_overlay_present='ABSENT' AND r.brand_overlay_present='ABSENT'))")
out = {}
for kw in ("蒸烤箱", "嵌入式", "火锅", "煮茶", "下层抽屉", "对开门"):
    rows = c.execute(
        "SELECT DISTINCT mf.id, mf.relative_path FROM media_files mf "
        "WHERE mf.relative_path LIKE ? AND mf.source_id IN (1,2) AND mf.extension='.mp4' "
        "AND mf.id IN (SELECT r.entity_id FROM b007_source_role_v1 r WHERE r.entity_kind='media_file' AND "
        + STRICT + ") LIMIT 5", (f"%{kw}%",)).fetchall()
    out[kw] = [{"media_id": r[0], "rel": r[1][:100]} for r in rows]
    print(kw, len(rows))
    for r in rows[:3]:
        print("   ", r[0], r[1][:90])
json.dump(out, open(r"C:\Users\admin\github\treecut-v13\reports\storage\_g2_extra_inventory.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
