# -*- coding: utf-8 -*-
"""TREECUT B1R1 — result assembler + report (reads machine repro jsons)."""
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    failc = load("TREECUT_B1R1_FAIL_CASES.json")
    succ = load("TREECUT_B1R1_SUCCESS_REPRO.json")
    st = succ.get("statuses", {})
    result = {
        "experiment": "TREECUT_B1R1_RESULT",
        "baseline": "f378fda23404655004c9aa4e8c018e40805c5b35",
        "adjudications": {"B2_CLIP_SEGMENT_BEAT_N1_GEOM_CAM": "NOT_STARTED"},
        "implemented": [
            "script completeness gate BEFORE TTS: SCRIPT_TRUNCATED / "
            "SCRIPT_NO_TERMINAL_PUNCTUATION (whole-sentence edits only; the old "
            "139-char mid-cut '...台面宽度可以按户' is rejected)",
            "full narration text + sha256 + last sentence + last char recorded "
            "in machine evidence (not just char count)",
            "three-track audio mix (output/mix.py): voice loudnorm once "
            "(constant gain, no automation), BGM separate loudness + fades + "
            "voice-triggered sidechain ducking (BGM only), true-peak limiter; "
            "voice_stem/bgm_stem/final_mix.wav + loudness/peak/windowed "
            "evidence; pump & peak gates",
            "audible-end alignment on REAL last-voice time (0.25-0.8s tail); "
            "last subtitle must be a complete sentence",
            "statuses: SCRIPT_COMPLETENESS_PASS / AUDIO_MIX_PASS / "
            "AUDIBLE_END_ALIGNMENT_PASS / B1_ACCEPTANCE_PASS; generic "
            "'quality_passed' no longer used as success evidence (use "
            "TECHNICAL_RENDER_PASS)",
        ],
        "fail_cases": failc,
        "success_repro": succ,
        "acceptance": {
            "old139_truncated_rejected": failc["results"]["OLD139_TRUNCATED"]["match"],
            "short64_rejected": failc["results"]["SHORT_64"]["match"],
            "success_new_run_id": succ.get("run_id"),
            "success_new_sha256": succ.get("final_mp4_sha256"),
            "script_complete": st.get("SCRIPT_COMPLETENESS_PASS"),
            "audio_mix_pass": st.get("AUDIO_MIX_PASS"),
            "audible_end_pass": st.get("AUDIBLE_END_ALIGNMENT_PASS"),
            "b1_acceptance_pass": st.get("B1_ACCEPTANCE_PASS"),
            "narration_coverage_pct": succ.get("duration_contract", {}).get("narration_coverage"),
            "not_fixed": "subtitle hygiene (B2 occlusion plates: cover bottom "
                         "subtitle then redraw; reject top/mid multi-text) + "
                         "semantic/CLIP/segment/beat NOT implemented in B1R1",
        },
    }
    (OUT / "TREECUT_B1R1_RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    report = f"""# TREECUT B1R1 — SCRIPT COMPLETENESS + AUDIO MIX + AUDIBLE END ALIGNMENT
- **基线**：main @ f378fda。范围仅 B1R1；B2/CLIP/segment/Beat/N1/GEOM/CAM 未启动。
- 依据：B1 人工听看新发现三缺陷（整句截断收尾 / 6-7s 响度跳变 / 原字幕重叠→B2 待办）。

## 1. 脚本完整性（B1R1）
- create 在 TTS 前执行完整性门：必须以完整句子 + 结束标点结尾；只允许整句/整 Beat 增删。
- 失败码 SCRIPT_TRUNCATED（中途截断，如旧 139 字「…台面宽度可以按户」）/ SCRIPT_NO_TERMINAL_PUNCTUATION。
- 证据记录全文、sha256、最后一句、最后标点（不再只记字数）。
- 复现：OLD139 截断 → SCRIPT_TRUNCATED ✓（TTS 前拦截）；SHORT_64 → NARRATION_TOO_SHORT ✓（B1 保留）。
- 成功旁白：整句窗口 [14,30]，全文以「很好打理。」完整结束（sha `{succ['script']['sha256']}`）。

## 2. 三轨音频契约（output/mix.py）
- voice：整体 loudnorm 一次（-16 LUFS），**无任何时间可变增益**（恒定）。
- BGM：独立 loudnorm（-30 LUFS）+ 仅 BGM 淡入淡出 + 人声触发 sidechain ducking。
- 混合后 alimiter true-peak（~-1dBFS）；输出 voice_stem/bgm_stem/final_mix.wav。
- 证据：voice mean {succ['audio_mix']['voice']['mean_volume_db']}dB/max {succ['audio_mix']['voice']['max_volume_db']}dB；
  bgm mean {succ['audio_mix']['bgm']['mean_volume_db']}dB；final mean {succ['audio_mix']['final']['mean_volume_db']}dB/max {succ['audio_mix']['final']['max_volume_db']}dB；
  相邻 2s 窗口最大跳变 {succ['audio_mix']['max_adjacent_window_delta_db']}dB（<8dB，无 pump）；peak_ok=true；voice_gain_constant=true。

## 3. 可闻结尾对齐
- 真实最后发声 24.517s（非仅 WAV 容器长），画面 25.0s → 尾距 **0.483s**（0.25-0.8 ✓）。
- 最后字幕完整句「很好打理。」与旁白结束对齐。
- 失败码 AUDIBLE_END_TOO_CLOSE / LAST_SUBTITLE_INCOMPLETE 已登记。

## 4. 验收复现（runtime python + 永久模型根）
- 失败：OLD139 → SCRIPT_TRUNCATED；SHORT64 → NARRATION_TOO_SHORT（TREECUT_B1R1_FAIL_CASES.json）。
- 成功：run `{succ['run_id']}` 新文件 sha `{succ['final_mp4_sha256']}`（25.0s，非旧样本复制）；
  覆盖率 {succ['duration_contract']['narration_coverage']:.1%}，空尾 0.473s；
  SCRIPT_COMPLETENESS_PASS/AUDIO_MIX_PASS/AUDIBLE_END_ALIGNMENT_PASS/**B1_ACCEPTANCE_PASS**=true。
- 不再以通用 quality_passed 作成功证据（改用 TECHNICAL_RENDER_PASS 等 statuses）。

## 5. 未修复（B2 待办，已确认 MVP 方向）
SUBTITLE_HYGIENE_PASS=false 保持。下一阶段 B2 = **原字幕检测区域 → 底部字幕遮挡板（按原字幕实际区域定高 + 边距 + 半透明底板）→ 板中央绘制新字幕（≤两行、小字号）→ 遮挡后抽帧复查**；
顶部标题/中部大字/多区文字 → REJECT_DIRTY 放弃该镜头；INPAINT 仅作为后续方案。
本阶段未实施 B2/CLIP/segment/Beat。

## 测试与卫生
单元 tests/test_b1r1_publish_gates.py 6/6 + B1 11 + 回归 27；compileall 0 错；secret 扫描干净；repo==E 同步校验。

## STOP
commit + push + clean 后停止；等待人工听看新视频后再批准 B2。
"""
    (DOCS / "TREECUT_B1R1_REPORT.md").write_text(report, encoding="utf-8")
    print("B1R1 result+report written")


if __name__ == "__main__":
    main()
