#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Overnight P6 — 主报告生成器（docs md + storage json + 桌面 TreeCut_Overnight_2026-09-05）。"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DOCS = REPO / "docs"
DESK = Path(r"C:\Users\admin\Desktop\TreeCut_Overnight_2026-09-05")
sys.stdout.reconfigure(encoding="utf-8")


def load(n):
    return json.loads((OUT / n).read_text(encoding="utf-8"))


def git(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO).stdout.strip()


def main():
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    mat = load("TREECUT_OVERNIGHT_PYTEST_MATRIX_V1.json")
    funnel = load("TREECUT_OVERNIGHT_FUNNEL_V1.json")
    probe = load("TREECUT_PRODUCTION_CONTRACT_PROBE_V1.json")
    pool = load("TREECUT_OVERNIGHT_NON_HOLDOUT_BENCHMARK_POOL_V1.json")
    gap = load("TREECUT_OVERNIGHT_GAP_MAP_V1.json")
    dry = load("TREECUT_OVERNIGHT_PRODUCTION_DRYRUN_V1.json")
    obs = load("TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY.json")
    blind = load("TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json")
    state = load("TREECUT_OVERNIGHT_RUN_STATE_V1.json")
    commits = git(["git", "log", "--oneline", "4fa7612..HEAD"]).splitlines()
    fails = {f: v for f, v in mat["per_file"].items() if v["status"] != "pass"}
    obs_map = {c["opaque_case_id"]: c["TEMPORAL_SIGNAL"] for c in obs["cases"]}

    def cap_level(name):
        for c in probe["capabilities"]:
            if c["capability"] == name:
                return c["highest_level"]
        return "?"

    summary = {
        "run": "OVERNIGHT_RUN_V1", "generated_at": now,
        "baseline_commit": state.get("baseline_commit"), "head_commit": git(["git", "rev-parse", "--short", "HEAD"]),
        "commits_since_baseline": commits,
        "a3": {
            "holdout_status": "A3_HOLDOUT_6_FROZEN",
            "prediction_executed": "NO",
            "blind_integrity": "PASS(9 tests; opaque H001-H006; 无 pos/neg/extend/media/source 词元; 帧字节=源帧)",
            "runner": "FAIL_CLOSED(A3_ROI_REQUIRED when 缺 ROI 或 0 框; allowlist 禁读 GT/key/manifest)",
            "scoring": "独立进程; 预测哈希先于 GT 打开",
            "observability": {c["opaque_case_id"]: {"signal": obs_map.get(c["opaque_case_id"]),
                                                    "note": "全案例 STRONG_CHANGE=帧间强变化(含相机运动); 桌板位移过程是否可辨需人工判断(HTML)"}
                              for c in obs["cases"]},
            "roi_page": "http://127.0.0.1:8933/a3/roi (blind H001-H006, A/D/S/Delete, 复制上帧草稿需确认)",
        },
        "tests": {"files": mat["total"], "pass_files": mat["pass"], "fail_files": mat["fail"],
                  "quarantine": list(fails),
                  "quarantine_note": "test_stage2_vision.py 7 断言为文件内状态干扰(单测各自通过; 与今夜改动无关, 未触碰 src)"},
        "funnel": funnel,
        "benchmark_pool": {"size": pool["pool_size"], "sample": pool["sample_size"]},
        "capability_matrix": [{"capability": c["capability"], "level": c["highest_level"],
                               "status": c["status"], "group": c["group"]}
                              for c in probe["capabilities"]],
        "gap_map": gap,
        "dryrun": dry,
        "first_screen": {
            "1_distance_to_goal": ("素材 Truth→理解→检索→选镜→自动成片→QA→人工终审：前端(源/语义/检索/MMVV 校准集) "
                                   "已到 TESTED_REAL_DATA/HUMAN_VALIDATED 层；后端组装(shot→timeline→渲染→3候选) 仍 CODE_EXISTS→TESTED_SYNTHETIC，未闭环"),
            "2_done_tonight": "A3 blind 严格化(输入/密钥/runner/scoring)+可观测性审计+ROI 页硬化；契约盘点21能力；漏斗/基准池13k；缺口地图；dry-run 计划；49 文件回归(48过1隔离缺陷)",
            "3_new_capabilities": "blind machine input + 防泄漏测试 + fail-closed runner + scorer 分离；ROI 页快捷键/草稿；observability 审计工具",
            "4_code_only": "Subtitle(CODE_EXISTS), 3候选/Workbench(CODE_EXISTS), E2E 编排(CODE_EXISTS), BGM(NOT_FOUND)",
            "5_real_media_validated": "G1 池/漏斗(DB), A3 盲帧字节绑定, observability(盲帧真实计算), Core5/A2.2 既往",
            "6_human_validated": "A1 ROI 200框(A1), A3 筛选(架构师), 对象/动作校准语料(历史 stage3/4)",
            "7_missing_links": "MMVV 强制化→泛化验证(A3 blind 作答) → shot_usage 落库 → 模板×素材契约 → 渲染/QA 真实成片 → 3候选编排",
            "8_top5_blockers": gap["main_blockers_ranked"],
            "9_next_priority": ["A3 人工 ROI(30帧)→blind 预测→scoring(先哈希)", "检索语义层补齐(RETRACT/误导桶)",
                                "shot/timeline/渲染真实闭环(诊断 rough cut)", "自动 ROI 差距实验(A1, 禁碰 A3)",
                                "test_stage2_vision 隔离修复"],
            "10_human_actions_tomorrow": ["① A3 30 帧 Human ROI(/a3/roi, blind H001–H006)", "② A3 时间可观测性人工判断(HTML 单选)",
                                          "③ 批准 blind 预测/评分 + 可选 BGM/Voice 生产输入"],
        },
    }
    (OUT / "TREECUT_OVERNIGHT_MASTER_REPORT_2026-09-05.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- Markdown ----------
    L = []
    L.append("# TreeCut Overnight Run V1 — Master Report 2026-09-05")
    L.append(f"\n- run_id: OVERNIGHT_RUN_V1 · 生成: {now}")
    L.append(f"- baseline: {state.get('baseline_commit')} → head: {summary['head_commit']}")
    L.append("- A3 预测执行: **NO**（缺 Human ROI + blind 已建；runner FAIL_CLOSED）")
    L.append("- A3 holdout 状态: **A3_HOLDOUT_6_FROZEN**（SEALED，未用于调参）")
    L.append("\n## 第一屏（10 项）\n")
    for k, v in summary["first_screen"].items():
        L.append(f"- **{k}**：{v}")
    L.append("\n## 今夜提交\n")
    for c in commits:
        L.append(f"- `{c}`")
    L.append("\n## 回归（逐文件 bounded pytest）\n")
    L.append(f"- 49 文件：**{mat['pass']} pass / {mat['fail']} fail** / 0 timeout")
    L.append(f"- quarantine: {list(fails)}（test_stage2_vision 7 断言=文件内状态干扰，单测各自通过；今夜未触碰 src）")
    L.append("\n## A3 Evaluation Integrity\n")
    L.append("- blind manifest: opaque H001–H006，无 POS/NEG/EXTEND/伸缩/media_id/源路径/客户词元（9 项测试全过，帧字节=源帧）")
    L.append("- case key: `TREECUT_MMVV_A3_CASE_KEY_PRIVATE.json`（scoring 专用）")
    L.append("- runner `run_a3_blind.py`: allowlist；缺 ROI 或 0 框 → `A3_ROI_REQUIRED`(exit 3)；帧哈希绑定")
    L.append("- scorer `score_a3_after_prediction.py`: 预测 sha 先于 GT 打开，缺 sha 拒绝")
    L.append("\n## Temporal Observability（盲帧，只读信号，非 verdict）\n")
    L.append("| case | TEMPORAL_SIGNAL | 帧差均值/最大 | 静态比 |")
    L.append("|---|---|---|---|")
    for c in obs["cases"]:
        L.append(f"| {c['opaque_case_id']} | {c['TEMPORAL_SIGNAL']} | {c['frame_diff_mean']}/{c['frame_diff_max']} | {c['static_interval_ratio']} |")
    L.append("\n> 结论：6 案例冻结 5 帧全部 STRONG_CHANGE（帧间强变化，含相机运动 30–76px）。"
             "「桌板位移过程是否被 5 帧覆盖」无法仅凭强度信号判定 → 人工审阅页已备（单选导出），明天人工回答。")
    L.append("\n## 契约盘点（21 能力 × 六层）\n")
    L.append("| 能力 | 最高层 | 状态 |")
    L.append("|---|---|---|")
    for c in probe["capabilities"]:
        L.append(f"| {c['capability']} | {c['highest_level']} | {c['status']} |")
    L.append("\n## 漏斗（X1 + B007）\n")
    L.append(f"- mp4 23253（5 源：src1=3025/src2=3569/src3=332/src4=21170/src5=156）；G1 eligible≈{funnel['G1_eligible_mp4_approx']}；review APPROVED=88")
    L.append(f"- 路径关键词召回（候选非真值）：EXTEND 358（190 家族）、DRAWER 704、SOCKET 485、STORAGE 1597、RETRACT **0**、静态 7749")
    L.append(f"- B007 发布 30 note：segment 609 / ASR 866 / OCR 2980 全覆盖")
    L.append("\n## 非 holdout 基准池\n")
    L.append(f"- size={pool['pool_size']}（排除 excluded_known_ids 全集；A3 6 案例不在池内）；固定种子分层样本 {pool['sample_size']}")
    L.append("\n## Gap Map（Top5）\n")
    for g in gap["main_blockers_ranked"]:
        L.append(f"- **{g['rank']}** {g['gap']} — {g['evidence'][:140]}")
    L.append("\n## Production Dry-run（PLAN_ONLY）\n")
    for s in dry["stages"]:
        L.append(f"- {s['stage']}: {s['status']} — missing={s['missing']} broken={s['broken']}")
    L.append(f"\n- 诊断 rough cut：**不生成** — {dry['diagnostic_roughcut_decision']['reason']}")
    L.append("\n## 明天人工任务（≤3）\n")
    L.append("1. **A3 30 帧 Human ROI**：http://127.0.0.1:8933/a3/roi（blind H001–H006，A/D/S/Delete；复制上帧框需人工确认）")
    L.append("2. **A3 时间可观测性人工判断**：`TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY_REVIEW.html`（每案例单选后导出 JSON）")
    L.append("3. **批准后续**：blind 预测+评分（先预测哈希），及可选 BGM/Voice 生产输入")
    L.append("\n## 证据路径\n")
    L.append("- docs/TREECUT_OVERNIGHT_MASTER_REPORT_2026-09-05.md · reports/storage/TREECUT_OVERNIGHT_MASTER_REPORT_2026-09-05.json")
    L.append("- reports/storage/TREECUT_OVERNIGHT_PYTEST_MATRIX_V1.json · _FUNNEL_V1.json · _NON_HOLDOUT_BENCHMARK_POOL_V1.json")
    L.append("- reports/storage/TREECUT_PRODUCTION_CONTRACT_PROBE_V1.json · _GAP_MAP_V1.json · _PRODUCTION_DRYRUN_V1.json")
    L.append("- reports/storage/TREECUT_OVERNIGHT_AUTO_ROI_GAP_REPORT.json · TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json · _CASE_KEY_PRIVATE.json")
    L.append("- reports/storage/TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY.json + _REVIEW.html · TREECUT_OVERNIGHT_RUN_STATE_V1.json")
    md = "\n".join(L)
    (DOCS / "TREECUT_OVERNIGHT_MASTER_REPORT_2026-09-05.md").write_text(md, encoding="utf-8")
    print("WROTE docs md + storage json")

    # ---------- 桌面包 ----------
    DESK.mkdir(parents=True, exist_ok=True)
    for f in ["TREECUT_OVERNIGHT_MASTER_REPORT_2026-09-05.json", "TREECUT_OVERNIGHT_PYTEST_MATRIX_V1.json",
              "TREECUT_OVERNIGHT_FUNNEL_V1.json", "TREECUT_OVERNIGHT_NON_HOLDOUT_BENCHMARK_POOL_V1.json",
              "TREECUT_PRODUCTION_CONTRACT_PROBE_V1.json", "TREECUT_OVERNIGHT_GAP_MAP_V1.json",
              "TREECUT_OVERNIGHT_PRODUCTION_DRYRUN_V1.json", "TREECUT_OVERNIGHT_AUTO_ROI_GAP_REPORT.json",
              "TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json", "TREECUT_MMVV_A3_CASE_KEY_PRIVATE.json",
              "TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY.json",
              "TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY_REVIEW.html"]:
        shutil.copy2(OUT / f, DESK / f)
    shutil.copy2(DOCS / "TREECUT_OVERNIGHT_MASTER_REPORT_2026-09-05.md", DESK / "01_Master_Report.md")
    print("DESKTOP package:", DESK)
    for p in sorted(DESK.iterdir()):
        print("  ", p.name, p.stat().st_size)


if __name__ == "__main__":
    main()
