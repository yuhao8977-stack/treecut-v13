# TreeCut B007 Pilot V1 vs V2 对比报告

V2 Final: **B007_PILOT_V2_READY_WITH_LIMITATIONS** | 2026-09-02 17:32:18

```json
{
  "old_subtitle": "V1: 有(B007 published 硬字幕) → V2: 无(干净 X1 原片)",
  "watermark": "V1: 小红书水印 → V2: 无",
  "shot_count": "V1: 5 → V2: 8",
  "avg_shot_s": "V2: 2.8",
  "script_visual_match": "V1: 标签级 → V2: 动作片段(folder 语义)+原子主张",
  "action_evidence": "V1: OBJECT_PRESENT → V2: 动作片段(薄抽/插座/伸缩文件夹)",
  "case_consistency": "V1: 5 案例硬拼 → V2: INFORMATION_MONTAGE 通用语言",
  "voice": "V1: SAPI 原速 → V2: SAPI 1.3x(loudnorm)",
  "speed": "V1: 3.58字/s → V2: ~4.6字/s",
  "bgm": "V1/V2: NONE(限制)",
  "av_sync": "V1: 差4.68s → V2: True (≤0.10s)",
  "new_subtitle": "V1: 未烧 → V2: True(硬烧)",
  "claim_support": "V1: 粗 → V2: atomic claims",
  "technical_qa": {
    "CLEAN_SOURCE": true,
    "OLD_SUBTITLE_ABSENT": true,
    "PLATFORM_WATERMARK_ABSENT": true,
    "AV_SYNC": true,
    "video_stream_s": 22.767,
    "audio_stream_s": 22.698,
    "video_tail_covers_audio": true,
    "VIDEO_DECODABLE": true,
    "AUDIO_PRESENT": true,
    "resolution": "1080x1920",
    "NEW_CAPTION_RENDERED": true,
    "caption_evidence": {
      "ok": true,
      "method": "qwen2.5vl-ocr",
      "qwen_text": "岛台想好用，",
      "cue_text": "岛台想好用，",
      "cue_time_s": 0.6,
      "char_hit_ratio": 1.0,
      "note": ""
    },
    "caption_frames": [
      "E:\\树剪整理\\02_安装程序\\TreeCut_v13\\runtime\\production_smoke\\B007\\pilot_v2\\caption_frames\\cue1_t0.6s.png",
      "E:\\树剪整理\\02_安装程序\\TreeCut_v13\\runtime\\production_smoke\\B007\\pilot_v2\\caption_frames\\cue2_t2.2s.png",
      "E:\\树剪整理\\02_安装程序\\TreeCut_v13\\runtime\\production_smoke\\B007\\pilot_v2\\caption_frames\\cue3_t4.2s.png"
    ],
    "BGM_PRESENT": false,
    "VOICE_SPEED_VALID": true,
    "SHOT_PACING_VALID": true,
    "CLAIM_SUPPORTED": true,
    "ACTION_VISUAL_MATCH": true,
    "STORY_ENTITY_CONSISTENT": true,
    "BEAT_VISUAL_SYNC": true
  }
}
```

## V2 QA 明细

{
  "CLEAN_SOURCE": true,
  "OLD_SUBTITLE_ABSENT": true,
  "PLATFORM_WATERMARK_ABSENT": true,
  "AV_SYNC": true,
  "video_stream_s": 22.767,
  "audio_stream_s": 22.698,
  "video_tail_covers_audio": true,
  "VIDEO_DECODABLE": true,
  "AUDIO_PRESENT": true,
  "resolution": "1080x1920",
  "NEW_CAPTION_RENDERED": true,
  "caption_evidence": {
    "ok": true,
    "method": "qwen2.5vl-ocr",
    "qwen_text": "岛台想好用，",
    "cue_text": "岛台想好用，",
    "cue_time_s": 0.6,
    "char_hit_ratio": 1.0,
    "note": ""
  },
  "caption_frames": [
    "E:\\树剪整理\\02_安装程序\\TreeCut_v13\\runtime\\production_smoke\\B007\\pilot_v2\\caption_frames\\cue1_t0.6s.png",
    "E:\\树剪整理\\02_安装程序\\TreeCut_v13\\runtime\\production_smoke\\B007\\pilot_v2\\caption_frames\\cue2_t2.2s.png",
    "E:\\树剪整理\\02_安装程序\\TreeCut_v13\\runtime\\production_smoke\\B007\\pilot_v2\\caption_frames\\cue3_t4.2s.png"
  ],
  "BGM_PRESENT": false,
  "VOICE_SPEED_VALID": true,
  "SHOT_PACING_VALID": true,
  "CLAIM_SUPPORTED": true,
  "ACTION_VISUAL_MATCH": true,
  "STORY_ENTITY_CONSISTENT": true,
  "BEAT_VISUAL_SYNC": true
}

## STOP — 等 V1 vs V2 人工看片
