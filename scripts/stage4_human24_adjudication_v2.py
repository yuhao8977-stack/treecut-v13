# -*- coding: utf-8 -*-
"""Stage 2 — HUMAN24_ADJUDICATION_V2 manifest（12 条）。

构成：
  - 9 条高影响 error/分歧样本：
      6 个 FP 段（unsupported_claims 涉及）
      + b2f971fdb539（human 观察 SCENE_ASR_CONFLICT 而 AI 未检出 + overall_unknown=YES）
      + 31b982947032（overall_unknown=YES 证据不足）
      + 66cc43823369（AI 检到 conflict 而 Human 未确认，CONFLICTING 类）
  - 3 条对照（AI/Human 一致、TP 高）：75c6e986027d / d96ec7179e6e / 95d73053ea12

要求：
  - segment identity 固定（来自 Human24 的 24 段）
  - blind：不显示 AI 答案 / Human V1 答案 / 旧评分 / 错误类型 / sampling class
  - 独立 Human Truth UI（完整固定 Taxonomy）
  - 每条可保存 review_confidence = HIGH/MEDIUM/LOW + review_duration_seconds（仅诊断）
  - 完成 12 条后仅比较 Human V1 vs V2，不修改 AI
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
HUMAN_MANIFEST = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json")
OUT = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_HUMAN_ADJUDICATION_V2.json")

# 9 error + 3 对照（来自 HUMAN24_V1 的 24 段）
ERROR_SIDS = [
    "40d5fdbe96cb44d3a8e9c2024f80712e",   # FP: STORAGE/STORAGE_EFFICIENCY/ISLAND_STORAGE
    "80f182c8a51346e39c87fa66f43ff970",   # FP: POWER_CONVENIENCE
    "9df423b8ab374b07a569ff1fe946bf9b",   # FP: ISLAND_STORAGE
    "a1223854e64f479db797a42114e3ace2",   # FP: CHARGING_POWER
    "bf686b31816e47b6a2fad191b62f4890",   # FP: STORAGE_EFFICIENCY/ISLAND_STORAGE
    "d780c9edafef4687aa70f291db884145",   # FP: STORAGE
    "b2f971fdb5394d2a81167edfe327c7dc",  # 高影响: human 观察冲突 AI 未检出 + unknown=YES
    "31b98294703243849975ffe2a17a26ed",   # 高影响: overall_unknown=YES（证据不足）
    "66cc438233694ef59d0bf4f38b6ed33f",   # 高影响: AI 检冲突 Human 未确认（CONFLICTING）
]
CONTROL_SIDS = [
    "75c6e986027d4a50960c9edea4bc9e41",   # 对照: TP=6（NEGATIVE）
    "d96ec7179e6e43e093c08444eff97303",   # 对照: TP=4（MULTI）
    "95d73053ea124098972ba841ba7acdb0",   # 对照: TP=2（STRONG）
]


def main():
    man = json.load(open(HUMAN_MANIFEST, encoding="utf-8"))
    by_id = {s["segment_id"]: s for s in man["segments"]}

    # 校验：error+control 都在 Human24 内且唯一
    all_sids = ERROR_SIDS + CONTROL_SIDS
    assert len(set(all_sids)) == 12, "12 条必须唯一"
    missing = [s for s in all_sids if s not in by_id]
    assert not missing, f"不在 Human24 内: {missing}"

    # 构建 blind manifest：不含 V1 答案 / AI / 评分 / 错误类型 / sampling class
    segs = []
    for i, sid in enumerate(all_sids, 1):
        src = by_id[sid]
        fe = src.get("frozen_evidence", {})
        segs.append({
            "segment_id": sid,
            "stratum": "BUSINESS_COGNITION_HUMAN_ADJUDICATION_V2",
            "review_target": "business_cognition",
            "item_no": i,
            "frozen_evidence": {
                "component": fe.get("component", []),
                "function": fe.get("function", []),
                "scene_family": fe.get("scene_family", ""),
                "material": fe.get("material", []),
                "action_sequence": fe.get("action_sequence", []),
                "asr_text": fe.get("asr_text", ""),
            },
            "taxonomy_ref": "BUSINESS_COGNITION_HUMAN_TAXONOMY_V1.json",
        })

    manifest = {
        "manifest": "BUSINESS_COGNITION_STAGE2_HUMAN_ADJUDICATION_V2",
        "generated_at": "2026-08-29",
        "guard": "ADJUDICATION_V2; blind=true（无 AI/V1/评分/错误类型/sampling class）; "
                 "9 error + 3 control; 每条可保存 review_confidence + review_duration_seconds; "
                 "完成 12 条后仅比较 V1 vs V2，不修改 AI",
        "blind": True,
        "composition": {"error_high_impact": len(ERROR_SIDS), "control": len(CONTROL_SIDS)},
        "review_confidence_levels": ["HIGH", "MEDIUM", "LOW"],
        "taxonomy": man["taxonomy"],
        "count": len(segs),
        "segments": segs,
    }
    json.dump(manifest, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)
    print("总数:", len(segs), "| error:", len(ERROR_SIDS), "| control:", len(CONTROL_SIDS))
    for i, s in enumerate(segs, 1):
        print(f"  {i:2d}. {s['segment_id'][:16]}")


if __name__ == "__main__":
    main()
