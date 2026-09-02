# -*- coding: utf-8 -*-
"""G2 诊断: 严格池口径 + 每动作关键词命中(按 review/污染拆解)。"""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)

# 严格池: 五字段='ABSENT' 精确 或 APPROVED(role CLEAN)
strict_sql = """SELECT r.entity_id, r.source_id, r.review_status, r.burned_subtitle_present
    FROM b007_source_role_v1 r
    WHERE r.entity_kind='media_file'
    AND r.source_role IN ('PRODUCTION_CLEAN_RAW','PRODUCTION_CLEAN_SEMI')
    AND r.review_status!='REJECTED'
    AND (r.review_status='APPROVED' OR (
        r.burned_subtitle_present='ABSENT' AND r.platform_watermark_present='ABSENT'
        AND r.unrelated_overlay_present='ABSENT' AND r.old_title_overlay_present='ABSENT'
        AND r.brand_overlay_present='ABSENT'))"""
print("strict pool:", c.execute("SELECT count(*) FROM (" + strict_sql + ")").fetchone()[0])

def hits(kw, cond):
    rows = c.execute(f"""SELECT DISTINCT mf.id FROM media_files mf
        WHERE mf.relative_path LIKE ? AND mf.source_id IN (1,2,4) AND mf.extension='.mp4'
        AND mf.id IN (SELECT r.entity_id FROM b007_source_role_v1 r WHERE r.entity_kind='media_file' AND {cond})""",
                     (f"%{kw}%",)).fetchall()
    return len(rows)

STRICT = ("(r.source_role IN ('PRODUCTION_CLEAN_RAW','PRODUCTION_CLEAN_SEMI') AND r.review_status!='REJECTED' "
          "AND (r.review_status='APPROVED' OR (r.burned_subtitle_present='ABSENT' AND r.platform_watermark_present='ABSENT' "
          "AND r.unrelated_overlay_present='ABSENT' AND r.old_title_overlay_present='ABSENT' AND r.brand_overlay_present='ABSENT')))")
ALLS1 = "r.source_id IN (1,2,4)"
for kw in ("伸缩", "抽屉", "薄抽", "插座", "轨道插座", "柜门", "收纳", "尺寸展示", "功能"):
    print(f"{kw}: strict={hits(kw, STRICT)}  (all-S1S2S4-with-any-role={hits(kw, '1=1')})")

# S4 raw 是否可能含动作(无文件夹名, 全量 eligible raw 数)
print("S4 RAW eligible(ABSENT):",
      c.execute("SELECT count(*) FROM (" + strict_sql + ") WHERE source_id=4").fetchone()[0])
print("S1 eligible:", c.execute("SELECT count(*) FROM (" + strict_sql + ") WHERE source_id=1").fetchone()[0])
print("S2 eligible:", c.execute("SELECT count(*) FROM (" + strict_sql + ") WHERE source_id=2").fetchone()[0])
