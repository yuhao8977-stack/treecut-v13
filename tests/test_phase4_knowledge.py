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


def test_knowledge_audit_clean():
    a = json.load(open(r"C:\Users\admin\github\treecut-v13\knowledge\knowledge_audit.json",
                       encoding="utf-8"))
    assert a["total"] == 186
    assert a["duplicate_ids"] == []
    assert a["conflicts"] == []
    assert a["no_source_count"] == 0
    assert a["platform_rule_missing_ttl"] == []


def test_knowledge_service_get_search():
    ks = KnowledgeService()
    r = ks.get_by_id("FUNCTION-0001")
    assert r is not None
    assert r["knowledge_type"] == "FACT"
    # platform 规则
    plat = ks.search("", namespace="platform_compliance", limit=50)
    assert len(plat) == 10
    for p in plat:
        assert p["knowledge_type"] == "PLATFORM_RULE"
        assert p["ttl_days"] == 30
    ks.unload()


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
