#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MMVV A3 — BLIND PREDICTION RUNNER（prepare-only；今晚禁止执行动作预测）。

纪律:
- 机器侧唯一输入 = TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json + opaque 帧
  + （未来人工完成后）TREECUT_MMVV_A3_HUMAN_GT_ROI_BLIND.json。
- 禁止读取: HUMAN_GT / SCREENING / 原 HOLDOUT_MANIFEST / AUDIT / REPORT /
  CASE_KEY_PRIVATE / 源 DB / 源路径元数据。读取受 allowlist 强制约束。
- Human ROI 缺失 → FAIL CLOSED: 状态 A3_ROI_REQUIRED，退出码 3。
  绝不以 Qwen/heuristic/auto ROI 兜底。
- 预测输出: A3_MACHINE_PREDICTIONS_BLIND.json（先写文件再写 sha256 摘要，
  供 score 进程在打开人工答案前核对 prediction_output_hash）。

用法:
  python scripts/run_a3_blind.py            # 今晚(无 ROI) → A3_ROI_REQUIRED (exit 3)
  python scripts/run_a3_blind.py --roi <ROI_BLIND.json>   # 未来人工 ROI 完成后
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "storage"
BLIND_JSON = OUT / "TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json"
ROI_BLIND_JSON = OUT / "TREECUT_MMVV_A3_HUMAN_GT_ROI_BLIND.json"
PRED_JSON = OUT / "TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.json"
PRED_SHA = OUT / "TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.sha256.txt"
# 盲帧目录（与构建器共享常量；blind JSON 本身不含本地路径）
BLIND_FRAMES_DIR = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_a3_blind_frames")

# 允许打开的文件/目录（文件级防泄漏 allowlist）
ALLOWED_ROOTS = [
    BLIND_JSON,
    ROI_BLIND_JSON,          # 未来人工 ROI（可能尚不存在）
    BLIND_FRAMES_DIR,
]


class ForbiddenFileError(PermissionError):
    pass


def ensure_allowed(path) -> Path:
    """文件级访问防泄漏：非 allowlist 一律拒绝（fail closed）。"""
    p = Path(path).resolve()
    for root in ALLOWED_ROOTS:
        r = Path(root).resolve()
        if p == r or (r.is_dir() and r in p.parents):
            return p
    raise ForbiddenFileError(f"FORBIDDEN_FILE: {path}（不在 A3 机器输入 allowlist 内）")


def load_blind() -> dict:
    if not BLIND_JSON.exists():
        raise SystemExit("A3_BLIND_MANIFEST_MISSING")
    return json.loads(BLIND_JSON.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roi", default=None, help="ROI blind json（人工完成后提供）")
    ap.add_argument("--selfcheck", action="store_true", help="仅完整性自检，不读取 ROI")
    a = ap.parse_args()

    blind = load_blind()
    # 帧目录必须存在且帧哈希可核（目录位置为 runner 常量；blind JSON 无本地路径）
    frames_dir = BLIND_FRAMES_DIR
    n_ok = 0
    for c in blind["cases"]:
        for f in c["frames"]:
            fp = ensure_allowed(frames_dir / f["frame"])
            if not fp.exists():
                raise SystemExit(f"A3_BLIND_FRAME_MISSING: {f['frame']}")
            n_ok += 1
    print(f"blind frames verified: {n_ok}")

    if a.selfcheck:
        print("A3_SELFCHECK_OK (ROI not required)")
        return 0

    roi = None
    if a.roi:
        roi = ensure_allowed(a.roi)
        if not roi.exists():
            raise SystemExit("A3_ROI_FILE_MISSING")
        json.loads(roi.read_text(encoding="utf-8"))   # 结构校验
    elif ROI_BLIND_JSON.exists():
        roi = ensure_allowed(ROI_BLIND_JSON)
        json.loads(roi.read_text(encoding="utf-8"))

    if roi is None:
        # FAIL CLOSED：没有人工 ROI 就绝不预测（也不允许任何自动 ROI 兜底）
        print("A3_ROI_REQUIRED")
        print("note: 人工 ROI 未完成 → 预测 FAIL CLOSED；禁止 Qwen/heuristic/auto ROI 兜底。")
        return 3

    # ---- 未来预测主体（今晚不执行；算法冻结 ca34678）----
    raise SystemExit("A3_PREDICTION_NOT_IMPLEMENTED_TONIGHT")


if __name__ == "__main__":
    sys.exit(main())
