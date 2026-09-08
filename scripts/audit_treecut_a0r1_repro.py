# -*- coding: utf-8 -*-
"""A0 R1 — CURRENT REDUCED CHAIN REPRODUCTION (read-only on prod data, outputs to audit temp).

Runs the existing reduced production chain (ProductionService._create) against a
temporary COPY of the production DB, real narration, current valid eligible media.
Output redirected via TREECUT_DATA_ROOT to audit temp. No production code modified.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
AUDIT = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\a0r1_repro")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(REPO / "src"))

os.environ["TREECUT_DATA_ROOT"] = str(AUDIT)
AUDIT.mkdir(parents=True, exist_ok=True)
DB_COPY = AUDIT / "materials_copy.db"
shutil.copy2(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\database\materials.db", DB_COPY)

NARRATION = ("小户型也能拥有实用岛台。伸缩设计兼顾办公、用餐和聚会。"
             "分区收纳让常用物品随手可取。合理定制高度、宽度和台面厚度，让小空间更舒适。")
SELLING = "小户型岛台 可伸缩设计 分区收纳 实用尺寸 家庭办公会客两用"


def main():
    from treecut.application import CreativeRequest, ProductionService
    from treecut.platform.paths import RuntimePaths
    paths = RuntimePaths.discover()
    paths.ensure()
    # point service at our DB copy via env is not enough; ProductionService uses context.paths.databases
    # -> copy DB into the discovered databases dir of the audit data root
    db_dir = paths.databases
    db_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB_COPY, db_dir / "materials.db")
    request = CreativeRequest(
        selling_points=SELLING,
        narration=NARRATION,
        target_duration=25.0,
        clip_seconds=4.0,
        output_mp4=True,
        output_jianying=True,
        include_test_materials=False,
        bgm_path="",
        output_preset="vertical",
        narration_speed=1.0,
        style="natural",
        watermark_path="")
    svc = ProductionService()
    t0 = time.time()
    try:
        result = svc.create(request)
        dt = round(time.time() - t0, 1)
        out = {"PASS": True, "seconds": dt,
               "project": result.project_dir, "preview": result.preview_mp4,
               "final_mp4": result.final_mp4, "draft": result.jianying_draft,
               "report": result.report_path, "cover": result.cover_path,
               "n_matches": result.match_count, "plan_duration": result.planned_duration,
               "data_root": str(AUDIT)}
    except Exception as e:
        import traceback
        out = {"PASS": False, "error": f"{type(e).__name__}: {str(e)[:300]}",
               "trace": traceback.format_exc()[-1200:]}
    (AUDIT / "reproduction_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
