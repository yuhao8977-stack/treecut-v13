# TREECUT VC1-ZS — GPT-SoVITS ISOLATED ZERO-SHOT VOICE CLONE + FAIR A/B
- **基线**：cbd67ba；授权 VOICE_OWNER_AUTHORIZED=YES；声音/权重不入 Git；不改生产链、未替换 Melo、未训练。
- 本轮只做零样本；FINE_TUNE_ALLOWED=NO；PRODUCTION_INTEGRATION_ALLOWED=NO；TREECUT_TTS_REPLACED=NO。

## VC0 试听状态纠正
- SAMPLE_A_RAW_BACKEND = MELO（旧对照组）；SAMPLE_A_IS_CLONED_VOICE = NO。
- 旧包只有 A → 不称"已完成盲听包"；本次新包含 A/B 匿名对后才 BLIND_REVIEW_READY。
- 全部试听输出 RAW + EVAL；EVAL 统一 integrated ≈ -16 LUFS、true peak ≤ -1.5 dBTP（目标）、同采样率/声道/文本（fair_loudness_check 实测值见 SAMPLE_METRICS）。

## 参考审核页（人工）
`E:\TreeCutRuntime\voice_profiles\VOICE_001\VOICE_REFERENCE_REVIEW.html`：15 条独立音频播放 +
ASR 转写编辑 + 目标说话人 YES/NO + 噪声/提示音/多人重叠 + 允许零样本 + 导出 review_result.json；
优先显示 seg13/seg23/seg25/seg27。零样本最低要求（≥1 条 5-10s 逐字核对、目标人确认、无重叠、
无提示音、clipping=0）待人工在此页完成后满足（当前 VERIFIED_REFERENCE_COUNT=0；
SINGLE_SPEAKER_HUMAN_CONFIRMED=NO_PENDING_REVIEW_PAGE，不再用频谱重心冒充证明）。

## GPT-SoVITS 安装（独立环境）
- 官方仓库：https://github.com/RVC-Boss/GPT-SoVITS（commit 48b1a01，MIT LICENSE）。
- venv：`E:\TreeCutRuntime\voice_clone_envs\GPT_SoVITS\venv`（system-site 复用 runtime torch 2.6.0+cu124 CUDA；
  不污染 TreeCut runtime、不覆盖 LocalTTS）。
- 权重：`E:\TreeCutRuntime\models\VoiceClone\GPT_SoVITS\repo`（hf-mirror 稀疏 git clone，git-lfs；
  hubert/roberta/v2final s1+s2G/s2D；SHA-256 见 BACKEND_MANIFEST）。权重商用许可未确认 → 仅内部测试。
- 本地适配补丁（记录在案）：jieba_fast shim、fast_langdetect 离线 zh 回退、api_v2 400 traceback 日志、
  g2pw bert tokenizer 资产（bert_path）、requirements 过滤 + opencc 轮子。
- 服务：api_v2.py（v2final custom config，cuda half）@127.0.0.1:9880。

## 零样本生成（12 组，seed=42）
- GPT-SoVITS：T1-T5 用 seg23 参考；额外 T1-seg13、T3-seg25 检查音色随参考变化（reference_audio_sha 见 metrics）。
- Melo 基线同文本。
- T4 20s+ 长介绍、T5 ~25s 生产长度旁白（仅 WAV，不合成视频）。
- 指标（SAMPLE_METRICS）：duration/LUFS/TP/clipping、ASR 文本与 CER、gen_seconds；
  机器 CER 受 ASR 噪声影响，仅辅助；最终由人工听审决定。

## 盲听包（桌面 TreeCut_VC1_ZS_试听）
ORIGINAL_REFERENCE.wav(seg23, 明确参考音色) + TEST_01(T1)/TEST_02(T3)/TEST_03(T5) 各
SAMPLE_A/B.wav（EVAL 归一、seed 随机匿名，reviewer_map.json 单独保存）+ BLIND_REVIEW.html（无模型名）。
评分维度：音色相似度/自然度/清晰度/情绪语气/长句稳定性/数字与岛台词准确性/商业可用意愿/备注。

## 结果字段（TREECUT_VC1_RESULT.json）
REFERENCE_REVIEW_COMPLETED=NO · SINGLE_SPEAKER_HUMAN_CONFIRMED=NO_PENDING_REVIEW_PAGE ·
VERIFIED_REFERENCE_COUNT=0 · GPT_SOVITS_INSTALLED=YES · CODE_LICENSE_STATUS=MIT ·
WEIGHT_LICENSE_STATUS=INTERNAL_TEST_ONLY_PENDING_COMMERCIAL_CONFIRM ·
ZERO_SHOT_GENERATED=YES · FAIR_LOUDNESS_NORMALIZATION=YES ·
ZERO_SHOT_PASS=PENDING_HUMAN_BLIND_REVIEW · HUMAN_BLIND_REVIEW_STATUS=AWAITING ·
FINE_TUNE_NEEDED=PENDING_DECISION · FINE_TUNE_ALLOWED=NO ·
PRODUCTION_INTEGRATION_ALLOWED=NO · TREECUT_TTS_REPLACED=NO ·
NEXT_BLOCKER=人工盲听（桌面 TreeCut_VC1_ZS_试听）→ 决定零样本通过或 VC2 少样本。

## Git 提交
仅代码 / 匿名指标 / hash manifest / 后端清单 / 报告 / 测试；无 WAV、无原视频、无转写正文、无权重。
完成后 STOP，等待人工盲听。
