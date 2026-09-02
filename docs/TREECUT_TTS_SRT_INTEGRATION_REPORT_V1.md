# TreeCut TTS/SRT Integration Report (V0.8.4)

Status: **TREECUT_TTS_SRT_INTEGRATION_PASS** | 2026-09-02 15:25:59

## First page

- TTS engine reused: Windows SAPI (sherpa-onnx 不可用: 无外网/无模型)
- real TTS integrated into produce: True
- 2s placeholder removed from production mode: True
- SHORT audio: 8.716s (4.02 字/s)
- MEDIUM audio: 33.593s
- LONG audio: 69.389s
- SMOKE30S audio: 34.247s
- SRT non-empty 4/4: 4/4
- subtitle text coverage: [1.0, 1.0, 1.0, 1.0]
- timestamps valid: True
- 30s smoke test: PASS
- tests: 8 new TTS/SRT tests PASS
- remaining blocker: none (BGM 仍为静音占位——非本阶段目标；成片渲染/时间线接 B007 为下一阶段)

## Artifacts

- narration.wav/srt 见 E:\...\tts_smoke\{SHORT,MEDIUM,LONG,SMOKE30S}\
- metadata: narration_metadata.json (tts_source/voice/text_hash/audio_sha256/...)
