# -*- coding: utf-8 -*-
"""Candidate Discovery Recovery V1.1 — 全量廉价排序(DB, 无qwen) → 每动作 Top 排序清单(多样性)。
产出 _v11_ranked.json: action -> [{media_id, sid, rel, folder, score_components, score}] top≤60"""
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
# 中性动作族: EXTEND/RETRACT 共享 FLEXIBLE_TABLE_MOTION 池(方向由时序层判定)
FAMILY = {
    "EXTEND": "flexible", "RETRACT": "flexible",
    "DRAWER_OPEN": "drawer", "STORAGE_PUT_IN": "storage", "SOCKET_INSERT": "socket"}
FOLDER_ACT = {
    "flexible": ["【21】伸缩功能", "伸缩", "折叠", "展开"],
    "drawer": ["【01】上层薄抽", "【02】下层抽屉", "薄抽", "抽屉"],
    "storage": ["【01】上层薄抽", "【02】下层抽屉", "收纳", "分区"],
    "socket": ["【05】公牛轨道插座", "轨道插座", "插座"]}
TOKENS = {
    "flexible": ["伸缩", "变宽", "延伸", "拉开", "加宽"],
    "drawer": ["薄抽", "抽屉", "抽拉", "拉开"],
    "storage": ["收纳", "放置", "分区", "抽屉", "放"],
    "socket": ["轨道插座", "插座", "插拔", "插上"]}
OCR_TERMS = {
    "flexible": ["伸缩", "变宽", "拉开", "拉出"],
    "drawer": ["拉开", "抽屉", "拉出", "打开"],
    "storage": ["放进去", "放东西", "收纳", "拿走", "拿出"],
    "socket": ["插拔", "插上", "插座", "插电"]}

def ocr_hits(asset_ids, terms):
    if not asset_ids:
        return {}
    like = " OR ".join(["o.text LIKE ?"] * len(terms))
    rows = c.execute(
        f"SELECT a.media_id, count(*) FROM ocr_text o JOIN assets a ON a.asset_id=o.asset_id "
        f"WHERE ({like}) AND a.media_id IN ({','.join('?' * len(asset_ids))}) GROUP BY a.media_id",
        [f"%{t}%" for t in terms] + list(asset_ids)).fetchall()
    return {r[0]: r[1] for r in rows}

ranked = {}
for act, fam in FAMILY.items():
    like = " OR ".join(["mf.relative_path LIKE ?"] * len(FOLDER_ACT[fam]))
    rows = c.execute(
        f"SELECT mf.id, mf.source_id, mf.relative_path, r.review_status FROM media_files mf "
        f"JOIN b007_source_role_v1 r ON r.entity_id=mf.id AND r.entity_kind='media_file' "
        f"WHERE mf.source_id IN (1,2,4) AND mf.extension='.mp4' AND ({like}) AND ({ELIG}) LIMIT 1200",
        [f"%{k}%" for k in FOLDER_ACT[fam]]).fetchall()
    ids = [r[0] for r in rows]
    ocr = ocr_hits(ids, OCR_TERMS[fam])
    scored = []
    for mid, sid, rel, rev in rows:
        s = 0.0
        comp = {}
        folder = rel.split("\\")[0] if "\\" in rel else ""
        # 文件夹语义强信号
        if fam == "flexible" and "伸缩" in folder:
            s += 4.0; comp["folder_function"] = 4.0
        elif fam == "drawer" and ("薄抽" in folder or "抽屉" in folder):
            s += 4.0; comp["folder_function"] = 4.0
        elif fam == "socket" and "轨道插座" in folder:
            s += 4.0; comp["folder_function"] = 4.0
        elif fam == "storage" and ("收纳" in folder or "薄抽" in folder):
            s += 3.0; comp["folder_function"] = 3.0
        # 文件名 token 数
        tok = sum(1 for t in TOKENS[fam] if t in rel)
        if tok:
            s += min(2.0, tok * 0.8); comp["path_tokens"] = round(min(2.0, tok * 0.8), 2)
        # OCR 命中
        n_ocr = ocr.get(mid, 0)
        if n_ocr:
            s += min(2.0, n_ocr * 0.5); comp["ocr_terms"] = round(min(2.0, n_ocr * 0.5), 2)
        # 人工核准加分
        if rev == "APPROVED":
            s += 0.5; comp["approved"] = 0.5
        scored.append({"media_id": mid, "sid": sid, "rel": rel[:130], "folder": folder[:24],
                       "score": round(s, 2), "components": comp})
    scored.sort(key=lambda x: -x["score"])
    # 多样性: 每 asset 仅1条(已是asset级), 取 top 60
    ranked[act] = scored[:60]
    print(act, "family", fam, "scored", len(scored), "top60 score range",
          scored[0]["score"] if scored else None, "-", scored[-1]["score"] if scored else None)
json.dump(ranked, open(OUT / "_v11_ranked.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("V1.1 cheap ranking saved")
