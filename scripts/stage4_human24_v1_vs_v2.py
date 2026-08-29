# -*- coding: utf-8 -*-
"""Stage 2 — Human24 Adjudication V2 vs V1 比较（Truth Reliability Gate 判定）。

只比较 Human V1（stage2_business_cognition_review_v1）与
Human V2（stage2_business_cognition_adjudication_v2）的 12 条重合段。
不修改 AI。

输出：
  agreement_rate（多标签 set 级）
  per-field agreement
  label additions（V2 新增）
  label removals（V2 移除）
  high-impact disagreement（V1 有 V2 无 / V1 无 V2 有 的 needs+values）
  confidence distribution（review_confidence + 时长诊断）
  verdict：ADJUDICATED_HUMAN_TRUTH / UNRELIABLE_FOR_CALIBRATION
"""
import io
import json
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
V2_MANIFEST = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_HUMAN_ADJUDICATION_V2.json")
OUT = os.path.join(DATA_ROOT, "HUMAN24_V1_VS_V2_COMPARISON.json")

SET_FIELDS = ["user_needs", "business_values", "decision_factors", "trust_signals",
              "search_intents", "shot_functions"]
# 高影响判定只关心 needs+values（业务核心 claims）
HIGH_IMPACT_FIELDS = ["user_needs", "business_values"]


def _jlist(v):
    if isinstance(v, list):
        return v
    try:
        x = json.loads(v) if v else []
        return x if isinstance(x, list) else []
    except Exception:
        return []


def main():
    man = json.load(open(V2_MANIFEST, encoding="utf-8"))
    v2_ids = [s["segment_id"] for s in man["segments"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    v1 = {}
    for r in conn.execute("SELECT * FROM stage2_business_cognition_review_v1"):
        v1[r["segment_id"]] = dict(r)
    v2 = {}
    try:
        for r in conn.execute("SELECT * FROM stage2_business_cognition_adjudication_v2"):
            v2[r["segment_id"]] = dict(r)
    except sqlite3.OperationalError:
        pass
    conn.close()

    done = [s for s in v2_ids if s in v2]
    print(f"V2 已审 {len(done)}/{len(v2_ids)}")
    if not done:
        print("尚未有 V2 评审结果。")
        return

    # ---------------- 逐条比较 ----------------
    per_seg = []
    total_set = 0          # 参与 set agreement 的 (字段,标签) 对
    total_agree = 0
    high_impact_diff = []  # needs+values 级分歧明细
    label_add = []         # V2 新增
    label_rm = []          # V2 移除
    conf_dist = {}

    for sid in done:
        h1, h2 = v1[sid], v2[sid]
        row = {"segment_id": sid}
        for fld in SET_FIELDS:
            s1 = set(_jlist(h1.get(fld)))
            s2 = set(_jlist(h2.get(fld)))
            agree = s1 == s2
            row[f"{fld}_agree"] = agree
            row[f"{fld}_v1"] = sorted(s1)
            row[f"{fld}_v2"] = sorted(s2)
            if fld in HIGH_IMPACT_FIELDS:
                for x in (s1 - s2):
                    high_impact_diff.append({"segment_id": sid, "field": fld,
                                             "label": x, "dir": "V1_only"})
                    label_rm.append({"segment_id": sid, "field": fld, "label": x})
                for x in (s2 - s1):
                    high_impact_diff.append({"segment_id": sid, "field": fld,
                                             "label": x, "dir": "V2_only"})
                    label_add.append({"segment_id": sid, "field": fld, "label": x})
            # set 级 agreement（逐 label 计数）
            for x in (s1 | s2):
                total_set += 1
                if x in s1 and x in s2:
                    total_agree += 1
        # 冲突观察一致性
        row["conflict_v1"] = h1.get("conflict_observed", "")
        row["conflict_v2"] = h2.get("conflict_observed", "")
        row["overall_unknown_v1"] = h1.get("overall_unknown", "")
        row["overall_unknown_v2"] = h2.get("overall_unknown", "")
        row["review_confidence"] = h2.get("review_confidence", "")
        row["review_duration_seconds"] = h2.get("review_duration_seconds")
        row["review_status_v2"] = h2.get("review_status", "")
        conf_dist[row["review_confidence"]] = conf_dist.get(row["review_confidence"], 0) + 1
        per_seg.append(row)

    agreement_rate = total_agree / total_set if total_set else 0.0
    # 高影响一致率：needs+values 逐 label
    hi_total = sum(len(set(row[f"{f}_v1"]) | set(row[f"{f}_v2"])) for row in per_seg for f in HIGH_IMPACT_FIELDS)
    hi_agree = sum(len(set(row[f"{f}_v1"]) & set(row[f"{f}_v2"])) for row in per_seg for f in HIGH_IMPACT_FIELDS)
    hi_rate = hi_agree / hi_total if hi_total else 1.0

    # per-field agreement
    per_field = {}
    for fld in SET_FIELDS:
        n = sum(1 for r in per_seg if r[f"{fld}_agree"])
        per_field[fld] = {"exact_match_segments": n, "segments": len(per_seg)}

    # 判定
    verdict = "ADJUDICATED_HUMAN_TRUTH" if hi_rate >= 0.85 else "UNRELIABLE_FOR_CALIBRATION"

    print(f"\n===== V1 vs V2（{len(done)} 条）=====")
    print(f"set agreement_rate = {agreement_rate:.3f} ({total_agree}/{total_set})")
    print(f"needs+values 高影响一致率 = {hi_rate:.3f} ({hi_agree}/{hi_total})")
    print(f"高影响分歧明细 {len(high_impact_diff)} 条:")
    for d in high_impact_diff[:20]:
        print(f"  {d['segment_id'][:12]} {d['field']} {d['label']} ({d['dir']})")
    print("label additions:", len(label_add), "| label removals:", len(label_rm))
    print("review_confidence 分布:", conf_dist)
    print(f"\n判定: {verdict}")

    out = {
        "manifest": "HUMAN24_V1_VS_V2_COMPARISON",
        "reviewed": len(done), "total": len(v2_ids),
        "agreement_rate": round(agreement_rate, 4),
        "high_impact_agreement_rate": round(hi_rate, 4),
        "per_field_agreement": per_field,
        "high_impact_disagreements": high_impact_diff,
        "label_additions": label_add,
        "label_removals": label_rm,
        "confidence_distribution": conf_dist,
        "verdict": verdict,
        "per_segment": per_seg,
        "guard": "仅比较 Human V1 vs V2；不修改 AI；"
                 "高一致(≥0.85)→ADJUDICATED_HUMAN_TRUTH；否则→UNRELIABLE_FOR_CALIBRATION",
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
