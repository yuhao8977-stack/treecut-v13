#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Overnight P4/P5 — production dry-run plan + code-quality inventory（只读）。

P4: 对非 A3 校准 beat 做分阶段契约 dry-run 计划（不渲染；空槽保留；不产出 rough cut 并给出正当理由）。
P5: legacy/重复实现只读盘点。
"""
import json
import re
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
SCRIPTS = REPO / "scripts"
SRC = REPO / "src" / "treecut" / "services"
OUT = REPO / "reports" / "storage"
sys.stdout.reconfigure(encoding="utf-8")

DRYRUN = {
    "experiment": "TREECUT_OVERNIGHT_PRODUCTION_DRYRUN_V1",
    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "mode": "PLAN_ONLY_DRY_RUN (不渲染、不产出 rough cut)",
    "calibration_beat": {
        "claim": "空镜岛台伸缩餐桌一体（EXTEND）",
        "media_pool_ref": "NON_HOLDOUT_BENCHMARK_POOL EXTEND 命中样本（非 A3；A3 6 案例 SEALED）",
        "a3_usage": "未使用",
    },
    "stages": [
        {"stage": "G1 源资格", "input": "media_id", "output": "eligible+role",
         "contract": "ProductionSourceService.is_media_production_eligible",
         "status": "OK(TESTED_REAL_DATA)", "missing": [], "broken": [],
         "note": "池≈13700 已由漏斗统计"},
        {"stage": "G2 action subclip", "input": "media+window", "output": "候选 subclip",
         "contract": "action_subclip / hrp_g2",
         "status": "TESTED_SYNTHETIC", "missing": ["真实媒体校准重跑(避 A3)"], "broken": [],
         "note": ""},
        {"stage": "G3 claim→visual", "input": "claim+候选", "output": "匹配片段",
         "contract": "claim_visual / hrp_g3", "status": "TESTED_SYNTHETIC",
         "missing": ["真实 claim 匹配证据"], "broken": [], "note": ""},
        {"stage": "MMVV SHADOW evidence", "input": "帧+人工 ROI", "output": "几何/时序证据",
         "contract": "mmvl_master_v1 (frozen ca34678)",
         "status": "SHADOW_ONLY", "missing": ["人工 ROI", "blind 预测授权"],
         "broken": ["MMVV_ENFORCEMENT 硬阻断"], "note": "A3 外媒体同样缺 ROI → 本 beat 无法产出 MMVV 证据"},
        {"stage": "Dedup", "input": "候选集", "output": "去重后镜头",
         "contract": "production_dedup / g5",
         "status": "OK(TESTED_SYNTHETIC)", "missing": ["shot_usage 为空(生产未消费)"], "broken": [], "note": ""},
        {"stage": "Timeline schema", "input": "镜头序列", "output": "timeline",
         "contract": "content_templates(4) / phase251 manifest",
         "status": "CODE_EXISTS", "missing": ["模板-素材契约未在真实剪辑验证"], "broken": [], "note": ""},
        {"stage": "Narration availability", "input": "timeline", "output": "旁白稿",
         "contract": "narration (test 8 pass)",
         "status": "TESTED_SYNTHETIC", "missing": ["VOICE_PRODUCTION_INPUT_REQUIRED"], "broken": [], "note": "仅 fallback TTS 诊断"},
        {"stage": "Subtitle plan", "input": "ASR 文本", "output": "字幕轨道",
         "contract": "transcripts/fts + hrp_ff",
         "status": "CODE_EXISTS", "missing": ["字幕样式端到端证据"], "broken": [], "note": ""},
        {"stage": "Render preflight", "input": "timeline+媒体", "output": "技术预检",
         "contract": "test_production_path_preflight_v01 (8 pass)",
         "status": "OK(TESTED_SYNTHETIC)", "missing": [], "broken": [], "note": ""},
        {"stage": "G5 QA", "input": "成片", "output": "技术/内容 QA",
         "contract": "production_qa + g5 test (10 pass)",
         "status": "TESTED_SYNTHETIC", "missing": ["内容 QA 真实成片校准"], "broken": [], "note": ""},
    ],
    "empty_slots_rule": "若某 beat 无有效镜头 → 保留空槽，不用错误镜头填满",
    "diagnostic_roughcut_decision": {
        "allowed": False,
        "reason": "链未全通：MMVV SHADOW_ONLY(无 ROI→无证据)、shot_usage=0、Voice/BGM 无生产输入。"
                  "按 §28 条件(所有 source contracts+技术路径完整)不满足 → 不生成诊断成片（避免“为工作量而开发”）。",
        "blocked_by": ["MMVV 人工 ROI", "VOICE_PRODUCTION_INPUT_REQUIRED", "BGM_LIBRARY_INPUT_REQUIRED"],
    },
}

QUALITY = {
    "experiment": "TREECUT_OVERNIGHT_CODE_QUALITY_INVENTORY_V1",
    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "scripts_total": len(list(SCRIPTS.glob("*.py"))),
    "scripts_by_prefix": {},
    "duplicate_family_services": [
        {"family": "conflict_resolver", "files": ["conflict_resolver.py", "conflict_resolver_v2.py"]},
        {"family": "business_cognition", "files": ["business_cognition_service.py", "business_cognition_v2.py", "business_cognition_v2_1.py"]},
        {"family": "semantic_action", "files": ["semantic_action_v1.py", "semantic_action_v2.py"]},
        {"family": "stage2/3/4 历史脚本", "note": "大量 stage*_*.py 为旧校准/审计脚本(只读盘点, 未删)"},
    ],
    "note": "只读盘点；不删不改；重复实现统一属后续 canonical 小步整合(§32 允许范围外需审批)",
}

OUT1 = OUT / "TREECUT_OVERNIGHT_PRODUCTION_DRYRUN_V1.json"
OUT2 = OUT / "TREECUT_OVERNIGHT_CODE_QUALITY_INVENTORY_V1.json"
prefix = {}
for p in SCRIPTS.glob("*.py"):
    m = re.match(r"^([a-z0-9_]+)", p.name)
    key = (m.group(1) if m else "other")
    prefix[key] = prefix.get(key, 0) + 1
QUALITY["scripts_by_prefix"] = dict(sorted(prefix.items(), key=lambda x: -x[1])[:40])
OUT1.write_text(json.dumps(DRYRUN, ensure_ascii=False, indent=1), encoding="utf-8")
OUT2.write_text(json.dumps(QUALITY, ensure_ascii=False, indent=1), encoding="utf-8")
print("WROTE dryrun plan + code quality inventory")
print("scripts total:", QUALITY["scripts_total"])
print("top prefixes:", list(QUALITY["scripts_by_prefix"].items())[:10])
