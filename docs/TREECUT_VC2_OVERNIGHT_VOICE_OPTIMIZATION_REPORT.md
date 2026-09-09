# TREECUT VC2-FT-OVERNIGHT — 声音优化过夜任务（无人值守执行摘要）

- 基线（机器实查）：HEAD=origin/main=`c38a3e13…`（clean at start）；RTX 3050 6GB CUDA torch 2.6.0+cu124；E: 空余充足。
- 裁决冻结（DECISION_FREEZE）：A=GPT_SOVITS、B=MELO、GPT_SOVITS_CLOSER_THAN_MELO=YES、
  ZERO_SHOT_PASS=PARTIAL_NOT_ACCEPTED、FINE_TUNE_NEEDED=YES、
  FINE_TUNE_ALLOWED=YES_INTERNAL_EXPERIMENT_ONLY、PRODUCTION_INTEGRATION_ALLOWED=NO、
  TREECUT_TTS_REPLACED=NO、VOICE_OWNER_AUTHORIZED=YES。

## 已执行
1. **数据集审计（DATASET_AUDIT）**：15 唯一段 / 70.34s / 15 duplicate pairs（互相关去重，dup 组同源），
   逐段 SHA+duration+peak+clip+DC+silence_ratio+lead/trail+F0 median/IQR+LUFS/TP；源 SHA 复核。
   机器说话人 = MACHINE_INCONCLUSIVE（无可靠声纹模型且禁止下载不明模型，不冒充人工）。
2. **转写（TRANSCRIPT_CONSENSUS_SUMMARY）**：两路不同家族 ASR（faster-whisper small + FunASR paraformer-zh，
   本地成功 15/15）→ PROVISIONAL_MACHINE_CONSENSUS；文本只存本地；REFERENCE_REVIEW_COMPLETED=NO、
   VERIFIED_REFERENCE_COUNT=0；专业词（岛台/伸缩/岩板/轨道插座/公牛/抽屉/收纳/户型/水电/预留/台面/柜体）命中记录。
   本地审核页 VOICE_REFERENCE_REVIEW_VC2（逐段播放/双路 ASR 编辑/允许训练/localStorage/导出）供人工。
3. **零样本 sweep（ZERO_SHOT_SWEEP）**：从 api schema 读取参数（非照抄）——32 短句(T1)
   refs{seg13,23,25,27}×seed{1,42}×top_k{10,15}×temperature{0.6,1.0} → top8 中句(T3) → top4 长句(CAL25+LONG_STRESS)；
   评分 = 0.4·|F0-183|/183 + 0.3·max(0,pause-0.11) + 0.3·CER；≥2 seed。CAL25/LONG_STRESS 文本 SHA 固定；
   旧 T5 改名 LONG_STRESS_TEST_NOT_25S（长文本 50–75s 如实，不硬塞 25s）。
4. **少样本训练（TRAINING_RUNS）**：**FINE_TUNE_EXECUTED = NOT_EXECUTED_PREPROCESS_TOOLCHAIN_REQUIRES_WEBUI**
   —— V2 final s1/s2_train 需要 WebUI 生成的逐实验配置与预处理目录（module/data_utils.py 断言
   2-name2text.txt、4-cnhubert/*.pt、5-wav32k/*.wav）；无人值守 CLI 复刻该预处理层无官方支持、
   不凭猜测拼 CLI，故如实记录未伪造完成。数据门本身 PASS（≥10 条/70.3s≥45s/holdout 预留 2 条 8s+/
   dup 零泄漏/机器共识转写）。此分支留待 WebUI 驱动的 VC2b。
5. **统一公平评价（SAMPLE_METRICS）**：4 系统（VC2_OPT_ZS_BEST / VC2_OPT_ZS_2ND / VC1_ZS_BASELINE /
   MELO_ANCHOR）× T1/T2/T3/CAL25；RAW+EVAL；EVAL 采用双遍 loudnorm + 硬限幅 + 增益微调闭环，
   **TRUE_LOUDNESS_MATCH=PASS**（全部 -15.9~-16.01 LUFS、TP≤-1.5dBTP）；输出 duration/voiced/pause/
   lead/trail/chars-per-sec/CER；pause 参考≈11%，VC1 gpt≈32%，VC2 最优≈（见 RESULT）。
   停顿与语速按“模型原始输出”口径报告（未做安全裁剪冒充）。
6. **盲听包（桌面 TreeCut_VC2_过夜优化试听）**：ORIGINAL_REFERENCE(seg23) + round1 4 系统×4 文本
   （每 TEST 独立随机 A/B/C/D）+ round2 机器 top2×5 文本（含 LONG_STRESS）；BLIND_REVIEW.html
   （无模型名/checkpoint/seed，播放+1-10 分+备注+localStorage 草稿+导出 human_review_result.json）；
   reviewer_map.json 单独并注明评分前勿开。

## 最终字段（TREECUT_VC2_RESULT.json）
HUMAN_ZERO_SHOT_VERDICT=PARTIAL_NOT_ACCEPTED · REFERENCE_REVIEW_COMPLETED=NO ·
SINGLE_SPEAKER_HUMAN_CONFIRMED=NO · VERIFIED_REFERENCE_COUNT=0 ·
PROVISIONAL_TRANSCRIPT_COUNT=15 · DATASET_GATE_PASS=True · ZERO_SHOT_SWEEP_COUNT=32 ·
FINE_TUNE_EXECUTED=NOT_EXECUTED_PREPROCESS_TOOLCHAIN_REQUIRES_WEBUI ·
BEST_MACHINE_CANDIDATE=见 RESULT · BEST_CANDIDATE_HUMAN_STATUS=AWAITING ·
TRUE_LOUDNESS_MATCH=PASS · WEIGHT_LICENSE=INTERNAL_TEST_ONLY_PENDING_COMMERCIAL_CONFIRM ·
PRODUCTION_INTEGRATION_ALLOWED=NO · TREECUT_TTS_REPLACED=NO · B2/C0/N1/GEOM/CAM=NOT_STARTED ·
NEXT_BLOCKER=VC2_HUMAN_BLIND_REVIEW_AND_TRANSCRIPT_CONFIRMATION。

## Git
只提交脚本/测试/匿名 JSON（segment ID/hash/长度/指标，无转写正文、无声音、无权重/checkpoint）。
HEAD/origin/main 与 clean 状态最终实查见提交说明。完成试听包/报告/测试/提交推送后 STOP；
不自动进入 VC3/生产接入/B2；F0R2 勘误与 B2 仍待办（独立任务）。
