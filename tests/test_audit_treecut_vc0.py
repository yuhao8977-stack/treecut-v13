# -*- coding: utf-8 -*-
"""VC0 data-driven tests — anonymous summary + hash manifest consistency
(no audio content in repo files)."""
import hashlib
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
LOCAL = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001")
SRC_SHA = "4f453ddfa046fe9b7d9f373d1f7a80c8fe9e16703dd95054bda0fb0cb58992e5"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_counts_and_durations():
    s = load("TREECUT_VC0_SEGMENTS_SUMMARY.json")
    assert s["dedup"]["raw_segment_count"] == 30
    assert s["dedup"]["duplicate_pair_count"] == 15
    assert s["dedup"]["kept_unique_count"] == 15
    assert 69.0 <= s["dedup"]["unique_speech_duration_s"] <= 76.0
    assert len(s["segments_anonymous"]) == 15


def test_no_transcript_text_in_repo():
    s = load("TREECUT_VC0_SEGMENTS_SUMMARY.json")
    for seg in s["segments_anonymous"]:
        assert "transcript" not in seg  # transcript text stays local only


def test_hash_manifest_consistent():
    hm = load("TREECUT_VC0_HASH_MANIFEST.json")
    assert hm["source_mp4_sha256"] == SRC_SHA
    assert hm["original_wav"] == sha256_file(LOCAL / "source_original_audio.wav")
    assert hm["working_wav"] == sha256_file(LOCAL / "source_working_24k.wav")
    assert len(hm["segments"]) == 15


def test_result_fields():
    r = load("TREECUT_VC0_RESULT.json")
    assert r["VOICE_OWNER_AUTHORIZED"] == "YES"
    assert r["UNIQUE_SEGMENT_COUNT"] == 15
    assert r["DUPLICATE_PAIR_COUNT"] == 15
    assert r["FINE_TUNE_ALLOWED"] == "NO"
    assert r["PRODUCTION_INTEGRATION_ALLOWED"] == "NO"
    assert r["ZERO_SHOT_A_B_COMPLETED"] in ("A_ONLY", "COMPLETED")
    assert r["SINGLE_SPEAKER_CONFIRMED"] in ("YES", "NO")


def test_decision_backends_not_installed_honest():
    d = load("TREECUT_VC0_BACKEND_DECISION.json")
    inst = d["backend_preflight"]["clone_backends_installed"]
    # environment truth: none of the clone packages importable now
    assert all(v is False for v in inst.values())
    assert d["ZERO_SHOT_A_B_COMPLETED"] == "A_ONLY"
    assert "PENDING_OFFLINE_INSTALL" in d["SELECTED_BACKEND"]
