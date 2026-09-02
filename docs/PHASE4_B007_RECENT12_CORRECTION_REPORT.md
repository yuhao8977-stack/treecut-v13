# Phase4 — B007 Recent12 Correction Report (V0.8.2 + V0.8.3)

Status: **B007_RECENT12_CORRECTION_COMPLETE_WITH_LIMITATIONS** | 2026-09-02 14:46:12

- Recent12 selected = 12 (Latest6 2026-07~08, Earlier6 2026-04~06)
- Exact Media = 10/12
- Unavailable = ['RC-6A659145', 'RC-6A37DA9D']
- Gate 10/12 = True
- Recent Asset = 10 | Segments = 235 | ASR = 10 | OCR = 10 | Visual = 10 | Cognition = 10 | Qwen segs = 20

## Historical20 vs Recent12

| dim | historical | recent |
|---|---|---|
| opening_product_visibility | {"historical_yes_ratio": 0.45, "recent_yes_ratio": 0.6} |
| opening_human | {"historical_yes_ratio": 0.45, "recent_yes_ratio": 0.6} |
| opening_function_demo | {"historical_yes_ratio": 0.2, "recent_yes_ratio": 0.4} |
| storage | {"historical_yes_ratio": 0.1, "recent_yes_ratio": 0.1} |
| power | {"historical_yes_ratio": 0.0, "recent_yes_ratio": 0.0} |
| flexible | {"historical_yes_ratio": 0.1, "recent_yes_ratio": 0.2} |
| dining | {"historical_yes_ratio": 0.05, "recent_yes_ratio": 0.2} |
| has_subtitle | {"historical_yes_ratio": 0.95, "recent_yes_ratio": 1.0} |
| has_speech | {"historical_yes_ratio": 0.95, "recent_yes_ratio": 1.0} |
| scene_dominant | {"historical": "OTHER", "recent": "OTHER", "type": "dominant"} |
| duration_avg_s | {"historical": 48.2, "recent": 61.0} |
| segments_avg | {"historical": 18.7, "recent": 23.5} |

## Temporal Pattern Candidates

- **STABLE_PATTERN_CANDIDATE**: opening_product_visibility ({"dim": "opening_product_visibility", "class": "STABLE_PATTERN_CANDIDATE", "historical_yes_ratio": 0.45, "recent_yes_ratio": 0.6, "diff": 0.15})
- **STABLE_PATTERN_CANDIDATE**: opening_human ({"dim": "opening_human", "class": "STABLE_PATTERN_CANDIDATE", "historical_yes_ratio": 0.45, "recent_yes_ratio": 0.6, "diff": 0.15})
- **STABLE_PATTERN_CANDIDATE**: opening_function_demo ({"dim": "opening_function_demo", "class": "STABLE_PATTERN_CANDIDATE", "historical_yes_ratio": 0.2, "recent_yes_ratio": 0.4, "diff": 0.2})
- **UNCERTAIN_PATTERN**: storage ({"dim": "storage", "class": "UNCERTAIN_PATTERN", "historical_yes_ratio": 0.1, "recent_yes_ratio": 0.1, "diff": 0.0})
- **UNCERTAIN_PATTERN**: power ({"dim": "power", "class": "UNCERTAIN_PATTERN", "historical_yes_ratio": 0.0, "recent_yes_ratio": 0.0, "diff": 0.0})
- **UNCERTAIN_PATTERN**: flexible ({"dim": "flexible", "class": "UNCERTAIN_PATTERN", "historical_yes_ratio": 0.1, "recent_yes_ratio": 0.2, "diff": 0.1})
- **UNCERTAIN_PATTERN**: dining ({"dim": "dining", "class": "UNCERTAIN_PATTERN", "historical_yes_ratio": 0.05, "recent_yes_ratio": 0.2, "diff": 0.15})
- **STABLE_PATTERN_CANDIDATE**: has_subtitle ({"dim": "has_subtitle", "class": "STABLE_PATTERN_CANDIDATE", "historical_yes_ratio": 0.95, "recent_yes_ratio": 1.0, "diff": 0.05})
- **STABLE_PATTERN_CANDIDATE**: has_speech ({"dim": "has_speech", "class": "STABLE_PATTERN_CANDIDATE", "historical_yes_ratio": 0.95, "recent_yes_ratio": 1.0, "diff": 0.05})
- **STABLE_PATTERN_CANDIDATE**: scene_dominant ({"dim": "scene_dominant", "class": "STABLE_PATTERN_CANDIDATE", "historical": "OTHER", "recent": "OTHER", "note": "historical dominant OTHER vs recent dominant OTHER"})

## TTS/SRT Diagnostic

- narration.wav=2s 与 narration.srt=0 系 cognitive/production.produce() 的**设计占位**（anullsrc -t 2 静音 + 空 srt，代码注释'认知链路无 TTS/选曲时跳过'）；narration_script.txt 仅为结构提示（'结合素材内容口播'）。**真 TTS 链（copywriter.build_narration + models/tts_local.synthesize）存在于 desktop._generate_narration，但从未接入 produce()** → 集成缺口，非 TTS 引擎损坏。

## STOP

Recent12 + analysis + comparison + Review16V2 + TTS diagnostic complete; NO L3 written; NO V0.9/Template/AutoCut/Production Render entered.
