# -*- coding: utf-8 -*-
"""EH01 — 轻量逻辑测试：structural symmetric 修正判定、agreement/conflict 阈值、
transform disagreement grid 计算、role-blind 顺序（router 冻结前无 role 读取证据）。"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "storage"


def test_structural_symmetric_rule_corrects_r2():
    """symmetric P90>12 → DISAGREEMENT；R2 漏标的 2 对须被 EH01 捕获。"""
    sv = json.loads((OUT / "TREECUT_CAM01_DENSE01R2_STRUCTURAL_VALIDATION.json")
                    .read_text(encoding="utf-8"))["rows"]
    mm = json.loads((OUT / "TREECUT_CAM01_DENSE01R2_MATCH_MATRIX.json")
                    .read_text(encoding="utf-8"))["pairs"]
    val = {(p["case"], p["pair"]) for p in mm
           if p.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL")}
    assert len(val) == 8
    disagree = set()
    for r in sv:
        key = (r["case"], r["pair"])
        if key not in val:
            continue
        s = r.get("structural") or {}
        sym = s.get("symmetric")
        if sym and sym.get("p90") is not None and sym["p90"] > 12.0:
            disagree.add(key)
    # R2 forward-only flag 漏标的 2 对
    assert (3571, "1.842->4.299") in disagree   # sym P90 25.73
    assert (25894, "3.112->4.07") in disagree   # sym P90 25.98
    assert len(disagree) == 5
    # R2 原 flag 只标了 3
    r2_flag = {(r["case"], r["pair"]) for r in sv
               if (r.get("structural") or {}).get("flag") == "DENSE_STRUCTURAL_DISAGREEMENT"}
    assert r2_flag == {(3571, "7.984->10.441"), (10000, "0.768->1.793"),
                       (25894, "0.718->1.676")}


def test_local_agreement_verdicts():
    ag = json.loads((OUT / "TREECUT_CAM01_EH01_LOCAL_AGREEMENT.json")
                    .read_text(encoding="utf-8"))["rows"]
    verdicts = {}
    for r in ag:
        verdicts[(r["case"], r["pair"])] = r.get("verdict")
    # 两源冲突应判 LOCAL_CONFLICT
    assert verdicts.get((12095, "5.191->7.416")) == "LOCAL_CONFLICT"
    assert verdicts.get((25894, "3.112->4.07")) == "LOCAL_CONFLICT"
    # 一致 pair 应有 agree
    assert any(v == "LOCAL_AGREE" for v in verdicts.values())


def test_router_counts_match_result():
    res = json.loads((OUT / "TREECUT_CAM01_EH01_RESULT.json").read_text(encoding="utf-8"))
    router = json.loads((OUT / "TREECUT_CAM01_EH01_ROUTER_SHADOW.json")
                        .read_text(encoding="utf-8"))["rows"]
    assert len(router) == 36
    from collections import Counter
    rc = Counter(r["route"] for r in router)
    assert rc.get("ROUTE_LOCAL_STRONG", 0) == res["LOCAL_STRONG"]
    assert rc.get("ROUTE_LOCAL_PARTIAL", 0) == res["LOCAL_PARTIAL"]
    usable = rc.get("ROUTE_LOCAL_STRONG", 0) + rc.get("ROUTE_LOCAL_PARTIAL", 0) + \
             rc.get("ROUTE_GLOBAL_RELIABLE", 0)
    assert usable == res["ROUTER_USABLE"] == 19


def test_raw_union_exceeds_usable_not_equal():
    """RAW_SOURCE_UNION != ROUTER_USABLE：不得把 raw union 冒充 coverage。"""
    res = json.loads((OUT / "TREECUT_CAM01_EH01_RESULT.json").read_text(encoding="utf-8"))
    assert res["RAW_SOURCE_UNION"] == 22
    assert res["ROUTER_USABLE"] == 19
    assert res["RAW_SOURCE_UNION"] > res["ROUTER_USABLE"]


def test_structural_corrected_counts():
    res = json.loads((OUT / "TREECUT_CAM01_EH01_RESULT.json").read_text(encoding="utf-8"))
    sc = res["structural_corrected_8"]["among_r2_validated_8"]
    assert sc == {"consistent": 3, "disagreement": 5, "unknown": 0}


def test_target_diagnostic_role_blind_after_freeze():
    """target diagnostic 存在且不改变 router 结论（POS/NEG 分开统计）。"""
    res = json.loads((OUT / "TREECUT_CAM01_EH01_RESULT.json").read_text(encoding="utf-8"))
    td = res["target_diagnostic"]
    assert td["POS"]["usable"] + td["NEG"]["usable"] == 19
    assert td["POS"]["target_valid"] == 9
    assert td["NEG"]["target_valid"] == 2
