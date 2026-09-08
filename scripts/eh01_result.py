# -*- coding: utf-8 -*-
"""EH01 final aggregation: RESULT + decision classification."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    mat = load("TREECUT_CAM01_EH01_EVIDENCE_MATRIX.json")
    router = load("TREECUT_CAM01_EH01_ROUTER_SHADOW.json")["rows"]
    tgt = load("TREECUT_CAM01_EH01_TARGET_DIAGNOSTIC.json")
    ag = load("TREECUT_CAM01_EH01_LOCAL_AGREEMENT.json")["rows"]
    gl = load("TREECUT_CAM01_EH01_GLOBAL_EVIDENCE.json")
    rc = mat["route_counts"]
    usable = mat["ROUTER_USABLE"]
    raw_union = mat["RAW_SOURCE_UNION"]
    # classification per §19
    r2_baseline = 8
    gain = usable - r2_baseline
    # no gate relaxation: usable derived strictly from historical gates + veto/conflict
    if usable > 12:
        cls = "HIERARCHY_FEASIBLE"
    elif usable <= 12:
        cls = "HIERARCHY_LOW_COVERAGE"
    else:
        cls = "HIERARCHY_BLOCKED"
    if gl.get("materialized") is not True:
        cls = "HIERARCHY_BLOCKED"
    next_cand = ("TEMPORAL_LEARNED_TRACKER" if cls == "HIERARCHY_LOW_COVERAGE"
                 else ("EH02_ROUTER_CALIBRATION" if cls == "HIERARCHY_FEASIBLE" else None))
    res = {"experiment": "CAM01_EH01_RESULT",
           "generated_at": "2026-09-08 (EH01)",
           "baseline": "main @ 8f84735",
           "pairs_36": mat["pairs_36"],
           "route_counts": rc,
           "LOCAL_STRONG": rc.get("ROUTE_LOCAL_STRONG", 0),
           "LOCAL_PARTIAL": rc.get("ROUTE_LOCAL_PARTIAL", 0),
           "LOCAL_CONFLICT": rc.get("ROUTE_UNSURE_CONFLICT", 0),
           "LOCAL_NONE": rc.get("ROUTE_UNSURE_NO_EVIDENCE", 0),
           "GLOBAL_RELIABLE_FALLBACK": rc.get("ROUTE_GLOBAL_RELIABLE", 0),
           "ROUTER_USABLE": usable,
           "RAW_SOURCE_UNION": raw_union,
           "case_coverage_9": mat["case_coverage_9"],
           "source_available_pairs": mat["source_available_pairs"],
           "source_unique_contribution": mat["source_unique_contribution"],
           "structural_corrected_8": mat["structural_corrected"],
           "local_agreement": {"pairs_compared": mat["local_agreement"]["pairs_compared"],
                               "agree": mat["local_agreement"]["agree"],
                               "conflict": mat["local_agreement"]["conflict"]},
           "global_evidence": {"materialized": gl["materialized"],
                               "reliable_among_36": gl["per_pair_states_among_36"]},
           "target_diagnostic": {"POS": {"usable": tgt["POS"]["usable"],
                                         "target_valid": tgt["POS"]["target_valid"]},
                                 "NEG": {"usable": tgt["NEG"]["usable"],
                                         "target_valid": tgt["NEG"]["target_valid"]}},
           "comparison_vs_r2": {"dense_r2_union": r2_baseline,
                                "router_gain": gain,
                                "gain_without_gate_relaxation": True},
           "eh01_classification": cls,
           "next_capability_candidate": next_cand,
           "no_action_verdict": True,
           "no_new_threshold": True,
           "note": "shadow routing only; not wired to GEOM/MMVV; role-blind until router frozen"}
    (OUT / "TREECUT_CAM01_EH01_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
