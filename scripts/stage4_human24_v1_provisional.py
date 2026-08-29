# -*- coding: utf-8 -*-
"""Stage 2 — Human Truth Reliability Gate：标记 HUMAN24_V1 = PROVISIONAL_NOISY_REVIEW。

不删除、不覆盖、不修改 HUMAN24_V1 数据与历史评分。
仅生成状态标记文件（diagnostic-only），禁止据此调规则。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
OUT = os.path.join(DATA_ROOT, "HUMAN24_TRUTH_RELIABILITY_STATUS.json")


def main():
    status = {
        "manifest": "HUMAN24_TRUTH_RELIABILITY_STATUS",
        "generated_at": "2026-08-29",
        "human24_v1": {
            "id": "HUMAN24_V1",
            "status": "PROVISIONAL_NOISY_REVIEW",
            "reason": "审核者确认审核过程存在明显疲劳、分多次完成、部分判断缺乏把握；"
                      "不适宜作为 Gold Truth 用于规则调优",
            "data_kept": True,          # 不删除
            "not_overwritten": True,    # 不覆盖
            "score_kept": True,         # 历史评分保留
        },
        "diagnostic_only": {
            "precision_recall_ucr_fp_fn": "DIAGNOSTIC_ONLY — 仅作发现问题的线索，不作精确成绩",
            "freeze_rule_changes": [
                "Business Rules", "Claim Gating", "Conflict Rules", "Knowledge", "Engine",
            ],
            "rule_change_prohibited": True,
        },
        "next_step": {
            "adjudication": "HUMAN24_ADJUDICATION_V2",
            "n_segments": 12,
            "composition": "9 高影响 FP/error case（含 conflict 分歧/证据不足段）+ 3 对照样本",
            "blind": True,
            "compare": "Human V1 vs Human V2 → agreement_rate / per-field agreement / "
                       "label additions/removals / high-impact disagreement / confidence distribution",
            "decision": "若核心 claims 高度一致 → ADJUDICATED_HUMAN_TRUTH；"
                        "若明显不一致 → HUMAN24_V1 = UNRELIABLE_FOR_CALIBRATION，重设计简化审核",
            "no_auto_review": True,     # 不自动开始人工审核
            "no_stage21_rule_changes": True,  # 不执行 Stage2.1 规则修改
        },
    }
    json.dump(status, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)
    print("HUMAN24_V1 已标记为 PROVISIONAL_NOISY_REVIEW（数据保留）")


if __name__ == "__main__":
    main()
