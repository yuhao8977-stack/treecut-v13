# -*- coding: utf-8 -*-
"""Adjudication V2 schema 历史归档（Simplification Gate）。

旧 V2 schema（完整 Business Cognition Taxonomy 版）保留为历史；
新 V2b schema（简化版：needs/values 四态 + evidence/conflict）用于正式复核。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
OUT = os.path.join(DATA_ROOT, "ADJUDICATION_V2_SCHEMA_HISTORY.json")


def main():
    hist = {
        "manifest": "ADJUDICATION_V2_SCHEMA_HISTORY",
        "generated_at": "2026-08-29",
        "schema_versions": [
            {
                "version": "v2_full_taxonomy",
                "status": "SUPERSEDED_BY_v2b_simplified",
                "reason": "完整 Business Cognition Taxonomy 认知负担过高（~98 项/条）；"
                          "复核目的仅为验证 Human24 V1 的 needs/values/evidence/conflict 可靠性",
                "fields": ["user_needs", "business_values", "decision_factors",
                           "trust_signals", "search_intents", "shot_functions",
                           "role_affinity", "theme_affinity",
                           "overall_unknown", "conflict_observed", "comment",
                           "review_confidence", "review_duration_seconds",
                           "review_status"],
                "table": "stage2_business_cognition_adjudication_v2",
                "created": "2026-08-29 (Human Truth Reliability Gate)",
            },
            {
                "version": "v2b_simplified",
                "status": "CURRENT",
                "reason": "只复核影响 Stage2 判断的核心：user_needs/business_values/evidence/conflict；"
                          "区分 CLEARLY_SUPPORTED 与 POSSIBLE_BUT_INSUFFICIENT（解决'可联想 vs 足以证明'混淆）",
                "fields": [
                    "clearly_supported_needs", "possible_needs",
                    "clearly_supported_values", "possible_values",
                    "needs_field_unknown", "values_field_unknown",
                    "evidence_sufficiency", "conflict_observed",
                    "review_confidence", "review_duration_seconds",
                    "comment", "review_status",
                ],
                "label_semantics": {
                    "CLEARLY_SUPPORTED": "仅根据当前视频/冻结可靠证据，该业务意义有明确直接支持",
                    "POSSIBLE_BUT_INSUFFICIENT": "业务上可以关联，但当前镜头本身证据不足，不能作为 SUPPORTED Claim",
                    "NOT_REVIEWED_NOT_ASSERTED": "未选择的默认态：Human 未主张，不计任何 Truth",
                    "FIELD_UNKNOWN": "整个字段无法可靠判断",
                },
                "scoring": {
                    "human_supported_truth": "clearly_supported_needs ∪ clearly_supported_values",
                    "possible_set": "possible_needs ∪ possible_values（报告但不计 SUPPORTED TP）",
                    "unreviewed": "未选择标签 = NOT_ASSERTED，不计",
                },
                "table": "stage2_business_cognition_adjudication_v2b",
                "created": "2026-08-29 (Adjudication V2 Simplification Gate)",
            },
        ],
        "guard": "12 segment identity 不变；AI_LOCK/V1/Engine/Rules/Knowledge 不变；"
                 "不执行 Stage2.1",
    }
    json.dump(hist, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)
    print("schema 历史已归档：v2_full_taxonomy（SUPERSEDED）→ v2b_simplified（CURRENT）")


if __name__ == "__main__":
    main()
