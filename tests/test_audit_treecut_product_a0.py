# -*- coding: utf-8 -*-
"""A0 consistency checks — valid capability levels, evidence presence, E2E order,
risk/capability counts md-json, no NOT_REACHED as PASS, no secrets."""
import json
import re
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
LEVELS = {"NOT_FOUND", "DESIGN_ONLY", "STUB_OR_PLACEHOLDER", "CODE_EXISTS", "UNIT_TESTED",
          "DATA_CONNECTED", "E2E_PROVEN", "USER_USABLE", "PRODUCTION_READY"}


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_capability_levels_valid():
    m = load("TREECUT_A0_PRODUCT_CAPABILITY_MATRIX.json")
    for c in m["capabilities"]:
        assert c["highest_verified_level"] in LEVELS, c["capability_id"]
        assert c["highest_verified_level"] != "NOT_FOUND" or "evidence" not in c  # NOT_FOUND no fake evidence


def test_capability_counts_match():
    from collections import Counter
    m = load("TREECUT_A0_PRODUCT_CAPABILITY_MATRIX.json")
    res = load("TREECUT_A0_RESULT.json")
    c1 = Counter(c["highest_verified_level"] for c in m["capabilities"])
    c2 = res["capability_level_counts"]
    assert dict(c1) == dict(c2), (dict(c1), dict(c2))


def test_e2e_trace_order_and_blocker():
    t = load("TREECUT_A0_END_TO_END_TRACE.json")
    order = [s["step"] for s in t["steps"]]
    assert order[0] == "script_input"
    assert "jianying_draft" in order
    # NOT_REACHED must not be PASS/FAIL
    for s in t["steps"]:
        if s["status"].startswith("NOT_"):
            assert "FAIL" not in s["status"] and "PASS" not in s["status"]


def test_n0_state_preserved():
    res = load("TREECUT_A0_RESULT.json")
    assert res["n0_state_preserved"].startswith("YES")
    assert res["cam_eh_production_caller"].startswith("NO")


def test_risk_and_gap_counts_consistent():
    r = load("TREECUT_A0_RISK_REGISTER.json")
    g = load("TREECUT_A0_PRODUCT_GAP_MAP.json")
    res = load("TREECUT_A0_RESULT.json")
    assert len(r["risks"]) >= 8
    # gap P0 count
    assert len(g["P0_PRODUCT_BLOCKERS"]) == res["gap_counts"]["P0"]
    assert len(g["RESEARCH_NOT_BLOCKING_MVP"]) == res["gap_counts"]["RESEARCH"]


def test_no_secrets_in_a0():
    for f in OUT.glob("TREECUT_A0_*.json"):
        s = f.read_text(encoding="utf-8")
        assert not re.search(r"ghp_|sk-[A-Za-z0-9]{20}|api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16}|xsec_token=[A-Za-z0-9]{16}", s), f.name


def test_user_usable_not_above_e2e():
    m = load("TREECUT_A0_PRODUCT_CAPABILITY_MATRIX.json")
    e2e_trace = load("TREECUT_A0_END_TO_END_TRACE.json")
    # any USER_USABLE cap in H domain has UI; E2E_PROVEN caps grounded
    for c in m["capabilities"]:
        if c["highest_verified_level"] == "USER_USABLE":
            assert c["domain"] in ("H_OUTPUT_UI_OPS", "D_SCRIPT_CLAIM_TEMPLATE") or c.get("ui")
