#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Overnight Run V1 监督器（LONG RUN SUPERVISOR）。

用法:
  python scripts/overnight_supervisor.py init          # 首启
  python scripts/overnight_supervisor.py task <id> <status> [note]   # 更新单任务
  python scripts/overnight_supervisor.py checkpoint [phase] [note]   # 落 checkpoint

状态文件: reports/storage/TREECUT_OVERNIGHT_RUN_STATE_V1.json
支持崩溃后继续 / 任务跳过 / quarantine / 幂等重跑（status 字段 + 记录）。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / "reports" / "storage" / "TREECUT_OVERNIGHT_RUN_STATE_V1.json"

# 夜间任务清单（id -> 名称）；status: pending/running/done/skipped/quarantined
TASKS = [
    ("P0-blind-integrity", "A3 blind machine input + key + leakage tests"),
    ("P0-runner-failclosed", "A3 blind runner prepare-only + scoring separation"),
    ("P1-observability", "A3 temporal observability audit (blind, no verdict)"),
    ("P1-obs-review-html", "人工 Observability Review HTML（不显示 GT/POS/NEG）"),
    ("P1-roi-hardening", "A3 ROI 页夜间硬化（快捷键/复制草稿/防零框）"),
    ("P2-contract-probe", "G1→G5 contract probe dry-run（非 A3 校准素材）"),
    ("P2-capability-matrix", "六层验证证据矩阵（CODE_EXISTS..PRODUCTION_READY）"),
    ("P3-candidate-benchmark", "大规模非 holdout 召回基准（≥100 media，仅 CANDIDATE）"),
    ("P3-falsepass-audit", "G2/G3 false-pass 审计 + 缺口记录"),
    ("P3-funnel", "Production Source 漏斗统计（G1→Shot）"),
    ("P4-dryrun", "生产链 dry-run（1-3 calibration 脚本/beat，空槽保留）"),
    ("P4-diagnostic-roughcut", "诊断 rough cut ≤3（NOT_FOR_PUBLISH，非 Pilot）"),
    ("P5-tests", "逐文件 bounded pytest 回归矩阵"),
    ("P5-code-quality", "legacy path / duplicate impl inventory（只读盘点）"),
    ("P6-report", "主报告 md+json + 桌面 TreeCut_Overnight_2026-09-05"),
    ("P6-final", "收尾：停 jobs、无 orphan、final checkpoint、FINAL TERMINAL SUMMARY"),
]


def git_head() -> str:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                       text=True, cwd=REPO)
    return r.stdout.strip() or "unknown"


def git_branch() -> str:
    r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True,
                       text=True, cwd=REPO)
    return r.stdout.strip() or "unknown"


def load() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def save(doc):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    doc = load()
    if cmd == "init":
        if doc:
            print("STATE EXISTS — 复用（幂等）")
        else:
            doc = {"run_id": "OVERNIGHT_RUN_V1",
                   "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "baseline_commit": git_head(), "current_branch": git_branch(),
                   "phase": "P0", "task": "init", "status": "running",
                   "checkpoints": [], "tasks": {tid: {"name": name, "status": "pending"}
                                                for tid, name in TASKS},
                   "errors": [], "storage_health": {}}
            save(doc)
        print("run_id:", doc.get("run_id"), "baseline:", doc.get("baseline_commit"))
    elif cmd == "task":
        tid, status = sys.argv[2], sys.argv[3]
        note = sys.argv[4] if len(sys.argv) > 4 else ""
        if tid not in doc["tasks"]:
            raise SystemExit(f"unknown task {tid}")
        doc["tasks"][tid]["status"] = status
        if note:
            doc["tasks"][tid]["note"] = note
        doc["tasks"][tid]["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save(doc)
        print(f"task {tid} -> {status}")
    elif cmd == "checkpoint":
        phase = sys.argv[2] if len(sys.argv) > 2 else doc.get("phase", "?")
        note = sys.argv[3] if len(sys.argv) > 3 else ""
        doc["checkpoints"].append({"at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                   "phase": phase, "commit": git_head(),
                                   "note": note})
        doc["phase"] = phase
        doc["last_checkpoint"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save(doc)
        print(f"checkpoint @ {phase} ({git_head()})")
    elif cmd == "status":
        print("phase:", doc.get("phase"), "status:", doc.get("status"))
        for tid, t in doc.get("tasks", {}).items():
            print(f"  [{t['status']:>11}] {tid} {t.get('note','')}")
        print("checkpoints:", len(doc.get("checkpoints", [])))
    else:
        raise SystemExit(f"unknown cmd {cmd}")


if __name__ == "__main__":
    main()
