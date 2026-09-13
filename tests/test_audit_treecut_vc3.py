# -*- coding: utf-8 -*-
"""VC3 stage-A data-driven tests (source manifest / freeze / masters)."""
import hashlib
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def load(n):
    return json.loads((OUT / n).read_text(encoding="utf-8"))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def test_nine_sources_found_and_duration():
    m = load("TREECUT_VC3_SOURCE_MANIFEST.json")
    assert m["file_count"] == 9
    assert abs(m["raw_total_audio_duration_s"] - 539.5) <= 1.0
    assert len({f["sha256"] for f in m["files"]}) == 9


def test_freeze_fields():
    f = load("TREECUT_VC3_DECISION_FREEZE.json")
    for k in ("SAME_FEMALE_OWNER_CONFIRMED", "SAME_AS_VOICE_001_TARGET",
              "AUDIO_ONLY_POLICY", "ZERO_SHOT_FIRST",
              "FINE_TUNE_CONDITIONAL_ONLY", "PRODUCTION_INTEGRATION_ALLOWED",
              "TREECUT_TTS_REPLACED"):
        assert k in f
    assert f["PRODUCTION_INTEGRATION_ALLOWED"] == "NO"
    assert f["TREECUT_TTS_REPLACED"] == "NO"
    assert f["BACKGROUND_MUSIC_ALLOWED_FOR_MODEL"] == "NO"


def test_masters_forensics_present():
    a = load("TREECUT_VC3_DATASET_AUDIT.json")
    assert a["master_count"] == 9
    for m in a["masters"]:
        assert m["duration_s"] > 20
        assert m["sha256"]
        assert "low_band_energy_ratio" in m and "f0_median_hz" in m


def test_no_audio_or_transcripts_in_repo():
    for n in ("TREECUT_VC3_SOURCE_MANIFEST.json",
              "TREECUT_VC3_DATASET_AUDIT.json"):
        s = (OUT / n).read_text(encoding="utf-8")
        assert "另外就是您现在装修" not in s
