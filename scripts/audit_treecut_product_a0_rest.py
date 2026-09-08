# -*- coding: utf-8 -*-
"""A0 — E2E trace + gap map + two-track roadmap + risk register + user workflow."""
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")

def main():
    # ===== E2E TRACE (based on real 2026-08-06 production projects + current code) =====
    trace = {
        "experiment": "A0_E2E_TRACE_01",
        "evidence_basis": "real production projects 20260806_110330/120231 (STATUS=success) + current source",
        "script_input": "小户型岛台，可伸缩设计，分区收纳，实用尺寸，家庭办公与会客两用 (selling_points + narration from desktop)",
        "steps": [
            {"step": "script_input", "status": "REACHED_E2E_PROVEN", "function": "desktop._start_request",
             "artifact": "CreativeRequest(narration,selling_points,target_duration=30)", "id": "request dict"},
            {"step": "parser_beat_claim", "status": "NOT_FOUND_IN_PRODUCTION", "note": "no per-sentence beat split in prod chain; narration used whole"},
            {"step": "retrieval_query", "status": "REACHED_E2E_PROVEN", "function": "workflow/matching.py match_materials",
             "table": "materials.db media_files+analysis_jobs+sources", "artifact": "2 matches (media 5/6)", "caller": "ProductionService._create"},
            {"step": "candidate_segments", "status": "REACHED_E2E_PROVEN", "note": "whole-file clips (clip_seconds), not segment-based",
             "artifact": "matches with bge 0.569/0.61 clip 0.387/0.373"},
            {"step": "source_eligibility", "status": "PARTIAL", "note": "eligible_for_auto_edit used (3319); G1/A4 source-role gate is CAM-only not in prod matching"},
            {"step": "semantic_evidence", "status": "REACHED_E2E_PROVEN", "function": "semantic_scores BGE+CLIP", "artifact": "bge_scored=2 clip_scored=2 errors=[]"},
            {"step": "selection", "status": "REACHED_E2E_PROVEN", "function": "build_edit_plan category-dedup fill",
             "artifact": "plan 2 segments 30s complete"},
            {"step": "trim", "status": "REACHED_E2E_PROVEN", "function": "ffmpeg segment trim in render_video_plan", "artifact": "01_高清画面底片.mp4"},
            {"step": "timeline", "status": "REACHED_E2E_PROVEN", "function": "render_video_plan concat", "artifact": "preview mp4"},
            {"step": "voice_tts", "status": "REACHED_E2E_PROVEN", "function": "tts_local synthesize sherpa_onnx vits-melo", "artifact": "02_配音字幕预览.mp4 + voice_timeline.wav"},
            {"step": "new_subtitle", "status": "REACHED_E2E_PROVEN", "function": "narration.py burn_subtitles", "artifact": "TreeCut_成片.mp4 burned + narration.srt"},
            {"step": "bgm", "status": "REACHED_E2E_PROVEN", "function": "narration.py mix_background_music", "artifact": "03_配音音乐预览.mp4 + bgm_timeline.wav"},
            {"step": "qa", "status": "REACHED_E2E_PROVEN", "function": "inspection (final video/playback/burned subtitles/draft)", "artifact": "production_report quality passed=True"},
            {"step": "render_mp4", "status": "REACHED_E2E_PROVEN", "artifact": "TreeCut_成片.mp4 5.8MB 1080x1080@30"},
            {"step": "jianying_draft", "status": "REACHED_E2E_PROVEN", "function": "output/jianying.py", "artifact": "TreeCut_剪映草稿 draft_content.json real format"},
        ],
        "FIRST_REAL_E2E_BLOCKER": "NONE_IN_20260806_HISTORICAL_RUN (chain completed on 2026-08-06)",
        "current_repro_blocker": "HISTORICAL_MEDIA_PATH_INVALID — E2E 用过的 media 5/6 源文件当前不可读（旧 E:\\treecut-v13 素材路径已失效）；当前环境复现需先重新扫描接入现源盘素材",
        "not_reached": ["per-sentence beat/claim alignment (no such step exists in prod chain)"],
        "note": "historical E2E full-chain succeeded 2026-08-06 (2 projects success); media paths since invalid -> current re-run requires rescan"}
    (OUT / "TREECUT_A0_END_TO_END_TRACE.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== GAP MAP =====
    gap = {
        "P0_PRODUCT_BLOCKERS": [
            {"id": "P0_script_beat_parse", "desc": "生产链无脚本→逐句 Beat/Claim 拆分层（matching 整段匹配）",
             "evidence": "planning._fill_plan category-dedup; desktop narration free text; claim_visual CAM-only"},
            {"id": "P0_source_gate_in_prod", "desc": "Source/G1/A4 source-role gate 未接入生产 matching（只有 eligible flag）",
             "evidence": "production.py uses eligible_for_auto_edit; b007_source_role CAM-only"},
            {"id": "P0_media_path_validity", "desc": "历史 E2E 素材路径已失效；需当前源盘重扫才可复现",
             "evidence": "media 5/6 exists=False in current ROOTS"}],
        "P1_PRODUCT": [
            {"id": "P1_segment_based_selection", "desc": "生产链按整文件 clip 而非 segment 级选择", "evidence": "build_edit_plan clip_seconds on match.duration"},
            {"id": "P1_old_subtitle_handling", "desc": "硬字幕检测有（RapidOCR）但生产中裁剪/遮盖/换素材未接通", "evidence": "G1 note"},
            {"id": "P1_bgm_library", "desc": "仅 1 内置 BGM, 无授权曲库/版权管理", "evidence": "assets/bgm single mp3"},
            {"id": "P1_review_center_in_prod_flow", "desc": "ReviewCenterWindow 存在且可开, 但人工替换如何回流 production plan 未验证", "evidence": "desktop._open_review_center + plan_override path exists but unverified"}],
        "P2_PRODUCT": [
            {"id": "P2_voice_clone", "desc": "生产用 melo TTS 合成非克隆；克隆无授权/样音/运行证据", "evidence": "tts_local sherpa_onnx"},
            {"id": "P2_team_perm_backup", "desc": "团队/权限/备份/恢复未验证", "evidence": "unknown"}],
        "RESEARCH_NOT_BLOCKING_MVP": [
            {"id": "R1_cam_eh", "desc": "CAM/EH router/GEOM/action understanding = CAM LOCAL RESEARCH BLOCKER，不阻生产 MVP",
             "evidence": "SHADOW_NOT_PRODUCTION_CONNECTED; desktop no CAM import"},
            {"id": "R2_auto_publish", "desc": "AutoPublish 明确非目标"},
            {"id": "R3_learning_loop", "desc": "自动学习回流未验证真实效果"}],
        "product_vs_research_note": "P0/P1/P2 above are PRODUCT blockers; CAM/EH/GEOM are RESEARCH blockers (R-track) - must not gate Track A MVP"}
    (OUT / "TREECUT_A0_PRODUCT_GAP_MAP.json").write_text(
        json.dumps(gap, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== TWO TRACK ROADMAP =====
    twotrack = {
        "TRACK_A_SEMI_AUTO_MVP": {
            "goal": "脚本→Beat→推荐镜头→人工确认→时间线→配音字幕BGM→MP4/剪映草稿",
            "mvp_shape": "9:16 25-35s 单岛台模板 3候选 人工终审 禁自动发布",
            "already_working": ["素材检索(E1 E2E)", "匹配(E2E)", "时间线+渲染(F E2E)", "TTS配音(G3)", "字幕烧录(G4)",
                                "BGM(G5)", "MP4(H1)", "剪映草稿(H2)", "桌面UI(H3)"],
            "must_build_or_connect": ["脚本→Beat 拆分层(D2 NOT_FOUND)", "Source gate 接入生产(E2)", "人工替换回流生产(未验证)",
                                      "当前源盘素材重扫(P0)"],
            "note": "Track A 不依赖 Track B (CAM/EH/GEOM/动作理解)"},
        "TRACK_B_FULL_AUTO_RD": {
            "goal": "N0/N1/NEG families/Router/GEOM/动作理解/自动 Claim 验证",
            "status": "SHADOW research; N1_APPROVED=NO; PRESENT=YES ESTABLISHED=NO",
            "dependency": "不得自动成为 Track A 全部前置"},
        "parallelizable": "素材扫描/检索/渲染链(A-F,H) 与 CAM/EH 研究(Track B) 可并行；Track A MVP 不阻塞于 Track B"}
    (OUT / "TREECUT_A0_TWO_TRACK_ROADMAP.json").write_text(
        json.dumps(twotrack, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== RISK REGISTER =====
    risks = [
        {"severity": "P0", "risk": "脚本→镜头语义层缺失", "evidence": "D2 NOT_FOUND", "impact": "无法自动按句选镜", "blocking": True},
        {"severity": "P0", "risk": "历史素材路径失效", "evidence": "media 5/6 unreadable", "impact": "E2E 不可当前复现", "blocking": True},
        {"severity": "P1", "risk": "Source gate 未接入生产", "evidence": "prod matching uses eligible only", "impact": "可能选到不合格素材", "blocking": True},
        {"severity": "P1", "risk": "测试顺序依赖假绿", "evidence": "test_source_audit_r11/stage3 全量失败单独通过", "impact": "部分测试非隔离", "blocking": False},
        {"severity": "P1", "risk": "GPU 测试环境错位", "evidence": "test_stage2_vision 7 fail (system py CPU torch)", "impact": "需 runtime py 跑", "blocking": False},
        {"severity": "P2", "risk": "反馈仅 DB+ranking 未到 embedding/training", "evidence": "C3 note", "impact": "学习浅", "blocking": False},
        {"severity": "P2", "risk": "BGM 单曲无版权库", "evidence": "single mp3", "impact": "规模受限", "blocking": False},
        {"severity": "P2", "risk": "voice clone 未实现", "evidence": "melo TTS", "impact": "无克隆能力", "blocking": False},
        {"severity": "P2", "risk": "多套 DB(生产4表 vs CAM 88表)", "evidence": "two materials.db", "impact": "身份 confusion 风险", "blocking": False},
        {"severity": "P3", "risk": "README 路径 stale(G vs E)", "evidence": "README says G:", "impact": "误导", "blocking": False},
    ]
    (OUT / "TREECUT_A0_RISK_REGISTER.json").write_text(
        json.dumps({"risks": risks}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== USER WORKFLOW =====
    workflow = {
        "CURRENT_USER_WORKFLOW_ESTABLISHED": "PARTIAL",
        "note": "存在可操作的半自动产出链（扫描→分析→填文案→制作→MP4/剪映草稿→审核窗），但无'输入脚本自动拆镜'层；多数素材 unclassified 需先分析",
        "steps": [
            {"action": "启动 启动树剪v13.cmd", "result": "watchdog -> Tk desktop 打开"},
            {"action": "选择素材目录 扫描", "result": "媒体入 media_files，分析任务排队 (可看到 15378 已登记)"},
            {"action": "等待/查看分析", "result": "analysis_jobs 4347 完成含 caption/ASR/OCR/category"},
            {"action": "填写卖点词 + 文案 (或按卖点生成)", "result": "narration 文本框预填模板文案"},
            {"action": "选 输出MP4/剪映草稿 + 时长", "result": "ProductionService 后台制作"},
            {"action": "制作完成", "result": "output/projects/<ts>/ 下 TreeCut_成片.mp4 + TreeCut_剪映草稿 + cover + report"},
            {"action": "打开审核中心", "result": "review_center 可看任务/填审 (CAM-era 通道)"},
            {"action": "失败时", "result": "STATUS.json failed + advice (如 合格素材不足)"}],
        "missing_for_full_manual": "脚本→逐句镜选；人工替换后回流制作未验证；素材重扫后源可用性"}
    (OUT / "TREECUT_A0_USER_USABLE_WORKFLOW.json").write_text(
        json.dumps(workflow, ensure_ascii=False, indent=1), encoding="utf-8")
    print("trace/gap/roadmap/risk/workflow written")


if __name__ == "__main__":
    main()
