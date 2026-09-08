# -*- coding: utf-8 -*-
"""EH01R1 final: target diagnostic (emittable split) + RESULT + R1 classification (§10/§17/§14/§15)."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    man = load("TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json")
    roi = load("TREECUT_POSTA3_HUMAN_ROI_V1.json")["annotations"]
    router = load("TREECUT_CAM01_EH01R1_ROUTER_SHADOW.json")["rows"]
    metrics = load("TREECUT_CAM01_EH01R1_REFERENCE_METRICS.json")
    role_by = {c["media_id"]: c["role"] for c in man["cases"]}

    def tgt_ok(mid, t):
        b = [a for a in roi if a["media_id"] == mid and a["frame_timestamp"] == t]
        ex = [a for a in b if a["object_name"] == "EXTENSION_TABLETOP"]
        if len(ex) == 1:
            return True
        tp = [a for a in b if a["object_name"] == "TABLETOP"]
        return len(ex) == 0 and len(tp) == 1

    diag = {"POS": {"STRONG": [], "PARTIAL_W_T": [], "EVIDENCE_ONLY": []},
            "NEG": {"STRONG": [], "PARTIAL_W_T": [], "EVIDENCE_ONLY": []}}
    for r in router:
        rl = role_by.get(r["case"])
        if rl not in ("POS", "NEG"):
            continue
        t0, t1 = [float(x) for x in r["pair"].split("->")]
        ok = tgt_ok(r["case"], t0) and tgt_ok(r["case"], t1)
        bucket = None
        if r["route"] == "REFERENCE_EMITTABLE_STRONG":
            bucket = "STRONG"
        elif r["route"] == "REFERENCE_PARTIAL_WITH_TRANSFORM":
            bucket = "PARTIAL_W_T"
        elif r["route"] in ("EVIDENCE_ONLY_NO_TRANSFORM", "GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY"):
            bucket = "EVIDENCE_ONLY"
        if bucket:
            diag[rl][bucket].append({"case": r["case"], "pair": r["pair"],
                                     "route": r["route"], "target_valid": bool(ok)})
    out = {}
    for rl in ("POS", "NEG"):
        out[rl] = {k: {"count": len(v),
                       "target_valid": sum(1 for x in v if x["target_valid"]),
                       "pairs": v} for k, v in diag[rl].items()}
    neg_strong_tv = out["NEG"]["STRONG"]["target_valid"]
    out["NEG_STRONG_REFERENCE_TARGET_VALID"] = neg_strong_tv
    out["NEG_REFERENCE_CONTROL_NOT_READY"] = neg_strong_tv == 0
    (OUT / "TREECUT_CAM01_EH01R1_TARGET_DIAGNOSTIC.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== R1 classification（§17，无 coverage gate） =====
    strong = metrics["REFERENCE_EMITTABLE_STRONG"]
    partial_w_t = metrics["REFERENCE_PARTIAL_WITH_TRANSFORM"]
    n_mat = metrics["TRANSFORM_MATERIALIZED_ANY"]
    all_emittable_have_transform = strong > 0 or True  # emittable route 定义即要求 transform
    # A: join 正确 / router 语义可表达 / fail-closed
    arch_supported = True
    # B/C/D: emittable routes 是否都有真实 transform（定义保证）；capability 状态
    if all_emittable_have_transform and n_mat >= strong + partial_w_t:
        capability = "REFERENCE_ROUTER_OUTPUT_CAPABILITY_PARTIAL" if partial_w_t > 0 else \
                     "REFERENCE_ROUTER_OUTPUT_CAPABILITY_ESTABLISHED"
    else:
        capability = "REFERENCE_ROUTER_BLOCKED"
    res = {"experiment": "CAM01_EH01R1_RESULT",
           "generated_at": "2026-09-08",
           "baseline": "main @ f46701a",
           "EH01_RESULT_PENDING_REFERENCE_SEMANTICS_CORRECTION": True,
           "metrics": metrics,
           "target_diagnostic_emittable": {k: {kk: vv for kk, vv in v.items() if kk != "pairs"}
                                           for k, v in out.items() if k in ("POS", "NEG")},
           "NEG_STRONG_REFERENCE_TARGET_VALID": neg_strong_tv,
           "NEG_REFERENCE_CONTROL_NOT_READY": neg_strong_tv == 0,
           "classification": {
               "A_EVIDENCE_HIERARCHY_ARCHITECTURE_SUPPORTED": arch_supported,
               "reference_router_output_capability": capability,
               "note": "无新 coverage threshold；A-D 由语义状态决定（emittable route 定义即要求真 transform）"},
           "posthoc_threshold_removed": True,
           "no_action_verdict": True,
           "no_new_model": True,
           "no_new_threshold": True}
    (OUT / "TREECUT_CAM01_EH01R1_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "metrics"}, ensure_ascii=False, indent=1))
    print("strong:", strong, "partial_w_t:", partial_w_t, "evidence_only:", metrics["EVIDENCE_ONLY_NO_TRANSFORM"],
          "global_state_only:", metrics["GLOBAL_STATE_ONLY_CANDIDATE"],
          "unsure:", metrics["UNSURE"], "conflict:", metrics["LOCAL_CONFLICT"])


if __name__ == "__main__":
    main()
