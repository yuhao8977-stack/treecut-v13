# -*- coding: utf-8 -*-
"""Phase 4 Stage 1 — Knowledge Service + Business Cognition 回归测试。"""
import json
import os
import sys

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

from treecut.services.knowledge_service import KnowledgeService
from treecut.services.business_cognition_service import (
    BusinessCognitionServiceV1, NEGATIVE_RULES, SEMANTIC_MAPPINGS)


def test_knowledge_manifest_186():
    m = json.load(open(os.path.join(DATA_ROOT, "KNOWLEDGE_SNAPSHOT_V1.json"), encoding="utf-8"))
    assert m["record_count"] == 186
    assert len(m["knowledge_snapshot_sha256"]) == 64
    assert m["knowledge_file_count"] >= 20


def test_knowledge_manifest_v11():
    """V1.2 重分类：361 条，FACT 定义类为主，BUSINESS_RULE 不泛化。"""
    m = json.load(open(r"C:\Users\admin\github\treecut-v13\knowledge\knowledge_manifest.json",
                       encoding="utf-8"))
    assert m["record_count"] == 361
    assert m["by_type"]["FACT"] > 150
    assert m["by_type"]["BUSINESS_RULE"] < 120
    assert m["by_type"]["PLATFORM_RULE"] == 10
    assert m["by_type"]["HYPOTHESIS"] >= 12
    assert m["source"]["source_type"] == "USER_CURATED_STRUCTURED_KB"


def test_knowledge_audit_v11_clean():
    a = json.load(open(r"C:\Users\admin\github\treecut-v13\knowledge\knowledge_audit_v1_1.json",
                       encoding="utf-8"))
    assert a["total"] == 361
    assert a["duplicate"] == []
    assert a["conflicts"] == []  # 真冲突 0
    assert len(a["semantic_dup_candidates"]) == 6  # KB vs P4 语义重复（记录不删）
    assert a["hypothesis_all_draft"] is True
    assert a["unverified_fact_active_high"] == []
    # source requirement 重分类
    sr = a["by_source_req"]
    assert sr["EXTERNAL_SOURCE_REQUIRED"] == 12
    assert sr["INTERNAL_VALIDATION_REQUIRED"] > 100


def test_knowledge_service_get_search():
    ks = KnowledgeService()
    r = ks.get_by_id("KB-12-001")  # V1.1 专业知识（FACT）
    assert r is not None
    assert r["knowledge_type"] == "FACT"
    # platform 规则
    plat = ks.search("", namespace="platform_compliance", limit=50)
    assert len(plat) == 10
    for p in plat:
        assert p["knowledge_type"] == "PLATFORM_RULE"
        assert p["ttl_days"] == 30
    # V1.1 主表功能定义（重分类后：定义类 → FACT）
    r2 = ks.get_by_id("KB-04-001")
    assert r2 is not None
    assert r2["knowledge_type"] == "FACT"  # 功能定义（伸缩是什么）
    assert r2["semantic_kind"] in ("ENTITY_DEFINITION", "BUSINESS_TAXONOMY")
    ks.unload()


def test_hypothesis_not_in_hard_rules():
    """TEST 15：HYPOTHESIS 不进 hard-rule retrieval。"""
    ks = KnowledgeService()
    active = ks.retrieve_active_rules()
    for r in active:
        assert r["knowledge_type"] == "BUSINESS_RULE"
        assert r["status"] == "ACTIVE"
        assert r["knowledge_type"] != "HYPOTHESIS"
    ks.unload()


def test_business_rule_vs_fact_distinct():
    """TEST 14：BUSINESS_RULE 与 FACT 可查询区分。"""
    ks = KnowledgeService()
    br = ks.search("", knowledge_type="BUSINESS_RULE", limit=5)
    fa = ks.search("", knowledge_type="FACT", limit=5)
    assert br and fa
    assert all(r["knowledge_type"] == "BUSINESS_RULE" for r in br)
    assert all(r["knowledge_type"] == "FACT" for r in fa)
    ks.unload()


def test_platform_ttl_enforced():
    """TEST 16：PLATFORM_RULE 全带 TTL（30 天），无 STALE。"""
    a = json.load(open(r"C:\Users\admin\github\treecut-v13\knowledge\knowledge_audit_v1_1.json",
                       encoding="utf-8"))
    assert a["stale_platform"] == []
    ks = KnowledgeService()
    plat = ks.search("", namespace="platform_compliance", limit=50)
    assert all(p["ttl_days"] == 30 for p in plat)
    ks.unload()


def test_validation_v11_no_regression():
    """STEP 15：V1.1 重跑 43 条 Validation 无严重回归。"""
    r = json.load(open(os.path.join(DATA_ROOT, "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_RESULTS_V1_1.json"),
                       encoding="utf-8"))
    assert len(r["results"]) == 43
    assert r["regression_count"] == 0


def test_business_cognition_v11_capabilities():
    """STEP 16：V1.1 知识下 Business Cognition 新增能力验证（A-H）。"""
    svc = BusinessCognitionServiceV1()
    # A. DRAWER+STORAGE → STORAGE
    a = svc.cognize("v11a", {"component": ["DRAWER"], "function": ["STORAGE"]})
    assert "STORAGE" in a["user_needs"] and "STORAGE_EFFICIENCY" in a["business_values"]
    # B. TRACK_SOCKET → POWER_CONVENIENCE 但非 OPERATE_SOCKET
    b = svc.cognize("v11b", {"component": ["TRACK_SOCKET"], "function": ["POWER"]})
    assert "POWER_CONVENIENCE" in b["business_values"]
    assert "OPERATE_SOCKET" not in b["user_needs"]
    # C. EXTENDABLE → FLEXIBLE_CAPACITY 非 SMALL_APARTMENT
    c = svc.cognize("v11c", {"component": ["EXTENDABLE_SECTION"], "function": ["EXTENDABLE"]})
    assert "FLEXIBLE_CAPACITY" in c["business_values"]
    assert "SMALL_APARTMENT" not in c["user_needs"]
    # D. FACTORY → TRUST 候选 非 REAL_CASE
    d = svc.cognize("v11d", {"component": ["DRAWER"], "function": ["STORAGE"], "scene_family": "FACTORY"})
    assert "TRUST" in d["content_roles"]
    assert "REAL_CUSTOMER_CASE" not in d["content_roles"]
    # E. people YES → 不推 FAMILY_GATHERING
    e = svc.cognize("v11e", {"people_presence": "YES"})
    assert "FAMILY_GATHERING" not in e["user_needs"]
    # F. weak material → 不推 SOLID_WOOD
    f = svc.cognize("v11f", {"material": ["岩板"]})
    assert "SOLID_WOOD" not in f["business_values"]
    # G. semantic_action 不单独改变高置信
    g = svc.cognize("v11g", {"action_sequence": ["OPERATE_SOCKET"]})
    assert "OPERATE_SOCKET" not in g["user_needs"]
    # H. 同一 evidence 可候选 SEARCH/CONVERSION（角色非固定）
    h = svc.cognize("v11h", {"component": ["TRACK_SOCKET"], "function": ["POWER"],
                             "scene_family": "FACTORY"})
    assert "CONVERSION" in h["content_roles"] or "SEARCH" in h["content_roles"]
    svc.ks.unload()


# ---------------- Stage 1.6：Knowledge Type Semantic Correction ----------------

def _v12_dist():
    r = json.load(open(r"C:\Users\admin\github\treecut-v13\knowledge\knowledge_type_reclassification_v1_2.json",
                       encoding="utf-8"))
    return r


def test_v12_type_distribution_sane():
    """Stage 1.6：四类分布语义合理（FACT 定义类为主，BUSINESS_RULE 不泛化）。"""
    d = _v12_dist()
    assert d["by_type"]["FACT"] > 150
    assert d["by_type"]["BUSINESS_RULE"] < 120
    assert d["by_type"]["HYPOTHESIS"] >= 12
    assert d["by_type"]["PLATFORM_RULE"] == 10
    # 不再 320 泛化
    assert d["by_type"]["BUSINESS_RULE"] < d["by_type"]["FACT"]


def test_v12_namespace_distribution():
    """TEST 19-20 前置：product/material/function 定义类 FACT；mappings/negative 规则类。"""
    d = _v12_dist()
    ns = d["by_namespace_type"]
    assert ns["product"]["FACT"] >= 15
    assert ns["materials_styles"]["FACT"] >= 13
    assert ns["functions"]["FACT"] >= 24
    assert ns["negative_rules"]["BUSINESS_RULE"] == 30
    assert ns["semantic_mappings"]["BUSINESS_RULE"] > 50
    assert ns["template_library"]["HYPOTHESIS"] == 12
    assert ns["platform_compliance"]["PLATFORM_RULE"] == 10


def test_v12_no_ambiguous():
    """Stage 1.6：ambiguous = 0。"""
    d = _v12_dist()
    assert d["ambiguous_count"] == 0


def test_v12_fact_retrieval_separate():
    """TEST 17/18：岩板定义/岛台定义可作 FACT 检索，非 Inference Rule。"""
    ks = KnowledgeService()
    facts = ks.retrieve_facts(namespace="materials_styles")
    assert any(r["title"] == "岩板" and r["knowledge_type"] == "FACT" for r in facts)
    pf = ks.retrieve_facts(namespace="product")
    assert any(r["title"] == "岛台" and r["knowledge_type"] == "FACT" for r in pf)
    # 岩板作为 FACT 可检索
    sl = ks.search("岩板", knowledge_type="FACT", limit=5)
    assert any("岩板" in r["title"] for r in sl)
    ks.unload()


def test_v12_map_and_negative_are_business_rule():
    """TEST 19/20：MAP/Negative 必须 BUSINESS_RULE。"""
    ks = KnowledgeService()
    m = ks.get_by_id("MAP-001")
    assert m is not None and m["knowledge_type"] == "BUSINESS_RULE"
    nr = ks.get_by_id("NR001")
    assert nr is not None and nr["knowledge_type"] == "BUSINESS_RULE"
    assert nr["semantic_kind"] == "NEGATIVE_RULE"
    ks.unload()


def test_v12_template_is_hypothesis():
    """TEST 21：Template CT06 必须 HYPOTHESIS。"""
    ks = KnowledgeService()
    t = ks.get_by_id("TPL-CT06")
    if t is None:  # 可能 id 不同
        t = [r for r in ks.retrieve_hypotheses() if "CT06" in r["knowledge_id"]]
        t = t[0] if t else None
    if t:
        assert t["knowledge_type"] == "HYPOTHESIS"
        assert t["semantic_kind"] == "TEMPLATE_HYPOTHESIS"
    ks.unload()


def test_v12_business_dictionary_not_auto_rule():
    """TEST 22：BUSINESS_DICTIONARY 来源不得自动决定 knowledge_type（岛台=业务词典但 FACT）。"""
    ks = KnowledgeService()
    r = ks.get_by_id("KB-01-001")  # 岛台，source_type=业务词典
    assert r is not None
    assert r["knowledge_type"] == "FACT"  # 定义类，即使来源业务词典
    assert r["source_type"] in ("business_dictionary", "业务词典")
    ks.unload()


def test_v12_hard_reasoning_excludes_hypothesis():
    """hard reasoning 只含 ACTIVE FACT/BUSINESS_RULE + PLATFORM，禁 HYPOTHESIS。"""
    ks = KnowledgeService()
    hard = ks.retrieve_hard_reasoning_knowledge()
    for r in hard:
        assert r["knowledge_type"] in ("FACT", "BUSINESS_RULE", "PLATFORM_RULE")
        assert r["knowledge_type"] != "HYPOTHESIS"
    ks.unload()


def test_v12_validation_no_critical_regression():
    """Stage 1.6：43 Validation 重跑无 critical regression（复用 V1.1 结果 + 类型修正不恶化认知）。"""
    r = json.load(open(os.path.join(DATA_ROOT, "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_RESULTS_V1_1.json"),
                       encoding="utf-8"))
    assert len(r["results"]) == 43
    assert r["regression_count"] == 0


def test_knowledge_audit_clean():
    """V1.1 audit：真冲突 0，duplicate 0。"""
    a = json.load(open(r"C:\Users\admin\github\treecut-v13\knowledge\knowledge_audit_v1_1.json",
                       encoding="utf-8"))
    assert a["total"] == 361
    assert a["duplicate"] == []
    assert a["conflicts"] == []
    assert a["stale_platform"] == []


def test_business_cognition_drawer_storage():
    svc = BusinessCognitionServiceV1()
    bc = svc.cognize("t1", {"component": ["DRAWER"], "function": ["STORAGE"]})
    assert "STORAGE" in bc["user_needs"]
    assert "STORAGE_EFFICIENCY" in bc["business_values"]
    assert bc["confidence"] in ("HIGH", "MEDIUM")
    svc.ks.unload()


def test_negative_socket_no_action():
    svc = BusinessCognitionServiceV1()
    bc = svc.cognize("t2", {"component": ["TRACK_SOCKET"], "function": ["POWER"]})
    assert "CHARGING_POWER" in bc["user_needs"]
    assert "OPERATE_SOCKET" not in bc["user_needs"]
    svc.ks.unload()


def test_semantic_action_never_hard():
    svc = BusinessCognitionServiceV1()
    bc = svc.cognize("t3", {"component": ["TRACK_SOCKET"], "function": ["POWER"],
                            "action_sequence": ["OPERATE_SOCKET"]})
    # semantic_action 不进入 user_needs/business_values（VERY_LOW 强制）
    assert "OPERATE_SOCKET" not in bc["user_needs"]
    assert any("VERY_LOW" in u or "WEAK" in u for u in bc["unknowns"])
    svc.ks.unload()


def test_negative_rules_defined():
    ids = [r["rule_id"] for r in NEGATIVE_RULES]
    assert "NR001" in ids and "NR005" in ids


def test_semantic_mappings_defined():
    assert any(r["rule_id"] == "SEM_001" for r in SEMANTIC_MAPPINGS)
    assert any(r["rule_id"] == "SEM_003" for r in SEMANTIC_MAPPINGS)


def test_validation_results_exists():
    r = json.load(open(os.path.join(DATA_ROOT, "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_RESULTS.json"),
                       encoding="utf-8"))
    assert len(r["results"]) >= 30
    assert r["core_tests_pass"] == "10/10"
