#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Overnight P3 — NON_HOLDOUT_BENCHMARK_POOL（只读，分层抽样）。

池 = G1 eligible mp4（X1 素材） − excluded_known_ids（A1/A2/A3/Known/
review-memory/rule-design 全集）。产出全池统计 + 固定种子分层样本(≤300)，
仅 CANDIDATE 召回元数据（非动作真值）。
"""
import json
import random
import sys
import time
from pathlib import Path

import sqlite3

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
EXCLUDED_FILE = OUT / "TREECUT_MMVV_A3_CANDIDATES.json"
sys.stdout.reconfigure(encoding="utf-8")

SEED = 20260905
SAMPLE_TARGET = 300


def main():
    excl = json.loads(EXCLUDED_FILE.read_text(encoding="utf-8"))["excluded_known_ids"]
    excl_set = {int(x) for x in excl}
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    rows = cur.execute("""
        SELECT mf.id, mf.relative_path, a.duration, a.width, a.height
        FROM media_files mf
        JOIN b007_source_role_v1 r ON r.entity_id = mf.id AND r.entity_kind='media_file'
        LEFT JOIN assets a ON a.media_id = mf.id
        WHERE mf.extension='.mp4'
          AND r.source_role IN ('PRODUCTION_CLEAN_RAW','PRODUCTION_CLEAN_SEMI')
          AND r.review_status!='REJECTED'
          AND (r.review_status='APPROVED'
               OR (r.burned_subtitle_present!='PRESENT' AND r.platform_watermark_present!='PRESENT'
                   AND r.old_title_overlay_present!='PRESENT' AND r.brand_overlay_present!='PRESENT'
                   AND r.unrelated_overlay_present!='PRESENT'
                   AND r.burned_subtitle_present!='UNCERTAIN' AND r.platform_watermark_present!='UNCERTAIN'
                   AND r.old_title_overlay_present!='UNCERTAIN' AND r.brand_overlay_present!='UNCERTAIN'
                   AND r.unrelated_overlay_present!='UNCERTAIN'))
    """).fetchall()
    pool = [{"media_id": rid, "path": rel, "category": (rel.split("\\")[0] if "\\" in rel else "?"),
             "duration_s": dur, "width": w, "height": h}
            for rid, rel, dur, w, h in rows if rid not in excl_set]
    n = len(pool)
    from collections import Counter
    cat = Counter(p["category"] for p in pool)
    dur_stats = [p["duration_s"] for p in pool if p["duration_s"]]
    rnd = random.Random(SEED)
    # 分层：每类取比例配额
    sample = []
    per_cat = {c: max(1, int(SAMPLE_TARGET * k / n)) for c, k in cat.most_common()}
    for c, quota in per_cat.items():
        members = [p for p in pool if p["category"] == c]
        rnd.shuffle(members)
        sample.extend(members[:quota])
    rnd.shuffle(sample)
    sample = sample[:SAMPLE_TARGET]
    doc = {
        "experiment": "NON_HOLDOUT_BENCHMARK_POOL",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seed": SEED, "sample_target": SAMPLE_TARGET,
        "note": "仅召回候选元数据，非动作真值；已排除 excluded_known_ids(A1/A2/A3/Known/review-memory/rule-design)；A3 6 案例不在池内",
        "pool_size": n,
        "excluded_known_count": len(excl_set),
        "category_distribution": dict(cat.most_common(20)),
        "duration_min_max": [round(min(dur_stats), 2), round(max(dur_stats), 2)] if dur_stats else None,
        "duration_median": round(sorted(dur_stats)[len(dur_stats) // 2], 2) if dur_stats else None,
        "sample_size": len(sample),
        "sample": [{"media_id": p["media_id"], "category": p["category"],
                    "duration_s": p["duration_s"], "w": p["width"], "h": p["height"]}
                   for p in sample],
    }
    out = OUT / "TREECUT_OVERNIGHT_NON_HOLDOUT_BENCHMARK_POOL_V1.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("pool_size:", n, "sample:", len(sample))
    print("top categories:", list(cat.most_common(8)))
    print("WROTE", out)
    con.close()


if __name__ == "__main__":
    main()
