# -*- coding: utf-8 -*-
"""V3 — HUMAN_CALIBRATION_V3_MANIFEST + V2 降级标记。

12 segment 与 Adjudication V2 完全一致（set 相等证明）。
同时更新 HUMAN24_TRUTH_RELIABILITY_STATUS.json 记录 V2 = UI_CONTAMINATED。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
V2_MANIFEST = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_HUMAN_ADJUDICATION_V2.json")
TAXONOMY = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_CALIBRATION_TAXONOMY_V1.json")
OUT = os.path.join(DATA_ROOT, "HUMAN_CALIBRATION_V3_MANIFEST.json")
STATUS = os.path.join(DATA_ROOT, "HUMAN24_TRUTH_RELIABILITY_STATUS.json")


def main():
    v2 = json.load(open(V2_MANIFEST, encoding="utf-8"))
    tax = json.load(open(TAXONOMY, encoding="utf-8"))
    v2_segs = [s["segment_id"] for s in v2["segments"]]
    assert len(set(v2_segs)) == 12, "V2 应为 12 条"

    # 12 segment 锁：与 V2 完全一致
    segs = []
    for i, s in enumerate(v2["segments"], 1):
        fe = s.get("frozen_evidence", {})
        segs.append({
            "segment_id": s["segment_id"],
            "stratum": "HUMAN_CALIBRATION_V3",
            "item_no": i,
            "frozen_evidence": {
                "component": fe.get("component", []),
                "function": fe.get("function", []),
                "scene_family": fe.get("scene_family", ""),
                "material": fe.get("material", []),
                "action_sequence": fe.get("action_sequence", []),
                "asr_text": fe.get("asr_text", ""),
            },
            "taxonomy_ref": "BUSINESS_COGNITION_CALIBRATION_TAXONOMY_V1.json",
        })

    manifest = {
        "manifest": "HUMAN_CALIBRATION_V3_MANIFEST",
        "generated_at": "2026-08-29",
        "guard": "只校准当前引擎 AI_OUTPUT_VOCABULARY_V1（10 标签）；"
                 "每标签严格单状态；Evidence/Confidence 无默认必选；"
                 "AI/V1/V2 零泄漏；12 segment 与 Adjudication V2 完全一致",
        "calibration_taxonomy": tax,
        "count": len(segs),
        "segment_lock_proof": {
            "v3_count": len(segs),
            "v2_count": len(v2_segs),
            "set_equal": set(s["segment_id"] for s in segs) == set(v2_segs),
        },
        "segments": segs,
    }
    assert manifest["segment_lock_proof"]["set_equal"], "V3 段必须与 V2 完全一致"
    json.dump(manifest, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)
    print("V3 段数:", len(segs), "| 与 V2 set 相等:", manifest["segment_lock_proof"]["set_equal"])

    # V2 降级标记（保留数据）
    st = json.load(open(STATUS, encoding="utf-8"))
    st["human_adjudication_v2"] = {
        "id": "HUMAN_ADJUDICATION_V2",
        "status": "UI_CONTAMINATED / INVALID_FOR_CALIBRATION",
        "reason": "CLEARLY/POSSIBLE 重叠 128 次；POSSIBLE 整表全选；evidence 12/12 SUFFICIENT；"
                  "UI 交互（两个独立多选区）导致系统性污染",
        "data_kept": True,
        "not_overwritten": True,
        "role_in_comparison": "UI_FAILURE_DIAGNOSTIC",
    }
    st["human_calibration_v3"] = {
        "id": "HUMAN_CALIBRATION_V3",
        "status": "PENDING_REVIEW",
        "scope": "AI_OUTPUT_VOCABULARY_V1（10 标签，Calibration Scope 非完整 Taxonomy）",
        "12_segment_lock": True,
    }
    json.dump(st, open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("V2 已标记 UI_CONTAMINATED / INVALID_FOR_CALIBRATION（数据保留）->", STATUS)


if __name__ == "__main__":
    main()
