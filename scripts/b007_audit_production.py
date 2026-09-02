# -*- coding: utf-8 -*-
"""Corrective Audit B: production inventory / rendered product / chain / ETA / L3-16 plan + report. 只读。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
REC = json.loads((OUT / "B007_SAMPLE20_RECENCY_AUDIT_V1.json").read_text(encoding="utf-8"))
CAL = json.loads((OUT / "B007_V081_CALIBRATION40_V1.json").read_text(encoding="utf-8"))
QW = json.loads((OUT / "B007_V081_QWENVL_VISUAL_CANDIDATES_V1.json").read_text(encoding="utf-8"))

# ---------- 7. production module inventory ----------
inventory = [
    # (module, status, evidence)
    ("script parser (选题/脚本)", "PARTIAL", "treecut.workflow.planning? 未见独立 parser；brain/planning 有 plan 结构"),
    ("script beats (脚本节拍)", "EXISTS_NEEDS_INTEGRATION", "cognitive/production.py, application/production.py 引用 script_beats 概念"),
    ("semantic requirement builder", "PARTIAL", "workflow/planning.py build_edit_plan + narration_hint 槽位"),
    ("segment retrieval", "LEGACY_REUSABLE", "workflow/matching.py MatchResult; search/hybrid.py"),
    ("vector retrieval", "PARTIAL", "search/hybrid.py + embedding_worker; 旧 B003 索引可用性未实测"),
    ("shot candidate ranking", "PARTIAL", "roughcut/engine.py + roughcut/sort_advisor.py（旧链路）"),
    ("shot usage / cooldown", "EXISTS_NEEDS_INTEGRATION", "services/shot_usage.py; shot_usage 表 0 行（新链未用）"),
    ("duplicate control", "PARTIAL", "stage3_near_dup / library/hash_utils（旧验证过）; 新链未接"),
    ("continuity", "UNKNOWN", "未见专门模块"),
    ("template registry", "LEGACY_REUSABLE", "templates/engine.py + content_templates T001-T004（HAND_AUTHORED）"),
    ("edit plan", "LEGACY_REUSABLE", "workflow/planning.py build_edit_plan"),
    ("production plan", "LEGACY_REUSABLE", "production_plans 表 2 行; cognitive/production.py"),
    ("copywriter (文案)", "LEGACY_REUSABLE", "copywriter.py build_narration; narration_script.txt 289B 已生成"),
    ("TTS", "PARTIAL", "models/tts_local.py; narration.wav 仅 176KB(~2-3s) 疑似失败/片段"),
    ("subtitle", "PARTIAL", "output/narration.py build_srt; 实例 narration.srt=0 字节 → 未成"),
    ("BGM", "EXISTS_NEEDS_INTEGRATION", "实例 bgm.mp3 已生成；未验证混流"),
    ("transition / effects", "UNKNOWN", "jianying draft 槽位内；未验证"),
    ("jianying.py (剪映草稿)", "LEGACY_REUSABLE", "output/jianying.py; 实例 jianying_draft/ 存在但未在剪映验证"),
    ("pyJianYingDraft", "LEGACY_REUSABLE", "jianying.py 引用; 需确认 pip 包可用性（未在本次验证）"),
    ("VideoEditorBridge", "PARTIAL", "application/production.py 引用; 未在本次验证"),
    ("direct renderer (MP4)", "PARTIAL", "output/mp4.py; preview.mp4 540x960 32.4s 已生成（旧链）"),
    ("production QA", "PARTIAL", "quality/inspection.py + quality_validation/store.py（旧链）; 本次无 QA 记录"),
    ("preview UI", "LEGACY_REUSABLE", "ui/player.py, timeline_dialog.py 等（桌面 UI）"),
    ("feedback learning", "PARTIAL", "feedback_learning/ + learning/feedback.py; 无新链应用记录"),
]
inv = {"phase": "CORRECTIVE_STATUS_AUDIT", "module_inventory": [
    {"module": m, "status": s, "evidence": e} for m, s, e in inventory]}
(OUT / "TREECUT_PRODUCTION_MODULE_INVENTORY_V1.json").write_text(
    json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- 9. rendered product audit ----------
render = {
    "project": "产品介绍001", "template": "T003", "status_in_db": "rendered",
    "output_dir": r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\output\brain_production\产品介绍001",
    "files": {
        "preview.mp4": {"exists": True, "codec": "h264", "resolution": "540x960", "duration_s": 32.43,
                        "voice": "UNKNOWN(未探测音轨)", "subtitle_burned": "UNKNOWN"},
        "narration_script.txt": {"exists": True, "bytes": 289},
        "narration.wav": {"exists": True, "bytes": 176478, "note": "约2-3s，与32.4s成片不匹配 → TTS 疑似失败/仅片段"},
        "narration.srt": {"exists": True, "bytes": 0, "note": "空字幕 → 字幕未生成"},
        "bgm.mp3": {"exists": True},
        "jianying_draft": {"exists": True, "note": "剪映草稿目录存在，未在剪映验证"},
        "production_plan.json": {"exists": True},
    },
    "qa": "NO_EVIDENCE (本次审计未见该产物的 QA 记录)",
    "conclusion": "存在真实 preview.mp4（540x960/32.4s），但配音/字幕环节破损(srt=0, wav≈2s)；属旧链半成品，非可发布成片",
}
(OUT / "TREECUT_RENDERED_PRODUCT_AUDIT_V1.json").write_text(
    json.dumps(render, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- 11. end-to-end chain ----------
chain = {
    "TOPIC/SCRIPT": "PARTIAL (copywriter.py + brain; 无独立 parser)",
    "SCRIPT_BEATS": "EXISTS_NEEDS_INTEGRATION (cognitive/production.py)",
    "SEMANTIC_REQUIREMENTS": "PARTIAL (planning.py slots+narration_hint)",
    "SEGMENT_RETRIEVAL": "LEGACY_REUSABLE (matching.py; B003 资产可用, B007 未接)",
    "SHOT_RANKING": "PARTIAL (roughcut; 新链未验)",
    "TIMELINE": "LEGACY_REUSABLE (planning.py edit plan; 实例 plan_json 存在)",
    "SUBTITLE/TTS/BGM": "PARTIAL (实例: srt=0, wav≈2s, bgm 生成) → 破损环节",
    "JIANYING_DRAFT/RENDER": "PARTIAL (jianying.py+mp4.py; preview.mp4 已出但为旧链)",
    "FINISHED_VIDEO": "NOT_YET (存在旧链 demo MP4, 非新 Truth 链产物)",
    "runs_end_to_end_today": False,
}
(OUT / "TREECUT_END_TO_END_CHAIN_V1.json").write_text(
    json.dumps(chain, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- 12/13. ETA revised ----------
eta = {
    "basis": {"git_commits_last_14d": 206, "git_commits_per_day": 14.7,
              "v07_v08_actual": "2.5h (20 media pipeline)", "media_worker": "proven (20/20 exact)",
              "production_modules": "24 modules scanned; ~11 legacy-reusable, ~7 partial",
              "tests": "299 passed, 2 skipped"},
    "first_end_to_end_finished_video": {
        "optimistic": "1 effective dev day", "realistic": "2-3 effective dev days",
        "blocker": ["修复 TTS/字幕环节 (srt=0, wav 破损)", "把 B007 segment/ASR/OCR 接到 planning/matching/roughcut",
                    "新链渲染 QA 至少 1 条"]},
    "pilot_5": {"optimistic": "3 days", "realistic": "3-7 days",
                "blocker": ["first video 验收", "人工打分标准落地", "5 类内容各 1 条"]},
    "stable_daily_production": {"optimistic": "1 week", "realistic": "1-2 weeks",
                                "blocker": ["规则稳定", "QA 闸自动化", "素材去重/cooldown 生效"]},
    "mature_v1": {"optimistic": "3 weeks", "realistic": "3-6 weeks",
                  "blocker": ["认知校准(L3)", "Recent 样本补链", "反馈闭环"]},
    "note": "FIRST VIDEO 与 MATURE V1 分开：第一条重在打通链（含修复 TTS/字幕），成熟版才谈稳定性",
}
(OUT / "TREECUT_ETA_REVISED_V1.json").write_text(json.dumps(eta, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- 14. L3 review16 plan ----------
qw_by_seg = {s["segment_id"]: s for s in QW.get("segments", [])}
def seg_interest(sid):
    q = qw_by_seg.get(sid, {})
    f = q.get("fields", {})
    v = {k: (x.get("value") if isinstance(x, dict) else "UNKNOWN") for k, x in f.items()}
    score = 0
    for k in ("storage_evidence", "flexible_capacity_evidence", "dining_context_evidence",
              "detail_shot", "power_evidence"):
        if v.get(k) == "yes":
            score += 2
    if v.get("human_presence") == "yes":
        score += 1
    if v.get("product_visibility") == "yes":
        score += 1
    # conflict: qwen value vs CLIP
    return score

opening_segs = [s for s in CAL["segments"] if s["selection_role"] == "OPENING_SEGMENT"]
high_segs = [s for s in CAL["segments"] if s["selection_role"] == "HIGH_INFORMATION_SEGMENT"]
opening16 = sorted(opening_segs, key=lambda s: seg_interest(s["segment_id"]), reverse=True)[:8]
high16 = sorted(high_segs, key=lambda s: seg_interest(s["segment_id"]), reverse=True)[:8]
l3plan = {
    "goal": "先用16段判定 L3 校准收益；收益不足则不再审剩余24段",
    "selection_rule": "8 OPENING + 8 HIGH_INFORMATION，按 storage/flexible/dining/detail/power/human/product 证据分排序",
    "opening": [{"segment_id": s["segment_id"], "sample_id": s["sample_id"], "stratum": s["stratum"]} for s in opening16],
    "high_info": [{"segment_id": s["segment_id"], "sample_id": s["sample_id"], "stratum": s["stratum"]} for s in high16],
    "estimated_user_time_min": 30,
    "stop_rule": "若16段 L3 校准对认知准确率提升不明显 → 不继续剩余24段，先修 schema/模型",
}
(OUT / "TREECUT_L3_REVIEW16_PLAN_V1.json").write_text(json.dumps(l3plan, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- 4. recency conclusion + first page ----------
yd = REC["sample20_year_distribution"]
rb = REC["sample20_recency_buckets"]
n180 = REC["sample20_within_180d_count"]
recency_risk = {
    "HISTORICAL_STRUCTURE_VALUE": "HIGH (19条老样本仍可用于训练场景/功能/材质识别)",
    "CURRENT_EDITING_STYLE_RELEVANCE": "LOW (19/20 >180d；近180天仅1条)",
    "CURRENT_PLATFORM_RELEVANCE": "LOW-MEDIUM (2023-2024 为主，平台环境已变)",
    "CURRENT_PAID_RELEVANCE": "MEDIUM (付费结构与现状可比，但窗口 UNALIGNED)",
    "SAMPLE20_RECENCY_RISK": "HIGH (用于当前剪辑风格模板的证据不足；需 Recent12 补充)",
}
first_page = {
    "sample20_2026_count": REC["sample20_2026_count"],
    "sample20_within_180d_count": n180,
    "sample20_year_distribution": yd,
    "sample20_recency_buckets": rb,
    "recency_risk": recency_risk,
    "recommend_recent12": True,
    "existing_real_mp4": "存在旧链 demo preview.mp4 (540x960/32.4s)，配音字幕破损，非新链可发布成片",
    "first_video_eta": eta["first_end_to_end_finished_video"]["realistic"],
    "pilot5_eta": eta["pilot_5"]["realistic"],
    "stable_production_eta": eta["stable_daily_production"]["realistic"],
    "top5_gaps": ["1) TTS/字幕环节破损 (srt=0, wav≈2s)", "2) B007 新 Truth 链未接入 planning/matching/roughcut",
                  "3) 无新链 QA 记录/自动质量闸", "4) 时效性：Sample20 19/20>180d，缺 Recent12",
                  "5) 认知已知率低 (视觉 18.2% / claims 99.7% UNKNOWN) → 依赖 L3 校准"],
}
report = {**first_page, "module_inventory": inv, "rendered_product": render,
          "chain": chain, "eta": eta, "l3_review16": l3plan,
          "recent_universe": REC["recent_universe"], "recent12_feasibility": REC["recent12_feasibility"],
          "templates": REC["templates"], "production_plans": REC["production_plans"]}
md = ["# TreeCut Corrective Status Report — Recency + Production Readiness", "",
      f"Generated: 2026-09-02 | Mode: READ-ONLY", "",
      "## First Page", "", "```json", json.dumps(first_page, ensure_ascii=False, indent=2), "```",
      "", "## Sample20 exact recency", ""]
for r in REC["sample20_exact_recency"]:
    md.append(f"- {r['sample_id']} | {r['note_id']} | {r['publish_time']} | {r['year_month']} | {r['stratum']} | {r['age_days']}d | {r['title'][:30]}")
md += ["", "## Recent universe", "",
       "- 2026-03~08: " + json.dumps(REC["recent_universe"]["2026_03_08"], ensure_ascii=False),
       "- 2026-07~08: " + json.dumps(REC["recent_universe"]["2026_07_08"], ensure_ascii=False),
       "", "## Recent12 feasibility", "",
       json.dumps(REC["recent12_feasibility"], ensure_ascii=False, indent=2),
       "", "## Production module inventory", ""]
for m in inv["module_inventory"]:
    md.append(f"- **{m['module']}**: {m['status']} — {m['evidence']}")
md += ["", "## Rendered product audit", "", json.dumps(render, ensure_ascii=False, indent=2),
       "", "## End-to-end chain", ""]
for k, v in chain.items():
    md.append(f"- {k}: {v}")
md += ["", "## ETA (revised)", "", json.dumps(eta, ensure_ascii=False, indent=2),
       "", "## L3 review16 plan", "", json.dumps(l3plan, ensure_ascii=False, indent=2),
       "", "## STOP — audit complete; no selection/media recovery/L3/V0.9 performed", ""]
(DOCS / "TREECUT_CORRECTIVE_STATUS_REPORT_V1.md").write_text("\n".join(md), encoding="utf-8")
(OUT / "TREECUT_CORRECTIVE_STATUS_REPORT_V1.md").write_text("\n".join(md), encoding="utf-8")
print(json.dumps(first_page, ensure_ascii=False, indent=2))
sys.exit(0)
