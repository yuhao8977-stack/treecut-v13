# -*- coding: utf-8 -*-
"""VC3 B-redo tests: deterministic separation mapping + ambiguity regression."""
import hashlib
import importlib.util
import json
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
REDO = REPO / "scripts" / "audit_treecut_vc3_stageB_redo.py"


def load(n):
    return json.loads((OUT / n).read_text(encoding="utf-8"))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _redo_module():
    spec = importlib.util.spec_from_file_location("vc3redo", REDO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_18_rows_one_to_one():
    a = load("TREECUT_VC3_SEPARATION_AUDIT_R1.json")
    rows = [r for r in a["rows"] if r.get("status") == "OK"]
    assert a["rows_ok"] == 18 == len(rows)
    assert a["mapping_one_to_one_ok"] is True
    assert a["sha_unique_per_model"] is True
    keys = {(r["model"], r["source_id"]) for r in rows}
    assert len(keys) == 18


def test_sha_read_from_disk_matches_metrics_row():
    a = load("TREECUT_VC3_SEPARATION_AUDIT_R1.json")
    for r in a["rows"]:
        if r.get("status") != "OK":
            continue
        p = Path(r["canonical_path"])
        assert p.is_file()
        assert sha256_file(p) == r["sha256"]
        assert r["duration_consistent"] is True
        assert r["samplerate_consistent"] is True


def test_thresholds_and_music_residual_definition():
    a = load("TREECUT_VC3_SEPARATION_AUDIT_R1.json")
    t = a["thresholds"]
    assert t["music_residual_low_band_ratio_max"] == 0.25
    assert t["clipping_ratio_max"] == 1e-5
    assert t["speech_band_ratio_min"] == 0.45
    assert "MUSIC_RESIDUAL_FAIL_IN_TRAIN=0" in a["music_residual_definition"]


def test_high_pollution_sources_flagged_not_forced():
    a = load("TREECUT_VC3_SEPARATION_AUDIT_R1.json")
    need = set(a["sources_requiring_additional_model"])
    assert need == {"1f9c445a28736942cfd84d19ffc87293",
                    "3bad5e51a7e03bf91db9ea8192cf1044",
                    "4f8a6f3b4160ef49d5cf0135570b762d",
                    "67351bcb8b7d6de001cbc2d4235a559d"}
    for sid in need:
        src = a["per_source"][sid]
        assert src["selected"] is None
        assert src["selection_status"].startswith("SOURCE_REQUIRES_ADDITIONAL")


def test_no_rglob_in_output_resolution_and_ambiguous_dir_regression(tmp_path):
    src = REDO.read_text(encoding="utf-8")
    assert ".rglob(" not in src  # no recursive fallback lookup anywhere
    mod = _redo_module()
    sep = tmp_path / "02_separated_vocals"
    # two tracks, same file name vocals.wav (the historical ambiguity)
    for track in ("AAA.master48k24", "BBB.master48k24"):
        d = sep / "htdemucs" / track
        d.mkdir(parents=True)
        (d / "vocals.wav").write_bytes(track.encode())
    mod.SEP = sep
    p_a = mod.native_path("htdemucs", "AAA.master48k24")
    p_b = mod.native_path("htdemucs", "BBB.master48k24")
    assert p_a.name == "vocals.wav" and p_b.name == "vocals.wav"
    assert "AAA" in str(p_a) and "BBB" not in str(p_a)
    assert "BBB" in str(p_b) and "AAA" not in str(p_b)
    assert p_a.read_bytes() == b"AAA.master48k24"
    assert p_b.read_bytes() == b"BBB.master48k24"


def test_invalid_history_preserved():
    a = load("TREECUT_VC3_SEPARATION_AUDIT.json")
    assert a["status"] == "INVALID_SELECTION_PATH_RESOLUTION_BUG"
    b = load("TREECUT_VC3_SEPARATION_AUDIT_R1.json")
    assert "INVALID_SELECTION_PATH_RESOLUTION_BUG" in b["supersedes"]
