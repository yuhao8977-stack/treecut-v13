# -*- coding: utf-8 -*-
"""EH02 final: router config (rules doc) + RESULT + targeted NEG candidates (§26-§28)."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    # ===== router config =====
    cfg = {
        "ROUTER_VERSION": "EH02_V2",
        "confidence_classes": {
            "HIGH_CONF_LOCAL": ["V24R1 TRUE_MULTI_METHOD_CONSENSUS",
                                "DENSE_R2 MULTI_MODEL_CONSENSUS"],
            "MEDIUM_CONF_LOCAL": ["DENSE_R2 SINGLE_MODEL",
                                  "GFTT_V23 VALIDATED materialized (bakeoff FAILED, not natively strong)"]},
        "strong_rules": {
            "S1": "HIGH_CONF_LOCAL + no LOCAL_CONFLICT + structural != DISAGREEMENT "
                  "(structural UNKNOWN = NO_STRUCTURAL_VETO_AVAILABLE, not CONFIRMED)",
            "S2": "MEDIUM_CONF_LOCAL + STRUCTURAL_CONSISTENT + GLOBAL reliable state + no LOCAL_CONFLICT",
            "S3": "MEDIUM_CONF_LOCAL + cross-family materialized local source AGREE + "
                  "structural != DISAGREEMENT + no conflict "
                  "(V24<->GFTT same family cannot satisfy; DENSE<->GFTT / DENSE<->V24 can)"},
        "partial_rules": "real transform present but not STRONG; DISAGREEMENT -> "
                         "REFERENCE_PARTIAL_VETOED (SAFE_EMIT=False)",
        "conflict_precedence": "LOCAL_CONFLICT > STRONG > PARTIAL > EVIDENCE_ONLY/NONE",
        "representative_tiebreak": "DENSE_R2 > V24R1 > GFTT_M1; cross-family agreement cluster "
                                   "preferred; no matrix averaging",
        "structural_boundary": "symmetric P90 <=12 CONSISTENT / >12 DISAGREEMENT / none UNKNOWN (unchanged 12)",
        "global_role": "state-only SUPPORT (no transform; no veto; unreliable = NO_GLOBAL_SUPPORT)",
        "evidence_family": {"DENSE_R2": "SEMANTIC_DENSE_LK", "V24R1": "FEATURE_LOCAL_ENSEMBLE",
                            "GFTT_M1": "FEATURE_LOCAL", "GLOBAL": "GLOBAL_CAMERA",
                            "STRUCTURAL": "STRUCTURAL_VALIDATION", "DINO_MNN": "SEMANTIC_AVAILABILITY"},
        "note": "V24R1 与 GFTT_M1 同 feature-local 链，非完全独立 family"}
    (OUT / "TREECUT_CAM01_EH02_ROUTER_CONFIG.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== result =====
    met = load("TREECUT_CAM01_EH02_ROUTER_METRICS.json")
    rd = load("TREECUT_CAM01_EH02_TARGET_READINESS.json")
    gub = load("TREECUT_CAM01_EH02_GLOBAL_UPPER_BOUND.json")
    corr = load("TREECUT_CAM01_EH02_M1_CORRECTIONS.json")
    sc = load("TREECUT_CAM01_EH02_STRUCTURAL_CORRECTED.json")["rows"]
    old_sc = load("TREECUT_CAM01_EH01M1_STRUCTURAL_DIAGNOSTIC.json")["rows"]
    old_by = {(r["case"], r["pair"]): (r.get("structural") or {}).get("state") for r in old_sc}
    from collections import Counter
    old_cnt = Counter(v for v in old_by.values() if v)
    new_cnt = Counter((r.get("structural") or {}).get("state") for r in sc)
    changed = []
    for r in sc:
        k = (r["case"], r["pair"])
        o = old_by.get(k)
        n = (r.get("structural") or {}).get("state")
        if o != n:
            changed.append({"case": r["case"], "pair": r["pair"], "old": o, "new": n})
    # NEG control status per §23
    ntv = rd["NEG_strong_target_valid"]
    nfam = len(rd.get("NEG_unique_families", []))
    if ntv >= 3 and nfam >= 3:
        neg_control = "ESTABLISHED"
    elif ntv >= 1:
        neg_control = "PRESENT"
    else:
        neg_control = "NOT_READY"
    # global transform needed (§26)
    strong = met["REFERENCE_STRONG"]
    global_needed = False
    # 2543 route
    fr = load("TREECUT_CAM01_EH02_ROUTER_FREEZE.json")["36_pair_routes"]
    route_of = {(r["case"], r["pair"]): r for r in fr}
    r2543 = route_of.get((2543, "1.202->1.717"))
    r1641 = route_of.get((1641, "2.642->3.434"))
    res = {"experiment": "CAM01_EH02_RESULT",
           "baseline": "main @ 644c206",
           "M1_materialization_preserved": True,
           "corrections": {k: "registered" for k in corr},
           "structural_old": dict(old_cnt),
           "structural_corrected": dict(new_cnt),
           "structural_verdict_changed": changed,
           "metrics": met,
           "NEG_REFERENCE_CONTROL": neg_control,
           "NEG_REFERENCE_CONTROL_PRESENT": ntv >= 1,
           "NEG_REFERENCE_CONTROL_ESTABLISHED": ntv >= 3 and nfam >= 3,
           "readiness": {k: v for k, v in rd.items() if k != "POS_detail" and k != "NEG_detail"},
           "route_1641": {"case": 1641, "pair": "2.642->3.434",
                          "route": (r1641 or {}).get("route"),
                          "reason": (r1641 or {}).get("reason", "")[:80]},
           "route_2543": {"case": 2543, "pair": "1.202->1.717",
                          "route": (r2543 or {}).get("route"),
                          "rule": (r2543 or {}).get("rule"),
                          "reason": (r2543 or {}).get("reason", "")[:80]},
           "GLOBAL_MATERIALIZATION_UPPER_BOUND": gub["GLOBAL_MATERIALIZATION_UPPER_BOUND"],
           "GLOBAL_TRANSFORM_NEEDED": global_needed,
           "ROUTER_RULESET_FROZEN": True,
           "no_new_coverage_gate": True,
           "no_geom": True,
           "no_action_verdict": True,
           "NEXT_BLOCKER": ("TARGETED_NEGATIVE_REFERENCE_SET" if neg_control != "ESTABLISHED"
                            else "EH03_TARGET_RELATIVE_INTEGRATION"),
           "targeted_negative_recommendation": {
               "note": "diagnostic only; NO auto sample-add / ROI / run",
               "criteria": "target 两端可见 / 独立视觉 family / 非 1641/2543 重复 family",
               "candidates_cal10_external_NO_ACTION": [
                   {"media_id": 1019, "src": 1, "file": "32运动者+实木升降台 内蒙古炖锅"},
                   {"media_id": 1025, "src": 1, "file": "34可折叠水桶+实木桌 南京炖锅"},
                   {"media_id": 103, "src": 1, "file": "113欧式沙发+实木梳妆 山东炖锅"},
                   {"media_id": 1600, "src": 1, "file": "04壁挂水龙头+凉亭 内蒙古炖锅"},
                   {"media_id": 1638, "src": 1, "file": "1-4 55大理石+深黑 实木"},
                   {"media_id": 1639, "src": 1, "file": "05烤牛肉串"},
                   {"media_id": 2163, "src": 1, "file": "85瓷白+深灰+黑白 岩板炖锅"},
                   {"media_id": 2208, "src": 1, "file": "48大理石+运动者+深灰 拼花"},
                   {"media_id": 2211, "src": 1, "file": "32运动者+实木 内蒙古 餐厅"},
                   {"media_id": 2492, "src": 1, "file": "岩板白 鱼尾锅 01壁挂水龙头"},
                   {"media_id": 26023, "src": 4, "file": "DJI 青岛 2.18 (未处理工厂)"}]},
           "targeted_negative_note": "见 §27 recommendation；不得自动加样本/画 ROI/运行"}
    (OUT / "TREECUT_CAM01_EH02_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("metrics", "readiness")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
