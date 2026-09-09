# TREECUT VC0 — VOICE REFERENCE FREEZE + OFFLINE CLONE A/B
- **性质**：授权声音素材的只读提取/分段/去重/质量审核/离线克隆验证；不改生产链、不替换 Melo、
  不训练、画面零使用、原始声音零入 Git。
- **授权**：VOICE_OWNER_AUTHORIZED = YES（声音所有者确认授权）。
- 匿名 voice_profile_id：VOICE_001。聊天画面未被 OCR/截图/入库，报告不含画面内容。

## 源文件验证（机器）
- `0899bb1ff653be0070d46332d1b0d96a.mp4`（桌面）SHA-256 =
  `4f453ddfa046fe9b7d9f373d1f7a80c8fe9e16703dd95054bda0fb0cb58992e5`（与预期一致）。
- 音频流：AAC-LC 48000Hz mono ~47991bps；容器时长 193.89075s（≈193.891）。
- 视频流（h264 432×960）仅存在于源文件，未提取未入库。

## 提取（本地私有 E:\TreeCutRuntime\voice_profiles\VOICE_001\）
- `source_original_audio.wav`：48kHz mono PCM 不可变原件（sha256 见 HASH_MANIFEST）。
- `source_working_24k.wav`：24kHz mono PCM（供模型）。原 MP4 零改动；无降噪/变速/动态压缩。

## VAD + 去重（机器重算，非硬编码时间窗）
- VAD（能量 −50dBFS、帧 20ms、min 0.4s、gap 0.6s）→ **30 段**（raw 53 → merge 30）。
- 音频互相关（scipy fftconvolve 归一化峰值）→ **15 对重复**（相似度 0.972–0.9998）。
- 每对按 RMS/削顶评分保留较好一条 → **15 条独立语音，合计 70.34s**
  （含重复总有声 ≈ 140.7s；与检测预期 ~15 条 ~70–75s 吻合）。
- 保留片段时间窗与预期表一致（如 seg13 57.38–66.78 ≈ 57.397–67.076 等）。

## 每段记录（vc0_local_manifest.json，本地）
segment_id/start/end/duration/sha256/RMS/peak/LUFS/TP/clipping/duplicate_of/
speaker_consistency/transcript/transcript_review_status/dataset_eligible/
exclusion_reason。
- ASR：faster-whisper small（zh，CPU int8）对 15 条全部成功（0 错误）。
- 转写含同音词（导台/倒台=岛台、护型=户型 等）→ **TRANSCRIPT_UNVERIFIED**，
  必须人工逐条核对后才可用于需参考文本的克隆（数据集暂不 eligible）。
- SINGLE_SPEAKER_CONFIRMED = NO（代理特征 std 92Hz；需人工听审最终确认）。

## 后端预检与 A/B 状态
- 机器：RTX 3050（6GB VRAM，CUDA True，torch 2.6.0+cu124）；RAM 31.9GB；
  E: 空闲 142.3GB；TreeCut runtime 现有 LocalTTS(sherpa-onnx melo zh_en) —— voice clone 未接入（F0/A0R2 确认）。
- 克隆后端均未安装（GPT_SoVITS/CosyVoice/OpenVoice/f5_tts = False）。
- 候选：GPT-SoVITS（首选零样本）> CosyVoice（对照）> OpenVoice V2（轻量备选）；
  F5-TTS 预训练权重商用许可未决，不作生产默认。权重许可在安装时复核。
- **ZERO_SHOT_A_B_COMPLETED = A_ONLY**：Melo 基线样本 SAMPLE_A.wav 已生成（匿名）；
  GPT-SoVITS/CosyVoice 需授权离线安装后才可出 B/C —— 不伪造 B/C 样本。
- 试听包：`samples/SAMPLE_A.wav` + `samples/BLIND_REVIEW.html`（本地）。

## 硬门
FINE_TUNE_ALLOWED = NO；PRODUCTION_INTEGRATION_ALLOWED = NO；
FALLBACK（Melo 静默回退）规则留待接入阶段；后续接入需统一
`synthesize(text, output_path, voice_profile_id, parameters)` + 版本元数据。

## 结果字段（TREECUT_VC0_RESULT.json）
VOICE_REFERENCE_AVAILABLE=YES · VOICE_OWNER_AUTHORIZED=YES · RAW_DURATION=193.856s ·
ACTIVE_SPEECH_DURATION≈140.7s · UNIQUE_SPEECH_DURATION=70.34s · RAW_SEGMENT_COUNT=30 ·
UNIQUE_SEGMENT_COUNT=15 · DUPLICATE_PAIR_COUNT=15 · SINGLE_SPEAKER_CONFIRMED=NO ·
TRANSCRIPT_VERIFIED_COUNT=0 · DATASET_READY_FOR_ZERO_SHOT=YES_AFTER_TRANSCRIPT_REVIEW ·
DATASET_READY_FOR_FINE_TUNE=NO · SELECTED_BACKEND=GPT-SoVITS(PREFERRED,PENDING_INSTALL) ·
ZERO_SHOT_A_B_COMPLETED=A_ONLY · HUMAN_REVIEW_STATUS=AWAITING · FINE_TUNE_ALLOWED=NO ·
PRODUCTION_INTEGRATION_ALLOWED=NO · NEXT_BLOCKER=人工盲听 SAMPLE_A + 批准离线安装克隆后端出 B/C。

## Git 提交内容（不含任何声音）
VC0 代码 / 匿名摘要（无转写文本、无音频） / hash manifest（哈希非内容） /
后端决策报告 / 数据驱动测试。本地私有数据保留于
`E:\TreeCutRuntime\voice_profiles\VOICE_001\`（wav、segments、asr、manifest、samples）。
完成后 STOP，等待人工盲听与后端安装授权。
