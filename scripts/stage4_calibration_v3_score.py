# -*- coding: utf-8 -*-
"""Stage 2 — Human Calibration V3 评分（AI SUPPORTED claims vs V3 单状态 Human Truth）。

只校准当前引擎可输出的 10 标签。

V3 评分语义（Gate §16）：
  Human CLEARLY_SUPPORTED + AI SUPPORTED → TP（SUPPORTED_TRUE）
  Human POSSIBLE_BUT_INSUFFICIENT + AI SUPPORTED → OVERCONFIDENT_CLAIM（不是 TP）
  Human NOT_SUPPORTED + AI SUPPORTED → FP（SUPPORTED_FALSE）
  Human UNKNOWN + AI SUPPORTED → SUPPORTED_HUMAN_UNKNOWN（不进 Precision denominator 硬对错）

指标：
  supported_precision_clear = TRUE / (TRUE + OVERCONFIDENT + FALSE)
  overconfidence_rate = OVERCONFIDENT / (TRUE + OVERCONFIDENT + FALSE)
  false_claim_rate = FALSE / (TRUE + OVERCONFIDENT + FALSE)
  每 label 结果。

V1 vs V3 比较（V2 仅 UI_FAILURE_DIAGNOSTIC）：
  V1 标签 → V3 CLEARLY / POSSIBLE / NOT_SUPPORTED / UNKNOWN
  原 6 个 needs+values FP 逐项 V3 最终状态（search_intent = NOT_REVIEWED）。
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
AI_LOCK = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_AI_LOCK.json")
V3_MANIFEST = os.path.join(DATA_ROOT, "HUMAN_CALIBRATION_V3_MANIFEST.json")
TAXONOMY = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_CALIBRATION_TAXONOMY_V1.json")
OUT = os.path.join(DATA_ROOT, "HUMAN_CALIBRATION_V3_SCORE.json")

# 原 6 个 needs+values FP（V1 评分中 AI 主张 Human 未勾）
ORIG_FP = [
    ("d780c9edafef4687aa70f291db884145", "STORAGE"),
    ("40d5fdbe96cb44d3a8e9c2024f80712e", "STORAGE"),
    ("40d5fdbe96cb44d3a8e9c2024f80712e", "STORAGE_EFFICIENCY"),
    ("a1223854e64f479db797a42114e3ace2", "CHARGING_POWER"),
    ("80f182c8a51346e39c87fa66f43ff970", "POWER_CONVENIENCE"),
    ("bf686b31816e47b6a2fad191b62f4890", "STORAGE_EFFICIENCY"),
]


def main():
    ai = json.load(open(AI_LOCK, encoding="utf-8"))
    man = json.load(open(V3_MANIFEST, encoding="utf-8"))
    tax = json.load(open(TAXONOMY, encoding="utf-8"))
    ai_by_sid = {r["segment_id"]: r for r in ai["results"]}
    v3_ids = [s["segment_id"] for s in man["segments"]]

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    v3 = {}
    try:
        for r in conn.execute("SELECT * FROM stage2_business_cognition_calibration_v3"):
            v3[r["segment_id"]] = dict(r)
    except sqlite3.OperationalError:
        pass
    # V1 表（供 V1 vs V3 比较）
    v1 = {}
    for r in conn.execute("SELECT * FROM stage2_business_cognition_review_v1"):
        v1[r["segment_id"]] = dict(r)
    conn.close()

    done = [s for s in v3_ids if s in v3]
    print(f"V3 已审 {len(done)}/{len(v3_ids)}")
    if not done:
        print("尚未有 V3 评审结果。")
        return

    # ---------------- V3 评分（AI SUPPORTED vs V3 状态） ----------------
    # AI 的 SUPPORTED claims（needs+values，合并；仅校准 10 标签域）
    stats = Counter()
    per_label = {label: Counter() for label in
                 [n["id"] for n in tax["user_needs"]] +
                 [v["id"] for v in tax["business_values"]]}
    ai_claims_seen = Counter()  # 校准域内 AI 实际主张数

    for sid in done:
        a = ai_by_sid[sid]
        ai_supported = set(a["user_needs"]) | set(a["business_values"])
        labels = json.loads(v3[sid]["label_states"] or "{}")
        for label, state in labels.items():
            ai_claimed = label in ai_supported
            if not ai_claimed:
                continue
            ai_claims_seen[label] += 1
            if state == "CLEARLY_SUPPORTED":
                stats["SUPPORTED_TRUE"] += 1
                per_label[label]["TRUE"] += 1
            elif state == "POSSIBLE_BUT_INSUFFICIENT":
                stats["SUPPORTED_OVERCONFIDENT"] += 1
                per_label[label]["OVERCONFIDENT"] += 1
            elif state == "NOT_SUPPORTED":
                stats["SUPPORTED_FALSE"] += 1
                per_label[label]["FALSE"] += 1
            elif state == "UNKNOWN":
                stats["SUPPORTED_HUMAN_UNKNOWN"] += 1
                per_label[label]["HUMAN_UNKNOWN"] += 1

    n_judged = stats["SUPPORTED_TRUE"] + stats["SUPPORTED_OVERCONFIDENT"] + stats["SUPPORTED_FALSE"]
    prec = stats["SUPPORTED_TRUE"] / n_judged if n_judged else 0.0
    ocr = stats["SUPPORTED_OVERCONFIDENT"] / n_judged if n_judged else 0.0
    fcr = stats["SUPPORTED_FALSE"] / n_judged if n_judged else 0.0

    print("\n===== V3 Calibration 评分 =====")
    print(f"SUPPORTED_TRUE={stats['SUPPORTED_TRUE']} | "
          f"SUPPORTED_OVERCONFIDENT={stats['SUPPORTED_OVERCONFIDENT']} | "
          f"SUPPORTED_FALSE={stats['SUPPORTED_FALSE']} | "
          f"SUPPORTED_HUMAN_UNKNOWN={stats['SUPPORTED_HUMAN_UNKNOWN']}")
    print(f"supported_precision_clear={prec:.3f} | "
          f"overconfidence_rate={ocr:.3f} | false_claim_rate={fcr:.3f}")
    print("\n每 label（AI 主张数 / TRUE / OVERCONF / FALSE / UNKNOWN）：")
    for label, c in per_label.items():
        print(f"  {label}: claims={ai_claims_seen[label]} T={c['TRUE']} O={c['OVERCONFIDENT']} "
              f"F={c['FALSE']} U={c['HUMAN_UNKNOWN']}")

    # ---------------- V1 vs V3（V1 标签 → V3 状态） ----------------
    v1_to_v3 = Counter()
    v1_checked = 0
    for sid in done:
        h1 = v1.get(sid)
        if not h1:
            continue
        v1_labels = set(json.loads(h1.get("user_needs") or "[]")) | \
                     set(json.loads(h1.get("business_values") or "[]"))
        labels = json.loads(v3[sid]["label_states"] or "{}")
        for lab in v1_labels:
            if lab not in labels:
                continue  # 非校准域（如 AESTHETICS）不计
            v1_checked += 1
            v1_to_v3[labels[lab]] += 1
    print("\n===== V1 → V3（V1 标签在 V3 中的状态，仅校准域）=====")
    print(f"  V1 标签数(校准域)={v1_checked}: CLEARLY={v1_to_v3['CLEARLY_SUPPORTED']} "
          f"POSSIBLE={v1_to_v3['POSSIBLE_BUT_INSUFFICIENT']} "
          f"NOT_SUPPORTED={v1_to_v3['NOT_SUPPORTED']} UNKNOWN={v1_to_v3['UNKNOWN']}")

    # ---------------- 原 6 FP 重判 ----------------
    print("\n===== 原 6 FP 的 V3 最终状态 =====")
    fp_results = []
    for sid, label in ORIG_FP:
        if sid not in v3:
            fp_results.append({"segment_id": sid[:12], "label": label, "state": "NO_V3"})
            print(f"  {sid[:12]} {label}: NO_V3")
            continue
        labels = json.loads(v3[sid]["label_states"] or "{}")
        st = labels.get(label, "NOT_REVIEWED")
        fp_results.append({"segment_id": sid[:12], "label": label, "state": st})
        print(f"  {sid[:12]} {label}: {st}")

    # ---------------- evidence / confidence / duration ----------------
    ev = Counter(v3[s]["evidence_sufficiency"] for s in done)
    cf = Counter(v3[s]["conflict_observed"] for s in done)
    rc = Counter(v3[s]["review_confidence"] for s in done)
    durs = [v3[s]["review_duration_seconds"] or 0 for s in done]
    print("\n===== V3 质量诊断 =====")
    print(f"  evidence: {dict(ev)} | conflict: {dict(cf)} | confidence: {dict(rc)}")
    print(f"  duration min/avg/max: {round(min(durs),1)}/{round(sum(durs)/len(durs),1)}/{round(max(durs),1)}s")

    out = {
        "manifest": "HUMAN_CALIBRATION_V3_SCORE",
        "reviewed": len(done), "total": len(v3_ids),
        "scope": "AI_OUTPUT_VOCABULARY_V1（10 标签）",
        "supported": {"true": stats["SUPPORTED_TRUE"],
                      "overconfident": stats["SUPPORTED_OVERCONFIDENT"],
                      "false": stats["SUPPORTED_FALSE"],
                      "human_unknown": stats["SUPPORTED_HUMAN_UNKNOWN"]},
        "supported_precision_clear": round(prec, 4),
        "overconfidence_rate": round(ocr, 4),
        "false_claim_rate": round(fcr, 4),
        "per_label": {k: dict(v) for k, v in per_label.items()},
        "ai_claims_per_label": dict(ai_claims_seen),
        "v1_to_v3": dict(v1_to_v3),
        "v1_label_count_calibration_scope": v1_checked,
        "orig_fp_v3": fp_results,
        "evidence_distribution": dict(ev),
        "conflict_distribution": dict(cf),
        "confidence_distribution": dict(rc),
        "duration_stats": {"min": round(min(durs), 1), "avg": round(sum(durs) / len(durs), 1),
                           "max": round(max(durs), 1)},
        "guard": "V3 = 校准 Truth 候选；V2 = UI_FAILURE_DIAGNOSTIC；"
                 "仅校准当前引擎 10 标签；search_intent NOT_REVIEWED",
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
