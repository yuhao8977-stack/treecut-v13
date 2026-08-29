# -*- coding: utf-8 -*-
"""Stage 2 — EvidenceResolver / ConflictResolver / BusinessCognitionV2 测试。"""
import json
import os
import sys

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

from treecut.services.evidence_resolver import EvidenceResolverV1
from treecut.services.conflict_resolver import ConflictResolverV1
from treecut.services.business_cognition_v2 import BusinessCognitionServiceV2


def test_evidence_family_no_overcount():
    """SigLIP component/function 同 family，不算独立来源。"""
    er = EvidenceResolverV1()
    p = er.resolve({"component": ["DRAWER"], "function": ["STORAGE"], "material": ["岩板"]})
    # 三个都是 SIGLIP family
    assert p["family_counts"]["SIGLIP"] == 3
    assert p["independent_sources"] == 1  # 只有 SIGLIP 一个 family
    # 加 ASR 后独立来源 2
    p2 = er.resolve({"component": ["DRAWER"]}, asr_text="这个抽屉收纳很强")
    assert p2["family_counts"]["SIGLIP"] == 1
    assert p2["family_counts"]["ASR"] == 1
    assert p2["independent_sources"] == 2


def test_semantic_action_forced_very_low():
    er = EvidenceResolverV1()
    p = er.resolve({"action_sequence": ["OPEN_DRAWER"]})
    assert p["normalized_evidence"]["action_sequence"]["reliability"] == "VERY_LOW"


def test_conflict_scene_vs_asr():
    cr = ConflictResolverV1()
    er = EvidenceResolverV1()
    p = er.resolve({"scene_family": "FACTORY"}, asr_text="客户家里面做了这个岛台")
    r = cr.resolve(p)
    assert any(c["type"] == "CONFLICTING_EVIDENCE" for c in r["conflicts"])
    assert r["conflicts"][0]["resolution"] == "CUSTOMER_HOME=UNKNOWN"


def test_conflict_material_weak_vs_asr():
    cr = ConflictResolverV1()
    er = EvidenceResolverV1()
    p = er.resolve({"material": ["岩板"]}, asr_text="这是实木的")
    r = cr.resolve(p)
    assert any(c["type"] == "WEAK_EVIDENCE_CONFLICT" for c in r["conflicts"])


def test_v2_no_primary_role():
    """Segment 不输出 primary role，只输出 affinity。"""
    svc = BusinessCognitionServiceV2()
    bc = svc.cognize("t1", {"component": ["DRAWER"], "function": ["STORAGE"]})
    assert "primary_role" not in bc or bc.get("primary_role") is None
    assert "content_role_affinity" in bc
    assert all("affinity" in r for r in bc["content_role_affinity"])
    svc.ks.unload()


def test_v2_no_primary_theme():
    svc = BusinessCognitionServiceV2()
    bc = svc.cognize("t2", {"component": ["DRAWER"], "function": ["STORAGE"]})
    assert "primary_mother_theme" not in bc or bc.get("primary_mother_theme") is None
    assert "mother_theme_affinity" in bc
    svc.ks.unload()


def test_v2_search_intent_candidate():
    svc = BusinessCognitionServiceV2()
    bc = svc.cognize("t3", {"component": ["TRACK_SOCKET"], "function": ["POWER"]})
    assert "ISLAND_SOCKET" in bc["search_intent_candidates"]
    svc.ks.unload()


def test_v2_negative_blocks_operate_socket():
    svc = BusinessCognitionServiceV2()
    bc = svc.cognize("t4", {"component": ["TRACK_SOCKET"], "function": ["POWER"]})
    vals = [c["claim_value"] for c in bc["business_claims"]]
    assert "OPERATE_SOCKET" not in vals
    # POWER_CONVENIENCE 保留（产品能力）
    assert "POWER_CONVENIENCE" in vals
    svc.ks.unload()


def test_v2_semantic_action_not_hard():
    svc = BusinessCognitionServiceV2()
    bc = svc.cognize("t5", {"action_sequence": ["OPEN_DRAWER"]})
    assert bc["business_claims"] == []  # 无 hard claim（semantic_action VERY_LOW）
    assert bc["confidence"] in ("UNKNOWN", "LOW")
    svc.ks.unload()


def test_v2_drawer_storage_claims():
    svc = BusinessCognitionServiceV2()
    bc = svc.cognize("t6", {"component": ["DRAWER"], "function": ["STORAGE"]})
    claims = {c["claim_category"]: c["claim_value"] for c in bc["business_claims"]}
    assert claims.get("USER_NEED") == "STORAGE"
    assert claims.get("BUSINESS_VALUE") == "STORAGE_EFFICIENCY"
    svc.ks.unload()


def test_v12_replay43_no_critical_regression():
    r = json.load(open(os.path.join(DATA_ROOT, "BUSINESS_COGNITION_V12_REPLAY43.json"),
                       encoding="utf-8"))
    assert len(r["results"]) == 43
    assert r["critical_regression_count"] == 0
