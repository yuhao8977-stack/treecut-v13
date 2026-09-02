# -*- coding: utf-8 -*-
"""G4/G5/G7 静态产物: config/QA schema/QA rules/Dedup policy 写入。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.config.production import DEFAULTS

(OUT / "TREECUT_PRODUCTION_CONFIG_V1.json").write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2), encoding="utf-8")

qa_schema = {"version": "V2", "layers": ["TECHNICAL_QA", "SOURCE_QA", "SEMANTIC_QA", "PRODUCTION_QA", "HUMAN_QA"],
             "gates": ["SOURCE_PRODUCTION_ELIGIBLE", "NO_OLD_SUBTITLE", "NO_PLATFORM_WATERMARK",
                       "CLAIM_SUPPORTED", "ACTION_DEMONSTRATED", "BEAT_VISUAL_ALIGNMENT",
                       "STORY_ENTITY_CONSISTENT", "NEAR_DUPLICATE_FREE", "SHOT_ROLE_DIVERSITY",
                       "CAPTION_RENDERED", "CAPTION_READABLE", "VOICE_PROVIDER_VALID",
                       "BGM_PRESENT_IF_REQUIRED", "AV_SYNC", "VIDEO_TAIL_VALID",
                       "AUDIO_LOUDNESS_VALID", "VIDEO_DECODABLE"],
             "p0": ["DIRTY_SOURCE", "UNSUPPORTED_CORE_CLAIM", "WRONG_ACTION", "WRONG_FUNCTION_VISUAL",
                    "AV_DURATION_MISMATCH", "VIDEO_END_BEFORE_AUDIO", "NEW_CAPTION_MISSING", "MAJOR_DUPLICATE"],
             "p0_map": {"AV_SYNC": "AV_DURATION_MISMATCH", "VIDEO_TAIL_VALID": "VIDEO_END_BEFORE_AUDIO",
                        "CAPTION_RENDERED": "NEW_CAPTION_MISSING", "CLAIM_SUPPORTED": "UNSUPPORTED_CORE_CLAIM",
                        "ACTION_DEMONSTRATED": "WRONG_ACTION", "BEAT_VISUAL_ALIGNMENT": "WRONG_FUNCTION_VISUAL",
                        "NEAR_DUPLICATE_FREE": "MAJOR_DUPLICATE", "SOURCE_PRODUCTION_ELIGIBLE": "DIRTY_SOURCE",
                        "NO_OLD_SUBTITLE": "DIRTY_SOURCE", "NO_PLATFORM_WATERMARK": "DIRTY_SOURCE"},
             "human_override": "automated_result 与 human_result 分开持久化, human append-only 不覆盖历史机器结果"}
(OUT / "TREECUT_PRODUCTION_QA_SCHEMA_V2.json").write_text(json.dumps(qa_schema, ensure_ascii=False, indent=2), encoding="utf-8")

qa_rules = {"version": "V2", "checks": [
    {"gate": "TECHNICAL", "key": "AV_SYNC", "rule": "|video-audio| <= 0.10s(stream级, 非container)", "severity": "P0"},
    {"gate": "TECHNICAL", "key": "VIDEO_TAIL_VALID", "rule": "video >= audio - 0.05s", "severity": "P0"},
    {"gate": "TECHNICAL", "key": "CAPTION_RENDERED", "rule": "新字幕硬烧进final(证据: 帧OCR/像素或视觉)", "severity": "P0"},
    {"gate": "TECHNICAL", "key": "CAPTION_READABLE", "rule": "FontSize 62-68, outline4-6, <=2行; <62 记V2债务", "severity": "WARNING"},
    {"gate": "TECHNICAL", "key": "VOICE_PROVIDER_VALID", "rule": "SAPI=FALLBACK; 克隆需 consent", "severity": "WARNING"},
    {"gate": "TECHNICAL", "key": "AUDIO_LOUDNESS_VALID", "rule": "-14~-16LUFS, TP<=-1dBTP", "severity": "WARNING"},
    {"gate": "SOURCE", "key": "SOURCE_PRODUCTION_ELIGIBLE", "rule": "role∈CLEAN* & 污染非PRESENT & 非REJECTED(L3 APPROVED 覆盖具体对象)", "severity": "P0"},
    {"gate": "SOURCE", "key": "NO_OLD_SUBTITLE", "rule": "burned_subtitle_present != PRESENT", "severity": "P0"},
    {"gate": "SOURCE", "key": "NO_PLATFORM_WATERMARK", "rule": "platform_watermark_present != PRESENT", "severity": "P0"},
    {"gate": "SEMANTIC", "key": "CLAIM_SUPPORTED", "rule": "每 core claim 有证据; 无支撑→删除/降级", "severity": "P0"},
    {"gate": "SEMANTIC", "key": "ACTION_DEMONSTRATED", "rule": "动作口播需时序动作证据(≠静态/标签)", "severity": "P0"},
    {"gate": "SEMANTIC", "key": "BEAT_VISUAL_ALIGNMENT", "rule": "画面与当前口播语义一致(伸缩→插座=FAIL)", "severity": "P0"},
    {"gate": "SEMANTIC", "key": "STORY_ENTITY_CONSISTENT", "rule": "SINGLE_CASE≥70%同案 / MONTAGE 通用语言", "severity": "WARNING"},
    {"gate": "PRODUCTION", "key": "NEAR_DUPLICATE_FREE", "rule": "HIGH强度重复 → P0 MAJOR_DUPLICATE; WARNING 级记录", "severity": "P0"},
    {"gate": "PRODUCTION", "key": "SHOT_ROLE_DIVERSITY", "rule": "20-30s 内 7-12 镜; 避免整段5-6s低信息", "severity": "WARNING"},
    {"gate": "HUMAN", "key": "HUMAN_QA", "rule": "人工最终裁决; machine/human 分存", "severity": "GATE"}],
    "negative_regressions": ["V1: 旧字幕/水印/视频短于配音/缺新字幕/语义错配/缺BGM", "V2: 字幕小55/无BGM/SAPI机械/伸缩口播配插座/重复结尾/动作未演示"]}
(OUT / "TREECUT_PRODUCTION_QA_RULES_V2.json").write_text(json.dumps(qa_rules, ensure_ascii=False, indent=2), encoding="utf-8")

dedup_policy = {"version": "V1", "levels": ["EXACT_SEGMENT_DUPLICATE", "SOURCE_TIME_OVERLAP",
    "SAME_ASSET_NEAR_DUPLICATE", "VISUAL_NEAR_DUPLICATE", "NARRATIVE_NEAR_DUPLICATE"],
    "visual": {"method": "DCT-pHash", "strong_<=6": "HIGH 候选", "7-12": "复核"},
    "narrative_factors": ["同演示者", "同案例提示", "同功能文件夹", "同shot_role"],
    "timeline_usage": "production 项目追踪 segment_id/subclip/asset_id/visual_cluster/shot_role 已用",
    "note": "阈值记录校准, 不全局拍脑袋; V2 重复结尾须拦截(至少WARNING, 强重复HIGH=P0)"}
(OUT / "TREECUT_PRODUCTION_DEDUP_POLICY_V1.json").write_text(json.dumps(dedup_policy, ensure_ascii=False, indent=2), encoding="utf-8")
print("static artifacts written")
