# -*- coding: utf-8 -*-
"""Stage 3A — PHASE4_STAGE2_FINAL_FREEZE.json（Stage2 正式冻结）。"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
OUT = os.path.join(DATA_ROOT, "PHASE4_STAGE2_FINAL_FREEZE.json")


def main():
    freeze = {
        "manifest": "PHASE4_STAGE2_FINAL_FREEZE",
        "frozen_at": "2026-08-30",
        "verdict": "PHASE4_STAGE2_PASS_WITH_LIMITATIONS",
        "stage3_ready": True,
        "engine_version": "BusinessCognitionV2_1 (Candidate)",
        "rule_version": "STAGE2_1_GATES_V1 (EvidenceStrengthV2 + Storage/Power Gate + UtteranceContext + ConflictResolverV2)",
        "knowledge_snapshot": {
            "id": "KNOWLEDGE_SNAPSHOT_V1_2",
            "sha256": "a9ac59f60e13a0bc8bb6949f99884202d3e3e3872d7c3c153e09cc00b5e79eec",
        },
        "fresh18_ai_lock": {
            "file": "BUSINESS_COGNITION_FRESH_V1_AI_LOCK.json",
            "sha256": "818f8d61c44c427d0ff5810721bb856044bc9f0daeedcea3e4712f33237b6acf",
        },
        "fresh18_human_truth": {
            "version": "HUMAN_FRESH18_V1",
            "table": "stage2_business_cognition_calibration_v3",
            "count": 18,
            "blind": True,
        },
        "v3_calibration": {
            "verdict": "CALIBRATION_TRUTH_RELIABLE",
            "scope": "AI_OUTPUT_VOCABULARY_V1 (10 labels)",
        },
        "final_metrics_fresh18": {
            "supported_true": 13, "supported_overconfident": 2, "supported_false": 2,
            "supported_human_unknown": 0, "supported_effective": 17,
            "supported_precision_clear": 0.765,
            "hard_false_rate": 0.118,
            "supported_insufficiency_rate": 0.235,
            "storage_subset_precision": 1.000,
            "non_storage_subset_precision": 0.667,
            "negative_rule_hard_violation": 0,
            "conflict_hypothetical_false_positive": 0,
        },
        "known_limitations": [
            {"id": "LIM-01", "desc": "SUPPORTED 与 CANDIDATE 分界偏保守（CANDIDATE 9/9 被 Human 认可）；"
                                     "Confidence Separation 尚未校准好", "scope": "confidence_calibration"},
            {"id": "LIM-02", "desc": "STORAGE_EFFICIENCY 从过度外推转为部分过度保守（0 SUPPORTED 但 Human 13 CLEARLY）",
             "scope": "storage_efficiency_gate"},
            {"id": "LIM-03", "desc": "DINING/DINING_CONVENIENCE 2 FALSE（有 DINING function 但镜头讲充电/火锅）；"
                                     "标 LIMITED_CONTEXT_VALIDATION", "scope": "dining_gate"},
            {"id": "LIM-04", "desc": "ConflictResolverV2 = STRUCTURALLY_VALIDATED / LIMITED_FRESH_HUMAN_EVIDENCE"
                                     "（Fresh18 CONFLICT 样本多为动作↔组件不匹配，'如果家里有宝宝'vs FACTORY 人审样本不足）",
             "scope": "conflict_resolver"},
            {"id": "LIM-05", "desc": "无结构化输入段（AMBIGUOUS/OTHER）业务认知覆盖为 0（非规则问题，输入域问题）",
             "scope": "coverage"},
            {"id": "LIM-06", "desc": "UNKNOWN = MISSING/INSUFFICIENT MACHINE COGNITION；绝不能解释为 FALSE/NOT_PRESENT",
             "scope": "semantics"},
        ],
        "commit": "59a2194",
        "guard": "Stage2 正式封版；不再追加人工审核；不因追求百分点继续调规则；"
                 "限制由 STAGE3_BUSINESS_COGNITION_CONSUMER_POLICY_V1 消费",
    }
    json.dump(freeze, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
