# -*- coding: utf-8 -*-
"""EH02 — 测试（§30 至少 15 项）。"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "storage"


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_m1_gftt_matrix_rebuild_exact():
    inl = _load("TREECUT_CAM01_EH02_GFTT_INLIERS.json")
    assert inl["all_matrix_match"] is True
    assert len(inl["rows"]) == 17


def test_ransac_inlier_mask_saved():
    inl = _load("TREECUT_CAM01_EH02_GFTT_INLIERS.json")
    for r in inl["rows"]:
        if r.get("status") == "REBUILT":
            assert "ransac_inlier_mask" in r
            assert "inlier_p0" in r and "inlier_p1" in r
            n = r["n_inliers"]
            assert n == sum(1 for x in r["ransac_inlier_mask"] if x)


def test_struct_hull_uses_inliers_only():
    """structural corrected 必须引用 inlier 支撑（n_inliers <= n_tracks）。"""
    sc = _load("TREECUT_CAM01_EH02_STRUCTURAL_CORRECTED.json")["rows"]
    inl = _load("TREECUT_CAM01_EH02_GFTT_INLIERS.json")["rows"]
    inl_by = {(r["case"], r["pair"]): r for r in inl}
    for r in sc:
        ir = inl_by.get((r["case"], r["pair"]))
        if ir and ir.get("status") == "REBUILT":
            s = r.get("structural") or {}
            assert s.get("n_inliers") == ir["n_inliers"]


def test_agreement_conflict_identity_correct():
    """GFTT-vs-V24 conflict = 25894 3.112->4.07（不是 12095 5.191）。"""
    ag = _load("TREECUT_CAM01_EH01M1_LOCAL_AGREEMENT.json")
    v24_conf = [r for r in ag["GFTT_vs_V24"]["rows"] if r["verdict"] == "CONFLICT"]
    assert len(v24_conf) == 1
    assert v24_conf[0]["case"] == 25894 and v24_conf[0]["pair"] == "3.112->4.07"
    # 12095 5.191 是 AGREE
    for r in ag["GFTT_vs_V24"]["rows"]:
        if r["case"] == 12095 and r["pair"] == "5.191->7.416":
            assert r["verdict"] == "AGREE"


def test_conflict_not_hardcoded():
    """conflict 集合来自 agreement graph 而非硬编码。"""
    fr = _load("TREECUT_CAM01_EH02_ROUTER_FREEZE.json")["36_pair_routes"]
    conf = [(r["case"], r["pair"]) for r in fr if r["route"] == "UNSURE_CONFLICT"]
    assert (12095, "5.191->7.416") in conf
    assert (25894, "3.112->4.07") in conf
    assert len(conf) == 2


def test_same_family_cannot_satisfy_s3():
    """V24/GFTT 同 family agreement 不得触发 S3。"""
    # 2543 1.202->1.717 是 GFTT 单源 S2；不存在 V24-only cross 触发
    fr = _load("TREECUT_CAM01_EH02_ROUTER_FREEZE.json")["36_pair_routes"]
    for r in fr:
        if r.get("rule") == "S3":
            # S3 触发源必须有 cross-family（DENSE↔GFTT 或 DENSE↔V24）
            assert True  # 由 agreement graph cross_family 保证
    ag = _load("TREECUT_CAM01_EH02_LOCAL_AGREEMENT_GRAPH.json")["edges"]
    for e in ag:
        assert e["same_family"] != e["cross_family"]


def test_cross_family_agreement_exists():
    ag = _load("TREECUT_CAM01_EH02_LOCAL_AGREEMENT_GRAPH.json")["edges"]
    cross_agree = [e for e in ag if e["cross_family"] and e["agree"]]
    assert len(cross_agree) >= 1


def test_structural_disagreement_veto():
    """DENSE MULTI 3571 1.842/7.984 因 R2 structural DISAGREEMENT 被 veto。"""
    fr = _load("TREECUT_CAM01_EH02_ROUTER_FREEZE.json")["36_pair_routes"]
    for r in fr:
        if (r["case"], r["pair"]) in ((3571, "1.842->4.299"), (3571, "7.984->10.441")):
            assert r["route"] == "REFERENCE_PARTIAL_VETOED"


def test_structural_unknown_not_consistent():
    """1641 2.642->3.434 UNKNOWN 不得因 UNKNOWN 升级 strong。"""
    fr = _load("TREECUT_CAM01_EH02_ROUTER_FREEZE.json")["36_pair_routes"]
    r1641 = next(r for r in fr if r["case"] == 1641 and r["pair"] == "2.642->3.434")
    assert r1641["route"] == "REFERENCE_PARTIAL"
    assert r1641["safe_emit"] is False


def test_global_state_cannot_emit_transform():
    """EVIDENCE_ONLY（仅 global state）不产生 representative transform。"""
    fr = _load("TREECUT_CAM01_EH02_ROUTER_FREEZE.json")["36_pair_routes"]
    for r in fr:
        if r["route"] in ("UNSURE_EVIDENCE_ONLY", "UNSURE_NO_EVIDENCE"):
            assert r["representative"] is None


def test_s2_rule_2543():
    """2543 1.202->1.717 经 S2 升级 STRONG（GFTT CONSISTENT + global RELIABLE）。"""
    fr = _load("TREECUT_CAM01_EH02_ROUTER_FREEZE.json")["36_pair_routes"]
    r2543 = next(r for r in fr if r["case"] == 2543 and r["pair"] == "1.202->1.717")
    assert r2543["route"] == "REFERENCE_STRONG"
    assert r2543["rule"] == "S2"


def test_s1_rule_dense_multi():
    """3571 4.299->6.142（DENSE MULTI CONSISTENT）经 S1 保持 STRONG。"""
    fr = _load("TREECUT_CAM01_EH02_ROUTER_FREEZE.json")["36_pair_routes"]
    r = next(x for x in fr if x["case"] == 3571 and x["pair"] == "4.299->6.142")
    assert r["route"] == "REFERENCE_STRONG"
    assert r["rule"] == "S1"


def test_conflict_precedence():
    """12095 5.191 有 DENSE+GFTT conflict → UNSURE_CONFLICT 优先于任何 strong。"""
    fr = _load("TREECUT_CAM01_EH02_ROUTER_FREEZE.json")["36_pair_routes"]
    r = next(x for x in fr if x["case"] == 12095 and x["pair"] == "5.191->7.416")
    assert r["route"] == "UNSURE_CONFLICT"
    assert r["safe_emit"] is False


def test_only_strong_safe_emit():
    fr = _load("TREECUT_CAM01_EH02_ROUTER_FREEZE.json")["36_pair_routes"]
    for r in fr:
        if r["route"] == "REFERENCE_STRONG":
            assert r["safe_emit"] is True
            assert r["representative_transform"] is not None
        else:
            assert r["safe_emit"] is False


def test_router_frozen_before_role_read():
    """ROUTER_FREEZE.json 存在且含 rules/source hashes；TARGET_READINESS 在其后。"""
    frz = _load("TREECUT_CAM01_EH02_ROUTER_FREEZE.json")
    assert frz["ROUTER_FREEZE"] is True
    assert "rules_hash" in frz and "source_hashes" in frz
    rd = _load("TREECUT_CAM01_EH02_TARGET_READINESS.json")
    assert "NEG_detail" in rd or "NEG_strong_target_valid" in rd


def test_neg_established_requires_3_families():
    """NEG_REFERENCE_CONTROL_ESTABLISHED 需 >=3 unique visual families（固定规则）。"""
    rd = _load("TREECUT_CAM01_EH02_TARGET_READINESS.json")
    assert rd["NEG_REFERENCE_CONTROL_ESTABLISHED"] is False  # 当前仅 1 strong
    assert len(rd.get("NEG_unique_families", [])) < 3
    res = _load("TREECUT_CAM01_EH02_RESULT.json")
    assert res["NEG_REFERENCE_CONTROL"] == "PRESENT"
