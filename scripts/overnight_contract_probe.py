#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Overnight P2 — G1→G5 生产契约探针（只读盘点 + 代码存在校验 + 证据层级）。

不运行完整生产链；对每能力输出 code_refs(存在性校验)/tests/real_data_evidence/
highest_level/status/blocker。与 pytest 矩阵(背景任务)结果合并后进主报告。
"""
import json
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
SRC = REPO / "src" / "treecut" / "services"
SCRIPTS = REPO / "scripts"
sys.stdout.reconfigure(encoding="utf-8")

LEVELS = ["NOT_FOUND", "CODE_EXISTS", "INTEGRATED", "TESTED_SYNTHETIC",
          "TESTED_REAL_DATA", "HUMAN_VALIDATED", "PRODUCTION_READY"]


def exists(rel: str) -> bool:
    p = REPO / rel
    return p.exists()


def svc(name: str) -> str:
    return f"src/treecut/services/{name}.py"


CAPS = [
    {"capability": "素材导入/资产指纹", "group": "Source",
     "code_refs": ["src/treecut/services/canonical_truth.py", "src/treecut/services/identity.py",
                   "scripts/stage3a2_import.py", "scripts/stage3a2_write_db.py"],
     "tests": ["tests/test_phase1_identity.py", "tests/test_p1_assets.py", "tests/test_p1_migrate.py"],
     "real_data_evidence": "media_files 28252(mp4 23253, 5 源), assets 22466(指纹/探测), 分层抽查入库",
     "highest_level": "TESTED_REAL_DATA", "status": "PARTIAL",
     "blocker": "B007 主库仅 30 note 侧管线；X1 大池为资产库非发布管线"},
    {"capability": "素材去重", "group": "Source",
     "code_refs": ["src/treecut/services/production_dedup.py", "scripts/hrp_dedup.py"],
     "tests": ["tests/test_g5_dedup_qa.py"],
     "real_data_evidence": "A3 候选 1985≡1986/1987≡1988 帧级重复被检出；dedup 测试 10 过",
     "highest_level": "TESTED_REAL_DATA", "status": "PARTIAL",
     "blocker": "shot_usage=0（镜头级去重尚未在生产链消费）"},
    {"capability": "ASR", "group": "Semantic",
     "code_refs": ["scripts/stage3a1_import_spec.py"],
     "tests": ["tests/test_p2_scene_asr_ocr.py"],
     "real_data_evidence": "transcripts 51543 行(asset 键控, faster-whisper-large-v3), B007 30 note 全有 ASR(866 行)",
     "highest_level": "TESTED_REAL_DATA", "status": "PARTIAL",
     "blocker": "置信度低文本(负值)未清洗；未见全库质量审计"},
    {"capability": "OCR/字幕检测", "group": "Semantic",
     "code_refs": ["scripts/stage3a1_import_spec.py"],
     "tests": ["tests/test_p2_scene_asr_ocr.py"],
     "real_data_evidence": "ocr_text 289218 行 + fts_ocr；B007 30 note 全有 OCR(2980 行)",
     "highest_level": "TESTED_REAL_DATA", "status": "PARTIAL",
     "blocker": "OCR 文本≠动作证据；语义消费路径待 G3 打通"},
    {"capability": "Segment(切分)", "group": "Segment",
     "code_refs": ["src/treecut/services/segment_cognition.py", "scripts/b007_v07_pipeline.py"],
     "tests": ["tests/test_p2_scene_asr_ocr.py", "tests/test_mmvv_a1.py"],
     "real_data_evidence": "segments 41834 + b007_segment_v1 609(30 note, ffmpeg-scdet-0.30)",
     "highest_level": "TESTED_REAL_DATA", "status": "PARTIAL",
     "blocker": "切点质量仅 B007 30 note 有人工可见证据"},
    {"capability": "动作识别(语义/人员)", "group": "Cognition",
     "code_refs": ["src/treecut/services/semantic_action_v2.py",
                   "src/treecut/services/temporal_action_v2.py",
                   "src/treecut/services/people_analyzer_v2.py",
                   "src/treecut/services/static_vision_v2.py"],
     "tests": ["tests/test_cognitive_regression.py", "tests/test_stage3_consolidation.py"],
     "real_data_evidence": "targeted_human_review 141 + fresh_holdout 60 + human24 语料(历史 stage3/4)；动作真值仅校准集",
     "highest_level": "HUMAN_VALIDATED", "status": "PARTIAL",
     "blocker": "多动作人/手干扰仍存在(A3 负例观察)；生产未启用(需后续校准)"},
    {"capability": "对象识别/ROI", "group": "Cognition",
     "code_refs": ["src/treecut/services/vision_runtime.py",
                   "src/treecut/services/visual_understanding_v2.py",
                   "src/treecut/services/static_vision_v2.py"],
     "tests": ["tests/test_mmvv_a1.py"],
     "real_data_evidence": "A1 人工 ROI 200 框(32 帧, L3)；A21 绑定；A3 blind ROI 页待人工",
     "highest_level": "HUMAN_VALIDATED", "status": "PARTIAL",
     "blocker": "自动 ROI vs 人工 ROI 差距未测(AUTO_ROI_GAP 待做, 禁碰 A3)"},
    {"capability": "Camera(运动补偿)", "group": "MMVV",
     "code_refs": ["src/treecut/services/mmv_camera_diag.py", "src/treecut/services/mmvl_master_v1.py"],
     "tests": ["tests/test_mmvv_a22.py"],
     "real_data_evidence": "A2.2 R1 相机闭合 PASS(1 唯一案例, 背景掩码=受控实验, 全帧受前景污染)",
     "highest_level": "TESTED_REAL_DATA", "status": "PARTIAL",
     "blocker": "背景掩码法需 L3 前景掩码；非 Auto-camera 解决"},
    {"capability": "方向/状态(几何)", "group": "MMVV",
     "code_refs": ["src/treecut/services/mmvl_master_v1.py"],
     "tests": ["tests/test_mmvv_a21.py", "tests/test_mmvv_a21b.py", "tests/test_mmvv_a22.py"],
     "real_data_evidence": "Core5 5/5(冻结), A2.1b PASS_FOR_CURRENT_SET；A3 未测(待人工 ROI)",
     "highest_level": "TESTED_REAL_DATA", "status": "SHADOW_ONLY",
     "blocker": "MMVV_ENFORCEMENT 硬阻断；A3 泛化待验证"},
    {"capability": "Candidate Discovery", "group": "Retrieval",
     "code_refs": ["src/treecut/services/production_source.py", "scripts/b007_g1_source_gate.py"],
     "tests": ["tests/test_g1_source_gate.py"],
     "real_data_evidence": "G1 池≈13700(mp4); 路径关键词召回 EXTEND358/DRAWER704/SOCKET485/STORAGE1597/RETRACT0/静态7749",
     "highest_level": "TESTED_REAL_DATA", "status": "PARTIAL",
     "blocker": "RETRACT 路径召回=0(无文件夹词)；路径误导风险(需语义层)"},
    {"capability": "G2(action subclip)", "group": "Retrieval",
     "code_refs": ["src/treecut/services/action_subclip.py", "scripts/hrp_g2.py", "scripts/sprintv2_g2_probe.py"],
     "tests": ["tests/test_g2_action_subclip.py"],
     "real_data_evidence": "测试 11 过(合成契约)；sprintv2 G2 历史校准脚本存在",
     "highest_level": "TESTED_SYNTHETIC", "status": "PARTIAL",
     "blocker": "真实媒体 G2 全量校准未重跑(需避 A3)"},
    {"capability": "G3(claim→visual)", "group": "Retrieval",
     "code_refs": ["src/treecut/services/claim_visual.py", "scripts/hrp_g3.py"],
     "tests": ["tests/test_g3_claim_visual.py"],
     "real_data_evidence": "测试 11 过(合成契约)；hrp_g3 脚本存在",
     "highest_level": "TESTED_SYNTHETIC", "status": "PARTIAL",
     "blocker": "真实 claim 匹配证据未系统化(校准素材 dry-run 待做)"},
    {"capability": "Story/Timeline", "group": "Assembly",
     "code_refs": ["scripts/hrp_builder.py", "scripts/b007_v07_pipeline.py", "scripts/phase251_build_manifest_v2.py"],
     "tests": ["tests/test_p6_roughcut.py", "tests/test_p7_templates_ext.py"],
     "real_data_evidence": "content_templates 4；phase251 manifest 工具；b007 v0.6/v0.7 曾产出 pilot 相关",
     "highest_level": "TESTED_SYNTHETIC", "status": "PARTIAL",
     "blocker": "模板-素材契约未在真实剪辑闭环验证"},
    {"capability": "Voice(TTS fallback)", "group": "Assembly",
     "code_refs": ["scripts/b007_v084_tts_smoke.py"],
     "tests": ["tests/test_production_narration_v01.py"],
     "real_data_evidence": "TTS smoke 历史；narration 测试过",
     "highest_level": "TESTED_SYNTHETIC", "status": "PARTIAL",
     "blocker": "VOICE_PRODUCTION_INPUT_REQUIRED(真人声未授权)"},
    {"capability": "Subtitle", "group": "Assembly",
     "code_refs": ["scripts/hrp_ff.py"],
     "tests": ["tests/test_production_path_preflight_v01.py"],
     "real_data_evidence": "ASR 文本可作字幕源；渲染管线含字幕步骤(ffmpeg)",
     "highest_level": "CODE_EXISTS", "status": "PARTIAL",
     "blocker": "字幕样式/校验端到端证据未产出"},
    {"capability": "BGM", "group": "Assembly",
     "code_refs": [],
     "tests": [],
     "real_data_evidence": "无授权 BGM 库",
     "highest_level": "NOT_FOUND", "status": "BROKEN",
     "blocker": "BGM_LIBRARY_INPUT_REQUIRED(禁止未知版权音乐)"},
    {"capability": "Render(ffmpeg)", "group": "Assembly",
     "code_refs": ["scripts/hrp_ff.py", "scripts/b007_v061_pilot.py"],
     "tests": ["tests/test_p6_roughcut.py"],
     "real_data_evidence": "诊断/历史 pilot 渲染存在；ffmpeg 8.1.1 就绪",
     "highest_level": "TESTED_REAL_DATA", "status": "PARTIAL",
     "blocker": "非 NOT_FOR_PUBLISH 之外未经内容 QA"},
    {"capability": "Production QA(技术/内容分离)", "group": "QA",
     "code_refs": ["src/treecut/services/production_qa.py", "src/treecut/services/evidence_strength_v2.py"],
     "tests": ["tests/test_g5_dedup_qa.py", "tests/test_review_productization.py"],
     "real_data_evidence": "QA 模块存在；技术 QA 可跑(时长/分辨率/音画)；内容 QA 规则未全量校准",
     "highest_level": "TESTED_SYNTHETIC", "status": "PARTIAL",
     "blocker": "内容 PASS ≠ 技术 PASS 的判定链需真实成片验证"},
    {"capability": "Human Review", "group": "Review",
     "code_refs": ["src/treecut/services/review_center.py", "tools/mmv_a1_annotate/server.py",
                   "tools/production_workbench/server.py"],
     "tests": ["tests/test_review_productization.py"],
     "real_data_evidence": "b007_l3_review16_v1 16 条人工审；A1/A2/A3 人工 ROI/标签管线在线",
     "highest_level": "HUMAN_VALIDATED", "status": "PARTIAL",
     "blocker": "最终人工终审流程(v061 workbench)与 MMVV 证据未统一"},
    {"capability": "3 候选输出/Workbench", "group": "Output",
     "code_refs": ["tools/production_workbench/server.py", "scripts/b007_v07_pipeline.py"],
     "tests": [],
     "real_data_evidence": "workbench 8899 服务历史在跑；单条 pilot 类输出存在；3 条候选模式未实现",
     "highest_level": "CODE_EXISTS", "status": "PARTIAL",
     "blocker": "一次生成 3 条候选的编排未落地(未批准大 Orchestrator 开发)"},
    {"capability": "End-to-end 编排", "group": "Output",
     "code_refs": ["scripts/b007_v07_pipeline.py", "scripts/b007_v09_pilot.py"],
     "tests": [],
     "real_data_evidence": "v0.7 pipeline 脚本存在；v0.9 pilot=需批准项；本轮 dry-run 仅规划",
     "highest_level": "CODE_EXISTS", "status": "PARTIAL",
     "blocker": "端到端真实成片(脚本→3 候选)未在夜间执行(审慎+避 A3)"},
]

doc = {"experiment": "TREECUT_PRODUCTION_CONTRACT_PROBE_V1",
       "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
       "note": "只读契约盘点; 六层=CODE_EXISTS/INTEGRATED/TESTED_SYNTHETIC/TESTED_REAL_DATA/HUMAN_VALIDATED/PRODUCTION_READY; 未跑完整生产链(Pilot 禁)",
       "capabilities": []}
for c in CAPS:
    missing = [r for r in c["code_refs"] if not exists(r)]
    miss_t = [t for t in c["tests"] if not exists(t)]
    c2 = dict(c)
    c2["code_refs_exist"] = len(c["code_refs"]) - len(missing)
    c2["code_refs_missing"] = missing
    c2["tests_missing"] = miss_t
    doc["capabilities"].append(c2)
out = OUT / "TREECUT_PRODUCTION_CONTRACT_PROBE_V1.json"
out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
print("WROTE", out, "| capabilities:", len(doc["capabilities"]))
for c in doc["capabilities"]:
    print(f"  [{c['highest_level']:>16}] {c['capability']}  missing_refs={c['code_refs_missing']}")
