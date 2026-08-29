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


# ---------------------------------------------------------------------------
# Gate：独立 Human Truth（Human24 Review Schema）
# ---------------------------------------------------------------------------

def test_human_taxonomy_is_fixed_and_complete():
    """固定 Taxonomy 非 AI 生成：包含完整 user_needs/business_values 等。"""
    tax = json.load(open(os.path.join(DATA_ROOT, "BUSINESS_COGNITION_HUMAN_TAXONOMY_V1.json"),
                         encoding="utf-8"))
    assert len(tax["user_needs"]) >= 21
    assert len(tax["business_values"]) >= 18
    assert len(tax["decision_factors"]) >= 16
    assert len(tax["search_intents"]) >= 13
    assert len(tax["shot_functions"]) >= 15
    assert len(tax["content_roles"]) == 4  # TRAFFIC/SEARCH/TRUST/CONVERSION
    assert len(tax["mother_themes"]) == 5
    assert set(tax["affinity_levels"]) == {"STRONG", "MEDIUM", "WEAK",
                                           "NOT_SUPPORTED", "UNKNOWN"}
    # 关键：包含 AI 引擎不会预测的标签（如 CUSTOMIZATION / AESTHETICS）→ 可补标
    need_ids = {t["id"] for t in tax["user_needs"]}
    assert "CUSTOMIZATION" in need_ids and "AESTHETICS" in need_ids


def test_human24_manifest_blind_and_balanced():
    """manifest 4×6 平衡、blind（无 AI claims）、段与 Challenge60 一致。"""
    man = json.load(open(os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json"),
                         encoding="utf-8"))
    assert man["blind"] is True
    counts = man["class_counts"]
    assert all(v == 4 for v in counts.values())
    assert sum(counts.values()) == 24
    assert "taxonomy" in man  # 固定 Taxonomy 内嵌
    # blind：任何段都不含 AI claims
    for s in man["segments"]:
        assert "ai_claims" not in s and "claims" not in s
        assert "affinity" not in s and "confidence" not in s
    # 段身份与 Challenge60 一致
    ch = json.load(open(os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_CHALLENGE_V1.json"),
                        encoding="utf-8"))
    ch_ids = {s["segment_id"] for s in ch["segments"]}
    assert all(s["segment_id"] in ch_ids for s in man["segments"])


def test_human_only_label_becomes_fn_in_scoring():
    """核心：Human-only label（AI 未预测）在评分中计入 FN → Recall 真实可计算。"""
    import sqlite3
    from treecut.services.annotation_governance import AnnotationService
    db = os.path.join(DATA_ROOT, "database", "materials.db")
    svc = AnnotationService(db)
    mock = "MOCK-HUMAN24-FN-TEST-0001"
    try:
        svc.save_business_cognition_review(mock, "WEAK_EVIDENCE", {
            "user_needs": ["STORAGE", "CUSTOMIZATION"],  # CUSTOMIZATION = human-only
            "business_values": [], "decision_factors": [], "trust_signals": [],
            "search_intents": [], "shot_functions": [],
            "role_affinity": {r: "UNKNOWN" for r in
                              ("TRAFFIC", "SEARCH", "TRUST", "CONVERSION")},
            "theme_affinity": {t: "UNKNOWN" for t in
                               ("SPACE_SOLUTION", "FAMILY_SCENE", "DECISION_AVOID_PIT",
                                "AESTHETIC_STYLE", "CRAFT_TRUST")},
            "overall_unknown": "NO", "conflict_observed": "NONE", "comment": "test",
        }, "HIGH", "REVIEWED", operator="TEST")
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT user_needs FROM stage2_business_cognition_review_v1 "
                           "WHERE segment_id=?", (mock,)).fetchone()
        conn.close()
        assert row is not None
        stored = json.loads(row[0])
        assert "CUSTOMIZATION" in stored  # human-only label 已持久化
        # 评分语义：AI={STORAGE} → TP=1 FN=1
        ai_set, human_set = {"STORAGE"}, set(stored)
        assert len(human_set - ai_set) == 1  # FN=1
        assert len(human_set & ai_set) == 1  # TP=1
    finally:
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM stage2_business_cognition_review_v1 WHERE segment_id=?", (mock,))
        conn.commit()
        conn.close()


def test_affinity_stored_as_english():
    """亲和度存库必须为英文（STRONG/MEDIUM/WEAK/NOT_SUPPORTED/UNKNOWN）。"""
    import sqlite3
    from treecut.services.annotation_governance import AnnotationService
    db = os.path.join(DATA_ROOT, "database", "materials.db")
    svc = AnnotationService(db)
    mock = "MOCK-HUMAN24-AFF-0002"
    try:
        svc.save_business_cognition_review(mock, "WEAK_EVIDENCE", {
            "user_needs": [], "business_values": [], "decision_factors": [],
            "trust_signals": [], "search_intents": [], "shot_functions": [],
            "role_affinity": {"TRAFFIC": "MEDIUM", "SEARCH": "WEAK",
                              "TRUST": "UNKNOWN", "CONVERSION": "NOT_SUPPORTED"},
            "theme_affinity": {"SPACE_SOLUTION": "STRONG", "FAMILY_SCENE": "MEDIUM",
                               "DECISION_AVOID_PIT": "WEAK", "AESTHETIC_STYLE": "UNKNOWN",
                               "CRAFT_TRUST": "NOT_SUPPORTED"},
            "overall_unknown": "NO", "conflict_observed": "NONE", "comment": "test",
        }, "HIGH", "REVIEWED", operator="TEST")
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT role_affinity, theme_affinity FROM "
                           "stage2_business_cognition_review_v1 WHERE segment_id=?",
                           (mock,)).fetchone()
        conn.close()
        ra = json.loads(row[0])
        assert all(v in ("STRONG", "MEDIUM", "WEAK", "NOT_SUPPORTED", "UNKNOWN")
                   for v in ra.values()), ra
    finally:
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM stage2_business_cognition_review_v1 WHERE segment_id=?", (mock,))
        conn.commit()
        conn.close()


def test_score_report_has_conflict_agreement():
    """评分输出必须含 conflict 对照（AI vs Human）与 per-segment 明细。"""
    p = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_SCORE_V1.json")
    if not os.path.exists(p):
        return  # 未评分时不强制
    s = json.load(open(p, encoding="utf-8"))
    assert "conflict_agreement" in s
    assert set(s["conflict_agreement"]) == {"agree", "ai_only", "human_only", "both_none"}
    assert all("human_conflict_observed" in ps and "ai_conflict_count" in ps
               for ps in s["per_segment"])
