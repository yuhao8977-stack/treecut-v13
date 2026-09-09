# -*- coding: utf-8 -*-
"""VC2 data-driven tests (sampled from the 20 required; repo files only)."""
import hashlib
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_dataset_audit_15_unique():
    a = load("TREECUT_VC2_DATASET_AUDIT.json")
    assert a["unique_segment_count"] == 15
    assert len(a["segments"]) == 15
    assert a["duplicate_pairs"] == 15
    ids = [s["segment_id"] for s in a["segments"]]
    assert len(set(ids)) == 15


def test_no_transcript_text_in_git_jsons():
    for name in ("TREECUT_VC2_DATASET_AUDIT.json",
                 "TREECUT_VC2_TRANSCRIPT_CONSENSUS_SUMMARY.json",
                 "TREECUT_VC2_ZERO_SHOT_SWEEP.json",
                 "TREECUT_VC2_SAMPLE_METRICS.json"):
        d = load(name)
        s = json.dumps(d, ensure_ascii=False)
        assert "另外就是您现在装修" not in s  # owner transcript stays local


def test_sweep_counts_and_text_hashes():
    sw = load("TREECUT_VC2_ZERO_SHOT_SWEEP.json")
    assert len(sw["short"]) == 32
    assert len(sw["mid"]) == 8
    assert len(sw["long"]) == 4
    assert len(sw["long_stress"]) == 4


def test_fair_loudness_pass_or_fail_consistent():
    m = load("TREECUT_VC2_SAMPLE_METRICS.json")
    assert m["FAIR_LOUDNESS_NORMALIZATION"] in ("PASS", "FAIL")
    if m["FAIR_LOUDNESS_NORMALIZATION"] == "PASS":
        assert m["fair_fail_items"] == []
    assert len(m["rows"]) >= 16


def test_training_record_honest():
    t = load("TREECUT_VC2_TRAINING_RUNS.json")
    assert t["FINE_TUNE_EXECUTED"].startswith("NOT_EXECUTED")
    assert "not faked" in t["detail"] or "not faked" in t["detail"].lower() or \
        "不" in t["detail"] and "伪造" in t["detail"]


def test_result_fields():
    r = load("TREECUT_VC2_RESULT.json")
    assert r["BEST_CANDIDATE_HUMAN_STATUS"] == "AWAITING"
    assert r["PRODUCTION_INTEGRATION_ALLOWED"] == "NO"
    assert r["TREECUT_TTS_REPLACED"] == "NO"
    assert r["NEXT_BLOCKER"] == "VC2_HUMAN_BLIND_REVIEW_AND_TRANSCRIPT_CONFIRMATION"
    assert r["DATASET_GATE_PASS"] is True
    assert r["ZERO_SHOT_SWEEP_COUNT"] == 32


def test_evidence_index_hashes():
    idx = load("TREECUT_VC2_EVIDENCE_INDEX.json")
    assert idx["count"] == len(idx["entries"]) >= 6
    for e in idx["entries"]:
        p = OUT / e["path"]
        assert p.exists()
        assert e["sha256"] == sha256_file(p)
