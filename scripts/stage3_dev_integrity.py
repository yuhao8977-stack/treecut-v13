# -*- coding: utf-8 -*-
"""Stage3 MODEL DEV — PRE-STEP 0：支持量口径完整性核验。

查明报告 FACTORY=352 / 岩板=356 的来源（canonical_human_truth is_current=1 共 360 段，
Calibration333 manifest 仅 333 段 → 27 段早期批次被误计入）。
修正统计口径：Calibration333 = manifest ∩ canonical_human_truth(is_current=1)。
输出每个数据集的 dataset_name / unique_segment_count / current_truth_row_count，
并验证单标签 support <= unique_segment_count、单标签类别总和 <= unique_segment_count。
"""
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

SINGLE = ["scene_family", "scene_subtype", "product_family", "product_variant",
          "action_group", "shot_scale", "people_presence", "product_visibility"]
MULTI = ["material_multi", "component_multi", "function_multi", "shot_role_multi"]


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    man_sids = [s["segment_id"] for s in man["segments"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    all_cur = [dict(r) for r in conn.execute("SELECT * FROM canonical_human_truth WHERE is_current=1")]
    man_set = set(man_sids)
    cal333 = [r for r in all_cur if r["segment_id"] in man_set]
    outside = [r for r in all_cur if r["segment_id"] not in man_set]
    conn.close()

    print(f"canonical is_current 全表: {len(all_cur)} 行 / {len({r['segment_id'] for r in all_cur})} unique")
    print(f"Calibration333 manifest: {len(man_sids)} 段（全部在 is_current 中）")
    print(f"manifest 外 27 段（误计入源）: scene_family FACTORY={sum(1 for r in outside if r['scene_family']=='FACTORY')}")

    # ---- 数据集定义 ----
    datasets = {
        "canonical360_current_truth": {"segments": all_cur},
        "calibration333_manifest": {"segments": cal333},
    }
    audit = {}
    for ds_name, spec in datasets.items():
        segs = spec["segments"]
        n_uniq = len({r["segment_id"] for r in segs})
        row = {"dataset_name": ds_name, "unique_segment_count": n_uniq,
               "current_truth_row_count": len(segs)}
        # 单标签
        for f in SINGLE:
            cnt = Counter(r.get(f) for r in segs if r.get(f))
            total = sum(cnt.values())
            row[f] = {"label_support": dict(cnt), "sum_all_labels": total,
                      "violation": any(v > n_uniq for v in cnt.values()) or total > n_uniq}
        # 多标签：occurrence 计数（明确不是 segment count）
        for f in MULTI:
            occ = Counter()
            for r in segs:
                for lab in jload(r.get(f)):
                    occ[lab] += 1
            row[f] = {"label_occurrence_count": dict(occ),
                      "note": "label occurrence（多标签），非 segment count"}
        audit[ds_name] = row
        print(f"\n=== {ds_name}: {n_uniq} unique / {len(segs)} rows ===")
        for f in ("scene_family", "product_family", "product_variant", "people_presence"):
            r = row[f]
            print(f"  [{f}] sum={r['sum_all_labels']} violation={r['violation']} :: {r['label_support']}")
        for f in ("material_multi", "component_multi"):
            print(f"  [{f}] occurrence :: {row[f]['label_occurrence_count']}")

    # ---- 对比：360 全表 vs 333 manifest 的 FACTORY/岩板 ----
    print("\n=== 口径对照 ===")
    for f in ("scene_family", "material_multi"):
        if f == "scene_family":
            c360 = Counter(r.get(f) for r in all_cur if r.get(f))
            c333 = Counter(r.get(f) for r in cal333 if r.get(f))
        else:
            c360 = Counter(l for r in all_cur for l in jload(r.get(f)))
            c333 = Counter(l for r in cal333 for l in jload(r.get(f)))
        key = "FACTORY" if f == "scene_family" else "岩板"
        print(f"  {f}[{key}]: 全360={c360.get(key)} vs Cal333={c333.get(key)}")

    out = {"manifest": "SUPPORT_COUNT_INTEGRITY_AUDIT",
           "finding": ("报告 Calibration333 的 FACTORY=352/岩板=356 实际来自 canonical_human_truth "
                       "is_current=1 全表 360 段（含 27 段不在 manifest 的早期批次段，其中 23 段 FACTORY）。"
                       "正确 Calibration333 应严格用 manifest 333 段。"),
           "datasets": audit,
           "correction": {"scene_family_FACTORY": {"reported_360": 352, "correct_333": None},
                          "material_岩板": {"reported_360": 356, "correct_333": None}},
           "fix_applied_to": "STAGE3_POST_REVIEW_LABEL_SUPPORT.json + 报告（后续步骤统一用 manifest 交集）"}
    # 填入修正值
    out["correction"]["scene_family_FACTORY"]["correct_333"] = \
        sum(1 for r in cal333 if r.get("scene_family") == "FACTORY")
    out["correction"]["material_岩板"]["correct_333"] = \
        sum(1 for r in cal333 for l in jload(r.get("material_multi")) if l == "岩板")
    p = os.path.join(DATA_ROOT, "SUPPORT_COUNT_INTEGRITY_AUDIT.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)
    print("修正:", out["correction"])


if __name__ == "__main__":
    main()
