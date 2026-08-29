# -*- coding: utf-8 -*-
"""Stage 2.1 — Fresh18 独立验证评分（AI_LOCK vs Human Fresh Truth）。

在 Human Fresh18 完成后运行。指标（Gate §33-35）：
  SUPPORTED_TRUE / SUPPORTED_OVERCONFIDENT / SUPPORTED_FALSE / SUPPORTED_HUMAN_UNKNOWN
  supported_precision_clear / hard_false_rate / supported_insufficiency_rate
  SUPPORTED_COVERAGE / ACTIONABLE_CLAIM_COVERAGE / CLAIM_ABSTENTION_RATE
  CANDIDATE acceptance / WEAK behavior / UNKNOWN behavior
  Negative Rule violation / Storage-specific raw counts
  Confidence calibration：SUPPORTED 应明显比 CANDIDATE/WEAK 更强
Small-N 纪律：只报 raw counts，不称生产级准确率。
"""
import io
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
AI_LOCK = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_FRESH_V1_AI_LOCK.json")
FRESH = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_FRESH_VALIDATION_V1.json")
OUT = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_FRESH_V1_SCORE.json")


def main():
    ai = json.load(open(AI_LOCK, encoding="utf-8"))
    fresh = json.load(open(FRESH, encoding="utf-8"))
    ai_by_sid = {r["segment_id"]: r for r in ai["results"]}
    fresh_ids = [s["segment_id"] for s in fresh["segments"]]

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    human = {}
    try:
        for r in conn.execute("SELECT * FROM stage2_business_cognition_calibration_v3"):
            human[r["segment_id"]] = dict(r)
    except sqlite3.OperationalError:
        pass
    conn.close()

    done = [s for s in fresh_ids if s in human]
    print(f"Fresh18: {len(done)}/{len(fresh_ids)} 已审")
    if not done:
        print("尚未有 Fresh18 人工评审结果。")
        return

    # ---- SUPPORTED claims 评估 ----
    stats = Counter()
    per_label = Counter()
    n_supported_claims = 0
    n_candidate = 0
    n_weak = 0
    n_unknown_claims = 0
    storage_stats = Counter()
    for sid in done:
        a = ai_by_sid[sid]
        labels = json.loads(human[sid]["label_states"] or "{}")
        for c in a["business_claims"]:
            val, status = c["claim_value"], c["claim_status"]
            hv = labels.get(val, "UNKNOWN")
            if status == "SUPPORTED":
                n_supported_claims += 1
                per_label[val] += 1
                if val in ("STORAGE", "STORAGE_EFFICIENCY"):
                    storage_stats[hv] += 1
                if hv == "CLEARLY_SUPPORTED":
                    stats["SUPPORTED_TRUE"] += 1
                elif hv == "POSSIBLE_BUT_INSUFFICIENT":
                    stats["SUPPORTED_OVERCONFIDENT"] += 1
                elif hv == "NOT_SUPPORTED":
                    stats["SUPPORTED_FALSE"] += 1
                elif hv == "UNKNOWN":
                    stats["SUPPORTED_HUMAN_UNKNOWN"] += 1
            elif status == "CANDIDATE":
                n_candidate += 1
                if hv in ("CLEARLY_SUPPORTED", "POSSIBLE_BUT_INSUFFICIENT"):
                    stats["CANDIDATE_ACCEPTED"] += 1
                elif hv == "NOT_SUPPORTED":
                    stats["CANDIDATE_REJECTED"] += 1
                else:
                    stats["CANDIDATE_UNKNOWN"] += 1
            elif status == "WEAK":
                n_weak += 1
                if hv in ("CLEARLY_SUPPORTED", "POSSIBLE_BUT_INSUFFICIENT"):
                    stats["WEAK_SUPPORTED_BY_HUMAN"] += 1
            elif status == "UNKNOWN":
                n_unknown_claims += 1

    n_judged = stats["SUPPORTED_TRUE"] + stats["SUPPORTED_OVERCONFIDENT"] + stats["SUPPORTED_FALSE"]
    prec = stats["SUPPORTED_TRUE"] / n_judged if n_judged else 0.0
    hard_false = stats["SUPPORTED_FALSE"] / n_judged if n_judged else 0.0
    insuff = (stats["SUPPORTED_FALSE"] + stats["SUPPORTED_OVERCONFIDENT"]) / n_judged if n_judged else 0.0

    # 覆盖率指标
    total_claims = n_supported_claims + n_candidate + n_weak + n_unknown_claims
    supported_coverage = n_supported_claims / total_claims if total_claims else 0.0
    actionable = n_supported_claims + n_candidate
    actionable_coverage = actionable / total_claims if total_claims else 0.0
    abstention = n_unknown_claims / total_claims if total_claims else 0.0

    print(f"\n===== Fresh18 独立验证评分（{len(done)} 条）=====")
    print(f"SUPPORTED_TRUE={stats['SUPPORTED_TRUE']} | OVERCONF={stats['SUPPORTED_OVERCONFIDENT']} "
          f"| FALSE={stats['SUPPORTED_FALSE']} | UNKNOWN={stats['SUPPORTED_HUMAN_UNKNOWN']}")
    print(f"supported_precision_clear={prec:.3f} | hard_false_rate={hard_false:.3f} "
          f"| insufficiency_rate={insuff:.3f}")
    print(f"SUPPORTED claims={n_supported_claims} | CANDIDATE={n_candidate} | WEAK={n_weak} | UNKNOWN={n_unknown_claims}")
    print(f"SUPPORTED_COVERAGE={supported_coverage:.3f} | ACTIONABLE={actionable_coverage:.3f} "
          f"| ABSTENTION={abstention:.3f}")
    print(f"CANDIDATE: accepted={stats['CANDIDATE_ACCEPTED']} rejected={stats['CANDIDATE_REJECTED']} "
          f"unknown={stats['CANDIDATE_UNKNOWN']}")
    print(f"Storage SUPPORTED claims 的 Human 判定: {dict(storage_stats)}")

    out = {"manifest": "BUSINESS_COGNITION_FRESH_V1_SCORE",
           "reviewed": len(done), "total": len(fresh_ids),
           "supported": dict(stats),
           "supported_precision_clear": round(prec, 4),
           "hard_false_rate": round(hard_false, 4),
           "supported_insufficiency_rate": round(insuff, 4),
           "coverage": {"supported": round(supported_coverage, 4),
                        "actionable": round(actionable_coverage, 4),
                        "abstention": round(abstention, 4)},
           "counts": {"supported": n_supported_claims, "candidate": n_candidate,
                      "weak": n_weak, "unknown": n_unknown_claims},
           "candidate_outcomes": {k: v for k, v in stats.items() if k.startswith("CANDIDATE")},
           "storage_supported_human": dict(storage_stats),
           "per_label_supported_count": dict(per_label),
           "guard": "MINI INDEPENDENT VALIDATION (N=18); Small-N: raw counts 不得称生产级准确率"}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
