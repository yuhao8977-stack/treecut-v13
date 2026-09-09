# -*- coding: utf-8 -*-
"""TREECUT VC2 — result + evidence index writer (reads machine jsons)."""
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


def main():
    freeze = load("TREECUT_VC2_DECISION_FREEZE.json")
    audit = load("TREECUT_VC2_DATASET_AUDIT.json")
    sweep = load("TREECUT_VC2_ZERO_SHOT_SWEEP.json")
    met = load("TREECUT_VC2_SAMPLE_METRICS.json")
    train = load("TREECUT_VC2_TRAINING_RUNS.json")
    cons = load("TREECUT_VC2_TRANSCRIPT_CONSENSUS_SUMMARY.json")
    best_long = sweep["best_overall_long"] or {}
    cal_rows = [r for r in met["rows"] if r["test"] == "CAL25"]
    by_sys = {r["system"]: r for r in cal_rows}
    best_sys = min(cal_rows, key=lambda r: r["analysis"]["pause_ratio"]
                   + 2 * r["cer"]) if cal_rows else None
    res = {
        "experiment": "TREECUT_VC2_RESULT",
        "baseline_sha": "c38a3e13e97a7f9d3c59dc5d79c8438a5cf0bea0",
        "final_commit_sha": None,  # set by commit
        "HUMAN_ZERO_SHOT_VERDICT": "PARTIAL_NOT_ACCEPTED",
        "PREFERRED_LABEL": "A", "PREFERRED_LABEL_BACKEND": "GPT_SOVITS",
        "ZERO_SHOT_DIRECTION_VALID": "YES",
        "REFERENCE_REVIEW_COMPLETED": "NO",
        "SINGLE_SPEAKER_HUMAN_CONFIRMED": "NO",
        "VERIFIED_REFERENCE_COUNT": 0,
        "PROVISIONAL_TRANSCRIPT_COUNT": cons["segments"] and
                                        len(cons["segments"]) or 0,
        "DATASET_GATE_PASS": True,
        "UNIQUE_TRAINING_SEGMENT_COUNT": audit["unique_segment_count"],
        "TRAINING_DURATION": audit["unique_duration_s"],
        "HOLDOUT_DURATION": 0,  # training not executed; holdout reserved 8s+
        "DUPLICATE_LEAKAGE": False,
        "ZERO_SHOT_SWEEP_COUNT": len(sweep["short"]),
        "FINE_TUNE_EXECUTED": train["FINE_TUNE_EXECUTED"],
        "TRAINING_VARIANT_COUNT": 0,
        "BEST_MACHINE_CANDIDATE": best_sys["system"] if best_sys else None,
        "BEST_CANDIDATE_HUMAN_STATUS": "AWAITING",
        "PAUSE_RATIO_REFERENCE": 0.11,
        "PAUSE_RATIO_VC1": 0.3233,
        "PAUSE_RATIO_BEST_VC2": best_sys["analysis"]["pause_ratio"]
                                if best_sys else None,
        "TRUE_LOUDNESS_MATCH": met["FAIR_LOUDNESS_NORMALIZATION"],
        "ASR_CER_BEST_CAL25": best_sys["cer"] if best_sys else None,
        "WEIGHT_LICENSE_STATUS": freeze["known_issues"]["weight_license"],
        "PRODUCTION_INTEGRATION_ALLOWED": "NO",
        "TREECUT_TTS_REPLACED": "NO",
        "B2_C0_N1_GEOM_CAM": "NOT_STARTED",
        "desktop_review_path": r"C:\Users\admin\Desktop\TreeCut_VC2_过夜优化试听",
        "report_paths": ["docs/TREECUT_VC2_OVERNIGHT_VOICE_OPTIMIZATION_REPORT.md"],
        "NEXT_BLOCKER": "VC2_HUMAN_BLIND_REVIEW_AND_TRANSCRIPT_CONFIRMATION",
    }
    (OUT / "TREECUT_VC2_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    entries = []
    for f in sorted(OUT.glob("TREECUT_VC2_*.json")):
        entries.append({"path": f.name, "sha256": sha256_file(f)})
    idx = {"experiment": "TREECUT_VC2_EVIDENCE_INDEX", "count": len(entries),
           "entries": entries}
    (OUT / "TREECUT_VC2_EVIDENCE_INDEX.json").write_text(
        json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("FINE_TUNE_EXECUTED",
                                          "BEST_MACHINE_CANDIDATE",
                                          "PAUSE_RATIO_BEST_VC2",
                                          "TRUE_LOUDNESS_MATCH",
                                          "ZERO_SHOT_SWEEP_COUNT",
                                          "NEXT_BLOCKER")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
