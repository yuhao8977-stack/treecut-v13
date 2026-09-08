# -*- coding: utf-8 -*-
"""A0 — architecture map + data identity + test truth + evidence index + result."""
import hashlib
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def main():
    # ===== architecture map =====
    arch = {
        "real_launch_chain": "启动树剪v13.cmd -> runtime pythonw -m treecut.watchdog -> pythonw -m treecut.desktop (Tk UI)",
        "cli_entry": "treecut.main:main (--status/--scan/--catalog-scan)",
        "api_server": "treecut.api:main (FastAPI: submit/get/retry_job/category/tags/feedback)",
        "desktop_ui": "treecut.desktop (731 lines Tk: scan/generate/produce/narration/library/schedule/dashboard/review)",
        "browser_ui": "treecut.browser (XHS work browser, separate)",
        "formal_main_chain": "media scan -> analysis(worker/p2/p3: ffprobe+frames+Florence vision+RapidOCR+faster-whisper) -> "
                             "analysis_jobs result_json(category/objects/speech/selection) -> ProductionService._create: "
                             "load_candidates -> semantic_scores(BGE/CLIP) -> match_materials -> build_edit_plan -> "
                             "render_video_plan(mp4) -> create_narrated_video(melo TTS) -> mix_bgm -> burn_subtitles -> "
                             "build_jianying_draft -> QA inspect -> MP4+draft+cover+report",
        "experimental_chain": "CAM01 (scripts/posta3_cam01_*), MMVV/EH02 router, N0/N1 NEG (research; no prod caller)",
        "legacy_or_dual": "CAM analysis DB (temp/batch1 88 tables) separate from production DB (database 4 tables); "
                          "b007_* legacy tables in CAM db",
        "dead_or_orphan": "many src modules no prod caller (claim_visual/visual_beat/mmvl_master/action_subclip etc = CAM)",
        "production_db": "runtime_data/database/materials.db (4 tables: sources/media_files/analysis_jobs/media_tags)",
        "cam_db": "runtime_data/temp/batch1/database/materials.db (88 tables)",
        "config_load": "bootstrap() -> RuntimePaths.discover + settings",
        "models": "install models dir (LocalTTS vits-melo, Florence via torch hub cache G:), torch cache G:\\TreeCut_AI",
        "output": "runtime_data/output/projects/<ts>/",
        "note": "user today actually runs desktop Tk chain; CAM/EH are shadow research not in UI chain"}
    (OUT / "TREECUT_A0_CURRENT_ARCHITECTURE_MAP.json").write_text(
        json.dumps(arch, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== data identity =====
    di = {
        "identity_audit": {
            "media_files.id": {"meaning": "file identity (physical discovered file)", "pk": "id",
                               "table": "media_files", "prod_rows": 15378,
                               "parent": "sources.source_id", "consumers": "analysis_jobs.media_id"},
            "assets.asset_id": {"meaning": "canonical asset identity", "pk": "asset_id",
                                "table": "assets (CAM analysis db only)", "cam_rows": 22466,
                                "note": "NOT in production db — asset identity lives only in CAM db"},
            "segments.segment_id": {"meaning": "segment identity", "pk": "segment_id",
                                    "table": "segments (CAM db)", "cam_rows": 41834,
                                    "note": "NOT in production db; prod chain uses whole-file clips"},
            "analysis_jobs": {"identity": "job per media", "rows": 4347, "table": "analysis_jobs (prod db)",
                              "consumers": "load_candidates join"},
            "conflict_or_mix": {
                "two_db_split": "production db(4 tables) vs CAM db(88 tables) same file name materials.db in different dirs — 身份混淆风险",
                "entity_kind_mix": "b007_source_role_v1 uses entity_kind/entity_id generic (CAM); not in prod",
                "fourth_shot_id": "NOT_FOUND (shot_usage uses segment_id+beat_id)"},
            "sql_bypass": "NOT_EXHAUSTIVELY_AUDITED (scripts/*.py direct sqlite probes exist; service layer not proven bypass-free)"},
        "orphan_or_path_issue": {"historical_e2e_media_unreadable": "media 5/6 source paths invalid (old E:\\treecut-v13)"}}
    (OUT / "TREECUT_A0_DATA_IDENTITY_MAP.json").write_text(
        json.dumps(di, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== test truth =====
    tt = {
        "total_collected": 586, "files": 63,
        "run_result": {"passed": 570, "failed": 12, "xfailed": 4, "skipped": 0, "error": 0},
        "run_time_s": 184.57,
        "failures": {
            "test_stage2_vision.py (7)": "GPU/real-inference tests run under system python (CPU torch) — environment mismatch; "
                                         "expected RTX3050 CUDA; NOT code defect (runtime py has CUDA)",
            "test_source_audit_r11.py (3)": "workbench replace/trim/qa — pass when run alone -> ORDER-DEPENDENT/state pollution",
            "test_stage3 (2)": "people output structure / v2 smoke — pass alone -> same isolation issue"},
        "categories": {
            "unit": "majority", "integration": "some", "real_media": "few (CAM runners are real-frame, not pytest)",
            "artifact_regression": "EH02/EH01/EH01M1/EH01R1 test files read frozen JSON — ARTIFACT_REGRESSION_TEST (46 tests)",
            "synthetic": "some (camera/geometry synthetic)",
            "placeholder_or_dead": "not proven"},
        "cautions": ["artifact-regression tests verify frozen numbers not live behavior",
                     "12 failures include environment + order-dependency; 570 pass is NOT clean green"],
        "note": "586 collected / 570 passed / 12 failed / 4 xfailed in one full run (system py); "
                "GPU tests require runtime py"}
    (OUT / "TREECUT_A0_TEST_TRUTH_AUDIT.json").write_text(
        json.dumps(tt, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== evidence index =====
    ev = [
        ("PRE_RUN_BASELINE", "TREECUT_A0_PRE_RUN_BASELINE.json", "generated", "HEAD/origin/clean"),
        ("PROD_DB_SCHEMA", "runtime_data/database/materials.db (4 tables)", "authoritative", "prod chain tables"),
        ("PROD_DB_ROWS", "media_files 15378/analysis_jobs 4347/eligible 3319/classified 3207", "real", "db counts"),
        ("CAM_DB_ROWS", "temp/batch1: assets 22466/segments 41834/transcripts 51543/ocr 289218", "real", "CAM db"),
        ("REAL_ANALYSIS_JOB", "analysis_jobs result_json sample (Florence captions+objects+speech)", "real", "Domain B"),
        ("REAL_E2E_PROJECT", "output/projects/20260806_110330+120231 (success + full outputs)", "real", "E2E full chain"),
        ("E2E_FAILURE_EVIDENCE", "20260806_102815 failed: 合格素材不足", "real", "fail-closed"),
        ("MP4_OUTPUT", "TreeCut_成片.mp4 5.8MB 1080x1080@30", "real", "H1"),
        ("JIANYING_DRAFT", "TreeCut_剪映草稿/draft_content.json (tracks/materials)", "real", "H2"),
        ("TTS_EVIDENCE", "voice_timeline.wav + 02_配音字幕预览.mp4", "real", "G3"),
        ("SUBTITLE_EVIDENCE", "narration.srt + burned TreeCut_成片.mp4", "real", "G4"),
        ("BGM_EVIDENCE", "bgm_timeline.wav + 03_配音音乐预览.mp4", "real", "G5"),
        ("PROD_REPORT", "production_report.json (matches/plan/quality passed)", "real", "E2E QA"),
        ("DESKTOP_UI", "src/treecut/desktop.py 731 lines", "code", "H3"),
        ("API", "src/treecut/api.py FastAPI", "code", "H4"),
        ("PROD_CHAIN_SRC", "application/production.py + workflow/{matching,planning} + output/{mp4,narration,jianying,inspection,cover}", "code", "main chain"),
        ("ASR_OCR_SRC", "asr/engine.py (faster-whisper) + ocr/engine.py (RapidOCR)", "code", "Domain B"),
        ("MODELS", "models/tts_local.py sherpa_onnx + vision_florence + registry", "code", "models"),
        ("CAM_EH_RESEARCH", "EH02 router/scripts/posta3_cam01_* + N0 decision status", "generated", "Track B shadow"),
        ("N0_STATUS", "TREECUT_CAM01_EH02N0_ARCHITECT_DECISION_STATUS.json", "generated", "N1=NO/PRESENT=YES"),
        ("TEST_RUN", "586 collected/570 pass/12 fail/4 xfail", "run", "test truth"),
        ("HISTORICAL_E2E_MEDIA_INVALID", "media 5/6 exists=False", "real", "repro blocker"),
    ]
    entries = []
    for label, path, status, supports in ev:
        entries.append({"evidence": label, "path_or_value": path, "status": status, "supports": supports})
    (OUT / "TREECUT_A0_EVIDENCE_INDEX.json").write_text(
        json.dumps({"entries": entries, "count": len(entries)}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== result =====
    res = {
        "experiment": "TREECUT_A0_RESULT",
        "baseline": "740ca949fd30388d4887a7eb0edd46a440528f2d",
        "overall_product_state": "半自动素材资产+生产链真实存在且 2026-08-06 E2E 跑通(MP4+剪映草稿)；"
                                 "但脚本→逐句镜选层缺失、素材源路径失效需重扫、Source-gate 未接入生产；CAM/EH 为 shadow 未连生产",
        "current_user_workflow": "PARTIAL (可操作产出链存在；无脚本自动拆镜层)",
        "capability_domains": {
            "A_ASSET_INGESTION": "DATA_CONNECTED", "B_SEGMENT_MM": "DATA_CONNECTED",
            "C_KNOWLEDGE_FEEDBACK": "E2E_PROVEN(feedback consumed)", "D_SCRIPT_CLAIM_TEMPLATE": "NOT_FOUND(beat)/USER_USABLE(manual input)",
            "E_RETRIEVAL_SELECTION": "E2E_PROVEN", "F_TIMELINE_EDITING": "E2E_PROVEN",
            "G_SUBTITLE_VOICE_BGM": "E2E_PROVEN", "H_OUTPUT_UI_OPS": "USER_USABLE",
            "CAM_EH_RESEARCH": "UNIT_TESTED(SHADOW)"},
        "capability_level_counts": {"DATA_CONNECTED": 12, "E2E_PROVEN": 11, "CODE_EXISTS": 4,
                                    "USER_USABLE": 3, "NOT_FOUND": 2, "UNIT_TESTED": 1},
        "real_db_material_connected": True,
        "e2e_trace_last_success": "jianying_draft (full chain reached 2026-08-06)",
        "FIRST_REAL_E2E_BLOCKER": "NONE_in_2026-08-06_historical_run; CURRENT repro blocker = historical media paths invalid",
        "mp4_actual_output": "YES(2026-08-06)", "jianying_draft_actual_output": "YES(2026-08-06)",
        "voice_clone_actual": "NO(melo TTS synthesis only)", "new_subtitle_actual": "YES", "bgm_actual": "YES",
        "human_feedback_consumed": "PARTIAL (DB stored + ranking adjustment read in match; not embedding/training)",
        "cam_eh_production_caller": "NO (SHADOW_NOT_PRODUCTION_CONNECTED)",
        "n0_state_preserved": "YES (N1=NO/PRESENT=YES/ESTABLISHED=NO/GEOM=NO/NEW_NEG=0)",
        "gap_counts": {"P0": 3, "P1": 4, "P2": 3, "RESEARCH": 3},
        "shortest_mvp_blockers": ["D2 script→beat parse (NOT_FOUND)", "source-gate into prod matching",
                                  "current media rescan (paths invalid)"],
        "track_a_recommendation": "连接已有链(检索/渲染/TTS/字幕/BGM/草稿) + 建脚本拆层 + 人工确认门；不依赖 Track B",
        "track_b_recommendation": "CAM/EH/GEOM/动作理解保持 shadow 研究；N1 暂停",
        "tests": "586 collected/570 pass/12 fail/4 xfail(全量一次, system py)",
        "no_overall_pct": "按证据等级不输出百分比"}
    (OUT / "TREECUT_A0_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("arch/map/identity/testtruth/evidence/result written")


if __name__ == "__main__":
    main()
