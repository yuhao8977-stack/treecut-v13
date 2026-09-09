# -*- coding: utf-8 -*-
"""VC1-ZS data-driven tests (repo files only; no audio)."""
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


def test_metrics_rows_complete():
    m = load("TREECUT_VC1_SAMPLE_METRICS.json")
    assert len(m["rows"]) == 12
    texts = {r["test"] for r in m["rows"]}
    assert texts == {"T1", "T2", "T3", "T4", "T5"}
    backends = {r["backend"] for r in m["rows"]}
    assert backends == {"melo", "gpt"}
    # second-reference check exists (T1 seg13)
    assert any(r["test"] == "T1" and r["ref"] == "seg13" for r in m["rows"])
    for r in m["rows"]:
        assert r["raw_sha256"] and r["eval_sha256"]
        assert "duration_s" in r["raw"] and "cer" in r


def test_fair_loudness_fields():
    m = load("TREECUT_VC1_SAMPLE_METRICS.json")
    assert "fair_loudness_check" in m and len(m["fair_loudness_check"]) == 12


def test_result_fields():
    r = load("TREECUT_VC1_RESULT.json")
    assert r["GPT_SOVITS_INSTALLED"] == "YES"
    assert r["ZERO_SHOT_GENERATED"] == "YES"
    assert r["FINE_TUNE_ALLOWED"] == "NO"
    assert r["PRODUCTION_INTEGRATION_ALLOWED"] == "NO"
    assert r["TREECUT_TTS_REPLACED"] == "NO"
    assert r["ZERO_SHOT_PASS"] in ("YES", "PARTIAL", "NO",
                                   "PENDING_HUMAN_BLIND_REVIEW")


def test_backend_manifest():
    b = load("TREECUT_VC1_BACKEND_MANIFEST.json")
    assert b["official_repo_url"].startswith("https://github.com/RVC-Boss")
    assert b["repo_commit"]
    assert len(b["weight_file_sha256"]) >= 4
    assert all(len(v) == 64 for v in b["weight_file_sha256"].values())


def test_evidence_index_hashes():
    idx = load("TREECUT_VC1_EVIDENCE_INDEX.json")
    assert idx["count"] == len(idx["entries"]) >= 3
    for e in idx["entries"]:
        p = OUT / e["path"]
        assert p.exists()
        assert e["sha256"] == sha256_file(p)


def test_no_audio_or_transcripts_in_repo_metrics():
    m = load("TREECUT_VC1_SAMPLE_METRICS.json")
    for r in m["rows"]:
        # repo metrics may include our own synthetic test text, never the
        # voice-owner reference transcripts
        assert not r["text"].startswith("另外就是您现在装修")
