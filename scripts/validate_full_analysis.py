"""Run one isolated real video through the formal full-analysis worker."""
from __future__ import annotations

import json
import os
import sqlite3
import time

from treecut.analysis.worker import AnalysisWorker
from treecut.library import Catalog


SOURCE = r"G:\TreeCut_v13\runtime_data\test_materials\desktop_树剪调用_20260803"


def main() -> None:
    catalog = Catalog()
    if os.environ.get("TREECUT_VALIDATION_SUMMARY_ONLY") != "1":
        scan = catalog.scan(SOURCE, kind="isolated_validation")
        print("scan", scan.to_dict(), flush=True)
        started = time.time()
        run = AnalysisWorker(catalog=catalog).run(limit=1)
        print("worker", run.to_dict(), "seconds", round(time.time() - started, 2), flush=True)
    with sqlite3.connect(catalog.db_path) as connection:
        row = connection.execute(
            "SELECT result_json FROM analysis_jobs WHERE status='success' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise RuntimeError("正式分析工作器没有成功结果")
    data = json.loads(row[0])
    summary = {
        "vision_model": data["vision"]["model"],
        "captions": len(data["vision"]["captions"]),
        "vision_error": data["vision"]["error"],
        "speech_model": data["speech"]["model"],
        "has_speech": data["speech"]["has_speech"],
        "speech_error": data["speech"]["error"],
        "objects": data["objects"]["detections"],
        "object_error": data["objects"]["error"],
        "eligible": data["selection"]["eligible_for_auto_edit"],
        "category": data["category_resolution"]["category"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
