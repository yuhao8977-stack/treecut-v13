# -*- coding: utf-8 -*-
"""F0R1 data-driven tests — read real F0R1 evidence jsons + B1/B1R1 jsons."""
import hashlib
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
EXPECTED_IDS = {
    "caption_display_punctuation", "subtitle_occlusion_plate",
    "old_subtitle_detection", "caption_safe_zone", "source_gate",
    "beat_claim", "feedback_loop", "semantic_selection",
    "cam_mmvv_action", "plan_override_bypass",
}


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_ten_features_unique_complete():
    cg = load("TREECUT_B1R1_F0R1_CALL_GRAPH.json")
    ids = {f["id"] for f in cg["features"]}
    assert ids == EXPECTED_IDS
    assert len(ids) == 10


def test_closure_not_all_false_and_known_modules_reachable():
    cg = load("TREECUT_B1R1_F0R1_CALL_GRAPH.json")
    known = cg["known_production_modules_reachable"]
    assert known["treecut/application/production.py"] is True
    assert known["treecut/output/narration.py"] is True
    assert known["treecut/quality/publish_gates.py"] is True
    assert known["treecut/models/semantic_matching.py"] is True
    assert sum(known.values()) >= 4  # not all false


def test_never_implemented_worded_as_not_found_in_reachable_history():
    res = load("TREECUT_B1R1_F0R1_RESULT.json")
    for fid in ("caption_display_punctuation", "subtitle_occlusion_plate",
                "caption_safe_zone"):
        det = next(d for d in res["feature_details"] if d["id"] == fid)
        assert det["derived_classification"] == "NEVER_IMPLEMENTED"
        assert det["rule_id"].startswith("R_NEVER")
        assert "NOT_FOUND_IN_REACHABLE_GIT_HISTORY" in det["rule_reason"]


def test_disconnected_features_found_by_filename_not_content():
    cg = load("TREECUT_B1R1_F0R1_CALL_GRAPH.json")
    by = {f["id"]: f for f in cg["features"]}
    assert any("services/production_source.py" in f
               for f in by["source_gate"]["canonical_code_files"])
    assert any("services/mmvl_master_v1.py" in f
               for f in by["cam_mmvv_action"]["canonical_code_files"])
    assert any("services/production_qa.py" in f
               for f in by["old_subtitle_detection"]["canonical_code_files"])


def test_history_both_S_and_G_actually_ran():
    gh = load("TREECUT_B1R1_F0R1_GIT_HISTORY.json")
    for fe in gh["features"]:
        for kind in ("S", "G"):
            for token, rec in fe["history"][kind].items():
                assert rec["ran"] is True, (fe["id"], kind, token)


def test_classification_is_rule_derived_not_fixed_dict():
    res = load("TREECUT_B1R1_F0R1_RESULT.json")
    assert res["classifier_note"] and "NOT a fixed CLASS dict" in res["classifier_note"]
    for det in res["feature_details"]:
        assert det["rule_id"]
        assert "machine_inputs" in det
        assert "derived_classification" in det
    # manual adjudication is a separate field, never the only basis
    for det in res["feature_details"]:
        if det["manual_adjudication"] is not None:
            assert det["adjudication_reason"]


def test_plan_override_bypass_consistent_with_b1_b1r1_jsons():
    res = load("TREECUT_B1R1_F0R1_RESULT.json")
    b1 = load("TREECUT_B1_SUCCESS_REPRO.json")
    b1r1 = load("TREECUT_B1R1_SUCCESS_REPRO.json")
    assert b1["media"]["id"] == 32 and b1r1["media"]["id"] == 32
    # B1R1 json records semantic models directly
    assert (b1r1.get("semantic_models") or {}).get("bge_scored") == 0
    assert (b1r1.get("semantic_models") or {}).get("clip_scored") == 0
    # B1 json lacks the field; claim rests on runner plan_override code path
    sel = res["selection_route_bypass"]
    assert sel["SELECTION_ROUTE_BYPASSED"] is True
    assert sel["b1r1_bge_clip"] == [0, 0]
    assert "plan_override" in sel["b1_evidence"]
    assert res["SELECTION_ROUTE_BYPASSED"] == "YES"


def test_result_fields():
    res = load("TREECUT_B1R1_F0R1_RESULT.json")
    assert res["F0_SUBSTANTIVE_FINDINGS"] in ("ACCEPTED", "REVISED", "REJECTED")
    assert res["F0_EVIDENCE_CLOSURE"] in ("YES", "NO")
    assert res["OLD_FEATURES_DELETED_PROVEN"] == "NO"
    assert res["B2_READY"] == ("YES" if res["F0_EVIDENCE_CLOSURE"] == "YES"
                               else "NO")


def test_evidence_index_hashes():
    idx = load("TREECUT_B1R1_F0R1_EVIDENCE_INDEX.json")
    assert idx["count"] == len(idx["entries"]) >= 3
    for e in idx["entries"]:
        p = OUT / e["path"]
        assert p.exists(), e["path"]
        assert e["sha256"] == sha256_file(p), e["path"]
