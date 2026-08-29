# -*- coding: utf-8 -*-
"""Stage 2 — Human Business Review 24 manifest（4×6 平衡，blind）。

从 Challenge60（每类 10）每类固定种子抽 4 → 24 条。
盲审：manifest 仅含题目 + 冻结证据（视觉摘要 + ASR/OCR 原文），
不含任何 AI claims / affinity / confidence。
评审任务 = 业务认知判定（用户需求/商业价值主张是否被视频支持），非视觉重标注。
"""
import io
import json
import os
import random
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
CHALLENGE = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_CHALLENGE_V1.json")
OUT = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json")

# 评审者可勾选的候选主张（blind 版：只给候选清单，不给 AI 答案）
NEED_CANDIDATES = ["STORAGE", "DINING", "OFFICE", "CHARGING_POWER", "GUEST_CAPACITY",
                   "SPACE_EFFICIENCY", "FAMILY_GATHERING", "AESTHETICS", "DURABILITY",
                   "DECISION_CONFIDENCE"]
VALUE_CANDIDATES = ["STORAGE_EFFICIENCY", "DINING_CONVENIENCE", "WORK_FROM_HOME",
                    "POWER_CONVENIENCE", "FLEXIBLE_CAPACITY", "QUALITY_TRUST",
                    "SPACE_SAVING", "CRAFT"]


def main():
    ch = json.load(open(CHALLENGE, encoding="utf-8"))
    segs = ch["segments"]
    by_class = {}
    for s in segs:
        by_class.setdefault(s["challenge_class"], []).append(s)

    # 每类固定种子抽 4（确定性：类名 → 固定偏移，避免 PYTHONHASHSEED 随机）
    chosen = []
    for idx, cls in enumerate(sorted(by_class.keys())):
        lst = by_class[cls]
        rng = random.Random(20260829 + idx * 131)
        picked = rng.sample(lst, 4)
        chosen.extend(picked)
        print(f"  {cls}: 抽 {len(picked)} (池 {len(lst)})")
    print("Human24 总数:", len(chosen))

    # manifest：题目 + 冻结证据（blind，无 AI 输出）
    segs_out = []
    for s in chosen:
        fe = s.get("evidence_features", {})
        segs_out.append({
            "segment_id": s["segment_id"],
            "stratum": "BUSINESS_COGNITION_HUMAN24",
            "challenge_class": s["challenge_class"],  # 采样结构标签（非 AI 预测）
            "review_target": "business_cognition",
            "frozen_evidence": {
                "component": fe.get("component_multi", []),
                "function": fe.get("function_multi", []),
                "scene_family": fe.get("scene_family", ""),
                "material": fe.get("material_multi", []),
                "action_sequence": fe.get("action_sequence", []),
                "asr_text": fe.get("asr_text", ""),
            },
            "need_candidates": NEED_CANDIDATES,
            "value_candidates": VALUE_CANDIDATES,
        })

    manifest = {
        "manifest": "BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1",
        "generated_at": "2026-08-29",
        "guard": "HUMAN_REVIEW_24; blind=true（无 AI claims/affinity/confidence）; "
                 "评审=业务认知判定，非视觉重标注; 4×6 每类4条平衡; 不与 Validation43/Holdout 重叠",
        "blind": True,
        "count": len(segs_out),
        "class_counts": {c: sum(1 for s in segs_out if s["challenge_class"] == c)
                         for c in sorted({s["challenge_class"] for s in segs_out})},
        "segments": segs_out,
    }
    json.dump(manifest, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)
    print("类别分布:", manifest["class_counts"])
    assert all(v == 4 for v in manifest["class_counts"].values()), "每类必须 4 条"


if __name__ == "__main__":
    main()
