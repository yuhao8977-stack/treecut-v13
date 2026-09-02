# TreeCut Corrective Status Report — Recency + Production Readiness

Generated: 2026-09-02 | Mode: READ-ONLY

## First Page

```json
{
  "sample20_2026_count": 1,
  "sample20_within_180d_count": 1,
  "sample20_year_distribution": {
    "2023": 9,
    "2024": 7,
    "2025": 2,
    "2026": 1,
    "2022": 1
  },
  "sample20_recency_buckets": {
    "30d": 0,
    "60d": 0,
    "90d": 0,
    "180d": 1,
    "gt180d": 19
  },
  "recency_risk": {
    "HISTORICAL_STRUCTURE_VALUE": "HIGH (19条老样本仍可用于训练场景/功能/材质识别)",
    "CURRENT_EDITING_STYLE_RELEVANCE": "LOW (19/20 >180d；近180天仅1条)",
    "CURRENT_PLATFORM_RELEVANCE": "LOW-MEDIUM (2023-2024 为主，平台环境已变)",
    "CURRENT_PAID_RELEVANCE": "MEDIUM (付费结构与现状可比，但窗口 UNALIGNED)",
    "SAMPLE20_RECENCY_RISK": "HIGH (用于当前剪辑风格模板的证据不足；需 Recent12 补充)"
  },
  "recommend_recent12": true,
  "existing_real_mp4": "存在旧链 demo preview.mp4 (540x960/32.4s)，配音字幕破损，非新链可发布成片",
  "first_video_eta": "2-3 effective dev days",
  "pilot5_eta": "3-7 days",
  "stable_production_eta": "1-2 weeks",
  "top5_gaps": [
    "1) TTS/字幕环节破损 (srt=0, wav≈2s)",
    "2) B007 新 Truth 链未接入 planning/matching/roughcut",
    "3) 无新链 QA 记录/自动质量闸",
    "4) 时效性：Sample20 19/20>180d，缺 Recent12",
    "5) 认知已知率低 (视觉 18.2% / claims 99.7% UNKNOWN) → 依赖 L3 校准"
  ]
}
```

## Sample20 exact recency

- SA-6544d761 | 6544d761000000001f038f12 | 2023-11-03 20:19 | 2023-11 | A_CREATOR_HIGH_NO_PAID_ASSOC_OBSERVED | 1033d | 请大数据把我推给🔥小户型进门就是厨房
- SA-64f158f4 | 64f158f4000000001d014203 | 2023-09-01 17:00 | 2023-09 | A_CREATOR_HIGH_NO_PAID_ASSOC_OBSERVED | 1096d | 小户型进门就是厨房❗岛台这样做好看又好用
- SA-64e42823 | 64e42823000000000800c82d | 2023-08-22 11:14 | 2023-08 | A_CREATOR_HIGH_NO_PAID_ASSOC_OBSERVED | 1106d | 我发现🆘2023年岛台灯光万能🔥6个逻辑
- SA-66f672d6 | 66f672d6000000001902efbb | 2024-09-29 21:00 | 2024-09 | A_CREATOR_HIGH_NO_PAID_ASSOC_OBSERVED | 702d | 造孽啊🤯岛台内嵌烤箱翻倒到地上!?️
- SB-63c5675a | 63c5675a000000001c034435 | 2023-01-16 23:03 | 2023-01 | B_CREATOR_MID_LOW_NO_PAID_ASSOC_OBSERVED | 1324d | 餐厅布局案例:错位岛台让餐厅提高档次❗
- SB-682edce4 | 682edce4000000001101e878 | 2025-06-01 17:00 | 2025-06 | B_CREATOR_MID_LOW_NO_PAID_ASSOC_OBSERVED | 457d | 岛台水电如何预留布局?才合理不翻车?
- SB-66d7c509 | 66d7c509000000000c018964 | 2024-09-05 17:00 | 2024-09 | B_CREATOR_MID_LOW_NO_PAID_ASSOC_OBSERVED | 726d | 岛台水电布局不想返工❌一定要看👀
- SC-64fbe901 | 64fbe901000000001d01424c | 2023-09-09 11:39 | 2023-09 | C_PAID_HIGH_EFFICIENCY_CANDIDATE | 1088d | 8m2小厨房✅,被问爆的岛台安装&设计来啦!
- SC-65bc60fe | 65bc60fe0000000008022950 | 2024-02-14 17:00 | 2024-02 | C_PAID_HIGH_EFFICIENCY_CANDIDATE | 930d | 奶呼呼的岛台太哇塞了🔥颜值扛把子!!
- SC-69f9a0ac | 69f9a0ac000000003701d937 | 2026-05-06 12:01 | 2026-05 | C_PAID_HIGH_EFFICIENCY_CANDIDATE | 118d | 通透又显大的开放式厨房标配岛台🤔
- SC-63c8d157 | 63c8d157000000001f02357d | 2023-01-19 13:12 | 2023-01 | C_PAID_HIGH_EFFICIENCY_CANDIDATE | 1321d | 岛台不做收纳储物真的很可惜❗再配个水槽
- SD-66de90b3 | 66de90b3000000000c01a935 | 2024-09-09 19:01 | 2024-09 | D_PAID_HIGH_INPUT_WEAK_OUTCOME | 722d | 岛台餐椅咋配😭
- SD-670630e9 | 670630e9000000001a023e3f | 2024-10-11 17:00 | 2024-10 | D_PAID_HIGH_INPUT_WEAK_OUTCOME | 690d | 有了这款餐椅🪑终于实现梦想的岛台氛围
- SD-69367987 | 69367987000000001b027d8f | 2025-12-09 18:01 | 2025-12 | D_PAID_HIGH_INPUT_WEAK_OUTCOME | 266d | 还愁电器没地方放?这款岛台真的很实用
- SD-64db4e87 | 64db4e87000000001701a578 | 2023-08-15 18:08 | 2023-08 | D_PAID_HIGH_INPUT_WEAK_OUTCOME | 1113d | 救命🆘岛台工厂大牌平替被我找到了❗💡
- SE-64336391 | 643363910000000013036c3a | 2023-04-10 10:58 | 2023-04 | E_CROSS_SOURCE_CONTRAST | 1240d | 高能预警🔥智能未来3.0降临餐桌岛台
- SE-66ebc041 | 66ebc041000000000c01b331 | 2024-09-20 21:00 | 2024-09 | E_CROSS_SOURCE_CONTRAST | 711d | 对天发誓 这个沙发后岛台真的....
- SE-6718abc7 | 6718abc70000000021009845 | 2024-10-24 19:01 | 2024-10 | E_CROSS_SOURCE_CONTRAST | 677d | 我怎么没早点看到岛台收纳🔥
- SF-63a6a53f | 63a6a53f000000001f00d5e2 | 2022-12-24 15:07 | 2022-12 | F_PAID_ASSOCIATED_NO_NOTE_METRIC | 1347d | 传统餐桌换成岛台🎃简直不要太美!
- SF-640dc105 | 640dc1050000000014025280 | 2023-03-12 20:09 | 2023-03 | F_PAID_ASSOCIATED_NO_NOTE_METRIC | 1269d | 不做岛台不知道的“坑”,太真实啦❗

## Recent universe

- 2026-03~08: {"total": 341, "video": 340, "by_paid_status": {"NOTE_PAID_METRIC_PRESENT": 251, "NO_PAID_ASSOCIATION_OBSERVED": 36, "PAID_ASSOCIATED_NO_METRIC_RECORD": 53}, "creator_high": 8, "recent_nopaid_control": 28, "paid_efficient": 251, "paid_high_input_weak": 25, "cross_source": 53, "p75_creator_view": 139.0}
- 2026-07~08: {"total": 116, "video": 116, "by_paid_status": {"NOTE_PAID_METRIC_PRESENT": 62, "NO_PAID_ASSOCIATION_OBSERVED": 20, "PAID_ASSOCIATED_NO_METRIC_RECORD": 34}, "creator_high": 4, "recent_nopaid_control": 16, "paid_efficient": 62, "paid_high_input_weak": 0, "cross_source": 34, "p75_creator_view": 158.0}

## Recent12 feasibility

{
  "proposal": "6x 2026-07~08 + 6x 2026-03~06",
  "eligible_2026_07_08_total_video": 116,
  "eligible_2026_03_06_total_video": 224,
  "by_category_07_08": {
    "total": 116,
    "video": 116,
    "by_paid_status": {
      "NOTE_PAID_METRIC_PRESENT": 62,
      "NO_PAID_ASSOCIATION_OBSERVED": 20,
      "PAID_ASSOCIATED_NO_METRIC_RECORD": 34
    },
    "creator_high": 5,
    "recent_nopaid_control": 15,
    "paid_efficient": 62,
    "paid_high_input_weak": 0,
    "cross_source": 34
  },
  "by_category_03_06": {
    "total": 225,
    "video": 224,
    "by_paid_status": {
      "NOTE_PAID_METRIC_PRESENT": 189,
      "NO_PAID_ASSOCIATION_OBSERVED": 16,
      "PAID_ASSOCIATED_NO_METRIC_RECORD": 19
    },
    "creator_high": 3,
    "recent_nopaid_control": 13,
    "paid_efficient": 189,
    "paid_high_input_weak": 25,
    "cross_source": 19
  },
  "note": "eligibility counts only; no selection/media recovery performed"
}

## Production module inventory

- **script parser (选题/脚本)**: PARTIAL — treecut.workflow.planning? 未见独立 parser；brain/planning 有 plan 结构
- **script beats (脚本节拍)**: EXISTS_NEEDS_INTEGRATION — cognitive/production.py, application/production.py 引用 script_beats 概念
- **semantic requirement builder**: PARTIAL — workflow/planning.py build_edit_plan + narration_hint 槽位
- **segment retrieval**: LEGACY_REUSABLE — workflow/matching.py MatchResult; search/hybrid.py
- **vector retrieval**: PARTIAL — search/hybrid.py + embedding_worker; 旧 B003 索引可用性未实测
- **shot candidate ranking**: PARTIAL — roughcut/engine.py + roughcut/sort_advisor.py（旧链路）
- **shot usage / cooldown**: EXISTS_NEEDS_INTEGRATION — services/shot_usage.py; shot_usage 表 0 行（新链未用）
- **duplicate control**: PARTIAL — stage3_near_dup / library/hash_utils（旧验证过）; 新链未接
- **continuity**: UNKNOWN — 未见专门模块
- **template registry**: LEGACY_REUSABLE — templates/engine.py + content_templates T001-T004（HAND_AUTHORED）
- **edit plan**: LEGACY_REUSABLE — workflow/planning.py build_edit_plan
- **production plan**: LEGACY_REUSABLE — production_plans 表 2 行; cognitive/production.py
- **copywriter (文案)**: LEGACY_REUSABLE — copywriter.py build_narration; narration_script.txt 289B 已生成
- **TTS**: PARTIAL — models/tts_local.py; narration.wav 仅 176KB(~2-3s) 疑似失败/片段
- **subtitle**: PARTIAL — output/narration.py build_srt; 实例 narration.srt=0 字节 → 未成
- **BGM**: EXISTS_NEEDS_INTEGRATION — 实例 bgm.mp3 已生成；未验证混流
- **transition / effects**: UNKNOWN — jianying draft 槽位内；未验证
- **jianying.py (剪映草稿)**: LEGACY_REUSABLE — output/jianying.py; 实例 jianying_draft/ 存在但未在剪映验证
- **pyJianYingDraft**: LEGACY_REUSABLE — jianying.py 引用; 需确认 pip 包可用性（未在本次验证）
- **VideoEditorBridge**: PARTIAL — application/production.py 引用; 未在本次验证
- **direct renderer (MP4)**: PARTIAL — output/mp4.py; preview.mp4 540x960 32.4s 已生成（旧链）
- **production QA**: PARTIAL — quality/inspection.py + quality_validation/store.py（旧链）; 本次无 QA 记录
- **preview UI**: LEGACY_REUSABLE — ui/player.py, timeline_dialog.py 等（桌面 UI）
- **feedback learning**: PARTIAL — feedback_learning/ + learning/feedback.py; 无新链应用记录

## Rendered product audit

{
  "project": "产品介绍001",
  "template": "T003",
  "status_in_db": "rendered",
  "output_dir": "E:\\树剪整理\\02_安装程序\\TreeCut_v13\\runtime_data\\temp\\batch1\\output\\brain_production\\产品介绍001",
  "files": {
    "preview.mp4": {
      "exists": true,
      "codec": "h264",
      "resolution": "540x960",
      "duration_s": 32.43,
      "voice": "UNKNOWN(未探测音轨)",
      "subtitle_burned": "UNKNOWN"
    },
    "narration_script.txt": {
      "exists": true,
      "bytes": 289
    },
    "narration.wav": {
      "exists": true,
      "bytes": 176478,
      "note": "约2-3s，与32.4s成片不匹配 → TTS 疑似失败/仅片段"
    },
    "narration.srt": {
      "exists": true,
      "bytes": 0,
      "note": "空字幕 → 字幕未生成"
    },
    "bgm.mp3": {
      "exists": true
    },
    "jianying_draft": {
      "exists": true,
      "note": "剪映草稿目录存在，未在剪映验证"
    },
    "production_plan.json": {
      "exists": true
    }
  },
  "qa": "NO_EVIDENCE (本次审计未见该产物的 QA 记录)",
  "conclusion": "存在真实 preview.mp4（540x960/32.4s），但配音/字幕环节破损(srt=0, wav≈2s)；属旧链半成品，非可发布成片"
}

## End-to-end chain

- TOPIC/SCRIPT: PARTIAL (copywriter.py + brain; 无独立 parser)
- SCRIPT_BEATS: EXISTS_NEEDS_INTEGRATION (cognitive/production.py)
- SEMANTIC_REQUIREMENTS: PARTIAL (planning.py slots+narration_hint)
- SEGMENT_RETRIEVAL: LEGACY_REUSABLE (matching.py; B003 资产可用, B007 未接)
- SHOT_RANKING: PARTIAL (roughcut; 新链未验)
- TIMELINE: LEGACY_REUSABLE (planning.py edit plan; 实例 plan_json 存在)
- SUBTITLE/TTS/BGM: PARTIAL (实例: srt=0, wav≈2s, bgm 生成) → 破损环节
- JIANYING_DRAFT/RENDER: PARTIAL (jianying.py+mp4.py; preview.mp4 已出但为旧链)
- FINISHED_VIDEO: NOT_YET (存在旧链 demo MP4, 非新 Truth 链产物)
- runs_end_to_end_today: False

## ETA (revised)

{
  "basis": {
    "git_commits_last_14d": 206,
    "git_commits_per_day": 14.7,
    "v07_v08_actual": "2.5h (20 media pipeline)",
    "media_worker": "proven (20/20 exact)",
    "production_modules": "24 modules scanned; ~11 legacy-reusable, ~7 partial",
    "tests": "299 passed, 2 skipped"
  },
  "first_end_to_end_finished_video": {
    "optimistic": "1 effective dev day",
    "realistic": "2-3 effective dev days",
    "blocker": [
      "修复 TTS/字幕环节 (srt=0, wav 破损)",
      "把 B007 segment/ASR/OCR 接到 planning/matching/roughcut",
      "新链渲染 QA 至少 1 条"
    ]
  },
  "pilot_5": {
    "optimistic": "3 days",
    "realistic": "3-7 days",
    "blocker": [
      "first video 验收",
      "人工打分标准落地",
      "5 类内容各 1 条"
    ]
  },
  "stable_daily_production": {
    "optimistic": "1 week",
    "realistic": "1-2 weeks",
    "blocker": [
      "规则稳定",
      "QA 闸自动化",
      "素材去重/cooldown 生效"
    ]
  },
  "mature_v1": {
    "optimistic": "3 weeks",
    "realistic": "3-6 weeks",
    "blocker": [
      "认知校准(L3)",
      "Recent 样本补链",
      "反馈闭环"
    ]
  },
  "note": "FIRST VIDEO 与 MATURE V1 分开：第一条重在打通链（含修复 TTS/字幕），成熟版才谈稳定性"
}

## L3 review16 plan

{
  "goal": "先用16段判定 L3 校准收益；收益不足则不再审剩余24段",
  "selection_rule": "8 OPENING + 8 HIGH_INFORMATION，按 storage/flexible/dining/detail/power/human/product 证据分排序",
  "opening": [
    {
      "segment_id": "b007:66de90b3000000000c01a935:0",
      "sample_id": "SD-66de90b3",
      "stratum": "D_PAID_HIGH_INPUT_WEAK_OUTCOME"
    },
    {
      "segment_id": "b007:64db4e87000000001701a578:0",
      "sample_id": "SD-64db4e87",
      "stratum": "D_PAID_HIGH_INPUT_WEAK_OUTCOME"
    },
    {
      "segment_id": "b007:66f672d6000000001902efbb:0",
      "sample_id": "SA-66f672d6",
      "stratum": "A_CREATOR_HIGH_NO_PAID_ASSOC_OBSERVED"
    },
    {
      "segment_id": "b007:66d7c509000000000c018964:0",
      "sample_id": "SB-66d7c509",
      "stratum": "B_CREATOR_MID_LOW_NO_PAID_ASSOC_OBSERVED"
    },
    {
      "segment_id": "b007:670630e9000000001a023e3f:0",
      "sample_id": "SD-670630e9",
      "stratum": "D_PAID_HIGH_INPUT_WEAK_OUTCOME"
    },
    {
      "segment_id": "b007:6718abc70000000021009845:0",
      "sample_id": "SE-6718abc7",
      "stratum": "E_CROSS_SOURCE_CONTRAST"
    },
    {
      "segment_id": "b007:640dc1050000000014025280:0",
      "sample_id": "SF-640dc105",
      "stratum": "F_PAID_ASSOCIATED_NO_NOTE_METRIC"
    },
    {
      "segment_id": "b007:63c5675a000000001c034435:0",
      "sample_id": "SB-63c5675a",
      "stratum": "B_CREATOR_MID_LOW_NO_PAID_ASSOC_OBSERVED"
    }
  ],
  "high_info": [
    {
      "segment_id": "b007:69367987000000001b027d8f:10",
      "sample_id": "SD-69367987",
      "stratum": "D_PAID_HIGH_INPUT_WEAK_OUTCOME"
    },
    {
      "segment_id": "b007:63c8d157000000001f02357d:2",
      "sample_id": "SC-63c8d157",
      "stratum": "C_PAID_HIGH_EFFICIENCY_CANDIDATE"
    },
    {
      "segment_id": "b007:65bc60fe0000000008022950:5",
      "sample_id": "SC-65bc60fe",
      "stratum": "C_PAID_HIGH_EFFICIENCY_CANDIDATE"
    },
    {
      "segment_id": "b007:66ebc041000000000c01b331:5",
      "sample_id": "SE-66ebc041",
      "stratum": "E_CROSS_SOURCE_CONTRAST"
    },
    {
      "segment_id": "b007:63c5675a000000001c034435:3",
      "sample_id": "SB-63c5675a",
      "stratum": "B_CREATOR_MID_LOW_NO_PAID_ASSOC_OBSERVED"
    },
    {
      "segment_id": "b007:69f9a0ac000000003701d937:5",
      "sample_id": "SC-69f9a0ac",
      "stratum": "C_PAID_HIGH_EFFICIENCY_CANDIDATE"
    },
    {
      "segment_id": "b007:66d7c509000000000c018964:19",
      "sample_id": "SB-66d7c509",
      "stratum": "B_CREATOR_MID_LOW_NO_PAID_ASSOC_OBSERVED"
    },
    {
      "segment_id": "b007:66de90b3000000000c01a935:4",
      "sample_id": "SD-66de90b3",
      "stratum": "D_PAID_HIGH_INPUT_WEAK_OUTCOME"
    }
  ],
  "estimated_user_time_min": 30,
  "stop_rule": "若16段 L3 校准对认知准确率提升不明显 → 不继续剩余24段，先修 schema/模型"
}

## STOP — audit complete; no selection/media recovery/L3/V0.9 performed
