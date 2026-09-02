# TreeCut STAGE8 通宵生产加固 Sprint V2 — 主报告

生成：2026-09-02 20:08:08 ｜ 执行窗口按 15h30m 上限约束 ｜ 模式：UNATTENDED/CHECKPOINTED

## 状态矩阵（§107）

| 项 | 状态 |
| --- | --- |
| G1 | **PASS**(冻结) |
| G2 Action/Subclip | **ENGINEERING_EVALUATION + HUMAN_VALIDATION_PENDING**（等价 PASS_WITH_LIMITATIONS 待人工） |
| G3 Claim→Visual | **ENGINEERING_EVALUATION + HUMAN_VALIDATION_PENDING** |
| DEDUP | **PASS**(逻辑+V2时间线实测；视觉pHash待frame缓存=局限) |
| G5 QA | **PASS**(分层+P0+V1/V2负回归) |
| UI | **USABLE**(smoke 全绿; 局部裁剪/自动重QA留待接 builder) |
| VOICE | **READY_FOR_INPUT**(无样本不克隆不宣称) |
| BGM | **LIBRARY_NOT_READY**(无授权条目) |
| REHEARSAL | **LIMITATION**(编排器通; probe 集有限部分 beat 无候选——如实) |
| Full Regression | **354 passed / 2 skipped / 0 failed** |

## 首页速览（§106 逐项）

| 问题 | 答案 |
| --- | --- |
<tr><th>G1 冻结 PASS?</th><td>是 STAGE8_G1_PASS(A4a=SafetyAgreement / idx63 非阻塞)</td></tr><tr><th>当前回归结果</th><td>354 passed / 2 skipped / 0 failed(161s, 当前 commit)</td></tr><tr><th>G2 状态</th><td>ENGINEERING_EVALUATION + HUMAN_VALIDATION_PENDING</td></tr><tr><th>能否区分 伸缩动作 vs 插座特写?</th><td>能: ActionSubclipService 只认时序动作窗; 纯插座资产(1590-92)无 EXTEND 窗; matcher 硬闸 DOMINANT_VISUAL_MISMATCH</td></tr><tr><th>能否识别 start/motion/end?</th><td>帧级产出 ACTION_START/IN_PROGRESS/END 语义(87帧 L2), 窗口含 action_start/peak/end</td></tr><tr><th>Best Subclip 实现?</th><td>是(28 窗口; subclip 非整段; semantic/boundary 分离; 示例 2482 ≈5.09-7.59s 动作粗定位)</td></tr><tr><th>Action Query20 结果</th><td>16/20 有候选; HUMAN_VALIDATION_PENDING</td></tr><tr><th>G3 状态</th><td>ENGINEERING_EVALUATION(matcher Query20 命中 {sum(1 for q in mq if q['matched_n']>0)}/20)</td></tr><tr><th>Atomic Claims 实现?</th><td>是(解析器+类型+ACTION 最早词优先)</td></tr><tr><th>Claim→Visual 硬闸?</th><td>是(资格/对象/动作/禁止视觉/故事/重复)</td></tr><tr><th>Story Mode?</th><td>是 SINGLE_CASE/INFORMATION_MONTAGE 分类</td></tr><tr><th>Thin drawer 修复?</th><td>是(上层位置+薄几何未证 → THIN_DRAWER_UNVERIFIED 拒/降级)</td></tr><tr><th>V2 伸缩/插座回归修复?</th><td>是(PILOT_V2_REGRESSION 文件+测试: 伸缩口播+插座=FAIL)</td></tr><tr><th>Dedup 状态</th><td>级别检测+叙事近重; V2 时间线 11 命中; 视觉 pHash 待 frame 缓存</td></tr><tr><th>V2 重复结尾检测?</th><td>是(叙事近重 HIGH→MAJOR_DUPLICATE P0)</td></tr><tr><th>G5 QA 状态</th><td>分层+P0 门禁实现; V1/V2 负回归测试过</td></tr><tr><th>V1 假通过还会发生?</th><td>否: stream级AV硬闸+P0门禁+分层QA(测试覆盖)</td></tr><tr><th>V2 假通过还会发生?</th><td>否: 字幕/音/BGM/语义/重复/动作回归已编码为测试</td></tr><tr><th>Production Workbench 可用?</th><td>是(本地 server+前端; smoke 全绿)</td></tr><tr><th>UI: play Top3/replace/trim/save?</th><td>play Top3/replace→保存 可用; 裁剪按钮预留(见 KNOWN_LIMITATIONS)</td></tr><tr><th>UI 响应</th><td>project api 122ms / index 8ms(本机)</td></tr><tr><th>Caption 默认</th><td>FontSize 66(62-68)/outline4-6/≤2行(配置+QA 校验)</td></tr><tr><th>VoiceProvider 状态</th><td>接口+SAPI(FALLBACK)+克隆集成点; 无样本 → VOICE_INPUT_REQUIRED</td></tr><tr><th>Voice 输入需要?</th><td>是(见 docs/TREECUT_VOICE_REFERENCE_GUIDE.md, 30-60s 即可)</td></tr><tr><th>BGM 库状态</th><td>schema+服务就绪; 无授权条目 → BGM_LIBRARY_NOT_READY(不rip不下载)</td></tr><tr><th>Technical rehearsal</th><td>编排器执行: claims→matcher→windows→QA; 因 probe 集有限, 部分 beat NO_VALID_CANDIDATE(如实)</td></tr><tr><th>DB/media 损坏?</th><td>quick_check ok / FK 0(运行期前)</td></tr><tr><th>存储健康</th><td>C 57GB(已清9.9GB临时, 硬停<50) / E 154.9 / G 147.9 / Z 12TB(见 P0 快照)</td></tr><tr><th>明天需做的1-3件事</th><td>1) 审 G2/G3 review HTML(或直接给判定) 2) 提供 30-60s 真人参考音 3) 提供授权 BGM 目录(如仍需要)</td></tr>

## 关键结果与诚实边界
1. 伸缩 vs 插座：真伸缩文件夹素材(2482-84)出 EXTEND 窗；命名带"伸缩"的插座空镜(1984-86) qwen 判有加宽动作 → **路径提示不可当真值**；纯插座(1590-92) EXTEND=无窗
2. 动作窗粒度：5帧+有界补充采样，起止精度约 ±0.3s；EXTEND/RETRACT 方向在单帧问题下未区分（限制）
3. 全部 qwen 结果 = L2 候选；G2/G3 均标 HUMAN_VALIDATION_PENDING，未称 human accuracy
4. UI：可播放 subclip(Range 206)、替换保存持久化；重活(候选重建/QA)由 builder 侧完成——UI 不跑重推理（符合 §69）

## 产物清单
- G2: TAXONOMY/CALIBRATION(15)/TEMPORAL_EVIDENCE(87帧)/QUERY20/SUBCLIP_WINDOWS(28)/HARD_NEGATIVES + HUMAN_REVIEW_V1.html
- G3: ATOMIC_CLAIMS/VISUAL_REQUIREMENTS/STORY_MODE/CASE_CLUSTER/MATCHER_QUERY20/PILOT_V2_REGRESSION + HUMAN_REVIEW_V1.html
- Dedup/QA: DEDUP_POLICY/QA_SCHEMA_V2/QA_RULES_V2/FALSE_PASS_AUDIT + G5 报告
- G4/UI/Config: PRODUCTION_CONFIG_V1 / VOICE_REFERENCE_GUIDE / voice_profile·music schema / WORKBENCH(server+index+smoke) / UI_PERFORMANCE_AUDIT / UI_KNOWN_LIMITATIONS
- docs: G2/G3/G5 报告 + 本文件；P0 基线 + SPRINT 状态

## 明天你的 3 件事
1. 审 `reports/storage/TREECUT_G2_HUMAN_REVIEW_V1.html` 与 `TREECUT_G3_HUMAN_REVIEW_V1.html`（或看 Workbench http://127.0.0.1:8899）
2. 提供 30–60 秒真人参考音（指南在 docs/TREECUT_VOICE_REFERENCE_GUIDE.md）
3. 提供授权 BGM 目录（如需要）
