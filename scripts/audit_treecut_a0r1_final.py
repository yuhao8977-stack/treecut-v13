# -*- coding: utf-8 -*-
"""A0 R1 — THREE E2E STATES + TEST TRUTH + GAP MAP (corrected) + EVIDENCE INDEX + RESULT + DEFECT AUDIT.
Evidence read from real artifacts produced by audit scripts.
"""
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    # ===== THREE E2E STATES =====
    hist = load("TREECUT_A0R1_HISTORICAL_ARTIFACT_MANIFEST.json")
    repro = load("TREECUT_A0R1_CURRENT_REPRODUCTION.json")
    # historical success projects
    succ = [k for k, v in hist.items() if v.get("status") == "success"]
    failed = [k for k, v in hist.items() if v.get("status") == "failed"]
    hist_inputs = set()
    for k in succ:
        m = hist[k].get("report") or {}
        hist_inputs.add(str(m.get("request_narration"))[:40])
    three = {
        "A_HISTORICAL_REDUCED_CHAIN": {
            "evidence": "2026-08-06 projects",
            "success_projects": succ, "failed_projects": failed,
            "unique_inputs": len(hist_inputs),
            "note": "2 success projects share same narration+media [6,5] -> same input run twice, not 2 independent E2E",
            "last_reached": "jianying_draft (full reduced chain output existed)",
            "first_blocker": "NONE in historical reduced chain",
            "mp4": "YES(historical)", "jianying": "YES(historical)"},
        "B_CURRENT_REDUCED_CHAIN": {
            "evidence": "a0r1_repro3 live run on current baseline bdc7506",
            "current_run": repro.get("status"),
            "last_reached": "render (01_高清画面底片.mp4 15.7MB generated)" if repro.get("mp4", {}).get("exists") else "before render",
            "first_blocker": repro.get("first_blocker"),
            "mp4_generated_current": repro.get("mp4", {}).get("exists", False),
            "jianying_generated_current": False,
            "current_e2e_proven": False,
            "note": "chain validated+matching+plan+render real; TTS blocked by sherpa-onnx reading date.fst under Chinese install path"},
        "C_TARGET_PRODUCT_CHAIN": {
            "definition": "script -> Beat/Claim -> segment-level -> human confirm/replace -> timeline -> 9:16 -> 3 candidates -> MP4/Jianying",
            "last_reached": "script_input (manual narration only; no beat layer)",
            "first_blocker": "SCRIPT_TO_BEAT_CLAIM_NOT_FOUND",
            "not_reached": ["Beat/Claim parse", "segment-level candidates", "human confirm/replace loop",
                            "3-candidate generation", "target chain E2E"]},
        "FIRST_REAL_TARGET_BLOCKER": "SCRIPT_TO_BEAT_CLAIM_NOT_FOUND"}
    (OUT / "TREECUT_A0R1_THREE_E2E_TRACE.json").write_text(
        json.dumps(three, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== TEST TRUTH (both interpreters, real) =====
    tt = {
        "system_python": {"interpreter": "C:\\Users\\admin\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
                          "torch_cuda": False, "result": {"collected": 586, "passed": 570,
                                                           "failed": 12, "xfailed": 4, "skipped": 0},
                          "runtime_s": 184.57,
                          "failures_by_file": {"test_stage2_vision.py": 7, "test_source_audit_r11.py": 3,
                                               "test_stage3_mini_v2.py": 1, "test_stage3_model_dev.py": 1}},
        "runtime_python": {"interpreter": "E:\\树剪整理\\02_安装程序\\TreeCut_v13\\runtime\\python.exe",
                           "torch_cuda": True, "run_partial": {
                               "test_stage2_vision.py": {"passed": 13, "failed": 0, "runtime_s": 50.64,
                                                         "note": "all GPU tests pass under runtime py"}}},
        "classification": {
            "gpu_7_fail": "ENVIRONMENT_MISMATCH_CONFIRMED (system py CPU torch; runtime py CUDA passes 13/13)",
            "order_dependent_5": "TEST_ISOLATION_DEFECT (pass when run alone; fail in full suite order) - not removed",
            "artifact_regression": "46 EH02/EH01M1/EH01R1/EH01 tests read frozen JSON"},
        "note": "12 fail NOT clean-green; 5 isolation defects remain defects even if pass-alone"}
    (OUT / "TREECUT_A0R1_TEST_TRUTH.json").write_text(
        json.dumps(tt, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== GAP MAP corrected (P2 fixed to actual count, unified rules) =====
    gap = {
        "P0_PRODUCT_BLOCKERS": [
            {"id": "P0_script_beat_parse", "desc": "生产链无脚本→逐句 Beat/Claim 拆分层", "evidence": "D2 NOT_FOUND in production chain"},
            {"id": "P0_tts_chinese_path", "desc": "sherpa-onnx 读 LocalTTS date.fst 在中文安装路径失败（当前 reproduction blocker）",
             "evidence": "a0r1_repro3 STATUS error date.fst"},
            {"id": "P0_current_e2e_not_proven", "desc": "当前 baseline 全链（含 TTS/字幕/BGM/MP4/草稿）未跑通", "evidence": "repro stops at TTS"}],
        "P1_PRODUCT": [
            {"id": "P1_source_gate_prod", "desc": "Source/A4 gate 未接入生产 matching（仅 eligible flag）", "evidence": "prod matching uses eligible"},
            {"id": "P1_segment_bridge", "desc": "生产库(4表)与 CAM/segment 库(88表) 身份不互连；Track A 若需 segment 级选择需桥接", "evidence": "two materials.db; prod no assets/segments"},
            {"id": "P1_old_subtitle", "desc": "硬字幕检测有(RapidOCR) 但生产中拒绝/裁剪策略未验证", "evidence": "OCR data exists; no prod handling"},
            {"id": "P1_9x16_multi_shot", "desc": "历史产物 1080x1080 2 整片段；9:16 多镜头信息流混剪未验证（repro render vertical 成功但被 TTS 阻断）", "evidence": "hist canvas square; repro vertical mp4 exists"}],
        "P2_PRODUCT": [
            {"id": "P2_bgm_library", "desc": "仅 1 内置 BGM 无版权曲库管理", "evidence": "single mixkit mp3"},
            {"id": "P2_voice_clone", "desc": "生产用 melo TTS 非克隆", "evidence": "tts_local sherpa_onnx"}],
        "RESEARCH_NOT_BLOCKING_MVP": [
            {"id": "R1_cam_eh", "desc": "CAM/EH/GEOM/N0 动作理解 research", "evidence": "SHADOW_NOT_PRODUCTION_CONNECTED"},
            {"id": "R2_auto_publish", "desc": "非目标"}, {"id": "R3_team_ops", "desc": "团队/权限/备份"}],
        "unified_rule": "P0=阻当前半自动闭环 / P1=较强自动化所需 / P2=规模体验 / RESEARCH=不阻 MVP"}
    (OUT / "TREECUT_A0R1_GAP_MAP.json").write_text(
        json.dumps(gap, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== RESULT =====
    # actual_baseline derived from machine-captured REAL_BASELINE (NOT hardcoded):
    # start state clean (bdc7506, 0 untracked); generation-time dirt = A0R1 files only
    real = load("TREECUT_A0R1_REAL_BASELINE.json")
    start = real["start_state_before_a0r1"]
    res = {
        "experiment": "TREECUT_A0R1_RESULT",
        "baseline": "bdc7506005c3914049f56d6c38020a0fc2797b41",
        "a0_status": "DIRECTIONALLY_USEFUL_BUT_EVIDENCE_NOT_CLOSED (preserved)",
        "actual_baseline": {
            "start_clean": start["tracked_clean"],           # True (git empty before A0R1)
            "start_untracked": start["untracked_count"],     # 0
            "generation_tracked_files_clean": real["tracked_files_clean"],   # True (no tracked mods)
            "generation_untracked": real["untracked_count"],                 # 16 = A0R1 outputs only
            "untracked_all_a0r1_outputs": real["untracked_all_are_a0r1_outputs"],
            "head_eq_origin": real["head"] == real["origin_main"],
            "source": "derived from TREECUT_A0R1_REAL_BASELINE.json (machine git capture)"},
        "production_db_path": {"valid": 15246, "missing": 132, "total": 15378,
                               "eligible_valid": 3260, "eligible_missing": 59},
        "cam_db": {"assets": 22466, "segments": 41834, "transcripts": 51543, "ocr": 289218,
                   "segments_with_asset": 41834, "distinct_assets": 22391},
        "historical": {"projects": 4, "success": 2, "unique_inputs": 1,
                       "note": "2 success = same input rerun"},
        "three_e2e": three,
        "current_reproduction": {"PASS": False, "last_reached": "render",
                                 "blocker": "TTS_MODEL_LOAD_CHINESE_PATH",
                                 "mp4_render_generated": True, "final_mp4": False, "jianying": False},
        "capability_regrade_note": "A0 E2E_PROVEN(11) mostly downgraded to HISTORICALLY_E2E_PROVEN; "
                                   "current reduced chain reaches render only; target chain first blocker SCRIPT_TO_BEAT_CLAIM_NOT_FOUND",
        "test_truth": tt,
        "gap_counts": {"P0": 3, "P1": 4, "P2": 2, "RESEARCH": 3},
        "corrected_shortest_mvp_blockers": ["P0_script_beat_parse", "P0_tts_chinese_path", "P0_current_e2e_not_proven",
                                            "P1_segment_bridge", "P1_9x16_multi_shot"],
        "n0_preserved": "YES (N1=NO/PRESENT=YES/ESTABLISHED=NO/GEOM=NO/NEW_NEG=0)",
        "stop": True}
    (OUT / "TREECUT_A0R1_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("three_e2e / test_truth / gap / result written")


if __name__ == "__main__":
    main()
