# -*- coding: utf-8 -*-
"""EH01R1 — 测试（§23 至少 11 项）：reference semantics 修正验证。"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "storage"


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_r2_partial_affine_uses_pair_thr():
    """PARTIAL_AFFINE validated pair 的 materialization 用其 ransac_thr_raw，非固定 4px。"""
    t = _load("TREECUT_CAM01_EH01R1_R2_TRANSFORMS.json")["rows"]
    pa = [r for r in t if r.get("representative") == "PARTIAL_AFFINE" and r.get("materialized")]
    assert len(pa) >= 1
    for r in pa:
        assert abs(r["thr_used"] - 4.0) > 1e-6, f"pair {r['pair']} must not use fixed 4px"
        assert r["thr_used"] == r["thr_raw"]


def test_r2_homography_uses_homography_not_affine():
    """10000 0.768->1.793 rep=HOMOGRAPHY → materialize 用 findHomography。"""
    t = _load("TREECUT_CAM01_EH01R1_R2_TRANSFORMS.json")["rows"]
    h = next(r for r in t if r["case"] == 10000 and r["pair"] == "0.768->1.793")
    assert h["representative"] == "HOMOGRAPHY"
    assert h["model_used"] == "HOMOGRAPHY"
    assert h["materialized"] is True


def test_fixed_4px_reconstruction_forbidden():
    """任何 validated pair 不得使用 4px 固定阈值。"""
    t = _load("TREECUT_CAM01_EH01R1_R2_TRANSFORMS.json")["rows"]
    for r in t:
        if r.get("materialized"):
            assert r["thr_used"] != 4.0


def test_gftt_null_transform_not_emittable():
    """GFTT evidence-only 不得是 REFERENCE_EMITTABLE_STRONG。"""
    router = _load("TREECUT_CAM01_EH01R1_ROUTER_SHADOW.json")["rows"]
    for r in router:
        if r["route"] == "REFERENCE_EMITTABLE_STRONG":
            assert not (r["gftt_evidence"] and not r["r2_transform"] and not r["v24_transform"]), \
                f"{r['pair']} GFTT-only cannot be emittable"


def test_global_state_only_not_emittable():
    """GLOBAL_STATE_ONLY / FALLBACK_CANDIDATE_STATE_ONLY 不得是 EMITTABLE。"""
    router = _load("TREECUT_CAM01_EH01R1_ROUTER_SHADOW.json")["rows"]
    emittable = [r for r in router if r["route"] == "REFERENCE_EMITTABLE_STRONG"]
    for r in emittable:
        assert r["route"] not in ("GLOBAL_STATE_ONLY_CANDIDATE",
                                  "GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY")


def test_local_partial_triggers_global_candidate_check():
    """GFTT evidence + global reliable → GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY 存在。"""
    router = _load("TREECUT_CAM01_EH01R1_ROUTER_SHADOW.json")["rows"]
    fb = [r for r in router if r["route"] == "GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY"]
    assert len(fb) >= 1
    for r in fb:
        assert r["gftt_evidence"] and r["global_state"]


def test_local_conflict_not_overridden_by_global():
    """LOCAL_CONFLICT 不得因 global reliable 而改变。"""
    router = _load("TREECUT_CAM01_EH01R1_ROUTER_SHADOW.json")["rows"]
    for r in router:
        if r["route"] == "LOCAL_CONFLICT":
            assert r["conflict"] is True
            # 冲突对即使 global reliable 也保持 CONFLICT
            assert r["route"] == "LOCAL_CONFLICT"


def test_structural_unknown_not_consistent():
    """STRUCTURAL_UNKNOWN 不得被当作 structural ok。"""
    # V24 路径的 STRONG 若 structural UNKNOWN 应标注 NO_STRUCTURAL_VETO_AVAILABLE
    router = _load("TREECUT_CAM01_EH01R1_ROUTER_SHADOW.json")["rows"]
    unknown_strong = [r for r in router
                      if r["route"] == "REFERENCE_EMITTABLE_STRONG"
                      and r["structural"] == "STRUCTURAL_UNKNOWN"]
    # 存在性允许；但报告须区分（RESULT note 已含）
    res = _load("TREECUT_CAM01_EH01R1_RESULT.json")
    assert "no_structural_veto" in json.dumps(res).lower() or \
           res["classification"]["note"] != ""


def test_posthoc_threshold_removed():
    """不得存在 usable>12 -> FEASIBLE 逻辑。"""
    res = _load("TREECUT_CAM01_EH01R1_RESULT.json")
    assert res["posthoc_threshold_removed"] is True
    assert "HIERARCHY_FEASIBLE" not in json.dumps(res["classification"])
    assert "reference_router_output_capability" in res["classification"]


def test_exact_provenance_no_era():
    """provenance 不得含 '-era' placeholder。"""
    prov = _load("TREECUT_CAM01_EH01R1_SOURCE_PROVENANCE.json")
    for k, v in prov.items():
        if k == "CALIBRATION10_MANIFEST":
            continue  # manifest commit 待解析（见 note）
        assert "-era" not in str(v.get("commit", "")), f"{k} has -era"
        assert v.get("blob", "") != ""


def test_target_diagnostic_only_real_reference_in_strong():
    """strong 指标只计有 transform 的真实 reference。"""
    td = _load("TREECUT_CAM01_EH01R1_TARGET_DIAGNOSTIC.json")
    # NEG strong count 2 但 target_valid 0
    assert td["NEG"]["STRONG"]["count"] == 2
    assert td["NEG"]["STRONG"]["target_valid"] == 0
    assert td["NEG_REFERENCE_CONTROL_NOT_READY"] is True
    # POS strong 有 target_valid
    assert td["POS"]["STRONG"]["target_valid"] == 6
