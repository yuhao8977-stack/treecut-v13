# -*- coding: utf-8 -*-
"""Stage 3A — STAGE3_BUSINESS_COGNITION_CONSUMER_POLICY_V1.json。

定义 Stage3 消费 Stage2 Business Cognition 输出的规则。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
OUT = os.path.join(DATA_ROOT, "STAGE3_BUSINESS_COGNITION_CONSUMER_POLICY_V1.json")


def main():
    policy = {
        "manifest": "STAGE3_BUSINESS_COGNITION_CONSUMER_POLICY_V1",
        "generated_at": "2026-08-30",
        "basis": "PHASE4_STAGE2_FINAL_FREEZE (PASS_WITH_LIMITATIONS)",
        "claim_status_semantics": {
            "SUPPORTED": "可作为 Evidence-backed semantic feature（有镜头级证据支持）",
            "CANDIDATE": "只作为 soft feature；不得当 Hard Truth",
            "WEAK": "弱证据；仅诊断",
            "UNKNOWN": "= MISSING / INSUFFICIENT MACHINE COGNITION；"
                       "绝不能解释为 FALSE / NOT_PRESENT / NOT_USEFUL；"
                       "UNKNOWN 不代表'没有这个业务意义'，只代表'当前机器证据不足，TreeCut 不知道'",
            "BLOCKED": "NR 阻断",
        },
        "label_restrictions": {
            "DINING": {"status": "LIMITED_CONTEXT_VALIDATION",
                       "note": "Fresh18 2 FALSE（有 DINING function 但镜头讲充电/火锅）；"
                               "不能作为单独 Hard Performance Explanation"},
            "DINING_CONVENIENCE": {"status": "LIMITED_CONTEXT_VALIDATION",
                                   "note": "同 DINING"},
            "STORAGE_EFFICIENCY": {"status": "PARTIALLY_VALIDATED",
                                   "note": "Gate 修复成功但偏保守（0 SUPPORTED vs Human 13 CLEARLY）"},
        },
        "field_restrictions": {
            "Decision Factor": "CANDIDATE ONLY",
            "Trust Signal": "CANDIDATE ONLY",
            "Shot Function": "CANDIDATE ONLY",
            "Search Intent": "CANDIDATE ONLY",
            "Content Role": "AFFINITY ONLY（不得变成 primary role）",
            "Mother Theme": "AFFINITY ONLY（不得变成 primary theme）",
        },
        "conflict_resolver_v2": {
            "status": "STRUCTURALLY_VALIDATED / LIMITED_FRESH_HUMAN_EVIDENCE",
            "note": "Fresh18 CONFLICT 样本多用动作↔组件不匹配补池；"
                    "'如果家里有宝宝' vs FACTORY 的新鲜人审样本不足；"
                    "假设语境不触发冲突的修复已通过 TEST K 结构验证",
        },
        "prohibited_interpretations": [
            "UNKNOWN ≠ 没有该业务意义",
            "UNKNOWN ≠ 视频无用",
            "CANDIDATE ≠ 已证实的特征",
            "Role/Theme affinity ≠ primary role/theme",
            "DINING SUPPORTED ≠ 该镜头证明用餐（LIMITED_CONTEXT_VALIDATION）",
            "高表现视频中出现 DRAWER ≠ 抽屉导致转化（禁止因果语言）",
        ],
        "guard": "Stage3 消费方必须遵守；UNKNOWN 只能作为 coverage 低的信号，不得作为负信号",
    }
    json.dump(policy, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
