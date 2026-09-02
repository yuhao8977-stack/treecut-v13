# -*- coding: utf-8 -*-
"""G3 测试: 主张解析/硬闸/禁止推断/StoryMode/薄抽规则/V2 回归。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.claim_visual import (parse_script_to_claims, classify_story_mode,
                                           AtomicClaim, Candidate, ClaimVisualMatcher)

E_OK = lambda mid, kind="media_file": (True, {})


def test_stretch_claim_requires_action():
    claims = parse_script_to_claims("拉开以后变宽，收起来不占位")
    assert all(c.claim_type == "ACTION" for c in claims)
    assert claims[0].required_action in ("DRAWER_OPEN", "EXTEND")  # 拉开→EXTEND 语义由检索端验证
    assert claims[1].required_action == "RETRACT"


def test_socket_closeup_rejected_for_stretch():
    # V2 永久回归: 口播伸缩 → 轨道插座特写候选必须 REJECT(dominant mismatch)
    claim = AtomicClaim(claim_id="C1", beat_id="B1", text="拉开以后变宽", claim_type="ACTION",
                        required_action="EXTEND")
    cand = Candidate(media_id=1, object_="SOCKET", actions=["SOCKET_INSERT"])
    m = ClaimVisualMatcher(eligible_check=E_OK,
                           action_profile=lambda mid: {"actions": ["SOCKET_INSERT"], "object": "SOCKET"})
    res = m.rank(claim, "INFORMATION_MONTAGE", [cand])
    assert res[0]["status"] == "REJECT"
    assert any("DOMINANT_VISUAL_MISMATCH" in r for r in res[0]["reasons"])


def test_extend_candidate_passes_when_action_evidenced():
    claim = AtomicClaim(claim_id="C1", beat_id="B1", text="拉开以后变宽", claim_type="ACTION",
                        required_action="EXTEND")
    cand = Candidate(media_id=2, object_="TABLETOP", actions=["EXTEND", "RETRACT"])
    m = ClaimVisualMatcher(eligible_check=E_OK)
    res = m.rank(claim, "INFORMATION_MONTAGE", [cand])
    assert res[0]["status"] == "PASS"


def test_no_object_to_property_inference():
    # 岩板可见 ≠ 耐高温支持
    claims = parse_script_to_claims("岩板台面耐高温")
    assert claims[0].claim_type == "MATERIAL_PROPERTY"
    assert claims[0].knowledge_requirement is not None  # 需知识/实物证据, 不推断
    # drawer 可见 ≠ 静音滑轨支持
    c2 = parse_script_to_claims("抽屉用了静音滑轨")
    assert c2[0].claim_type == "HARDWARE_PROPERTY"


def test_path_hint_does_not_prove_action():
    # 文件夹名"伸缩"不作为 matcher 输入; 动作只来自时序证据(prof.actions)
    claim = AtomicClaim(claim_id="C1", beat_id="B1", text="伸缩桌面", claim_type="ACTION",
                        required_action="EXTEND")
    cand = Candidate(media_id=3, object_="TABLETOP", actions=[])  # 文件夹说伸缩但无动作证据
    m = ClaimVisualMatcher(eligible_check=E_OK)
    res = m.rank(claim, "INFORMATION_MONTAGE", [cand])
    assert res[0]["status"] == "REJECT"
    assert any("REQUIRED_ACTION_MISSING" in r for r in res[0]["reasons"])


def test_story_mode_single_case():
    assert classify_story_mode("这是上海陈女士定制的一套岛台") == "SINGLE_CASE"
    assert classify_story_mode("岛台这三个功能很好用") == "INFORMATION_MONTAGE"


def test_thin_drawer_requires_visual_evidence():
    claim = AtomicClaim(claim_id="C1", beat_id="B1", text="上层薄抽收纳", claim_type="ACTION",
                        required_action="DRAWER_OPEN", required_object="UPPER_THIN_DRAWER")
    cand = Candidate(media_id=4, object_="DRAWER", actions=["DRAWER_OPEN"])
    m = ClaimVisualMatcher(eligible_check=E_OK)
    res = m.rank(claim, "INFORMATION_MONTAGE", [cand])
    assert res[0]["status"] == "REJECT"
    assert any("THIN_DRAWER_UNVERIFIED" in r for r in res[0]["reasons"])


def test_duplicate_used_rejected():
    claim = AtomicClaim(claim_id="C1", beat_id="B2", text="收纳", claim_type="SPACE")
    cand = Candidate(media_id=5, object_="DRAWER", actions=[])
    m = ClaimVisualMatcher(eligible_check=E_OK)
    res = m.rank(claim, "INFORMATION_MONTAGE", [cand], already_used=[{"media_id": 5}])
    assert res[0]["status"] == "REJECT"
    assert any("DUPLICATE_USED" in r for r in res[0]["reasons"])


def test_retract_narration_rejects_socket():
    claim = AtomicClaim(claim_id="C1", beat_id="B4", text="收起来不占位", claim_type="ACTION",
                        required_action="RETRACT")
    cand = Candidate(media_id=6, object_="SOCKET", actions=["SOCKET_INSERT"])
    m = ClaimVisualMatcher(eligible_check=E_OK,
                           action_profile=lambda mid: {"actions": ["SOCKET_INSERT"], "object": "SOCKET"})
    res = m.rank(claim, "INFORMATION_MONTAGE", [cand])
    assert res[0]["status"] == "REJECT"
