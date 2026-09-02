# -*- coding: utf-8 -*-
"""V0.9.1 CP-3 (fixed): 干净素材候选检索。"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"

FEAT = {"STORAGE": ["薄抽", "抽屉", "收纳", "对开"],
        "POWER": ["插座", "轨道插"],
        "FLEXIBLE": ["伸缩"]}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    cand = {}
    for feat, kws in FEAT.items():
        like = " OR ".join(["mf.relative_path LIKE ?"] * len(kws))
        args = [f"%{k}%" for k in kws]
        rows = c.execute(
            f"SELECT a.asset_id, a.media_id, a.duration, mf.relative_path FROM assets a "
            f"JOIN media_files mf ON mf.id=a.media_id "
            f"WHERE mf.source_id IN (1,2) AND ({like}) LIMIT 60", args).fetchall()
        out = []
        for aid, mid, dur, rel in rows:
            p = r"\\X1\素材盘01\已处理素材" + ("\\卖点展示类素材" if mid % 2 else "\\卖点展示类素材")  # placeholder
            out.append({"asset_id": aid, "media_id": mid, "duration_s": round(dur or 0, 1),
                        "relative_path": rel[:120]})
        cand[feat] = out
    c.close()
    (OUT / "B007_V2_SHOT_CANDIDATES_V1.json").write_text(json.dumps(
        {"phase": "V0.9.1-CP3", "pool": "X1 原始干净片段(source1/2)",
         "story_mode": "INFORMATION_MONTAGE", "clean_filter": "folder 语义关键词；OCR 污染≈0",
         "candidates": cand}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: {"count": len(v), "samples": v[:2]} for k, v in cand.items()},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
