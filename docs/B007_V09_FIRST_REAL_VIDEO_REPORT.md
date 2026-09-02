# B007 V0.9 — First Real Video Report

Final: **B007_FIRST_REAL_VIDEO_READY_FOR_HUMAN_REVIEW** | 2026-09-02 16:25:17

```json
{
  "l3_integrated": true,
  "qwen_reviewed_accuracy": 0.688,
  "template_candidates_count": 3,
  "selected_template": "T_A_FEATURE_DEMONSTRATION",
  "recent_evidence_used": true,
  "script_beats": 5,
  "segments_selected": 5,
  "historical_segments_used": 0,
  "b003_contamination": 0,
  "video_rendered": true,
  "resolution": "1080x1920",
  "duration_s": 27.35,
  "narration": "NARRATION_READY",
  "subtitle": true,
  "technical_qa": "READY",
  "content_qa": true,
  "ready_for_human_review": true,
  "remaining_blockers": [
    "人工看片验收（ACCEPT/REJECT）",
    "若 540x960 限制已在 1080 渲染消除；听感/选镜是否符合审美待人工"
  ]
}
```

## Segments used

- B1 INTRO | b007:6a7b28ab000000002800316a:0 | 近期 | storage=yes power=yes flexible=yes
- B2 PRODUCT | b007:6a411feb000000001c026d77:7 | 近期 | storage=UNKNOWN power=yes flexible=yes
- B3 FEATURE_STORAGE | b007:6a411f31000000001503cdc6:0 | 近期 | storage=yes power=yes flexible=UNKNOWN
- B4 FEATURE_FLEXIBLE | b007:6a8edcca000000002a03b79e:0 | 近期 | storage=UNKNOWN power=yes flexible=yes
- B5 CTA | b007:6a92b9e8000000002501a357:5 | 近期 | storage=UNKNOWN power=UNKNOWN flexible=UNKNOWN

## QA

{
  "SOURCE_PROVENANCE": true,
  "NO_B003": true,
  "TIMELINE_VALID": true,
  "VIDEO_DECODABLE": true,
  "AUDIO_PRESENT": true,
  "DURATION_VALID": true,
  "RENDER_PASS": true,
  "video": {
    "codec": "h264",
    "w": 1080,
    "h": 1920,
    "duration_s": 27.35,
    "size": 11033180
  },
  "SUBTITLE_PRESENT": true
}

## Content QA

{
  "unsupported_claims": [],
  "missing_beat": [],
  "excessive_repeat": [],
  "near_dup": [],
  "continuity": []
}

## STOP — 等用户看片；不自动 Pilot2-5 / 不发布
