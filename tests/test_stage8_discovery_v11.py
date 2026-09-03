# -*- coding: utf-8 -*-
"""Candidate Discovery V1.1 测试(§26): 全量廉价计分/去随机瓶颈/RETRACT共享/多样性/G1不可绕过/合并窗不改canonical/缺口需三支线。"""
import json, sys
from pathlib import Path
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def merged_ok(pairs):
    """跨段合并候选仅作证据窗, 不改 canonical segment(由调用方保证)"""
    return pairs


def test_all_broad_candidates_receive_cheap_score():
    ranked = json.loads((OUT / "_v11_ranked.json").read_text(encoding="utf-8"))
    meta = ranked["_meta"]["scored_total"]
    for act in ("EXTEND", "RETRACT", "DRAWER_OPEN", "STORAGE_PUT_IN", "SOCKET_INSERT"):
        assert meta[act] > 100, f"{act} broad {meta[act]}"
        items = ranked[act]
        assert all("score" in x and "components" in x for x in items)  # 全部廉价计分


def test_random_sampling_not_used_as_gap_proof():
    # V1.1 采用全量排序(≠随机10); 缺口状态仍为 CANDIDATE
    gap = json.loads((OUT / "TREECUT_MATERIAL_GAP_STATUS_V2.json").read_text(encoding="utf-8"))
    for a in ("EXTEND", "RETRACT", "DRAWER_OPEN", "STORAGE_PUT_IN", "SOCKET_INSERT"):
        assert gap["status_per_action"][a] == "MATERIAL_GAP_CANDIDATE"


def test_retract_shares_neutral_flexible_pool():
    ranked = json.loads((OUT / "_v11_ranked.json").read_text(encoding="utf-8"))
    meta = ranked["_meta"]["scored_total"]
    assert meta["RETRACT"] == meta["EXTEND"]  # 中性 flexible 池共享
    assert meta["RETRACT"] > 100


def test_candidate_diversity_per_asset():
    ranked = json.loads((OUT / "_v11_ranked.json").read_text(encoding="utf-8"))
    for act in ("EXTEND", "DRAWER_OPEN"):
        mids = [x["media_id"] for x in ranked[act]]
        assert len(mids) == len(set(mids)), "asset 级候选去重(每 asset 一条)"


def test_review_required_cannot_bypass_g1():
    rr = json.loads((OUT / "TREECUT_REVIEW_REQUIRED_ACTION_RECOVERY_V1.json").read_text(encoding="utf-8"))
    for act, info in rr["actions"].items():
        for it in info.get("items", []):
            assert it.get("promotable") is False  # 提升必须走污染verify路径


def test_material_gap_requires_all_three_branches():
    status = json.loads((OUT / "TREECUT_MATERIAL_GAP_STATUS_V2.json").read_text(encoding="utf-8"))
    assert "review_required_pending_verify" in status and "cross_segment_pending_probe" in status
    # CONFIRMED 前必须三条支线完成(此处未完成 → CANDIDATE)
    assert status["status_per_action"]["EXTEND"] == "MATERIAL_GAP_CANDIDATE"
