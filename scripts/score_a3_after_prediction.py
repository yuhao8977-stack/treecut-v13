#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MMVV A3 — SCORING（独立进程，预测之后；预测与评分完全分离）。

输入:  A3_MACHINE_PREDICTIONS_BLIND.json（预测输出 + prediction_output_hash）
       A3_CASE_KEY_PRIVATE.json（opaque ↔ 真实素材）
       A3_HUMAN_GT.json（人工答案）
规则:  预测哈希须先于打开人工答案生成并核验；本进程是唯一允许同时读
       预测 + key + GT 的地方。今晚（无预测输出）→ A3_PREDICTIONS_REQUIRED。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "storage"
PRED_JSON = OUT / "TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.json"
PRED_SHA = OUT / "TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.sha256.txt"
KEY_JSON = OUT / "TREECUT_MMVV_A3_CASE_KEY_PRIVATE.json"
GT_JSON = OUT / "TREECUT_MMVV_A3_HUMAN_GT.json"
SCORED_JSON = OUT / "TREECUT_MMVV_A3_SCORED_RESULTS.json"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if not PRED_JSON.exists():
        print("A3_PREDICTIONS_REQUIRED")
        print("note: 今晚禁止执行预测（缺 Human ROI + blind 刚建立）；score 待预测后运行。")
        return 3
    pred_sha_file = sha256_file(PRED_JSON)
    if PRED_SHA.exists():
        recorded = PRED_SHA.read_text(encoding="utf-8").strip().split()[0]
        if recorded != pred_sha_file:
            raise SystemExit(f"PREDICTION_HASH_MISMATCH: {recorded} != {pred_sha_file}")
    else:
        # 预测哈希必须在 GT 打开前生成（此处强制）
        raise SystemExit("A3_PREDICTION_SHA_MISSING（score 拒绝在无预测哈希时打开人工答案）")

    key = json.loads(KEY_JSON.read_text(encoding="utf-8"))
    gt = json.loads(GT_JSON.read_text(encoding="utf-8"))
    preds = json.loads(PRED_JSON.read_text(encoding="utf-8"))
    # 合并逻辑（明日预测后实现）
    print("A3_SCORING_SCAFFOLD_OK (merge pending predictions)")


if __name__ == "__main__":
    sys.exit(main())
