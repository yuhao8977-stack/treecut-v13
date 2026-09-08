# TREECUT MASTER PRODUCT GOAL ALIGNMENT AUDIT A0 — 全产品能力审计

- **性质**：READ-ONLY 全产品能力审计（源码/DB/UI/E2E/测试/产物）
- **基线**：main @ `740ca949fd30388d4887a7eb0edd46a440528f2d`（生成前 clean/与 origin 一致）
- **方法**：证据优先级 = 实际执行路径源码 > 真实 DB > 真实产物 > 测试 > 文档 > README
- 机器对应：12 个 A0 JSON（见 §11）

## 0. 一句话结论（OVERALL PRODUCT STATE）

**TreeCut 存在一条真实可跑的"素材→分析→检索→匹配→时间线→TTS→字幕→BGM→MP4→剪映草稿"
半自动生产链，且在 2026-08-06 有真实成功产物（2 projects success，TreeCut_成片.mp4 +
剪映草稿 + QA passed）。** 但：(1) 生产链**没有"脚本→逐句 Beat/Claim 拆分层"**（整段文案匹配）；
(2) 历史 E2E 素材源路径已失效（当前需重扫）；(3) Source-gate/A4 是 CAM 研究未接入生产；
(4) CAM/EH/GEOM/N0/N1 全是 **shadow 研究，无生产 caller**。

## 1. 启动链（真实，非推断）

`启动树剪v13.cmd` → `runtime\pythonw.exe -m treecut.watchdog` → `pythonw -m treecut.desktop`（Tk UI, 731 行）。
Console scripts：treecut / treecut-desktop / treecut-api / treecut-xhs-browser。
**用户今天实际走的是 desktop Tk 链**；CAM/EH 不在 UI 链中。

## 2. 生产主链（E2E_PROVEN，2026-08-06 实证）

desktop._start_request → ProductionService._create → load_candidates(真实 DB 4 表) →
semantic_scores(BGE+CLIP 真实打分) → match_materials(n-gram 术语匹配) → build_edit_plan
(category 去重+时长填充) → render_video_plan(ffmpeg 切+拼) → create_narrated_video
(sherpa_onnx melo TTS) → mix_background_music(内置 mp3) → burn_subtitles(Noto CJK) →
build_jianying_draft(真实剪映格式) → QA inspect(回读校验) → MP4+draft+cover+report。

**实证产物**（output/projects/20260806_110330/120231）：
TreeCut_成片.mp4（5.8MB, 1080×1080@30, 含音频 30s）· 01-03 预览 mp4 ·
TreeCut_剪映草稿（draft_content.json 含 tracks/materials/keyframes + voice/bgm wav）·
cover.jpg · production_report.json（quality passed=True, bge/clip 真实分数）。

**E2E 失败证据**（20260806_102815 failed）："合格素材不足：计划 0.0 秒，目标 30.0 秒"——
fail-closed 真实生效。

## 3. 数据身份（两库分离是核心风险）

| 身份 | 位置 | 行数 | 备注 |
|---|---|---|---|
| media_files.id | 生产库 4 表 | 15378 | 生产链真实身份 |
| analysis_jobs | 生产库 | 4347（3319 eligible） | load_candidates 消费 |
| assets.asset_id | **CAM 库**(temp/batch1) | 22466 | 生产库无此表 |
| segments.segment_id | CAM 库 | 41834 | 生产链用整文件 clip 非 segment |
| transcripts/ocr | CAM 库 | 51543 / 289218 | Domain B 实证 |

**核心风险**：同名 materials.db 存在于两目录——生产 4 表 vs CAM 88 表。生产链不消费
asset/segment（整文件 clip）；CAM 身份体系与生产不互通。第四套 shot ID 不存在。

## 4. 八域能力（证据等级）

| 域 | highest verified | 证据要点 |
|---|---|---|
| A Asset Ingestion | **DATA_CONNECTED** | 15378 media+fingerprint；去重表仅 CAM 库 |
| B Segment+MM | **DATA_CONNECTED** | analysis_jobs 4347 含 Florence caption/objects/ASR(RapidOCR/faster-whisper)；asset/segment/transcript/ocr 在 CAM 库 |
| C Knowledge+Feedback | **E2E_PROVEN** | feedback.adjustments 被 production:178 消费（ranking）；未到 embedding/training |
| D Script/Claim/Template | **NOT_FOUND(beat层)** / USER_USABLE(手工文案) | 生产链无脚本→逐句拆分；claim_visual CAM-only |
| E Retrieval+Selection | **E2E_PROVEN** | 真实 DB 检索；fail-closed 实证 |
| F Timeline+Editing | **E2E_PROVEN** | render mp4 实证 |
| G Subtitle/Voice/BGM | **E2E_PROVEN** | TTS+字幕烧录+BGM 实证；voice clone=NOT_FOUND |
| H Output+UI+Ops | **USER_USABLE** | desktop Tk+FastAPI；团队/权限未验证 |
| CAM/EH/N0 | **UNIT_TESTED(SHADOW)** | 无生产 caller |

## 5. CAM/EH/N0 定位（§13 核对）

EH02 Router / REFERENCE_STRONG / structural veto / NEG control **只解决 camera/object
reference evidence**，≠动作判断/素材理解/脚本匹配/视频生成。desktop 生产链 **不 import 任何
CAM 模块** → `SHADOW_NOT_PRODUCTION_CONNECTED`。N0 状态保持：N1_APPROVED=NO / PRESENT=YES /
ESTABLISHED=NO / GEOM_ALLOWED=NO / NEW_NEG_REFERENCE_ADDED=0（A0 不重新 adjudicate）。

## 6. REAL E2E TRACE（A0_E2E_TRACE_01）

- script_input：真实文案（"小户型岛台，可伸缩设计…"）→ **REACHED**
- parser_beat_claim：**NOT_FOUND_IN_PRODUCTION**（整段匹配）
- retrieval→selection→trim→timeline→voice→subtitle→bgm→qa→mp4→jianying：**全部 REACHED**
  （2026-08-06 历史实证）
- FIRST_REAL_E2E_BLOCKER（历史链）：**NONE**——链当时跑通
- 当前复现 blocker：**HISTORICAL_MEDIA_PATH_INVALID**（media 5/6 源文件不可读，旧路径失效；
  需当前源盘重扫）

## 7. TEST TRUTH

一次全量（system py）：**586 collected / 570 passed / 12 failed / 4 xfailed / 0 skip**（3 分钟）。
- 12 failed：test_stage2_vision 7 个 = **环境错位**（system py CPU torch 期望 CUDA；runtime py 有）；
  test_source_audit_r11 3 + test_stage3 2 = **顺序依赖/状态污染**（单独跑通过）。
- 46 个 EH02/EH01M1/EH01R1/EH01 测试 = **ARTIFACT_REGRESSION_TEST**（读冻结 JSON 验固定数）。
- 结论：570 pass 不是干净全绿；不能仅报"全部测试通过"。

## 8. USER WORKFLOW（PARTIAL）

可操作：启动→选素材扫描→分析→填卖点+文案→制作→output/projects 下拿 MP4+剪映草稿+报告→
审核窗。**无"输入脚本自动拆镜"层**；多数素材 unclassified 需先分析。非程序员运营者今天
能完成"扫描→填文案→出 MP4/草稿"（依赖素材已分析且有合格匹配）。

## 9. GAP MAP

- **P0(PRODUCT)**：①脚本→Beat 拆分层缺失(D2 NOT_FOUND) ②Source-gate 未接入生产 matching
  ③历史素材路径失效需重扫
- **P1(PRODUCT)**：segment 级选择/旧字幕处理/BGM 曲库/人工替换回流未验证
- **P2(PRODUCT)**：voice clone/团队权限备份/双库身份
- **RESEARCH(不阻 MVP)**：CAM/EH/GEOM/动作理解/AutoPublish/自动学习
- **明确区分**：P0-P2 是 PRODUCT blocker；CAM/EH 是 LOCAL RESEARCH blocker——**不得阻塞
  Track A MVP**。

## 10. TWO-TRACK + SHORTEST MVP

- **TRACK A SEMI-AUTO MVP**：可并行推进——复用已 E2E 的检索/渲染/TTS/字幕/BGM/草稿链 +
  **新建脚本→Beat 拆分层** + 人工确认门 + 当前源盘重扫。9:16/25-35s/单岛台模板/3 候选/
  人工终审/禁自动发布。
- **TRACK B FULL-AUTO R&D**：N0/N1/NEG/Router/GEOM/动作理解保持 shadow；不自动成为 A 前置。
- **最短路径 blockers**：D2 脚本拆层（must_build）· source-gate 接入（must_connect）·
  素材重扫（must_fix 数据）。can_defer：voice clone/team ops/BGM 库。

## 11. 输出文件

docs/：本报告（TREECUT_MASTER_PRODUCT_GOAL_ALIGNMENT_AUDIT_A0.md）
reports/storage/：PRE_RUN_BASELINE · CURRENT_ARCHITECTURE_MAP · DATA_IDENTITY_MAP ·
PRODUCT_CAPABILITY_MATRIX · END_TO_END_TRACE · TEST_TRUTH_AUDIT · USER_USABLE_WORKFLOW ·
PRODUCT_GAP_MAP · TWO_TRACK_ROADMAP · RISK_REGISTER · EVIDENCE_INDEX · RESULT（12 JSON）
scripts/audit_treecut_product_a0*.py · tests/test_audit_treecut_product_a0.py

## 12. 报告/源码重大矛盾（供架构师复核）

- README 声称"47 项自动测试全部通过" vs 当前 586 项含 12 fail（README 数字 stale）
- README 声称运行时在 G 盘 vs 实际安装 E:\（stale）
- CAM 库 asset/segment 大量数据 vs 生产链整文件 clip——两套语义并存未互连
- EH02 报告说 STRONG 8 是 reference 证据 vs 可能被误读为动作能力——A0 明确为 shadow
