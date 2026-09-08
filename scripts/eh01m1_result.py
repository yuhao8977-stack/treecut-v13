# -*- coding: utf-8 -*-
"""EH01 M1 final: stale report note + RESULT + decision. §24-§26."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    # ===== §24 stale report note =====
    stale = {"note": "V23 REPORT.md (docs/TREECUT_CAM01_V23_FEATURE_BAKEOFF_REPORT.md) 困难案例文字与 "
                    "METHOD_MATRIX.json 存在差异；METHOD_MATRIX 为 replay truth source",
             "truth_source": {"artifact": "TREECUT_CAM01_V23_METHOD_MATRIX.json",
                              "commit": "09e3b5b",
                              "blob": "98e74be9973097e7e02cc708482c1be5ea1d4da7"},
             "report_md_untouched": True,
             "known_stale_claims": "V23 REPORT.md 旧描述（如 2543 GFTT 3/4、10000 GFTT 3/4）与 matrix 实际 "
                                   "(1641 1/4 validated; 2543 1V+2P+1I; 10000 0V; 21674 0V) 不符——"
                                   "本轮以 matrix 为准，未修改历史 REPORT.md"}
    (OUT / "TREECUT_CAM01_EH01M1_V23_STALE_REPORT_NOTE.json").write_text(
        json.dumps(stale, ensure_ascii=False, indent=1), encoding="utf-8")

    fp = load("TREECUT_CAM01_EH01M1_REPLAY_FINGERPRINT.json")
    tr = load("TREECUT_CAM01_EH01M1_GFTT_TRANSFORMS.json")["rows"]
    ag = load("TREECUT_CAM01_EH01M1_LOCAL_AGREEMENT.json")
    imp = load("TREECUT_CAM01_EH01M1_ROUTER_IMPACT_SHADOW.json")
    sd = load("TREECUT_CAM01_EH01M1_STRUCTURAL_DIAGNOSTIC.json")["rows"]
    td = load("TREECUT_CAM01_EH01M1_TARGET_DIAGNOSTIC.json")
    mats = [r for r in tr if r.get("status") == "GFTT_MATERIALIZED_REFERENCE_CANDIDATE"]
    # §25 decision
    replay_verified = bool(fp["gate_passed"])
    complete = ("YES" if (fp["gate_passed"] and len(mats) == fp["historical_gftt_validated"])
                else ("PARTIAL" if len(mats) > 0 else "NO"))
    # §26 next blocker
    no_tf = imp.get("no_transform_routes_now_materialized", {})
    mat_count = no_tf.get("materialized", 0)
    total_no_tf = no_tf.get("total_no_tf", 0)
    if not fp["gate_passed"]:
        nb = "V23_PROVENANCE_REPLAY_REPAIR"
    elif total_no_tf > 0 and mat_count >= total_no_tf * 0.5:
        nb = "EH02_ROUTER_CALIBRATION"
    else:
        nb = "V23_PROVENANCE_REPLAY_REPAIR"
    global_rec = "GLOBAL_TRANSFORM_MATERIALIZATION_RECOMMENDED_AFTER_EH02_OR_AS_EH02_SUBTASK"
    res = {"experiment": "CAM01_EH01M1_RESULT",
           "baseline": "main @ 4aec680",
           "GFTT_REPLAY_VERIFIED": bool(replay_verified),
           "historical_gftt_validated": fp["historical_gftt_validated"],
           "replay_gftt_validated": fp["replay_gftt_validated"],
           "pair_state_fingerprint_match_36": fp["pair_state_fingerprint_match_36"],
           "fold_state_fingerprint_match": fp["fold_state_fingerprint_match"],
           "GFTT_TRANSFORM_MATERIALIZATION_COMPLETE": complete,
           "materialized_count": len(mats),
           "deterministic_count": sum(1 for r in mats if r.get("deterministic_rebuild")),
           "no_transform_routes_now_materialized": no_tf,
           "local_agreement": {"GFTT_vs_V24": {k: v for k, v in ag["GFTT_vs_V24"].items() if k != "rows"},
                               "GFTT_vs_DENSE": {k: v for k, v in ag["GFTT_vs_DENSE"].items() if k != "rows"}},
           "structural": {"consistent": sum(1 for r in sd if (r.get("structural") or {}).get("state") == "STRUCTURAL_CONSISTENT"),
                          "disagreement": sum(1 for r in sd if (r.get("structural") or {}).get("state") == "STRUCTURAL_DISAGREEMENT"),
                          "unknown": sum(1 for r in sd if (r.get("structural") or {}).get("state") == "STRUCTURAL_UNKNOWN")},
           "target": {"POS_materialized": td["POS"]["count"],
                      "POS_materialized_target_valid": td["POS"]["target_valid"],
                      "NEG_materialized": td["NEG"]["count"],
                      "NEG_materialized_target_valid": td["NEG"]["target_valid"],
                      "NEG_MATERIALIZED_REFERENCE_TARGET_VALID": td["NEG_MATERIALIZED_REFERENCE_TARGET_VALID"],
                      "NEG_STRONG_REFERENCE_TARGET_VALID": 0,
                      "strength_note": "NEG materialized != NEG strong；强度等级等 EH02"},
           "NEG_focus_pairs": [x for x in td["NEG"]["rows"] if x["case"] in (1641, 2543)],
           "no_new_coverage_gate": True,
           "no_action_verdict": True,
           "NEXT_BLOCKER": nb,
           "GLOBAL_TRANSFORM_MATERIALIZATION_RECOMMENDED": global_rec,
           "note": "shadow only; EH01R1 router 未修改; GFTT materialized 标 "
                   "GFTT_MATERIALIZED_REFERENCE_CANDIDATE 未自动升级 strong"}
    (OUT / "TREECUT_CAM01_EH01M1_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("NEG_focus_pairs",)},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
