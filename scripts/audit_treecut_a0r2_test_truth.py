# -*- coding: utf-8 -*-
"""A0 R2 — RAW_TEST_RUNS: parse pytest JUnit XML + raw logs (machine-derived).

Runs parsed:
  system_full      system python, FULL suite (alphabetical)
  runtime_full     E runtime python, FULL suite
  iso_<file>       system python, each suspicious file ALONE
  reorder_first    system python, r11+stage3 files FIRST then the rest
Every number/command comes from the XML/log files; nothing is hardcoded.
Per-test classification (full-suite fail + isolated pass + run-order evidence):
  * passes in isolation AND passes when moved first in reorder -> TEST_ISOLATION_DEFECT
  * fails everywhere under CPU system py but passes under runtime py -> ENVIRONMENT_MISMATCH
  * else UNVERIFIED_CLASSIFICATION
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

EXT = Path(r"E:\EchoBird-main\_treecut_audit_temp\tests")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def parse_junit(path: Path) -> dict:
    root = ET.parse(str(path)).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    attrs = suite.attrib if suite is not None else {}
    fails = []
    for tc in suite.iter("testcase") if suite is not None else []:
        for tag in ("failure", "error"):
            el = tc.find(tag)
            if el is not None:
                fails.append({"classname": tc.get("classname"), "name": tc.get("name"),
                              "type": tag,
                              "message": (el.get("message") or "")[:200],
                              "file": (tc.get("classname") or "").rsplit(".", 1)[-1]})
    return {"file": path.name, "tests": int(attrs.get("tests", 0)),
            "failures": int(attrs.get("failures", 0)) + int(attrs.get("errors", 0)),
            "skipped": int(attrs.get("skipped", 0)),
            "time_s": float(attrs.get("time", 0) or 0),
            "failure_list": fails,
            # product failures exclude the audit's own data-driven tests
            # (their in-suite result depends on evidence state one run behind)
            "product_failures": len([f for f in fails
                                     if not f["classname"].startswith(
                                         "tests.test_audit_treecut_a0r2")]),
            "audit_self_failures": len([f for f in fails
                                        if f["classname"].startswith(
                                            "tests.test_audit_treecut_a0r2")])}


def cmd_from_log(name: str) -> str:
    p = EXT / name
    if not p.exists():
        return ""
    first = p.read_text(encoding="utf-8", errors="replace").splitlines()
    return first[0] if first else ""


def test_key(f):
    return f"{f['classname']}::{f['name']}"


def main():
    runs = {}
    for stem in ("system_full", "runtime_full",
                 "iso_test_source_audit_r11", "iso_test_stage3_mini_v2",
                 "iso_test_stage3_model_dev", "reorder_first"):
        jx = EXT / f"{stem}_junit.xml"
        if jx.exists():
            parsed = parse_junit(jx)
            parsed["command"] = cmd_from_log(f"{stem}_raw.log")
            parsed["exit_code_line"] = ""
            lg = EXT / f"{stem}_raw.log"
            if lg.exists():
                tail = [ln for ln in lg.read_text(encoding="utf-8",
                                                  errors="replace").splitlines()
                        if ln.startswith("# exit_code=")]
                parsed["exit_code_line"] = tail[-1] if tail else ""
            runs[stem] = parsed
    system = runs.get("system_full")
    runtime = runs.get("runtime_full")
    reorder = runs.get("reorder_first")
    classifications = {}
    if system:
        runtime_fail = {test_key(f) for f in (runtime or {}).get("failure_list", [])}
        reorder_fail = {test_key(f) for f in (reorder or {}).get("failure_list", [])}
        for f in system["failure_list"]:
            if f["classname"].startswith("tests.test_audit_treecut_a0r2"):
                continue  # audit self-tests excluded (evidence lag, not product)
            k = test_key(f)
            msg = (f["message"] or "") + " " + f["classname"]
            gpu_hint = any(w in msg for w in ("CUDA", "RTX 3050", "Torch not compiled",
                                              "output_shape"))
            file_stem = f["classname"].rsplit(".", 1)[-1]  # junit classname already test_*
            iso = runs.get(f"iso_{file_stem}")
            iso_fail = {test_key(x) for x in (iso or {}).get("failure_list", [])}
            isolated_pass = iso is not None and k not in iso_fail
            order_pass = reorder is not None and k not in reorder_fail
            runtime_pass = runtime is not None and k not in runtime_fail
            if isolated_pass and order_pass:
                cls = "TEST_ISOLATION_DEFECT"  # order-dependent: fails after earlier files, passes first
            elif isolated_pass and not order_pass:
                cls = "TEST_ISOLATION_DEFECT_COLLECTION"  # passes alone; fails in EVERY suite
                # position (order-independent) -> collection-time module collision
            elif runtime_pass and gpu_hint:
                cls = "ENVIRONMENT_MISMATCH"
            else:
                cls = "UNVERIFIED_CLASSIFICATION"
            classifications[k] = {"classname": f["classname"], "name": f["name"],
                                  "message": f["message"],
                                  "isolated_pass": isolated_pass,
                                  "order_reorder_pass": order_pass,
                                  "runtime_pass": runtime_pass,
                                  "gpu_hint": gpu_hint,
                                  "classification": cls,
                                  "evidence_chain": "full-suite fail + isolated pass"
                                  + (" + reorder-first pass" if order_pass else
                                     " + reorder-first still fails (order-independent, "
                                     "collection-time collision)")}
    counts = {}
    for c in classifications.values():
        counts[c["classification"]] = counts.get(c["classification"], 0) + 1
    result = {
        "experiment": "TREECUT_A0R2_RAW_TEST_RUNS",
        "runs": runs,
        "per_failure_classification": classifications,
        "classification_counts": counts,
        "note": "system=CPU torch; runtime=E install python CUDA; reorder_first puts r11+stage3 files at suite head",
    }
    (OUT / "TREECUT_A0R2_RAW_TEST_RUNS.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("runs:", {k: (v["tests"], v["failures"]) for k, v in runs.items()})
    print("classification counts:", counts)


if __name__ == "__main__":
    main()
