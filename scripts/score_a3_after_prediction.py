#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MMVV A3 — SCORING（预测之后独立进程；GT 仅在预测 hash 锁验证后解封）。

规则:
- 第一件事: 重算 prediction JSON SHA256，与 .sha256.txt 及 PREDICTION_LOCK 比对；
  不一致 → PREDICTION_HASH_MISMATCH，禁止读取/应用 GT。
- 评分 truth 只用 Human GT 的 human_gt 字段（YES_EXTEND/NO_EXTEND）；
  expected_machine / expected_verdict 一律 IGNORE_FOR_SCORING。
- 判定: YES+PASS=TP, YES+FAIL=FN, YES+UNSURE=UNSURE_POS,
         NO+FAIL=TN, NO+PASS=FALSE_PASS/FP, NO+UNSURE=UNSURE_NEG。
- 状态: FP>0 → A3_CORE_GENERALIZATION_NEEDS_REPAIR；
        else pos PASS>=2/3 and neg FAIL>=2/3 and FP=0 → A3_CORE_GENERALIZATION_PROMISING；
        else → A3_CORE_GENERALIZATION_PARTIAL。
  EXTEND_POSITIVE_RECOGNITION: pos PASS<=1/3→NOT_ESTABLISHED；>=2/3→SUPPORTED_ON_THIS_SMALL_HOLDOUT。
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "storage"
PRED_JSON = OUT / "TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.json"
PRED_SHA = OUT / "TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.sha256.txt"
LOCK_JSON = OUT / "TREECUT_MMVV_A3_PREDICTION_LOCK_V1.json"
KEY_JSON = OUT / "TREECUT_MMVV_A3_CASE_KEY_PRIVATE.json"
GT_JSON = OUT / "TREECUT_MMVV_A3_HUMAN_GT.json"
SCORED_JSON = OUT / "TREECUT_MMVV_A3_SCORED_RESULTS.json"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def classify(verdict: str, human_gt: str) -> str:
    """verdict ∈ PASS/FAIL/UNSURE；human_gt ∈ YES_EXTEND/NO_EXTEND。"""
    if human_gt == "YES_EXTEND":
        return {"PASS": "TP", "FAIL": "FN", "UNSURE": "UNSURE_POS"}.get(verdict, "UNKNOWN")
    return {"PASS": "FP", "FAIL": "TN", "UNSURE": "UNSURE_NEG"}.get(verdict, "UNKNOWN")


def status_from_counts(pos_pass: int, pos_total: int, neg_fail: int, neg_total: int, fp: int) -> str:
    if fp > 0:
        return "A3_CORE_GENERALIZATION_NEEDS_REPAIR"
    pos_ok = pos_total and pos_pass >= (2 * pos_total + 2) // 3
    neg_ok = neg_total and neg_fail >= (2 * neg_total + 2) // 3
    if pos_ok and neg_ok and fp == 0:
        return "A3_CORE_GENERALIZATION_PROMISING"
    return "A3_CORE_GENERALIZATION_PARTIAL"


def extend_positive_recognition(pos_pass: int, pos_total: int) -> str:
    if pos_total == 0:
        return "NOT_ESTABLISHED"
    if pos_pass * 3 <= pos_total:          # <= 1/3
        return "NOT_ESTABLISHED"
    if pos_pass * 3 >= 2 * pos_total:      # >= 2/3
        return "SUPPORTED_ON_THIS_SMALL_HOLDOUT"
    return "NOT_ESTABLISHED"


def score(pred_path: Path, key_path: Path, gt_path: Path, sha_path: Path,
          lock_path: Path, out_path: Path) -> dict:
    if not pred_path.exists():
        return {"status": "A3_PREDICTIONS_REQUIRED"}
    pred_sha = sha256_file(pred_path)
    if not sha_path.exists():
        raise SystemExit("A3_PREDICTION_SHA_MISSING（score 拒绝在无预测哈希时打开人工答案）")
    recorded = sha_path.read_text(encoding="utf-8").strip().split()[0]
    if recorded != pred_sha:
        raise SystemExit(f"PREDICTION_HASH_MISMATCH: {recorded} != {pred_sha}")
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if lock.get("prediction_sha256") != pred_sha:
            raise SystemExit("PREDICTION_HASH_MISMATCH vs LOCK")
        if lock.get("gt_opened") is not False:
            raise SystemExit("LOCK gt_opened 异常（应在 GT 前为 false）")
    preds = json.loads(pred_path.read_text(encoding="utf-8"))
    key = json.loads(key_path.read_text(encoding="utf-8"))
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    # mapping opaque -> media/gt
    key_map = {r["opaque_case_id"]: r for r in key["mapping"]}
    gt_map = {a["case_id"]: a for a in gt["answers"]}
    rows = []
    for c in preds["cases"]:
        oid = c["opaque_case_id"]
        km = key_map[oid]
        ga = gt_map[km["original_case_id"]]
        human_gt = ga["human_gt"]  # truth 唯一来源（YES_EXTEND:/NO_EXTEND: 前缀）
        label = "YES_EXTEND" if human_gt.startswith("YES_EXTEND") else (
            "NO_EXTEND" if human_gt.startswith("NO_EXTEND") else "UNKNOWN")
        mv = c["machine_verdict"]
        rows.append({
            "opaque_case_id": oid, "original_case_id": km["original_case_id"],
            "media_id": km["media_id"], "human_gt": label,
            "expected_machine_ignored": ga.get("expected_machine"),
            "machine_verdict": mv, "category": classify(mv, label)})
    cats = [r["category"] for r in rows]
    pos = [r for r in rows if r["human_gt"] == "YES_EXTEND"]
    neg = [r for r in rows if r["human_gt"] == "NO_EXTEND"]
    pos_pass = sum(1 for r in pos if r["machine_verdict"] == "PASS")
    pos_fail = sum(1 for r in pos if r["machine_verdict"] == "FAIL")
    neg_fail = sum(1 for r in neg if r["machine_verdict"] == "FAIL")
    fp = sum(1 for r in neg if r["machine_verdict"] == "PASS")
    coverage = (sum(1 for r in rows if r["machine_verdict"] in ("PASS", "FAIL"))) / len(rows)
    status = status_from_counts(pos_pass, len(pos), neg_fail, len(neg), fp)
    epr = extend_positive_recognition(pos_pass, len(pos))
    doc = {
        "experiment": "MMVV_A3_SCORED_RESULTS",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "prediction_sha256": pred_sha,
        "roi_sha256": preds.get("roi_sha256"),
        "algorithm_freeze_commit": preds.get("algorithm_freeze_commit"),
        "truth_source": "human_gt only (expected_machine IGNORED)",
        "summary": {
            "TP": sum(1 for c in cats if c == "TP"), "TN": sum(1 for c in cats if c == "TN"),
            "FP": fp, "FN": sum(1 for c in cats if c == "FN"),
            "UNSURE_POS": sum(1 for c in cats if c == "UNSURE_POS"),
            "UNSURE_NEG": sum(1 for c in cats if c == "UNSURE_NEG"),
            "positive_pass_count": pos_pass, "positive_fail_count": pos_fail,
            "negative_fail_count": neg_fail, "false_pass_count": fp,
            "coverage": round(coverage, 3),
            "A3_STATUS": status,
            "EXTEND_POSITIVE_RECOGNITION": epr,
        },
        "rows": rows,
    }
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def main():
    doc = score(PRED_JSON, KEY_JSON, GT_JSON, PRED_SHA, LOCK_JSON, SCORED_JSON)
    if doc.get("status") == "A3_PREDICTIONS_REQUIRED":
        print("A3_PREDICTIONS_REQUIRED")
        return 3
    print("SCORED:", json.dumps(doc["summary"], ensure_ascii=False))
    for r in doc["rows"]:
        print(f"  {r['opaque_case_id']} {r['original_case_id']} GT={r['human_gt']} "
              f"machine={r['machine_verdict']} -> {r['category']}")
    print("WROTE", SCORED_JSON)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
