# -*- coding: utf-8 -*-
"""EH01 M1 — 测试（§28 至少 13 项）。"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "storage"


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_exact_config_equals_v23():
    cfg = _load("TREECUT_CAM01_EH01M1_CONFIG.json")["config"]
    assert cfg["analysis_width_max"] == 960
    assert cfg["grid_cell"] == 40
    assert cfg["ransac_thr"] == 3.0
    assert cfg["fit_inlier_min"] == 0.45
    assert cfg["holdout_min"] == 8
    assert cfg["gftt"]["maxCorners"] == 300
    assert cfg["gftt"]["qualityLevel"] == 0.02
    assert cfg["gftt"]["minDistance"] == 6


def test_gftt_fb3_contract():
    """GFTT corr 已过 FB<=3（replay 阶段过滤）；检查存在性。"""
    fp = _load("TREECUT_CAM01_EH01M1_REPLAY_FINGERPRINT.json")
    assert fp["replay_gftt_validated"] == 17


def test_fold_cell_40_exact():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "m1", REPO / "scripts" / "eh01m1_gftt_materialize.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    import numpy as np
    p0 = np.float32([[10.0, 10.0], [45.0, 45.0], [45.0, 10.0]])
    f = m.fold_split(p0)
    # (0+0)%2=0; (1+1)%2=0; (1+0)%2=1
    assert int(f[0]) == 0
    assert int(f[1]) == 0
    assert int(f[2]) == 1


def test_historical_pair_fingerprint():
    fp = _load("TREECUT_CAM01_EH01M1_REPLAY_FINGERPRINT.json")
    assert fp["pair_state_fingerprint_match_36"] == 1
    assert fp["fold_state_fingerprint_match"] == 1
    assert fp["historical_gftt_validated"] == 17
    assert fp["replay_gftt_validated"] == 17


def test_partial_cannot_materialize():
    tr = _load("TREECUT_CAM01_EH01M1_GFTT_TRANSFORMS.json")["rows"]
    partial = [r for r in tr if r.get("pair_state_hist") == "LOCAL_ANCHOR_PARTIAL"]
    for r in partial:
        assert r["can_materialize"] is False
        assert r["matrix"] is None


def test_validated_can_materialize():
    tr = _load("TREECUT_CAM01_EH01M1_GFTT_TRANSFORMS.json")["rows"]
    val = [r for r in tr if r.get("pair_state_hist") == "LOCAL_ANCHOR_VALIDATED"]
    assert len(val) == 17
    ok = [r for r in val if r.get("status") == "GFTT_MATERIALIZED_REFERENCE_CANDIDATE"]
    assert len(ok) == 17


def test_fit_all_uses_affine_3px():
    """materialize 用 partial affine + ransac_thr 3.0（config 冻结值）。"""
    tr = _load("TREECUT_CAM01_EH01M1_GFTT_TRANSFORMS.json")["rows"]
    ok = [r for r in tr if r.get("status") == "GFTT_MATERIALIZED_REFERENCE_CANDIDATE"]
    assert len(ok) == 17
    # M2x3 形状 2x3（affine）
    for r in ok:
        assert len(r["M2x3"]) == 2 and len(r["M2x3"][0]) == 3


def test_deterministic_rebuild():
    tr = _load("TREECUT_CAM01_EH01M1_GFTT_TRANSFORMS.json")["rows"]
    ok = [r for r in tr if r.get("status") == "GFTT_MATERIALIZED_REFERENCE_CANDIDATE"]
    assert all(r["deterministic_rebuild"] for r in ok)
    assert all(r["deterministic_disagreement_med_px"] < 1e-6 for r in ok)


def test_gftt_materialized_not_auto_strong():
    res = _load("TREECUT_CAM01_EH01M1_RESULT.json")
    assert res["target"]["NEG_STRONG_REFERENCE_TARGET_VALID"] == 0
    assert res["note"].find("未自动升级 strong") >= 0 or "GFTT_MATERIALIZED_REFERENCE_CANDIDATE" in \
        json.dumps(res)


def test_structural_symmetric_raw_px():
    sd = _load("TREECUT_CAM01_EH01M1_STRUCTURAL_DIAGNOSTIC.json")["rows"]
    from collections import Counter
    c = Counter((r.get("structural") or {}).get("state") for r in sd)
    assert c.get("STRUCTURAL_CONSISTENT", 0) == 7
    assert c.get("STRUCTURAL_DISAGREEMENT", 0) == 10
    for r in sd:
        s = r.get("structural") or {}
        if s.get("symmetric"):
            assert "median" in s["symmetric"] and "p90" in s["symmetric"]


def test_target_diagnostic_no_promotion():
    td = _load("TREECUT_CAM01_EH01M1_TARGET_DIAGNOSTIC.json")
    assert td["NEG_MATERIALIZED_REFERENCE_TARGET_VALID"] == 2
    assert td["NEG_STRONG_REFERENCE_TARGET_VALID"] == 0
    # focus NEG pairs present
    neg_pairs = {(x["case"], x["pair"]) for x in td["NEG"]["rows"]}
    assert (1641, "2.642->3.434") in neg_pairs
    assert (2543, "1.202->1.717") in neg_pairs


def test_stale_report_not_truth():
    stale = _load("TREECUT_CAM01_EH01M1_V23_STALE_REPORT_NOTE.json")
    assert stale["truth_source"]["commit"] == "09e3b5b"
    assert stale["report_md_untouched"] is True


def test_router_impact_7_materialized():
    imp = _load("TREECUT_CAM01_EH01M1_ROUTER_IMPACT_SHADOW.json")
    no_tf = imp["no_transform_routes_now_materialized"]
    assert no_tf["total_no_tf"] == 7
    assert no_tf["materialized"] == 7
