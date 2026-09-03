# -*- coding: utf-8 -*-
"""Candidate Discovery Recovery 测试(§20): 宽召回非Top3/跨段合并/REVIEW_REQUIRED门/物料缺口门。"""
import json, sys
from pathlib import Path
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def cross_segment_merge(segments):
    """segments: [(id,start_ms,end_ms)] → 相邻 gap<1200ms 合并候选。"""
    segs = sorted(segments, key=lambda x: x[1])
    out = []
    for i in range(len(segs) - 1):
        gap = segs[i + 1][1] - segs[i][2]
        if 0 <= gap < 1200:
            out.append({"seg_a": segs[i][0], "seg_b": segs[i + 1][0],
                        "merged": [segs[i][1], segs[i + 1][2]], "gap_ms": gap})
    return out


def confirm_requires_all(performed: dict) -> bool:
    required = ["broad_eligible", "cheap_filter", "temporal_probe", "cross_segment",
                "review_required_recovery"]
    return all(performed.get(k) for k in required)


def test_broad_recall_not_stop_at_top3():
    a = json.loads((OUT / "_g2_discovery_a.json").read_text(encoding="utf-8"))
    for act in ("EXTEND", "DRAWER_OPEN", "STORAGE_PUT_IN", "SOCKET_INSERT"):
        assert a[act]["union_eligible"] > 100, f"{act} broad recall {a[act]}"
    # RETRACT 无独立标签 → 在伸缩池内检索(记录), 不允许当作确认缺口
    assert a["RETRACT"]["union_eligible"] == 0


def test_cross_segment_action_window_recoverable():
    segs = [("s1", 0, 3000), ("s2", 3100, 6000), ("s3", 7500, 9000)]
    merged = cross_segment_merge(segs)
    assert any(m["seg_a"] == "s1" and m["seg_b"] == "s2" for m in merged)   # gap 100ms → 合并候选
    assert not any(m["seg_a"] == "s2" and m["seg_b"] == "s3" for m in merged)  # gap 1500ms → 不合并


def test_cross_segment_file_present():
    f = OUT / "TREECUT_CROSS_SEGMENT_ACTION_RECOVERY_V1.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    assert d["count"] > 0


def test_review_required_not_admitted_without_verify():
    d = json.loads((OUT / "TREECUT_REVIEW_REQUIRED_ACTION_RECOVERY_V1.json").read_text(encoding="utf-8"))
    for act, info in d["actions"].items():
        for it in info.get("items", []):
            assert it.get("promotable") is False  # 未过 contamination verify 不得提升


def test_material_gap_not_confirmed_without_stages():
    gap = json.loads((OUT / "TREECUT_STAGE8_MATERIAL_GAP_V1.json").read_text(encoding="utf-8"))
    for act in ("EXTEND", "RETRACT", "DRAWER_OPEN", "STORAGE_PUT_IN", "SOCKET_INSERT"):
        assert gap["per_action"][act]["status"] == "MATERIAL_GAP_CANDIDATE", "尚未确认缺口"
    assert confirm_requires_all({"broad_eligible": True, "cheap_filter": True, "temporal_probe": False,
                                 "cross_segment": False, "review_required_recovery": False}) is False
    assert confirm_requires_all({k: True for k in ("broad_eligible", "cheap_filter", "temporal_probe",
                                                   "cross_segment", "review_required_recovery")}) is True
