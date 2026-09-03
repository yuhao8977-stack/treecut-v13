# -*- coding: utf-8 -*-
"""Discovery Stage A: 全 Eligible 池宽召回计数/清单(纯廉价信号, 无qwen)。
信号: ①路径/文件夹关键词 ②OCR文本关键词 ③文件夹语义映射。"""
import json, sqlite3, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
ELIG = ("r.source_role IN ('PRODUCTION_CLEAN_RAW','PRODUCTION_CLEAN_SEMI') AND r.review_status!='REJECTED' "
        "AND (r.review_status='APPROVED' OR (r.burned_subtitle_present='ABSENT' "
        "AND r.platform_watermark_present='ABSENT' AND r.unrelated_overlay_present='ABSENT' "
        "AND r.old_title_overlay_present='ABSENT' AND r.brand_overlay_present='ABSENT'))")

PLAN = {
    "EXTEND": {"path": ["伸缩", "变宽", "延伸"], "ocr": ["伸缩", "变宽", "拉开"]},
    "RETRACT": {"path": ["收起", "收回"], "ocr": ["收起来", "收回", "收起"]},
    "DRAWER_OPEN": {"path": ["薄抽", "抽屉"], "ocr": ["拉开", "抽屉", "拉出"]},
    "STORAGE_PUT_IN": {"path": ["收纳", "放置"], "ocr": ["放进去", "放东西", "收纳"]},
    "SOCKET_INSERT": {"path": ["轨道插座", "插座插拔"], "ocr": ["插拔", "插上", "插座"]},
}
res = {}
for act, sig in PLAN.items():
    # ① 路径关键词
    like = " OR ".join(["mf.relative_path LIKE ?"] * len(sig["path"]))
    path_rows = c.execute(
        f"SELECT mf.id, mf.source_id, mf.relative_path FROM media_files mf WHERE mf.extension='.mp4' "
        f"AND mf.source_id IN (1,2,4) AND ({like}) AND mf.id IN "
        f"(SELECT r.entity_id FROM b007_source_role_v1 r WHERE r.entity_kind='media_file' AND {ELIG})",
        [f"%{k}%" for k in sig["path"]]).fetchall()
    path_ids = {r[0] for r in path_rows}
    # ② OCR 文本关键词(仅限有 OCR 的资产)
    olike = " OR ".join(["o.text LIKE ?"] * len(sig["ocr"]))
    ocr_rows = c.execute(
        f"SELECT DISTINCT mf.id FROM ocr_text o JOIN assets a ON a.asset_id=o.asset_id "
        f"JOIN media_files mf ON mf.id=a.media_id WHERE ({olike}) AND mf.id IN "
        f"(SELECT r.entity_id FROM b007_source_role_v1 r WHERE r.entity_kind='media_file' AND {ELIG})",
        [f"%{k}%" for k in sig["ocr"]]).fetchall()
    ocr_ids = {r[0] for r in ocr_rows}
    union = path_ids | ocr_ids
    res[act] = {"path_signal": len(path_ids), "ocr_signal": len(ocr_ids),
                "union_eligible": len(union)}
    print(act, "path", len(path_ids), "ocr", len(ocr_ids), "union", len(union))
json.dump(res, open(OUT / "_g2_discovery_a.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("Stage A saved")
