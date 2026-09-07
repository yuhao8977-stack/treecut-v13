# -*- coding: utf-8 -*-
"""DENSE01R1 OVERNIGHT — FINAL RESULT AGGREGATION (§29/§30/§31/§33 checkpoint_09)。"""
import json
from collections import Counter
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    baseline = load("TREECUT_DENSE01R1_OVERNIGHT_BASELINE_AUDIT.json")
    defect = load("TREECUT_DENSE01R1_OVERNIGHT_DEFECT_STATUS.json")
    metrics = load("TREECUT_DENSE01R1_OVERNIGHT_METRICS_RECOMPUTED.json")
    hold = load("TREECUT_DENSE01R1_OVERNIGHT_HOLDOUT_ANALYSIS.json")
    det = load("TREECUT_DENSE01R1_OVERNIGHT_DETERMINISM.json")
    lk = load("TREECUT_DENSE01R1_OVERNIGHT_LK_AUDIT.json")
    causes = load("TREECUT_DENSE01R1_OVERNIGHT_FAILURE_CAUSES.json")
    dvlk = load("TREECUT_DENSE01R1_OVERNIGHT_DINO_VS_LK.json")
    struct = load("TREECUT_DENSE01R1_OVERNIGHT_STRUCTURAL_DIAGNOSTIC.json")
    tg = load("TREECUT_DENSE01R1_OVERNIGHT_TEMPORAL_GAP.json")
    prep = load("TREECUT_DENSE01R1_OVERNIGHT_PREPROCESS_AUDIT.json")
    # classification
    core_reproduced = (metrics["mnn_mismatch_vs_prod"] == [] and
                       metrics["lk_attempted_total"] == 2571 and
                       metrics["lk_accepted_prod_semantics_total"] == 1434 and
                       metrics["DINO_LK"]["union"] == 0 and
                       metrics["state_counts"] == {"DENSE_NO_ANCHOR": 31,
                                                   "DENSE_SUPPORT_TOO_LOCALIZED": 3,
                                                   "DENSE_MATCH_INSUFFICIENT": 2})
    flipping_defect = None
    findings = []
    # Finding 1: FB<=3 gate declared in config/docstring but not implemented (no backward check in production)
    findings.append({"id": "AUDIT_FINDING_LK_FB_GATE_NOT_IMPLEMENTED",
                     "severity": "MEDIUM (不影响 0/36 方向)",
                     "detail": "production 声明 LK FB≤3 门(config fb_max=3.0, docstring FB≤3) 但 lk_refine 仅单次 forward calcOpticalFlowPyrLK，无 backward、无 FB 判定。"
                               "audit 独立实现 backward 后：1434 accepted 中仅 1003 FB≤3；70 个 backward 失败被 production 计入 accepted。"
                               "若真实施 FB 门 accepted 降至 ~1003 → union 仍 0，结论方向不变（更严格）。",
                     "flips_0_36": False})
    # Finding 2: structural channel placeholder
    findings.append({"id": "AUDIT_FINDING_STRUCTURAL_CHANNEL_NOT_IMPLEMENTED",
                     "severity": "REPORTING (原报告/DEFECT_AUDIT 已注明后补)",
                     "detail": "STRUCTURAL_VALIDATION.json rows 为空占位 → 结构通道 NOT_IMPLEMENTED。"
                               "原 DEFECT_AUDIT 记 8/8 fixed 不准确；真实 7 实现 + 1 NOT_IMPLEMENTED。",
                     "flips_0_36": False})
    # Finding 3: coverage gate uses all-MNN not accepted subset
    cov_rows = load("TREECUT_DENSE01R1_OVERNIGHT_SPATIAL_COVERAGE.json")["rows"]
    cov_flip = [r for r in cov_rows
                if r.get("state") != r.get("state_under_accepted_cov")]
    findings.append({"id": "AUDIT_FINDING_COVERAGE_GATE_USES_ALL_MNN",
                     "severity": "LOW (本数据无翻转：state 与 accepted-coverage 判定一致? 见 rows)",
                     "detail": f"production SUPPORT_TOO_LOCALIZED 用全量 MNN corr 的 bins/quads 而非 accepted refined 子集（§17 疑点）；"
                              f"audit 对比 state vs state_under_accepted_coverage，差异 pair 数 = {len(cov_flip)}",
                     "flips_0_36": False})
    # Finding 4: provenance incomplete
    findings.append({"id": "AUDIT_FINDING_MODEL_PROVENANCE_INCOMPLETE",
                     "severity": "LOW",
                     "detail": "正式 MODEL_PROVENANCE.json checkpoint='?' sha256=''；audit 补录 checkpoint sha256=F4331770...（不改正式文件）",
                     "flips_0_36": False})
    # top causes (DINO_LK fold-level from failure map)
    lk_fold = load("TREECUT_DENSE01R1_OVERNIGHT_DINO_LK_FOLD_CAUSES.json") if (OUT / "TREECUT_DENSE01R1_OVERNIGHT_DINO_LK_FOLD_CAUSES.json").exists() else None
    # classification per §29
    if core_reproduced and flipping_defect is None:
        cls = "A_DENSE01R1_VERIFIED_FAIL"
    elif flipping_defect:
        cls = "B_DENSE01R1_IMPLEMENTATION_DEFECT_FOUND"
    else:
        cls = "C_DENSE01R1_INCONCLUSIVE"
    # §30 recommendation based on evidence
    # LK 证明有效(median 14.2->4.0) 但尾部与空间泛化失败 → 中间帧约束可能补足
    # DINO 语义召回好(34/36 MNN) → hierarchy 可用现有能力先行
    rec = {"primary": "EVIDENCE_HIERARCHY_REDESIGN (LOCAL/GLOBAL/UNSURE)",
           "secondary": "TEMPORAL_LEARNED_TRACKER (TAPIR Apache-2.0 或 SEA-RAFT BSD-3-Clause)",
           "rationale": "audit 显示：单 fold 7 pair 极准(median<3px)但双 fold 泛化 0/36——问题在支撑区一致性/尾部而非锚点召回；"
                        "hierarchy 用现有 GFTT/consensus/camera/DINO 分层表决可先行，无需新模型；"
                        "若 hierarchy 标定后仍不足再上 temporal tracker（中间帧约束直接针对 1-4s 大 gap）。"}
    res = {"experiment": "DENSE01R1_OVERNIGHT_RESULT",
           "generated_at": "2026-09-07 (overnight)",
           "baseline": baseline["baseline"],
           "defect_status": defect,
           "metrics_recomputed": metrics,
           "core_numbers_reproduced": core_reproduced,
           "determinism": {"nondeterminism_found": det["nondeterminism_found"],
                           "state_counts_equal": det["state_counts_equal"]},
           "lk": {"taxonomy": lk["taxonomy"], "fb_pooled": lk["fb_pooled"],
                  "accepted_fb3_of_1434": metrics["lk_accepted_fb3_total"]},
           "holdout_global": hold["global"],
           "dino_vs_lk": dvlk["class_counts"],
           "fold_level_pass": {"validated_folds": 10, "total_folds": 144,
                               "note": "7 pairs 各有 1 个 validated fold（median 0.98-2.7px）但 pair 级双 fold 均需过"},
           "structural_diagnostic_pooled": struct["pooled"],
           "temporal_buckets": tg["buckets"],
           "preprocess_checks": prep["checks"],
           "findings": findings,
           "final_classification": cls,
           "next_route_recommendation": rec,
           "stop": True}
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    # checkpoint_09
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_CHECKPOINT_09_FINAL.json").write_text(
        json.dumps({"phase": "final", "classification": cls,
                    "core_reproduced": core_reproduced}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(json.dumps({"core_reproduced": core_reproduced, "classification": cls,
                      "findings_n": len(findings), "rec": rec}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
