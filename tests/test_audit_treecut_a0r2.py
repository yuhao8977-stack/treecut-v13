# -*- coding: utf-8 -*-
"""A0 R2 data-driven tests — read REAL machine evidence files (provenance /
preflight / test runs / tts ab / historical / corrected maps / result), never
RESULT self-strings as proof of facts the files themselves establish."""
import hashlib
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def sha256_file(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_preflight_head_and_clean():
    p = load("TREECUT_A0R2_RAW_PREFLIGHT.json")
    assert p["head"] == "02c1fc8abb4f28ec45745bb4e484a4efa0bb5bef"
    assert p["head_eq_origin"] is True
    assert p["worktree_clean"] is True
    assert p["branch"] == "main"


def test_source_provenance_self_contained_false_with_causes():
    s = load("TREECUT_A0R2_SOURCE_PROVENANCE.json")
    assert s["baseline_self_contained"] is False
    assert s["match_counts"]["NOT_IN_HEAD"] == 12
    assert s["match_counts"]["E_CONTENT_EQ_HEAD"] == 85
    assert s["match_counts"]["E_CONTENT_DIFFERS_HEAD"] == 4
    # all NOT_IN_HEAD live under the gitignored models package
    for rel in s["e_files_not_in_head"]:
        assert rel.startswith("treecut/models/"), rel
    assert s["gitignore_models_pattern"] == "models/"
    # the two files the architect flagged are NOT in HEAD
    for key in ("tts_local.py", "vision_florence.py"):
        row = s["explicit_check"][key]
        assert row["tracked"] is False
        assert row["match"] == "NOT_IN_HEAD"


def test_beat_claim_search_no_production_layer():
    b = load("TREECUT_A0R2_BEAT_CLAIM_SEARCH.json")
    assert b["target_beat_layer_in_production"] == "NOT_FOUND"
    assert b["production_import_closure"]["closure_module_count"] >= 1
    assert b["production_import_closure"]["beat_or_claim_modules_in_closure"] == []
    # repo has research beat/claim code, E running src does not
    assert len(b["repo_worktree_src"]["module_name_hits"]) >= 1
    assert len(b["E_running_src"]["module_name_hits"]) == 0


def test_historical_canonical_unique_input_one():
    c = load("TREECUT_A0R2_HISTORICAL_CANONICAL_INPUT.json")
    hashes = {v["canonical_hash"] for v in c.values() if "canonical_hash" in v}
    assert len(hashes) == 1  # 2 success projects = same input rerun
    for v in c.values():
        if "canonical" in v:
            assert len(v["canonical"]["narration"]) > 40  # full text, not 40-char prefix


def test_historical_relpath_manifest_keys():
    m = load("TREECUT_A0R2_HISTORICAL_RELPATH_MANIFEST.json")
    proj = [k for k in m if k.startswith("20260806_")]
    assert len(proj) == 4
    all_keys = [f for v in m.values() for f in v]
    # keys are project-relative paths (contain the project id as first segment)
    assert any(f.endswith("TreeCut_成片.mp4") for f in all_keys)
    for v in m.values():
        for f, e in v.items():
            assert e["exists"] is True
            assert len(e["sha256"]) == 64


def test_tts_ab_verdict_confirmed():
    t = load("TREECUT_A0R2_TTS_AB_RESULT.json")
    assert t["A"]["rc"] != 0
    assert "date.fst" in (t["A"]["error"] or "")
    assert t["B"]["rc"] == 0
    assert t["B"]["wav"]["duration_s"] > 0
    assert t["copy_identical"] is True
    assert t["verdict"] == "TTS_NON_ASCII_ROOT_CAUSE=CONFIRMED"


def test_raw_test_runs_machine_counts():
    r = load("TREECUT_A0R2_RAW_TEST_RUNS.json")
    sysrun = r["runs"]["system_full"]
    assert sysrun["product_failures"] == 12  # 7 GPU env + 5 isolation (audit self-tests excluded)
    assert sysrun["tests"] > 500
    # classification: exactly the 12 product failures, no audit self-tests
    assert set(r["per_failure_classification"]) == {
        "tests.test_stage2_vision::" + n for n in (
            "test_gpu_runtime_detection", "test_gpu_real_inference_smoke",
            "test_model_unload_reload", "test_vram_leak_stable",
            "test_static_inference_fields", "test_multilabel_output",
            "test_policy_mode_routing_final")} | {
        "tests.test_source_audit_r11::" + n for n in (
            "test_workbench_replace_invalid_candidate_400",
            "test_workbench_trim_preserves_action_window",
            "test_workbench_local_qa_caption_size_honest")} | {
        "tests.test_stage3_mini_v2::test_v2_smoke_on_sample",
        "tests.test_stage3_model_dev::test_people_output_structure"}
    counts = r["classification_counts"]
    assert counts == {"ENVIRONMENT_MISMATCH": 7,
                      "TEST_ISOLATION_DEFECT": 2,
                      "TEST_ISOLATION_DEFECT_COLLECTION": 3}
    for v in r["per_failure_classification"].values():
        if "TEST_ISOLATION" in v["classification"]:
            assert v["isolated_pass"] is True          # all 5 isolation pass alone
            if v["classification"] == "TEST_ISOLATION_DEFECT":
                assert v["order_reorder_pass"] is True  # passes when moved first
            else:
                assert v["order_reorder_pass"] is False  # collection: fails any position
    assert "runtime_full" in r["runs"]
    assert r["runs"]["runtime_full"]["product_failures"] == 3  # r11 collection only


def test_corrected_matrix_shadow_semantics():
    m = load("TREECUT_A0R2_CORRECTED_CAPABILITY_MATRIX.json")
    by = {i["capability"]: i for i in m["items"]}
    for cap in ("B2_ASR", "B3_OCR", "B4_vision", "segment_level"):
        assert "DATA_PRESENT_SHADOW" in by[cap]["level"], cap
        assert by[cap]["production_connected"] is False
    assert by["D2_script_beat_claim"]["level"] == "NOT_FOUND_IN_PRODUCTION"
    assert by["X1_cam_eh"]["production_connected"] is False


def test_corrected_gap_split_and_counts():
    g = load("TREECUT_A0R2_CORRECTED_GAP_MAP.json")
    rc = {x["id"] for x in g["ROOT_CAUSE"]}
    gate = {x["id"] for x in g["ACCEPTANCE_GATE"]}
    assert "RC_tts_non_ascii_model_path" in rc
    assert "RC_baseline_not_self_contained" in rc
    assert "GATE_current_e2e_to_final" in gate
    for miss in ("human_review_replace", "old_subtitle_policy", "segment_bridge",
                 "9x16_multishot", "candidate_generation"):
        assert any(miss in x for x in gate), miss
    assert "current_e2e_not_proven" not in rc  # gate, not independent root cause
    assert g["counts"]["ROOT_CAUSE"] == len(g["ROOT_CAUSE"])
    assert g["counts"]["ACCEPTANCE_GATE"] == len(g["ACCEPTANCE_GATE"])


def test_current_reproduction_consistent():
    r = load("TREECUT_A0R2_CURRENT_REPRODUCTION.json")
    if r.get("run") == "NONE":
        return  # no approved run: nothing to assert beyond documented absence
    assert r["run_id"]
    if r["PASS"]:
        assert r["status_state"] == "success"
        from pathlib import Path as P
        assert P(r["final_mp4"]).is_file()
        assert P(r["draft"]).is_dir()
        assert r["imported_module_source_sha"]


def test_result_consistent_with_evidence():
    res = load("TREECUT_A0R2_RESULT.json")
    prov = load("TREECUT_A0R2_SOURCE_PROVENANCE.json")
    tts = load("TREECUT_A0R2_TTS_AB_RESULT.json")
    assert res["BASELINE_SELF_CONTAINED"] == prov["baseline_self_contained"]
    assert res["TTS_NON_ASCII_ROOT_CAUSE"] == tts["verdict"]
    assert res["TRACK_A_ALLOWED"] == "NO"
    assert res["N1_GEOM_CAM_PRODUCTION"] == "NO"
    assert res["A0R1_EVIDENCE_CLOSURE"] == "NO"
    assert res["head_eq_origin"] is True


def test_evidence_index_hashes_match():
    idx = load("TREECUT_A0R2_EVIDENCE_INDEX.json")
    assert idx["count"] == len(idx["entries"])
    for e in idx["entries"]:
        p = OUT / e["path"]
        assert p.exists(), e["path"]
        assert e["sha256"] == sha256_file(p), e["path"]
