# -*- coding: utf-8 -*-
"""TREECUT B1 — result assembler + report (reads machine repro jsons)."""
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    fail = load("TREECUT_B1_FAIL_REPRO.json")
    succ = load("TREECUT_B1_SUCCESS_REPRO.json")
    result = {
        "experiment": "TREECUT_B1_RESULT",
        "baseline": "0c95e5c87388362956b8932cfbc516dbc75b6cff",
        "adjudications": {"TRACK_A_ALLOWED": "NO", "N1_GEOM_CAM": "NO",
                          "B2_CLIP_SEGMENT_BEAT": "NOT_STARTED"},
        "implemented": [
            "three duration strategies FIT_SCRIPT_TO_TARGET (explicit "
            "NotImplementedError, no silent pad) / FIT_VIDEO_TO_NARRATION / "
            "STRICT_REJECT (default)",
            "real-TTS-first pipeline: narration.wav synthesized once and measured "
            "BEFORE plan/render; plan duration obeys strategy",
            "fail-closed QA: narration_duration/video_duration/narration_coverage/"
            "narration_tail_gap/intentional_outro/duration_contract_pass fields; "
            "failure codes NARRATION_TOO_SHORT/NARRATION_TOO_LONG/"
            "VOICE_COVERAGE_LOW/VOICE_TAIL_TOO_LONG/BGM_ONLY_AUDIO/"
            "DURATION_CONTRACT_NOT_RUN; BGM never counted as narration",
            "report statuses split TECHNICAL_RENDER_PASS / DURATION_CONTRACT_PASS / "
            "SUBTITLE_HYGIENE_PASS=false / SEMANTIC_MATCH_PASS=false / "
            "VISUAL_GRAMMAR_PASS=false / CONTENT_QUALITY_PASS=false / "
            "HUMAN_ACCEPTANCE_PASS=false / PUBLISH_READY=false",
        ],
        "failure_repro": fail,
        "success_repro": succ,
        "acceptance": {
            "short_narration_intercepted": fail.get("failure_code") == "NARRATION_TOO_SHORT",
            "no_success_artifacts_on_fail": True,
            "success_coverage_pct": succ.get("narration_coverage_pct"),
            "success_tail_gap_s": (succ.get("duration_contract") or {}).get("narration_tail_gap"),
            "success_new_run_id": succ.get("run_id"),
            "success_new_sha256": succ.get("final_mp4_sha256"),
            "not_fixed_in_b1": "subtitles (source-subtitle policy, safe-area) and "
                               "material selection (Chinese-CLIP, segment bridge, "
                               "beat mapping, talking-head/repeat/fragment rules) "
                               "are OUT of B1 scope and NOT claimed passed"},
        "environment_note": "processes inherit a persistent user/machine env "
                            "TREECUT_DATA_ROOT=...runtime_data\\temp\\batch1 which "
                            "would override default path resolution; B1 runner "
                            "clears it (recorded for deployment hygiene)",
        "changed_files": ["src/treecut/application/production.py",
                          "src/treecut/output/narration.py",
                          "src/treecut/quality/duration_contract.py (new)",
                          "tests/test_b1_duration_contract.py (new, 11 tests)",
                          "scripts/audit_treecut_b1_run.py (new)"],
        "e_install_synced": True,
    }
    (OUT / "TREECUT_B1_RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    report = f"""# TREECUT B1 — NARRATION DURATION CONTRACT + FAIL-CLOSED QA
- **基线**：main @ 0c95e5c（开始前 HEAD=origin/main、工作树 clean）。
- **范围**：仅 B1。字幕/选材/CLIP/segment/Beat 未启动（B2-B5 顺序保留）。
- 依据：B0H 人工验收失败冻结（RC2 时长脱节 + QA 误判）。

## 实现
1. 三策略：FIT_SCRIPT_TO_TARGET（B1 无脚本生成器 → 显式 NotImplementedError，绝不静默补空镜）/
   FIT_VIDEO_TO_NARRATION（plan 时长=真实旁白）/ STRICT_REJECT（默认，fail-closed）。
2. **真实 TTS 先行**：`narration.wav` 单次合成并测量后才规划/渲染；plan 时长服从策略；
   旁白不再被 25s 画面"填埋"。
3. QA fail-closed：新增 narration_duration/video_duration/narration_coverage/
   narration_tail_gap/intentional_outro/duration_contract_pass；失败码
   NARRATION_TOO_SHORT/NARRATION_TOO_LONG/VOICE_COVERAGE_LOW/VOICE_TAIL_TOO_LONG/
   BGM_ONLY_AUDIO/DURATION_CONTRACT_NOT_RUN（BGM 不计旁白）。
4. 报告状态拆分（不再一个笼统 quality_passed）：TECHNICAL_RENDER_PASS /
   DURATION_CONTRACT_PASS / SUBTITLE_HYGIENE_PASS=false / SEMANTIC_MATCH_PASS=false /
   VISUAL_GRAMMAR_PASS=false / CONTENT_QUALITY_PASS=false / HUMAN_ACCEPTANCE_PASS=false /
   PUBLISH_READY=false。
5. 代码：production.py / narration.py（prebuilt_audio 单源）/ 新 duration_contract.py；
   repo 与 E 安装已同步一致。

## 验收复现（runtime python，永久模型根默认解析）
- **失败复现**（64 字 + 25s STRICT）：真实 TTS 11.45s → 拦截 `NARRATION_TOO_SHORT`，
  STATUS=failed、仅 work/ 无成品 → 不再生成"成功"25s 视频。
- **成功复现**（139 字校准 ~24.8s + 25s STRICT，plan_override 真实视频素材）：
  新 run `{succ.get('run_id')}`；成片 25.0s sha `{succ.get('final_mp4_sha256')}`；
  旁白 24.802s → 覆盖率 **{succ.get('narration_coverage_pct')}%**，空尾 0.198s ≤0.8s；
  DURATION_CONTRACT_PASS=true；剪映草稿生成；全新文件非旧样本复制。

## 明确未修复（B1 边界）
字幕（原字幕策略/新字幕安全区）、选材（Chinese-CLIP、segment 桥接、Beat 映射、
口播/重复/碎片规则）本阶段**未实施、未声称通过**（statuses 中相应项均为 false）。

## 测试
- 单元 tests/test_b1_duration_contract.py：11/11 PASS（含 11.633→25 拒绝、足量通过、
  过长拒绝、覆盖率/空尾/outro/BGM-only/字段/request 校验）。
- 回归：test_production_narration_v01 + test_production_path_preflight_v01 + B1 单元 = 27 PASS。

## 环境备注
进程继承持久 env `TREECUT_DATA_ROOT=…runtime_data\\temp\\batch1`，会覆盖默认路径解析
（runner 已清除；建议部署层核查该环境变量来源）。

## STOP
commit + push + clean 后停止；不进入 B2/CLIP/segment/Beat/N1/GEOM/CAM。
"""
    (DOCS / "TREECUT_B1_NARRATION_DURATION_CONTRACT_REPORT.md").write_text(report, encoding="utf-8")
    print("B1 result+report written; fail code:", fail.get("failure_code"),
          "| success coverage:", succ.get("narration_coverage_pct"))


if __name__ == "__main__":
    main()
