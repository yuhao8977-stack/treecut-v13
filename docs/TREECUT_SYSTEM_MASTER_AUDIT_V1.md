# TreeCut 全项目级系统审计报告

# TREECUT_SYSTEM_MASTER_AUDIT_V1

> 性质：PROJECT-WIDE SYSTEM AUDIT & ARCHITECTURE / FUNCTION / UI / PRODUCTION READINESS VALIDATION
> 审计对象：TreeCut 内容生产系统（当前主线 = KUBON B007 岛台业务）
> 基线：commit `11887df`（branch `main`）工作树；审计日 2026-09-03
> 语言：中文为主（证据/代码标识保留原文）
> 原则：READ-FIRST / EVIDENCE-BASED / **NO FALSE PASS**；"代码存在 ≠ 功能可用"

## 0. 第一屏裁决（请先读这里）

| 问题 | 裁决 | 依据摘要 |
| --- | --- | --- |
| TreeCut 当前是什么？ | 半自动内容生产 OS（素材 Truth→理解→检索→选镜→渲染→QA→人工 L3），**主线只服务 B007 岛台**，处于 Stage8 硬化期 | §02/§03 |
| 能产出技术合格 MP4？ | 能（已有真实产物，技术 QA 通过），但仅限脚本/素材齐备的受控样例 | §07/§21 |
| 能产出"可发布"成片？ | **不能自动**：V1 人工 REJECT、V2 READY_WITH_LIMITATIONS→NEEDS_REPAIR；无 BGM 库、Voice 未达生产级、内容 QA 未闭环 | §03/§18-21 |
| 能日常生产（运营人员每天用）？ | **不能**：无端到端编排、MMVV/候选/视觉匹配未达生产可用、需开发者介入 | §31/§35 |
| 非开发者能独立使用？ | 不能；无账号/项目管理入口、无渲染按钮、需要看 JSON/报告 | §22/§28 |
| 视觉匹配（Claim→Visual）可靠？ | 不可靠：G3 仍 NEEDS_REPAIR、真实命中率未过人工阈、候选缺失时无源可用 | §14/§15/§17 |
| MMVV 可 Enforcement？ | **不能**：SHADOW-only；R2 语义 ROI 泄漏未解决，Known6 全 UNSURE/FAIL 保守，无假 PASS | §13/§18 |
| UI 生产就绪？ | 否：工作台可看/可换镜/可 trim（BROKEN 部分见 §22），但缺生产入口与异常处理验证 | §22/§23 |
| Voice 生产就绪？ | 否：SAPI=降级（QA 会拦）、克隆=READY_FOR_INPUT（无样本/consent） | §19 |
| BGM 生产就绪？ | 否：LIBRARY_NOT_READY；字段存在 ≠ 可混音 | §20 |
| AutoPublish 就绪？ | 否（且被禁止作为当前目标） | §05 |
| 最大 P0 | Truth/数据碎片与"多套并行系统"漂移风险 + 无端到端编排 + 素材缺失（动作候选 0 PASS） | §32/§42 |
| 最大 P1 | G2/G3 真实候选召回=0 → 整条生产链无有效动作素材输入 | §15/§44 |
| Top 5 Blockers | ①动作素材真实候选缺失（拍摄/核验）②MMVV 语义 ROI ③Voice 参考音 ④BGM 授权库 ⑤端到端编排与 UI 生产入口 | §44 |
| Top 10 下一步 | §49/§50 | — |

（本表为"结论速览"，详细证据见对应章节；所有 PASS 均按 §1 词表重新核实，不沿用旧报告。）

# 01 执行方法与证据纪律

## 1.1 审计模式
MODE: AUDIT + VALIDATION + PACKAGING + DOCUMENTATION。
本审计**不改变任何产品逻辑**；仅新增审计证据/文档产物与安全 Git snapshot。
禁止（审计期间未执行）：Pilot V3 / Stage9 / AutoPublish / Voice·BGM 正式生产 / Qwen 训练 / 第二视觉模型 / 大规模重构 / DB 破坏性迁移。

## 1.2 证据优先级（Source of Truth）
1. 当前源代码（含调用链 file:line）
2. 当前数据库 schema/数据（materials.db 只读）
3. 当前自动化测试（全量回归）
4. 当前 runtime evidence（导入冒烟、真实媒体产物、帧证据）
5. 当前人工 L3 / adjudication（DB + reports/storage）
6. 报告文档（docs/）——**旧报告不能反向覆盖代码事实**

## 1.3 状态词表（每功能必须归入，允许组合，禁止"基本支持/应该可以/看起来能用"）
NOT_FOUND / STUB / LEGACY / EXPERIMENTAL / IMPLEMENTED / INTEGRATED / TESTED_SYNTHETIC /
TESTED_REAL_DATA / HUMAN_VALIDATED / SHADOW_ONLY / PRODUCTION_READY / PARTIAL / BROKEN / DEPRECATED / UNMERGED / UNKNOWN

## 1.4 六层验证（Code Existence ≠ Usability）
LEVEL 1 CODE_EXISTS → LEVEL 2 IMPORTS_OR_STARTS → LEVEL 3 MAIN_CHAIN_INTEGRATED →
LEVEL 4 AUTOMATED_TESTED → LEVEL 5 REAL_DATA_EXECUTED → LEVEL 6 HUMAN/PRODUCTION_VALIDATED。
报告中任何"可用/PASS"结论必须注明达到的最高层；只到 L1/L2 的功能一律按"存在/可导入，未接通"表述。

## 1.5 设计质量词表（每个关键设计必须给一个并说明为什么）
FIT_FOR_PURPOSE / ACCEPTABLE_BUT_NOT_OPTIMAL / NEEDS_REFACTOR / NEEDS_REDESIGN / EXPERIMENTAL / INSUFFICIENT_EVIDENCE

## 1.6 严重度
P0 = 会生成错误真值/错误成片/数据污染/安全问题；P1 = 严重影响生产质量/可用性；
P2 = 明显影响效率或体验；P3 = 优化项。

## 1.7 本审计实际执行的动作（可复核）
- 只读探测：git 状态/历史/remote/tag；跟踪文件 1196 个共 69.3MB（`_repo_stats.json`）；
- DB 只读探测：88 表 / 2,158,918 行 / WAL / user_version=3（`_db_counts.json`）；
- 导入冒烟：runtime python 3.12.13 下 18 个核心模块 + pyJianYingDraft/sherpa_onnx/torch/onnxruntime/faster_whisper/cv2/tkinter 全部 OK（`ev_layerA_imports.json`）；
- 并行 8 路证据采集（功能清单/联通性/DB/UI/测试/密钥存储/文档遗留/模块深度事实）→ `reports/storage/audit_evidence/ev_*.json`；
- 全量 pytest 回归（见 §30/ev_tests.json）；
- 真实媒体产物核验（Pilot V2 mp4/wav/srt/ass、human review 包、mmv 帧证据）；
- 密钥/大文件扫描后才 commit+push（见 §27/§28/§35）。

# 02 TreeCut 是什么 / 目标 / 范围 / 用户

## 2.1 一句话定位
TreeCut 是一套面向"**素材 Truth → 内容理解 → 检索 → 选镜 → 自动成片 → QA → 人工 L3 → 发布**"的**半自动视频内容生产 OS**；
当前唯一正式生产对象是 **KUBON 岛台（B007）业务**；正处于 Stage8（Production Quality Hardening）阶段，主线目标为 **TreeCut Production V1：topic/script 进，3 条候选成片出，人工最终审核**（Roadmap §5 冻结文本）。

## 2.2 面向谁（当前事实，非设想）
| 使用者 | 现状 |
| --- | --- |
| 开发者（本机） | 实际唯一使用者：跑脚本/服务/测试、读 JSON/HTML 报告、做裁决 |
| 运营人员 | **不是**当前使用者：无账号/项目管理入口、无一键生产 UI、需看 JSON（见 §22） |
| 剪辑人员 | 未接入（无时间线编辑 UI 概念之外的产物；workbench 仅能局部换镜/trim JSON 项目） |
| 管理者 | 只能通过报告/HTML 审阅包（L3 人工审核流已可用） |

## 2.3 业务支持程度（诚实分级）
| 业务 | 程度 |
| --- | --- |
| B007 岛台（小红书） | Truth 层最完整：Creator/Spotlight/Paid 双源事实、L3 审核、G1 生产源门、Pilot V1/V2 真实成片；**内容质量仍未达可发布** |
| 小红书平台能力 | 只读/结构化事实侧（发布清单、媒体恢复、浏览器基础）已有多轮证据；**AutoPublish 被禁止** |
| 其他账号/其他行业 | OUT-OF-SCOPE（无样本、无模板、无数据） |

## 2.4 PROJECT MISSION / CURRENT SCOPE / OUT-OF-SCOPE（冻结，Roadmap §5/§7）
- MISSION：Production V1 = script→3 候选成片→人工最终审核→发布；**禁止 AutoPublish 作为目标；禁止"人工逐槽位选镜"为最终常态**。
- CURRENT SCOPE：B007 岛台；Stage0–8 主线；素材 1/2/4 源（X1 素材盘）与 E 运行时、Z 备份盘。
- OUT-OF-SCOPE：Stage9 模板扩张（Stage8 PASS 前禁止）、大规模账号扩样本、大型模型替换、无关 UI 重构。

## 2.5 关键架构事实：存在**两套并行生产体系**（本审计最重要的结构发现之一）
代码实际分裂为两个"生产世界"，命名上都叫"production"：

**Layer A —— classic TreeCut（v12 时代延续，desktop 入口）**
- 位置：`src/treecut/application/production.py`、`src/treecut/cognitive/production.py`、`src/treecut/output/{mp4.py,jianying.py,narration.py,production_narration.py}`、`src/treecut/roughcut/`、`src/treecut/desktop.py`、`src/treecut/ui/*`、`src/treecut/models/tts_sapi.py`、`src/treecut/quality/inspection.py`
- 能力：扫描→OCR/ASR→资产/片段→认知生产（真实 TTS/SRT、MP4 渲染、剪映草稿 pyJianYingDraft）→质量检查。
- 证据：output/jianying.py L97-105 **真实 import pyJianYingDraft**；runtime 导入冒烟全 OK（`ev_layerA_imports.json`：pyJianYingDraft/sherpa_onnx/torch/tkinter 等 8 个三方库全部可导入）。desktop.py + tkinter UI 存在（导入 OK）。
- 使用证据：**无近期成片产物出自该链的证据**（最近真实成片出自 Layer B 脚本 b007_v091_v2）；cognitive/production.py 自带"认知链路无 TTS/选曲时跳过剪映草稿"的降级逻辑（L341/400）。

**Layer B —— B007/STAGE8 生产质量层（当前主线，无统一入口，由 scripts/ 编排）**
- 位置：`src/treecut/services/{production_source,action_subclip,claim_visual,visual_beat,visual_understanding_v2,mmvl_master_v1,production_dedup,production_qa}.py` + `scripts/sprintv2_*.py` + `tools/production_workbench/` + `reports/storage/*_V1.json`。
- 能力：G1 生产源资格门、G2 动作窗口、G3 Claim→Visual、V2 引擎、Discovery、MMVV(SHADOW)、Dedup、QA；**全部由一次性 runner 脚本驱动，无服务编排器、无统一 CLI**（见 §06/§18）。
- 真实成片：`scripts/b007_v091_v2.py`（monolithic 脚本，硬编码 SCRIPT/BEAT_PLAN，**未调用 G1/Claim/MMVV**）产出 `B007_FIRST_REAL_PILOT_V2.mp4`（21.9MB 已核验存在）。

**两层的接缝**：Layer A 的 output/production_narration.py（TTS/SRT/ASS）被 Layer B 的 b007_v091_v2 脚本复用；除此之外 Stage8 services 与 classic 生产链**没有互相调用**。G1(ProductionSource) 管的是"哪个素材可进生产"，但 V2 pilot 的取材走的是**旧 pick_clean 式关键词 SQL**（source_id∈(1,2)+LIKE+.mp4，见 b007_v091_v2.py L46-52）——**存在未接 G1 的历史取材路径**（详见 §16/§21）。
设计判定：`ACCEPTABLE_BUT_NOT_OPTIMAL`（两套体系各自有存在理由：classic=历史桌面产品线；B 层=面向内容质量的生产质量层；但"无统一编排+双命名空间 production"是主要架构债，见 §32）。

# 03 当前真实状态（逐项按代码/DB/产物重新核实，不沿用旧 PASS）

## 3.1 官方主线仪表盘（Roadmap V1 §2 冻结，本次核验）
| 主线 | 官方状态 | 本次核验结论 | 核验依据 |
| --- | --- | --- | --- |
| Stage0 Architecture | PASS | 成立（Git/DB/Truth/存储治理存在；但有碎片，见 §08/§29） | 源码+DB |
| Stage1 Asset | PASS | 成立（canonical asset/media 身份） | DB: assets 22,466 / media_files 28,252 |
| Stage2 Segment | 基础 PASS | 成立；动作切点未达 80–120 段/20 段校准目标（G2 拦） | PROJECT_STATE g2.calibration_met=false |
| Stage3 ASR/OCR/Type | 基础 PASS | ASR/OCR 成熟（b007_asr_v1 866/ocr 2980、transcripts 51,543/ocr_text 289,218）；raw/finished 分类已由 G1 补强 | DB+§16 |
| Stage4 Semantic Labels | 持续校准 | 存在多代（business_cognition v1/v2/v2_1、human_annotation v2/v3、canonical_human_truth 360 行） | DB+services_inv |
| Stage5 Dedup | PROVISIONAL_PASS_AFTER_TUNING | 成立（Exact SHA 成熟；叙事近重 WARNING） | production_dedup.py+测试 |
| Stage6 Retrieval | 自动召回可用 | 部分成立：B007 事实检索成熟；**视觉动作检索 = 0 PASS**（G2/G3 主阻塞） | §14/§15 |
| Stage7 Template | 未过真实成片验证 | 成立（无真实成片验证） | — |
| **Stage8 Production** | **当前主战场** | 未 PASS（需 4/5 BASICALLY_PUBLISHABLE；Pilot V1 REJECT / V2 READY_WITH_LIMITATIONS→NEEDS_REPAIR） | §21 |
| Stage9 | 禁止 | 未动 | — |
| Stage10 | 未开始 | 未动 | — |

## 3.2 STAGE8 Gates 逐门现状（按最新裁决/代码，非旧报告）
| Gate | 官方/裁决状态 | 本次证据核验 |
| --- | --- | --- |
| G1 Production Source | **PASS（冻结 idx63 后）** | production_source.py 存在+测试 test_g1_source_gate 11 条；L3 回填 30/14/1；strict pool machine 13,617 / post-L3 13,642（DB b007_source_role_v1 28,282 行，见 ev_db_dist）；**但历史 V2 pilot 取材未走此门**（§21） |
| G2 Action/Subclip | **NEEDS_REPAIR**（动态人审裁决；BLOCKED_BY_CANDIDATE_RECALL_VALIDATION） | action_subclip.py 存在；Discovery 脚本真实调用 build_windows/apply_action_gate（scripts grep）；**全量动作候选 0 PASS**（tvrc_pass=0，v11 final_top3=[]）；132 帧 L2 证据；20 段校准目标未达 |
| G3 Claim→Visual/Story | **NEEDS_REPAIR**（BLOCKED_BY_G2_VALID_ACTION_SOURCE） | claim_visual.py 存在+8 测试；真实有效动作源缺失 → 无法验证 |
| G4 Audio/Caption/BGM/AV | 部分（G4_VOICE_BGM=VOICE_READY_FOR_INPUT_BGM_LIBRARY_NOT_READY） | V2 技术 AV 硬闸 OK（±0.10s、count_frames）；BGM 无库；字幕硬烧已证（ASS+qwen 验证） |
| G5 Production QA | PROVISIONAL_PASS | production_qa.py 15 项 check+P0 门禁存在；test_g5_dedup_qa 10 条；UI local_reqa 仅为 LOCAL_RULE（§21/§22） |
| G6 Pilot Validation | NOT_STARTED（Pilot V1/V2 未过 4/5） | — |
| DEDUP | PROVISIONAL_PASS_AFTER_TUNING（R7） | detect_duplicates 存在；narrative WARNING 机制 |
| MMVV | **SHADOW**；R2=KNOWN_CASE_NEEDS_REPAIR | 见 §13/§18 专项 |

## 3.3 MMVV 现状（冻结口径，写入本报告）
- 模块存在且自洽（mmvl_master_v1.py，38 类/函数，含 ShadowGate；`MMVVMode` 默认 **SHADOW**，L1096）。
- src/ 内**零调用者**（grep 仅模块自身）→ 只被 `sprintv2_mmv_run.py / sprintv2_mmv_r2.py` 与测试调用 → **SHADOW_ONLY**。
- Known6（89/52/109/51/1985/1986）：V1 = FAIL/UNSURE/FAIL/UNSURE/UNSURE/UNSURE；R2 = **全部 UNSURE**（heuristic ROI + 运动簇归属仍不足；**无假 PASS**，但也**无 PASS**）。
- 官方口径：**MMVV 不能称 Production Ready；Enforcement 未获批准**；语义 ROI 获取（qwen bbox 不可信）未解决。

## 3.4 状态文档一致性问题（审计发现）
- `reports/storage/TREECUT_PROJECT_STATE_V1.json`：`updated_at` 混合（部分块停在 2026-09-03 13:15/早间，mmv r2 块到 18:04）；顶层 `stage8_gates.sprint_v2` 仍写 DEDUP=PASS/G2 ENGINEERING_PENDING（已被后续裁决覆盖为 NEEDS_REPAIR / PROVISIONAL_PASS_AFTER_TUNING）→ **该文件是 STALE/CONFLICTING 的混合体，不可作为唯一状态源**。
- 本 MASTER AUDIT 将成为新的 CANONICAL 状态入口（§28/§54）。

## 3.5 真实运行/产物证据（本次核验存在）
- `E:\...\runtime\production_smoke\B007\pilot_v2\`：B007_FIRST_REAL_PILOT_V2.mp4(21.9MB)/av_v2/video_v2/narration_1x3.wav/narration_mix.wav/narration_v2.srt/narration_v2.ass — 真实成片+中间产物。
- `reports/storage/human_review_package/`：G2/G3/DEDUP/CROSSSEG ChatGPT 审核 mp4+json（**mp4 已 gitignore，不入库**）。
- `reports/storage/mmv_frames/`：Known6 帧证据（m51/m52/m109/m1985/m1986…）。
- 关键诚实性记录：V2 的语义 QA 标志（CLAIM_SUPPORTED 等 4 项）是**脚本硬编码 True**（b007_v091_v2.py L223-226），非匹配器推导 → V2 的 READY_WITH_LIMITATIONS 只代表**技术/容器级 QA 通过 + 语义假设**。

# 04 完整功能清单（TREECUT_FUNCTION_INVENTORY 摘要）

状态词组合缩写约定：IMP=IMPLEMENTED, INTG=INTEGRATED, TEST_S=TESTED_SYNTHETIC, TEST_R=TESTED_REAL_DATA, HUM=HUMAN_VALIDATED, SHADOW=SHADOW_ONLY, PROD=PRODUCTION_READY, PART=PARTIAL, BRK=BROKEN, LEG=LEGACY, DEP=DEPRECATED, EXP=EXPERIMENTAL, UNM=UNMERGED。
证据级 L1=代码存在 / L2=可导入启动 / L3=主链接通 / L4=自动测试 / L5=真实数据跑过 / L6=人工验证过。
设计词：FFP=FIT_FOR_PURPOSE / ABNO=ACCEPTABLE_BUT_NOT_OPTIMAL / REF=NEEDS_REFACTOR / RED=NEEDS_REDESIGN / EXP=EXPERIMENTAL / IE=INSUFFICIENT_EVIDENCE。
完整字段版（Purpose/Entry/Input/Output/Deps/Called by/Calls/UI/Tests/证据/限制/生产影响）见 `TREECUT_CODE_MANIFEST_V1.json` 与 `ev_*.json`；本节为可读摘要表（★=本审计直接核验；[GAP]=部分依赖上轮记录证据）。

## 4.1 素材/Truth/扫描层（Layer A classic 主体）
| 功能 | 主要文件 | DB | 状态 | L | 设计 |
| --- | --- | --- | --- | --- | --- |
| 素材扫描/媒体注册 | src/treecut/scanner/*, media 相关 | media_files 28,252 / sources 5 | IMP+TEST_R★ | 5 | FFP |
| 去重(Exact SHA) | services? (identity.py/shot_usage.py) + b007 源 | media_files | IMP+TEST_R | 4-5 | ABNO |
| OCR | src/treecut/ocr/* | ocr_text 289,218 / b007_ocr_v1 2,980 / fts_ocr | IMP+TEST_R★ | 5 | FFP |
| ASR | src/treecut/asr/* (faster-whisper) | transcripts 51,543 / b007_asr_v1 866 / fts_transcript | IMP+TEST_R★ | 5 | FFP |
| Keyframe | src/treecut/keyframes/* | keyframes 125,199 / b007_keyframe_v1 608 | IMP+TEST_R★ | 5 | FFP |
| Segment | src/treecut/scenes?/services/identity | segments 41,834 / b007_segment_v1 609 | IMP+TEST_R★ | 5 | FFP |
| Asset/AssetType | services/identity.py, classifier | assets 22,466 / asset_types 22,465 / content_value | IMP+TEST_R | 4-5 | FFP |

## 4.2 认知/AI 层
| 功能 | 主要文件 | DB/产物 | 状态 | L | 设计 |
| --- | --- | --- | --- | --- | --- |
| Visual Cognition(旧) | services/visual_cognition.py | semantic_annotations 300 | LEG+TEST_R | 5 | DEP→被 V2/MMVV 取代 |
| Static Vision V2 / People V2 / Semantic Action V1/V2 / Temporal V2 | services/static_vision_v2, people_analyzer_v2, semantic_action_v1/v2, temporal_action_v2 | 历史验证集 | LEG_REUSABLE/EXPERIMENTAL | 4-5 | ABNO |
| Business Cognition v1/v2/v2_1 + DNA | services/business_cognition_* | b007_business_cognition_v1 609 / account_dna 1 / canonical_human_truth 360 | IMP+TEST_R+HUM | 5-6 | ABNO(三代并存) |
| Knowledge 服务 | services/knowledge_service.py, knowledge/* | knowledge_entries 39 | IMP | 3-4 | ABNO |
| Qwen2.5VL(7B, ollama) | sprintv2_* 脚本直接 http://localhost:11434 | L2 证据帧 | IMP(调用方在脚本)+TEST_R | 5 | ABNO(单 worker/需串行) |
| Embedding/CLIP/BGE | 记录：memory 与 api.py 提及；models/* | — | LEG/UNMERGED？ [GAP] | 1-2 | IE |

## 4.3 B007 事实/业务层
| 功能 | 主要文件 | DB | 状态 | L | 设计 |
| --- | --- | --- | --- | --- | --- |
| Creator Sync | services/b007_creator_adapter.py | b007_media_asset_v1 30 | IMP+TEST_R | 5 | FFP |
| Spotlight Sync/Calibration | scripts/b007_spotlight*.py | spotlight_*_v1 | IMP+TEST_R+HUM | 5-6 | FFP |
| Paid Facts/Dual Source | scripts + services | b007_note_dual_source_fact_v1 2,851 / paid 5,193/4,625 | IMP+HUM | 6 | FFP |
| Media Recovery | scripts/b007_v06* | b007_published_media_recovery_v1 30 | IMP+HUM | 5-6 | FFP |
| Sample Selection | scripts/b007_v05* | — | IMP+记录 | 5 | FFP |
| Browser Automation(XHS) | src/treecut/browser/*, xhs work browser | cookies 不入库 | PART(基础可用) | 4-5 | ABNO/EXPERIMENTAL |
| Human L3 / 审核 | canonical_human_truth(+history), b007_l3_review16_v1, phase3_review_ui, second_review_ui | 360+393+16 | IMP+HUM★ | 6 | FFP |
| 发布清单/许可审计 | scripts (发布清单) | published_content_v1 3,465 | IMP(清单层) | 5 | FFP；**AutoPublish 禁止** |

## 4.4 STAGE8 生产质量层（Layer B）
| 功能 | 主要文件 | 状态 | L | 设计 |
| --- | --- | --- | --- | --- |
| G1 Production Source Gate | services/production_source.py | IMP+TEST_R+HUM(G1 PASS)★ | 5-6 | FFP（但旧取材路径未接，见 §16） |
| G2 Action Understanding/Subclip | services/action_subclip.py | IMP+TEST_S+TEST_R(132帧) | 4-5 | ABNO（阈值启发式，语义定义未固化） |
| G3 Claim→Visual/Story | services/claim_visual.py + visual_beat.py | IMP+TEST_S | 4 | ABNO→REF |
| Visual Understanding V2 引擎 | services/visual_understanding_v2.py | IMP+TEST_S(10/10) | 4 | EXP（架构师验证中） |
| MMVV | services/mmvl_master_v1.py | IMP+TEST_R(SHADOW)★ | 5 | **EXP/RED（ROI 语义获取需重设计或人工首帧）** |
| Candidate Discovery V1.1 | scripts/sprintv2_disc_*, v11_* | IMP+TEST_R(真实运行，0 PASS)★ | 5 | EXP（漏斗有效但 Recall 未证） |
| Cross-Segment Recovery | scripts/sprintv2_v11_rr_xs.py 等 | IMP+TEST_R(4 条 motion 候选) | 5 | EXP→HUM_VALIDATED_USEFUL（记录） |
| Dedup(R7) | services/production_dedup.py | IMP+TEST_S★ | 4 | ABNO→FFP |
| Production QA(G5) | services/production_qa.py | IMP+TEST_S★ | 4 | ABNO（规则为主；语义项仍靠假设） |

## 4.5 生产/输出层
| 功能 | 主要文件 | 状态 | L | 设计 |
| --- | --- | --- | --- | --- |
| Script→Beat→Claim 解析 | claim_visual.parse_script_to_claims + visual_beat.group_visual_beats | IMP+TEST_S | 4 | FFP(方向对) |
| 候选/Subclip 选择 | action_subclip + Discovery 脚本 | PART（0 PASS 阻塞） | 5 | — |
| Narration/TTS(SAPI/sherpa) | output/production_narration.py + models/tts_sapi.py | IMP+TEST_R(V2 用过) | 5 | ABNO（SAPI=降级；无生产级人声） |
| Subtitle/ASS 硬烧 | output/narration.build_srt + b007_v091_v2.build_ass | IMP+TEST_R(qwen 验证)★ | 5 | FFP |
| BGM | config DEFAULTS + QA 检查 | **NOT_FOUND(库)/字段存在** | 1-2 | — |
| MP4 Renderer | output/mp4.py / output/narration.py / b007_v091_v2(自写 ffmpeg) | IMP+TEST_R★ | 5 | REF（至少 3 套渲染实现并存） |
| 剪映草稿 | output/jianying.py (pyJianYingDraft) | IMP(可导入)★；L3 接通=LEG（认知链可跳过）；无近期真实产物 | 2-3 | IE（从未在审计期验证过真实 draft 产物） |
| Timeline/音频优先 | b007_v091_v2.py | IMP+TEST_R(仅该脚本) | 5 | REF（逻辑埋在 monolithic 脚本） |
| Production QA 门禁 | production_qa.py + b007 QA 块 | IMP+TEST_S | 4 | ABNO |
| Workbench UI | tools/production_workbench/server.py+index.html | IMP(可用)+PART★ | 4-5 | ABNO（局部可用） |
| Review UI(L3) | phase3_review_ui/second_review_ui/segment_cognition_ui + HTML 包 | IMP+HUM★ | 6 | FFP |
| Checkpoint/Resume | 记录：任务表(task_store? analysis_tasks 31,106) | PART [GAP] | 2-4 | IE |
| 日志 | 记录（未见统一 logging 框架审计） | IMP(零散) | 2 | IE |
| Storage Health/Git Backup | scripts? + 本审计 | PART（人工脚本化） | 2-3 | IE |

## 4.6 明确 NOT_FOUND / STUB（用户清单逐项）
| 清单项 | 结论 |
| --- | --- |
| AutoPublish / Publishing | NOT_FOUND（禁止目标；只到"发布清单/许可审计"层） |
| Voice Clone | STUB/READY_FOR_INPUT（config：无样本+consent → VOICE_INPUT_REQUIRED；无引擎） |
| BGM 曲库/自动选曲/混音 | NOT_FOUND（无授权库；QA 只检测 absent） |
| Script Generation(自动写脚本) | NOT_FOUND（脚本由人提供，硬编码于脚本） |
| Checkpoint 框架（统一） | PARTIAL/分散（无统一框架证据） |
| 统一 CLI/编排入口 | NOT_FOUND（见 §06） |
| 真 Embedding/向量检索(生产内) | 记录层有 CLIP/BGE 提及；当前主链检索=关键词+廉价排序，向量未接通 [GAP] |

## 4.7 遗留/重复候选（详见 §29）
visual_cognition/static_vision_v2/semantic_action_v1/v2/temporal_action_v2 多代视觉；business_cognition v1/v2/v2_1；conflict_resolver vs _v2；evidence_resolver vs evidence_strength_v2；canonical_truth vs schema_v2；phase3_review_ui/second_review_ui/review_center；Layer A vs Layer B 双 production；scripts/ 296 个（多数一次性）。

# 05 系统架构与模块联通

## 5.1 分层架构（文字图）
```
[UI 层]  desktop.py(tkinter, LayerA)  |  tools/production_workbench(Web 8899)  |  review HTML(phase3/second/segment_cognition + 审阅包)  |  docs/reports 审阅
[Human L3]  canonical_human_truth / b007_l3_review16 / adjudication JSON → DB review_status(APPROVED/REJECTED/REVIEW_REQUIRED)
[Production Layer B]  production_source(G1) → action_subclip(G2) → claim_visual+visual_beat(G3/V2) → production_dedup → production_qa(G5)
                       ↑ 由 scripts/sprintv2_*.py 编排（无服务编排器）；MMVV(ShadowGate, SHADOW) 仅脚本/测试调用
[Production Layer A(legacy)]  application/production.py → cognitive/production.py → output/{mp4,narration,production_narration,jianying}.py → quality/inspection.py
[Search/Retrieval]  fts_ocr/fts_transcript(SQLite FTS5) + keywords/cheap-rank(scripts)  [向量检索：未接通]
[AI/Cognition]  qwen2.5vl:7b(ollama localhost:11434)  faster-whisper(ASR)  OCR(本地引擎)  sherpa-onnx/VITS?  pyJianYingDraft(草稿)  torch/cv2 静态视觉(历史)
[L1 Truth]  media_files/assets/segments/keyframes/ocr_text/transcripts + b007_*_v1 + ffprobe/hash/OCR 原文
[Browser]  src/treecut/browser/* (XHS) — 只读采集/恢复；不参与成片
[Persistence]  SQLite materials.db(WAL, 88 表, user_version=3) + reports/storage JSON + runtime_data
[Storage]  C(系统/临时) E(runtime/DB/工作) G(?) Z(备份/原始 12TB) X1(素材盘 \\X1\素材盘01)
[Source/Capture]  X1 S1(卖点展示)/S2(效果展示)/S4(工厂未处理) + B007 双源事实(Creator/Spotlight/Paid)
```
设计判定：LAYERING 合理（Truth/认知/生产/人审分层清晰），但**执行层混乱**：生产编排散落在 296 个 scripts + 2 套 production 命名空间；连接靠"人记得跑哪个脚本"，无依赖图。整体 `ABNO`（方向 FFP，落地 REF）。

## 5.2 MODULE_CONNECTION_MATRIX（调用链证据）
| 问题 | 结论 | 证据（file:line / grep） |
| --- | --- | --- |
| ProductionSourceService 被谁调用 | **仅 sprintv2_p0.py(单点抽查)+测试**；Discovery/生产脚本**未 import** | grep scripts: is_production_eligible 仅 sprintv2_p0.py L30-32 |
| Discovery 是否真调 ActionSubclip | **是**（v11_probe/v11_rr_xs/v11_verify/discovery/expand_retrieval 均 import parse_qwen_state/build_windows/apply_action_gate/parse_direction/fit_duration） | scripts grep L19/L16/L15/L17… |
| Discovery 是否喂候选给 Claim 匹配 | 脚本级部分（sprintv2_g2_build L10-12 同时 import claim_visual+dedup+qa；g3_dedup_run 用 **eligible_check=lambda True 桩**） | sprintv2_g3_dedup_run.py L57 |
| Visual Understanding V2 是否进 ClaimVisualMatcher | **未直连**：V2=独立引擎(10/10 合成测试)；sprintv2_v2map 只是"映射文档"；无代码把 V2 输出喂给 matcher | sprintv2_v2map.py L8-14(映射)、v2int 用 visual_beat |
| MMVV 是否进 Production | **否**：src 内 0 调用者；仅 sprintv2_mmv_run/r2 + 测试 → SHADOW_ONLY | grep src: mmvl 仅模块自身 L1082-1383 |
| TTS 是否被生产调用 | **是（部分）**：b007_v091_v2 L14/90 用 ProductionNarrationAdapter(SAPI)；cognitive/production L351 真 TTS/SRT | b007_v091_v2 L90-104 |
| BGM 是否可用 | **否**：BGM_PRESENT=False 记录为限制；无库 | b007_v091_v2 L220 |
| QA 是否阻止坏成片 | **部分**：b007_v091_v2 P0_KEYS 硬闸(REPAIR)；production_qa.py 有 P0 门禁；**但语义项=硬编码 True** | b007_v091_v2 L223-231 |
| UI 替换/trim 是否重触发 QA | **部分**：POST /api/replace|trim|reqa → local_reqa(LOCAL_RULE, 无 qwen)；GET /api/qa 返回 PENDING_BUILDER_QA 占位；完整 QA 靠外部 builder | server.py L66-70/L139-154/L161-195 |
| Discovery 候选来自 G1 池？ | ranked 由 DB 查询产出（Eligible 池/REVIEW_REQUIRED 分离），但生产源资格函数本身未被调用（SQL 条件内联） | sprintv2_v11_probe L2-19 + _v11_ranked.json [GAP: 排序脚本 SQL 未全文核] |
| G1 是否被绕过 | **是（历史路径）**：b007_v091_v2.pick_clean 用关键词 SQL，无 G1；b007_g1_source_gate.py 是独立裁决脚本 | b007_v091_v2 L46-52 |

## 5.3 主端到端数据流节点状态（§11）
| 节点 | 状态 | 证据 |
| --- | --- | --- |
| Source Media → media_files | CONNECTED | DB 28,252 / 扫描器 |
| media_files → Asset | CONNECTED | assets 22,466 |
| Asset → Segment | CONNECTED | segments 41,834 |
| Segment → OCR/ASR | CONNECTED | ocr_text/transcripts/fts |
| OCR/ASR → Visual/Qwen | PARTIAL | b007 帧证据 608-866 行；全量无 |
| Visual/Qwen → Production Source(G1) | **BROKEN(未串)**：G1 表与 qwen 证据表无 JOIN 主链 | ev_db_dist [GAP 深度] |
| G1 → Candidate Discovery | PARTIAL(SQL 内联资格) | §5.2 |
| Discovery → Subclip(G2) | CONNECTED(脚本层) | §5.2 |
| Subclip → Claim Visual(G3) | PARTIAL(桩/样本) | g3_dedup_run eligible 桩 |
| Claim Visual → Timeline | **BROKEN**：无编排器；V2 pilot 自建 timeline | b007_v091_v2 L121-143 |
| Timeline → Narration | CONNECTED(脚本内) | L90-104 |
| Narration → Subtitle/ASS | CONNECTED | L109-112/178-183 |
| Subtitle → BGM | **NOT_IMPLEMENTED**(BGM 无) | L220 |
| BGM → Render | — | — |
| Render → QA | CONNECTED(脚本内硬闸) | L194-238 |
| QA → Review | PARTIAL(HTML 审阅包人工) | human_review_package |
| Review → Final Output | PARTIAL(V2 产物存在，人工未最终放行) | Pilot V2 状态 |

## 5.4 B007 当前真实 Production 流（§12）
Truth 层（Creator/Spotlight/Paid/DualFact/L3 16 条）**大部分停留在 DB/报告层**：真正进入成片的只有 b007_v091_v2 脚本的"关键词取材+文件夹语义"。
G1/G2/G3/MMVV 与 Production 的串联 = **未完成**（G2/G3 阻塞、MMVV SHADOW、V2 pilot 未用它们）。
Historical20/Recent12-10 Exact/L3 等是**事实与样本选择输入**，不是成片链节点。结论：B007 "Truth→Production" 的桥尚未建成；当前是"Truth 完备 + 独立脚本样例成片"。

# 06 数据库审计（materials.db）与 Truth 模型审计

## 6.1 总览（本次只读探测）
- 单库 SQLite：`E:\...\runtime_data\temp\batch1\database\materials.db`；**WAL**；user_version=3；**88 表 / 2,158,918 行**（`_db_counts.json`，65s）。
- 迁移：schema_migrations 仅 **0001–0009**（baseline_v13 → fresh_holdout_human_review，全部 Phase0–3 时代）。
- **迁移债（P1 级发现）**：b007_*（14 表）、spotlight_*（6 表）、stage2_*、content_join_status、performance_snapshot、production_plans、shot_usage 等**大量表不在迁移历史内**（scripts 内 CREATE TABLE IF NOT EXISTS 自建）→ schema 演进无统一版本线；同名表语义漂移风险。

## 6.2 表分组与行数（关键）
| 组 | 表（行数） | 说明 |
| --- | --- | --- |
| 核心媒体 Truth | media_files 28,252 / assets 22,466 / asset_types 22,465 / segments 41,834 / keyframes 125,199 | L1 主链 |
| OCR/ASR 原文 | ocr_text 289,218 / transcripts 51,543 / b007_ocr_v1 2,980 / b007_asr_v1 866 / fts_ocr* / fts_transcript* | L1（fts≈23.8 万/5.1 万） |
| B007 生产源资格 | **b007_source_role_v1 28,282** / b007_media_asset_v1 30 / b007_published_media_recovery_v1 30 | G1 主表 |
| B007 认知 | b007_segment_v1 609 / b007_keyframe_v1 608 / b007_visual_evidence_v1 608 / b007_business_cognition_v1 609 | L2 层 |
| B007 事实(双源) | note_dual_source_fact 2,851 / note_month_paid_fact 5,193 / note_paid_association 4,625 / spotlight_note_paid_snapshot 5,694 / spotlight_paid_snapshot 265 | 商业 Truth |
| 人工 L3 | canonical_human_truth 360(+history 393) / b007_l3_review16_v1 16 / human_annotations 300 / human_annotation_v2 60 / v3 34 / fresh_holdout_human_review 60 / segment_boundary_reviews 300 / semantic_annotations 300 / accuracy_test/review 100/100 / targeted_human_review_v1 141 / stage2_* 0-30 | 分散多库（§6.4） |
| 生产/Stage8 落地表 | production_plans 2 / shot_usage 0 / review_queue 0 / duplicate_groups 0 / visual_clusters 0 / asset_quality 0 / asset_status 0 / media_tags 0 | **空表群**：设计存在、未接通（UNMERGED 证据） |
| 任务/处理 | analysis_jobs 23,312 / analysis_tasks 31,106 / processing_history 275,797 / asset_processing_state 224,650 / asset_locations 23,312 / content_value 22,465 | 管线账本 |
| 平台 | published_content_v1 3,465 / spotlight_account 1 / campaign 48 / unit 48 / note_link 4,625 / content_join_status 2,840 | 小红书事实 |

## 6.3 G1 表列级事实（b007_source_role_v1）
- 列：entity_kind/entity_id/source_id/initial_prior/**source_role**/role_basis/role_confidence/**asset_type(全 NULL)**/5×contamination/environment_text_present/contamination_confidence/contamination_evidence/**review_status**/role_version。
- source_role：PRODUCTION_CLEAN_RAW **21,170** / PRODUCTION_CLEAN_SEMI 6,594 / NOT_PRODUCTION_SOURCE 332 / PUBLISHED_REFERENCE 186。
- role_basis：**SOURCE_PRIOR(path/source registry)=28,252（role_confidence 0.5）**；PUBLISHED_MEDIA_ASSET_TABLE=30（confidence 1.0）。
  → **关键 Truth 事实**：所谓"生产资格"的基底是**路径/来源注册表的先验**（文件夹启发式），非逐文件视觉证据；仅 30 条已发布媒体恢复样本有高置信资产表依据。G1 的 A4a"45/45 准入一致"是 L3 抽样核对该先验门，不是全量证据。
- review_status：PENDING 19,466 / REVIEW_REQUIRED 8,696 / APPROVED 118 / REJECTED 2。
  - APPROVED 分解：RAW 23 + SEMI 65 + PUBLISHED_REFERENCE 30 → **仅 118/28,282 有人工批准**；PENDING 占 69% → 生产池大量素材未人审（严格池依赖"5 字段 ABSENT 机器验证"，见下）。
- contamination（以 burned_subtitle 为例）：**ABSENT 13,718 / UNCERTAIN 8,619 / NULL 5,817 / PRESENT 128**；5 字段为枚举字符串（非布尔）。
  → 机器验证"全 ABSENT"池 ≈13,718（扣除角色排除后 = 官方 machine_verified 13,617）；UNCERTAIN 8,619 + NULL 5,817 均不自动准入（严格门，正确方向）。
- **asset_type 列全 NULL**：raw/finished 判定的**列级数据缺失**（Roadmap 曾列 L3_ASSET_TYPE 为债；G1 冻结时 A4a 承认"asset_type 无法从当前 L3 schema 度量"——现进一步确认列空）。

## 6.4 Truth 模型审计（L1/L2/L3 是否真分开）
| 层 | 载体 | 是否分开 | 问题 |
| --- | --- | --- | --- |
| L1 | media_files/assets/segments/ocr_text/transcripts/b007_media_asset(sha256/probe) | ✅ 独立 | 无 |
| L2 | b007_visual_evidence_v1/b007_segment_v1/semantic_annotations/visual_cognition 产物/JSON 帧证据 | ✅ 基本独立 | L2 无统一版本/证据 schema（同帧证据散于 JSON+表） |
| L3 | canonical_human_truth(版本化,truth_version/is_current/supersedes)+review_status 列 | ✅ 独立且有版本线 | **L3 分散在至少 6 张表**（canonical_human_truth / human_annotations / v2 / v3 / b007_l3_review16 / fresh_holdout…）——历史演进未合并 |
| 覆盖风险 | 检查代码是否"把 UNKNOWN 当 false / NO_RECORD 当 0 / 模型候选当人工真值 / Performance 污染 Visual Truth" | 抽样结论 | 语义 QA 硬编码 True（§21）；`eligible_check=lambda True` 桩脚本（§5.2）；PENDING 未准入=严格方向正确 ✅；未见把模型候选直接写 review_status 的代码（本次未全扫，[GAP]） |

设计判定：Truth 分层方向 `FFP`（版本化 canonical_human_truth 设计优秀）；落地 `REF`（L3 多表并存、迁移缺失、asset_type 空列、PENDING 占比高意味着生产池主要靠机器先验）。

## 6.5 其它
- 索引/FK：sqlite 无强制 FK（需 PRAGMA foreign_keys=ON 才有）；索引未逐一核 [GAP]。
- 孤儿风险：asset_types 22,465 ≈ assets 22,466（1:1 可疑，可能存在 assets 无 type 或类型冗余表）；b007_media_asset 30 与 media_files/assets 的 join 未核 [GAP]。
- duplicate_groups/visual_clusters/shot_usage/review_queue 等空表 = "设计好但没接"（§29 归 UNMERGED）。

# 07 AI 模型清单 / 浏览器层 / 素材资产

## 7.1 实际调用模型清单（本次核验）
| 模型 | 版本/位置 | runtime | 调用方 | 真实用过？ | 资源 |
| --- | --- | --- | --- | --- | --- |
| Qwen2.5VL(7B) | ollama localhost:11434（运行中，8/31 起） | Ollama CPU 单 worker | scripts/sprintv2_*（ask()直接 HTTP）、b007_v091_v2.verify_caption_qwen、phase3 review | ✅ 真实（G2 132 帧、Discovery qwen、字幕验证） | 单调用 20–60s；**必须串行**；1080→≤480 缩放防 HTTP400 |
| faster-whisper | runtime 可导入✅ | 本地 | ASR 链 | ✅（transcripts 51,543） | CPU |
| OCR(本地引擎) | runtime | 本地 | ocr 链 | ✅（ocr_text 289,218） | CPU |
| sherpa-onnx | runtime 可导入✅ | 本地 | ProductionNarrationAdapter 首选后端 | 记录：V2 pilot 实际走 SAPI（见下） | CPU |
| Windows SAPI | 系统 | 系统 | tts_sapi.synthesize（降级） | ✅（Pilot V2 真用，1.3x+loudnorm） | 即时 |
| pyJianYingDraft | runtime 可导入✅ | 本地 | output/jianying.py（函数内 import） | **导入 OK；审计期无真实草稿产物证据** | — |
| torch/cv2/onnxruntime | runtime ✅ | — | static_vision_v2/semantic_action_v2/vision_runtime | 历史验证集阶段 | GPU 记录 |
| CLIP/BGE/Embedding | api.py 提及 memory 隔离 | — | — | **未接通主链** [GAP] | — |
| 第二大视觉模型/SAM | 禁止下载 | — | — | — | — |

**Voice Clone**：config/production.py：克隆需样本+consent，无则 VOICE_INPUT_REQUIRED → `READY_FOR_INPUT`，无引擎（STUB）。
**Qwen 训练/LoRA**：禁止，未发生。

## 7.2 浏览器层（XHS）
- src/treecut/browser/* + TREECUT_XHS_WORK_BROWSER_* 报告 + tools/stress_20_rounds_control.py + test_xhs_work_browser_v01.py。
- 用途：只读采集/媒体恢复/发布清单（Creator/Spotlight 事实），**不参与成片**；AutoPublish 禁止。
- 状态：`PARTIAL`（基础链路有测试与文档；真实登录态/会话为本地，不入库/不入 Git——见 §27 密钥审计）。
- 设计：`ABNO`（浏览器自动化复杂度高，当前仅辅助采集角色，与主生产弱相关——可暂缓投入，§50）。

## 7.3 素材资产（Storage/源）
- 源注册：sources 表 5 行；SRC 映射 X1 素材盘 S1 卖点展示/S2 效果展示/S4 工厂未处理（+记录 S3/S5）。
- media_files 28,252（extension 含 .mp4 等；assets.width/height/duration 在 X1 上常为 0 → 运行时 ffprobe——记录于上轮）。
- assets 22,466 vs media_files 28,252：约 5,786 文件未成 asset（发现→资产化不完全，[GAP] 原因未核）。
- 媒体实际存放：X1 素材盘（1/2/4）、E runtime（工作产物 pilot_v2）、G/Z（备份/原始 12TB）；**无媒体入 Git**（§28 全绿）。
- 已知限制：S4 工厂 21,170 = PRODUCTION_CLEAN_RAW 主体（raw 素材大池，多数 PENDING/REVIEW_REQUIRED 无人审）；成片/原片判别列（asset_type）空（§6.3）。

# 08 Visual Understanding / MMVV / Candidate Discovery / G2·G3 / Production Source 深度审计

## 8.1 Visual Understanding（多代并存）
- 旧：services/visual_cognition.py（FrameSampler/StaticVisualCognition/TemporalActionAnalyzer/VisualCognitionPipeline）→ Phase2-3 用，现被 V2/MMVV 思路取代（LEGACY_REUSABLE）。
- Stage2/3 代：static_vision_v2 + people_analyzer_v2 + semantic_action_v1/v2 + temporal_action_v2（torch/cv2）→ 历史 holdout 验证（human_annotation v2/v3 60/34）→ `LEGACY/EXPERIMENTAL`。
- **Visual Understanding V2 引擎**（services/visual_understanding_v2.py，10/10 合成测试）：TemporalActionValidator/IslandClaimLibrary/DomainVisualCritic/VisualBeatGrouper/NoCandidateResolver/DuplicateCritic/ExampleAdjudicationMemory 的"参考实现+映射文档"（sprintv2_v2map.py）；**未直接喂给 ClaimVisualMatcher**（§5.2）→ `INTEGRATED(映射级)+TESTED_SYNTHETIC`，架构师口径"INTEGRATED"指映射已落地到各 services。
- 判定：方向 FFP；落地层 `REF`（同一"视觉理解"概念在 5+ 模块里以不同 API 重复实现）。

## 8.2 MMVV（Multi-Module Visual Validation）
- 组成（mmvl_master_v1.py，38 顶层类/函数）：TruthLayer/Action/Verdict/Support/ROI/FrameSemantics/CameraMotion/CameraMotionEstimator(translation→affine 当残差>0.12)/ROITracker/ROIMotionAttributor/TargetObjectMotionRouter(Tabletop/Drawer/Socket/ObjectTransfer)/TemporalStateValidator(可见→运动→反向缺席→方向→状态转移硬闸)/DomainClaimCritic/EvidenceFusionEngine(mandatory 非投票)/ReviewExampleMemory/ShadowGate/MMVVMode。
- **模式**：MMVVMode 默认 **SHADOW**（L1096）；ShadowGate.apply SHADOW 分支（L1100）；自测试 demo L1383。
- **调用面**：src/ 零调用者 → 仅 sprintv2_mmv_run/r2 + tests → **SHADOW_ONLY，未进任何生产/QA/UI 链**。
- **Known6 现状**（真实媒体帧证据在 reports/storage/mmv_frames）：
  - V1：89=FAIL（人动桌板不动）52=UNSURE（抽屉动）109=FAIL（开着≠打开）51/1985/1986=UNSURE（保守）——无假 PASS。
  - R2（sprintv2_mmv_r2.py：heuristic 人带 ROI + 运动簇归属 + 小簇排除；门覆盖：core<0.045→FAIL）→ **全部 UNSURE**（89 也退回 UNSURE，因语义 ROI 归属不可信）。
  - 期望对照（架构师判）：89/109/51/1985/1986 应 FAIL（或 52 PASS/STRONG_UNSURE）→ **当前 6 例均未达判定目标 = KNOWN_CASE_NEEDS_REPAIR**。
- **R2 阻塞根因**：qwen2.5vl 无法返回可信多对象 bbox（回显名称并集/绝对 bbox_2d/markdown 围栏 → 语义 ROI 获取阻塞）；启发式人带+运动簇归属不足以把"目标物运动"从"人/相机运动"分离；相机补偿残差高（staged translation→affine 仍不足）。
- **选项（架构师待决）**：A) Known6 人工首帧 ROI（HUMAN，快、仅校准用）；B) 轻量检测器（需模型导入批准，当前禁止下载新模型）；C) 维持启发式（现状）。**未获批准前不 Enforcement、不 Blind30-50**。
- 裁决：**MMVV ≠ Production Ready；= SHADOW + KNOWN_CASE_NEEDS_REPAIR**；设计 `EXPERIMENTAL`（ROI 获取需 REDESIGN 或人工辅助，阈值 PROVISIONAL 不调）。

## 8.3 Candidate Discovery（V1.1）
- 流程（脚本层真实）：Eligible topN 廉价排序(_v11_ranked)→运动代理(帧差 top 24/17)→短名单 12→qwen(≤6)→TVRC 门→RR 正规提升→跨段合并 4 条 motion 候选。
- 漏斗结果（PROJECT_STATE v11）：broad_ranked 60/动作、motion_probed 17-24、qwen 6、**tvrc_pass 0（全动作 0 PASS）**、rr_action_verified_pass 0、final_top3=[]、crossseg_merged_motion 4（方向待人工）。
- 样本池：flexible 333/retract(共享)/drawer 888/storage 1200/socket 464（全量廉价排序，去随机 10）。
- REVIEW_REQUIRED 高价值未核：S4 等 7,823-8,696（DB §6.3）；157 高价值待人工（旧记录）。
- **结论**：漏斗**机制成立**（宽召回→廉价排序→运动→qwen→门），但**Recall 未被证明**（0 PASS），material gap = CANDIDATE_NOT_CONFIRMED（未标 CONFIRMED、不补拍——正确纪律）。状态 `TESTED_REAL_DATA + SHADOW/EXP`。

## 8.4 Cross-Segment Recovery
- 动机：canonical segment 切分可能把完整动作切断 → 相邻段合并恢复动作窗口（merged windows）。
- 是否改 canonical segment：**否**（合并只发生在候选层窗口，不改 segments 表）[GAP: 复核]。
- media52 证明：跨界合并能恢复"抽屉/动作"候选（4 条 motion，方向待人工）→ HUMAN_VALIDATED_USEFUL（记录）。
- 是否进主候选管线：脚本级（v11_rr_xs），未进统一服务 → `UNMERGED`（部分）。

## 8.5 G2 Action Understanding / ActionSubclip
- action_subclip.py：parse_qwen_state/parse_qwen_object/build_windows/fit_duration/parse_direction/_DIR_TOKENS/direction_rows/apply_action_gate/ActionSubclipService。
- 机制（记录+抽查）：窗口内 qwen 状态序列→状态转移→方向门（EXTEND/RETRACT 等需方向+≥2 动作帧；OPEN/CLOSE 同窗证据）→反向动作硬闸（OPPOSITE）→静态≠动作；132 帧 L2 证据（pass2/3/4+direction）。
- 现状：Discovery 脚本真实调用（§5.2）；**0 有效 PASS**；校准目标 80–120 段未达（20 段级）→ **G2 = NEEDS_REPAIR / BLOCKED_BY_CANDIDATE_RECALL_VALIDATION**。
- 判定：机制 ABNO（阈值启发式"≥2 帧"是人设约定，非语义定义——记录自人审反馈）。

## 8.6 G3 Claim→Visual / Story
- claim_visual.py：AtomicClaim/parse_script_to_claims（最早词动作匹配）/classify_story_mode/Candidate/ClaimVisualMatcher.rank（硬闸：资格/对象/动作/反向 OPPOSITE_DIRECTION/DOMINANT_VISUAL_MISMATCH/THIN_DRAWER_UNVERIFIED/DUPLICATE_USED…）。
- visual_beat.py：group_visual_beats(R4:16→4-5)/audit_action_availability/suggest_script_fix(OBJECT_ONLY/NO_SOURCE→BLOCK)。
- 现状：合成测试 8 条；真实源缺失 → **G3 = NEEDS_REPAIR / BLOCKED_BY_G2_VALID_ACTION_SOURCE**；无"从真实媒体验证过的 Claim→镜头命中率"。
- 判定：方向 FFP；`REF`（依赖 G2 有效源；故事模式与视觉证据链仍薄）。

## 8.7 Production Source Gate（G1）
- production_source.py：_default_db/ProductionSourceService（替代 pick_clean 临时过滤——docstring 明示）。
- is_production_eligible 语义（来自测试+上轮核验，记 L5）：role∈{PRODUCTION_CLEAN_RAW,PRODUCTION_CLEAN_SEMI}（注：DB 枚举带 PRODUCTION_ 前缀）+ review_status≠REJECTED +（APPROVED 人工 或 5 字段全部 ABSENT）；UNCERTAIN/NULL 不入；strict 池 machine 13,617 / post-L3 13,642（与 DB ABSENT 13,718 扣除角色后一致量级）。
- G1 应用面：裁决脚本 b007_g1_source_gate.py + sprintv2_p0.py 抽查；**Discovery SQL 内联资格、V2 pilot 关键词取材均未调用该 service**（§5.2）→ "G1 门存在于服务层+表，但未成为所有取材路径的唯一闸"。
- 判定：设计 FFP；集成 `PARTIAL`（历史路径未收口）。

## 8.8 MMVV / G2 / G3 关系一句话
G2 提供"哪一段真的发生目标动作"（被 Discovery 阻塞）；G3 用 G2 的有效源回答"这句脚本配哪个镜头"（被 G2 阻塞）；MMVV 是对 G2/G3 结论的**视觉事实复核器**（SHADOW，未接入）；三者共同卡在：**真实动作候选 = 0**。

# 09 生产管线审计：Script/Beat/Claim→成片 / Renderer / TTS·Voice / BGM / QA

## 9.1 从"一句脚本→真实 MP4"当前能力（诚实结论）
- **存在一条受控样例路径**：scripts/b007_v091_v2.py —— 硬编码 SCRIPT/BEAT_PLAN → 关键词取材 → ProductionNarrationAdapter(SAPI 1.3x) → build_srt → 音频优先 timeline → ffmpeg 1080×1920 拼剪 → ASS 硬烧 → stream 级 QA → `B007_FIRST_REAL_PILOT_V2.mp4`（已核验存在 21.9MB）。
- **不是产品化入口**：脚本=开发工具；脚本字段硬编码；**未调用 G1/Claim/MMVV/ProductionSource**；语义 QA 四项硬编码 True（L223-226）；每次换内容需开发者改代码重跑。
- **无统一编排器**：不存在"输入 topic/script → 自动 3 候选"的服务/CLI；296 个 scripts 各自为政。
- 结论：`IMPLEMENTED(样例) + TESTED_REAL_DATA(1 条真实成片) + PARTIAL（不可产品化）`；"能自动从一句脚本出 MP4"= **受控可，通用不可**。

## 9.2 Renderer（谁是真 renderer）
| 实现 | 文件 | 状态 |
| --- | --- | --- |
| LayerA MP4 | output/mp4.py(libx264/crf/preset) | IMP(存在)，近期无产物证据 |
| LayerA mux/mix | output/narration.py(混流/字幕轨/audition) | IMP |
| **B007 实际用** | **b007_v091_v2.py 自写 ffmpeg 链**（concat+scale1080x1920+fps30+libx264 crf19+AAC192k+ASS 烧录+count_frames 精确对齐） | ✅ 真实产物 |
| roughcut | roughcut/engine.py | LEG(粗剪) |
| gpu | gpu_acceptance.py(h264_nvenc) | 验收工具 |
| phase3_review_ui | services/phase3_review_ui.py(ultrafast 预览) | 审核工具 |
| 剪映草稿 | output/jianying.py(pyJianYingDraft) | **可导入✅；无审计期真实产物；认知链可跳过**（L341/400）→ `IMP+LEG`，剪映不是主链 |
结论：主 renderer = **ffmpeg 直渲**（多条自写实现，无统一封装=REF）。

## 9.3 TTS / Voice
- 后端选择（production_narration.py L88-105）：sherpa-onnx（若引擎+模型可用）→ Windows SAPI（离线 zh-CN）→ 失败即报错（不落静音占位）。
- V2 pilot 实际：SAPI → atempo=1.3 → loudnorm I=-15:TP=-1.5 → 48k（b007_v091_v2 L98-104）；输出 narration_1x3.wav/narration_mix.wav 已核验存在。
- QA 视角：production_qa.check_voice_provider：provider=SAPI 且非 production_ready → 标记（SAPI=降级，非主声）。
- **Voice Clone**：config/production.py → VOICE_INPUT_REQUIRED（无样本+consent）；无引擎 → `READY_FOR_INPUT`。
- 结论：TTS 链路 `IMP+TEST_R`；**质量=机械音（SAPI），生产不可接受**（需真人参考音）；sherpa/VITS 模型存在性未在本次核验（[GAP]：runtime\models\LocalTTS 未列目录）。

## 9.4 BGM
- 字段/配置存在（config DEFAULTS BGM required、QA check_bgm、b007 QA "BGM_PRESENT": False）。
- **库=无**（LIBRARY_NOT_READY）；无自动选曲；无混音；QA 只能查"缺失"。
- 结论：**"BGM 字段存在 ≠ BGM 可用"**——符合架构师警示的典型反例；状态 NOT_FOUND(库)/IMP(检查器)。

## 9.5 Production QA
- 服务层 production_qa.py：QAResult + 15 项 check（av_sync/video_tail/caption_rendered/caption_size/voice_provider/bgm/loudness/source_eligibility/no_old_subtitle/no_watermark/claim_supported/action_demonstrated/beat_visual_alignment/story_consistent/dedup）+ verdict + P0 门禁 + ProductionQAService。
- V2 脚本 QA：P0_KEYS（AV_SYNC/VIDEO_DECODABLE/AUDIO_PRESENT/NEW_CAPTION_RENDERED/OLD_SUBTITLE_ABSENT/PLATFORM_WATERMARK_ABSENT）硬闸 → NEEDS_REPAIR vs READY_WITH_LIMITATIONS；字幕渲染用 qwen 视觉验证（verify_caption_qwen 真调用）。
- **V1 教训能否自动检测**：old subtitle ✅（ABSENT 检查+qwen）；watermark ✅（ABSENT）；AV mismatch ✅（count_frames ±0.10）；video ends before audio ✅（video_tail）；subtitle absent ✅（NEW_CAPTION_RENDERED）；claim/visual mismatch ❌（硬编码 True）；duplicate shot ⚠️（去重用但 pilot 未接 dedup 服务）；voice fallback ⚠️（SAPI 有标记，未阻断）；BGM absent ✅（记录限制）。
- UI 层 local_reqa：LOCAL_RULE 仅资格+动作匹配+重复+配置占位（server.py L161-195）；**完整 QA 不在 UI 内执行**。
- 结论：QA 体系 `IMP + PARTIAL`；**技术 QA 可信；语义 QA（claim/action/story/beat 对齐）当前靠脚本假设 → P1 假 PASS 风险**（正是架构师红线）。

## 9.6 Script/Beat/Claim 编解码现状
- parse_script_to_claims（最早词动作匹配）→ group_visual_beats(R4)→ audit_action_availability/suggest_script_fix：链条代码完整、合成测试过；
- **缺口**：候选=0 → beats 无镜可配 → 无候选级联（SEARCH_MORE→REWRITE→DROP/BLOCK）只在脚本/测试存在，未在产品流出现。

# 10 UI 全面审计（Workbench / 审核 UI / Desktop）

## 10.1 UI 清单
| UI | 载体 | 用途 | 状态 |
| --- | --- | --- | --- |
| Production Workbench（主工作台） | tools/production_workbench/server.py + index.html（ThreadingHTTPServer，曾 8899） | 左=Script/Beats/Claims；中=subclip 播放+时间线；右=候选卡/证据/QA；替换镜头/裁剪/重QA | **可用（局部）**；Range 服务 `/file?p=` |
| 审核 UI（L3 系） | services/phase3_review_ui.py / second_review_ui.py / segment_cognition_ui.py | 人工裁决表单（Phase2.5-3 校准/审核）；生成 HTML 审阅包 | ✅ 真用过（L3 回填/裁决） |
| 审阅包 HTML | reports/storage/*REVIEW*.html + mp4 包 | 人工/外部 ChatGPT 看片裁决 | ✅ 真用过（G2/G3/DEDUP/CROSSSEG） |
| Desktop(tkinter) | src/treecut/desktop.py + ui/* | LayerA 桌面（扫描/制作/剪映草稿开关） | 可导入✅；**无近期真用证据** → LEG |
| blind UI | tests/test_*_blind_ui.py | 盲审工具（测试） | 测试用 |

## 10.2 Workbench 端点（server.py 证据）
| 端点 | handler | 行为 | QA？ | 持久化 |
| --- | --- | --- | --- | --- |
| GET /（index） | 静态 | — | — | — |
| GET /file?p= | Range 播放 | 本地文件字节流 | — | — |
| GET /api/project | 读项目 JSON | — | — | — |
| GET /api/qa/<id> | **占位**：返回 "PENDING_BUILDER_QA"（真 QA 由外部 builder 回写） | ❌ | — |
| POST /api/replace | 换镜 → local_reqa | **LOCAL_RULE**（无 qwen；资格/动作匹配/重复/配置占位）→ 写回 beat | 部分 | 写项目 JSON（os.replace） |
| POST /api/trim | 有界裁剪 | 同上 | 部分 | 写项目 JSON |
| POST /api/reqa | 重 QA | local_reqa | 部分 | 写项目 JSON |
local_reqa 明示："完整 QA 由 ProductionQAService 在重建时执行"（L161-195）→ **UI 内没有完整 QA**。

## 10.3 按钮→后端→DB 追踪结论
- 真实功能：看 beats/claims、看候选、播放 subclip（Range）、**换镜/trim/保存（写 JSON 项目，非 DB 表）**、局部规则重 QA。
- **不存在**：账号选择、项目列表管理、脚本编辑入库、Render 按钮、发布按钮、素材库管理入口（这些都在 Desktop/LayerA 或 scripts）。
- DB mutation：server.py 不直接写 materials.db（写 PROJECT JSON）→ "UI→Service→DB" 链**未通到 DB**（项目文件 JSON 层）。
- 结论：Workbench = **"审阅+微调 JSON 项目"工具**，不是生产控制台。

## 10.4 运营用户流程走查（§28 用户流）
启动→选账号→选项目→选 Script→看 Beat→看候选→播 Subclip→换镜→Trim→保存→重 QA→预览→Render→Review：
| 步 | 状态 | 依据 |
| --- | --- | --- |
| 启动/选账号/选项目 | NOT_IMPLEMENTED | 无入口 |
| 选 Script/看 Beat/看 Claim | WORKS（项目 JSON 内） | index.html 左栏 |
| 看候选/播 Subclip | WORKS | /file Range + 候选卡 |
| 换镜/Trim/保存 | WORKS（JSON 项目） | /api/replace,/api/trim |
| 重新 QA | PARTIAL（local rule；完整 QA 需外部 builder） | server.py |
| 预览/Render | NOT_IMPLEMENTED（无渲染端点） | — |
| Review(L3) | 另路可用：HTML 审阅包+裁决（非同一 UI） | human_review_package |

## 10.5 设计质量（§29）
信息层级：三栏可读；**但仍需理解 beats/claims/QA 术语，偏开发者**；证据分层（L1-L3-PATH）展示意图好；loading/错误提示/cancel/undo/确认弹窗：**未见**（[GAP]：index.html 未逐控件核，见 ev_ui 缺失说明）；危险操作（覆盖项目）无二次确认证据；长任务（qwen/渲染）无队列/进度 UI。
设计判定：`ABNO`（作为"开发者审阅台"够用；作为"运营工具"差得远）。

## 10.6 兼容性（§30，诚实结论）
- 无 viewport/响应式适配证据（index.html 未核 [GAP]）；**未在任何缩放/分辨率/浏览器矩阵测试过** → 除"本机 Edge/Chrome 默认缩放跑过 UI smoke（记录 200 请求）"外全部 **NOT_TESTED**；Z 盘不可用/模型不可用/浏览器断开等异常场景 NOT_TESTED。
- 长文件名/中文路径：服务端本机路径 Range 服务已处理中文（本机用过）；跨平台/弱硬盘未测。

# 11 性能 / 长任务稳健性 / 存储 / 安全 / Git

## 11.1 性能（§31，以证据为准，不做理论冒充）
- DB 单表 COUNT 全库探测 65s（88 表）→ 单库 2.16M 行规模可接受；PRAGMA quick_check 25–275s（记录）→ **大库检查慢是既有约束**。
- qwen 单调用 20–60s（CPU 单 worker）→ Discovery/G2 批量 qwen 是**主时间瓶颈**；孤儿 python 曾抢 ollama 使 pytest 卡 0 CPU（记录，已在此轮复现预防：单 worker 纪律）。
- OCR/ASR/keyframes 为离线批处理（processing_history 275,797 行账本存在）→ 有持久进度。
- 明显可优化点（P2/P3）：ffprobe/帧提取在脚本里重复 subprocess（每候选多次）；`frame_at` 每次重跑 ffmpeg 无缓存（sprintv2_v11_probe L37-41）→ 重复计算真实存在；无向量索引（检索=LIKE/廉价排序）。
- 未测：内存峰值、GPU、浏览器端性能、启动时间 → NOT_TESTED。

## 11.2 长任务稳健性（§32）
- 存在：analysis_jobs/analysis_tasks/processing_history 账本（可续跑基础）；脚本多数幂等设计（先写临时→os.replace）。
- 缺口：无统一 checkpoint 框架；qwen/渲染长任务无队列、无断点续传 UI；孤儿进程防护=人工纪律（本轮再次出现长跑 pytest 无法判定进度的问题——**缺超时与进度可见性**=真问题）；浏览器断开/断电/部分文件→ 无系统性 quarantine 证据 [GAP]。
- 结论：稳健性 `PARTIAL`（账本有、框架无）；这是"运营可用"前必须补的工程债（P1）。

## 11.3 存储（§33）
- 实测空闲：C 72.4GB / E 154.5GB / G 147.9GB / Z 12.2TB。
- 分工基本符合设计：素材 X1(网络盘/素材盘01)；运行 DB+工作产物 E(runtime_data/runtime\production_smoke)；备份 Z(12TB)；Git=C 盘仓库。
- 仓库内 tracked=69.3MB（小）；**reports/storage 350 文件 40.5MB 是仓库最大块**（含审阅 PNG/PDF/JSON）——证据入库可接受但偏重（P3：PDF 16.7MB/PNG 2.2MB 建议转存或移出）。
- 风险：C 盘仓库 + 系统共用（曾 57GB 用量/硬停 <50GB 纪律）；runtime_data 在 E（未入 Git ✅）；无证据显示媒体误落 C。

## 11.4 安全 / 隐私 / 密钥（§34，含本审计 P0 发现）
- **P0 发现**：`配置子机连接.cmd`（仓库根，已 push）硬编码**真实 hub token**（43 字符随机串，hub_url http://192.168.1.135:8766）→ 本审计已**在工作树中清除**（替换为 REPLACE_WITH_GENERATED_HUB_TOKEN）；**因历史中仍存在，必须在 hub 端轮换/吊销该 token**。已排除该串在 tracked 文件中其它出现。
- 全量 tracked 文本扫描（1,109 文件）：其余 8 处命中=文档示例/测试桩/占位（xsec_token=SECRET、MOCK_、'x'*32），无真实凭据。
- tracked 危险扩展名：**0**（无 mp4/wav/onnx/pt/db 等）；>5MB tracked 仅 3 个（字体/标签库/审阅 PDF）。
- 浏览器 profile/cookie/session：本地运行（runtime_data），**无入 Git 证据**；AutoPublish 禁止。
- 结论：除该 token 外仓库密钥卫生总体干净；**token 轮换为必办 P0 动作**。

## 11.5 Git / GitHub（§35/§36/§37）
- branch=main；remote= https://github.com/yuaho8977-stack/treecut-v13.git；HEAD=11887df（MMV R2 Known6…）；工作树在 token 清除前 clean。
- 现有 tag：v13.5.15-baseline；本审计将新增 snapshot tag（§37/§60 步骤）。
- 已跟踪大目录：reports 350 / src 214 / scripts 304 / docs 186；runtime_data/release 内容/素材未跟踪（ext 直方图证明）。
- 本审计新增物（待 commit）：docs/TREECUT_SYSTEM_MASTER_AUDIT_V1.md、docs/TREECUT_ARCHITECT_READ_GUIDE_V1.md、reports/storage/{TREECUT_SYSTEM_MASTER_AUDIT_V1.json, TREECUT_CODE_MANIFEST_V1.json, TREECUT_ENTRYPOINT_MAP_V1.json, audit_evidence/*.json}、配置子机连接.cmd 的 token 清除。

# 12 Legacy / 重复 / 未合并模块 + 测试审计

## 12.1 Legacy / Duplicate 分类（§13/§14；判定依据：caller grep + 文档）
| 组 | 成员 | 判定 |
| --- | --- | --- |
| 视觉多代 | visual_cognition.py / static_vision_v2.py / people_analyzer_v2.py / semantic_action_v1.py / semantic_action_v2.py / temporal_action_v2.py / visual_understanding_v2.py / mmvl_master_v1.py | visual_cognition/static/semantic/temporal = LEGACY_REUSABLE（历史验证集阶段，被 V2/MMVV 取代）；V2/MMVV = 当前方向 |
| 业务认知三代 | business_cognition_service(V1) / _v2 / _v2_1 | V2_1 最新（fresh18 用过）；V1/v2 LEGACY_REUSABLE；**建议收敛单一** |
| 冲突/证据 | conflict_resolver vs conflict_resolver_v2；evidence_resolver vs evidence_strength_v2 | 疑似 DUPLICATED（v2 替代）[GAP：caller 未全核] |
| Truth 载体 | canonical_truth.py vs schema_v2.py vs canonical_human_truth(表) | 命名混淆（service 与表名都叫 canonical）→ REF |
| 审核 UI 系 | phase3_review_ui / second_review_ui / segment_cognition_ui / review_center | 各代产物，phase3 最新最全；review_center 疑似 DEAD_CODE [GAP] |
| 双 Production | LayerA(application/cognitive/output) vs LayerB(services+scripts) | 并存（§2.5）；DUPLICATED 架构面 |
| scripts 296 个 | b007_* / sprintv2_* / stage* / phase* / v09* / hrp_* / security_audit_* / stress_* | 大量一次性 runner（b007_v06/spotlight 等历史）+ 当前 sprint 脚本；**缺统一"runner registry"** |
| 空表模块 | production_plans/shot_usage/review_queue/duplicate_groups/visual_clusters/asset_quality/media_tags | UNMERGED（设计存在未接） |
| desktop/ui(LayerA) | desktop.py + ui/settings_dialog/welcome_dialog | LEGACY_REUSABLE（无近期真用） |
| pyJianYingDraft 输出 | output/jianying.py | IMP+LEG（可导入，草稿导出在认知链中可跳过；无近期产物） |
| XHS browser | src/treecut/browser/* + tools/stress_20_rounds_control | ACTIVE(采集/恢复)但低优先级 |
| gpu/acceptance | gpu_acceptance.py, 配置子机连接.cmd, remote agent_main | 子机远程 agent（hub_url）→ ACTIVE(工具)；token 已清 |

## 12.2 测试审计（§52/§53）
- 测试文件 43 个（tests/），tracked 293KB；另有 test 目录之外测试散落 [GAP 核]。
- 覆盖分层（文件名+代码特征）：
  - Stage8 系：test_g1_source_gate(11)/g2_action_subclip(9)/g3_claim_visual(8)/g5_dedup_qa(10)/stage8_repair(10)/stage8_v2_integration(6)/stage8_discovery(5)/discovery_v11(6)；
  - 视觉 V2/MMVV：test_treecut_visual_understanding_engine_v2(10)/mmvl_real_media(13)/mmvl_r2(10: 6 pass + **4 xfail 标记 R2_KNOWN_UNMET**——即语义 ROI 未解）；
  - LayerA/历史：p1-p7/phase*/stage2/stage3/生产_narration_v01/production_path_preflight_v01/review_productization/xhs_work_browser_v01 等。
- **xfail/skip 必须逐条解释**（重点）：mmvl_r2 4 个 xfail = R2 已知缺口（ROI 语义获取失败→对应案例无法判）→ **是隐藏 blocker 的诚实外化**，转绿条件=ROI 解决后；其余 skip 多为环境/真实媒体条件（以本轮 ev_tests.json 实跑为准）。
- **"410 passed ≠ Production PASS"**：绝大多数测试是 unit/synthetic（合成帧/桩数据/规则单测）；真实媒体级只有 mmvl_real_media(6 案例帧)与少量 QA/产物测试；**没有任何测试覆盖"脚本→成片"端到端自动断言内容质量**；语义正确性依赖人工裁决（L3），测试只能证明"代码不崩+规则自洽"。
- 本轮实跑结果：见 §12.3（ev_tests.json；逐文件 bounded 运行，含卡死文件清单）。

## 12.3 本轮测试实跑（逐文件有界运行，ev_tests.json）
- 43 个文件全部跑完（每文件墙钟上限 240s）：**412 passed / 4 xfailed / 0 failed / 0 skip**；
  - `test_claim_multiprocess.py`：rc=5（**0 收集**，spawn 环境不注册用例）——单文件隔离下不计入；
  - `test_xhs_work_browser_v01.py`：51 passed（27.5s，1 条线程告警）；
  - 最慢：test_p4_search 62s / test_phase2_cognition 23s / test_phase1_identity 15s；
  - xfail 全部来自 `test_mmvl_r2.py`（6 passed + 4 xfailed，R2_KNOWN_UNMET）；
  - 与历史单次全量"410 passed/2 skipped/4 xfailed"的差异 = 运行隔离方式不同（逐文件无共享 fixture/收集差异），非代码回归。
- 注：此前一次整批全量跑 >15min 未见收口 → 改为有界逐文件跑；**这本身印证 TD08（长任务超时/进度可见性缺失）**。

# 13 文档一致性 / 技术债登记 / 风险登记

## 13.1 文档审计（§54，STALE/CONFLICTING/CANONICAL）
| 类别 | 文档 | 问题 |
| --- | --- | --- |
| CANONICAL（应保留为权威） | docs/TREECUT_ROADMAP_MASTER_V1.md（主宪章）；TREECUT_STAGE8_G1_EXECUTION_REPORT.md（G1 冻结）；TREECUT_MMV_REAL_MEDIA_VALIDATION_REPORT_V1.md + HARDENING_R2.md（MMVV 现状）；TREECUT_STAGE8_CANDIDATE_DISCOVERY_REPORT_V1.md；TREECUT_VISUAL_UNDERSTANDING_PLAYBOOK_V2.md；TREECUT_STORAGE_ARCHITECTURE_REPORT_V1.md；PRODUCTION_GRADE_ARCHITECTURE_CONSTITUTION.md | 与代码一致，是本报告主要二手来源 |
| STALE（结论已被后续裁决覆盖） | reports/storage/TREECUT_PROJECT_STATE_V1.json 部分块（sprint_v2: DEDUP=PASS/G2=ENGINEERING_PENDING 已被 NEEDS_REPAIR / PROVISIONAL_PASS_AFTER_TUNING 覆盖；顶层 G3_CLAIM_VISUAL_STORY=NOT_STARTED 已过时）；B007_PILOT_V1_VS_V2_REPORT.md（READY_WITH_LIMITATIONS 待人工对比——现已加 NEEDS_REPAIR 语境） | 单文件混合新旧（§3.4） |
| CONFLICTING 高危 | 任何写"MMVV 完成/Enforcement 就绪/生产可用"的表述（未发现于最新 MMV 报告，但旧文与口头摘要曾含糊）→ 本报告统一口径=SHADOW+NEEDS_REPAIR | — |
| 需注意 | 185 篇 docs 中 01-36 升级任务（v12→v13 历史）与 PHASE/BRAIN 大量早期报告=历史存档，**勿被外部架构师误当当前状态**（见 ARCHITECT READ GUIDE） | — |

## 13.2 TECH_DEBT_REGISTER（ID/问题/证据/严重度/修复/成本/优先级）
| ID | 问题 | 证据 | 严重度 | 修复方向 | 优先级 |
| --- | --- | --- | --- | --- | --- |
| TD01 | **无端到端生产编排器**；能力散在 296 scripts+2 套 production | §5/§9 | P1 | 收敛 1 个 PipelineService(script→3 候选→render→QA) + 1 个 CLI | P0 后即做 |
| TD02 | **动作候选召回=0** → G2/G3/成片全链无有效输入 | §8.3/§14/§15 | **P0(业务)** | 素材缺口核验+定向补拍/REVIEW_REQUIRED 157 人工核 | P0 |
| TD03 | **MMVV 语义 ROI 未解**（qwen bbox 不可信） | §8.2 | P1 | 选项 A/B/C 待批；不 Enforcement | P1 |
| TD04 | 语义 QA 硬编码 True（V2 pilot L223-226）→ 假 PASS 风险 | §9.5 | **P0(质量红线)** | QA 语义项接真实匹配器输出；未接前标 NOT_VERIFIED | P0 |
| TD05 | schema 迁移缺失：b007/spotlight/stage2 表不在 0001-0009 | §6.1 | P1 | 补 0010+ 基线迁移；禁止 scripts 自建表 | P1 |
| TD06 | b007_source_role_v1：asset_type 全 NULL；role=路径先验 0.5；PENDING 69% | §6.3 | P1 | L3 分批核 APPROVED；asset_type 接线 | P1 |
| TD07 | 真实 token 曾入 Git（配置子机连接.cmd） | §11.4 | **P0(安全)** | **hub 端轮换 token**（历史不可抹除） | P0 |
| TD08 | 长任务无超时/进度/孤儿防护（本轮复现：pytest 无法判定进度） | §11.2 | P1 | runner 统一 wall-clock 超时+日志可见 | P1 |
| TD09 | 视觉理解 5+ 代并存（visual_cognition→…→V2/MMVV） | §12.1 | P2 | 归档 LEGACY，单一路径 | P2 |
| TD10 | L3 分散 ≥6 表（canonical_human_truth/human_annotations v2/v3/b007_l3…） | §6.4 | P2 | 收敛 canonical 版本线 | P2 |
| TD11 | 3+ 套渲染实现（output/mp4、narration、b007 自写、roughcut） | §9.2 | P2 | 统一 RenderService（复用已验证 V2 参数） | P2 |
| TD12 | PROJECT_STATE_V1.json 混合新旧、无唯一状态源 | §3.4 | P2 | 本 MASTER AUDIT 转正+状态文件脚本化更新 | P2 |
| TD13 | BGM 无库；Voice SAPI 机械音 | §9.3/9.4 | P1(内容) | 授权 BGM 目录+真人参考音（架构师待输入） | P1(输入依赖) |
| TD14 | workbench 无 render/项目/账号；UI 无异常处理验证 | §10 | P2 | 见 §37 P2-UI | P2 |

## 13.3 RISK_REGISTER（§48）
| 风险 | 级 | 现状 |
| --- | --- | --- |
| 数据污染/串账号 | P0 潜在 | Truth 分层正确+source 隔离字段在；但 L3 多表+路径先验 → 人工核批量前有漂移可能 |
| 假视觉匹配/假 QA PASS | **P0 现实** | 语义 QA 硬编码 True（TD04）；matcher eligible 桩（g3_dedup_run） |
| 版权/BGM | P1 | 无库=无风险但无能力；拿到未授权曲目将成新风险 → 许可清单纪律保留 |
| 模型不可用（ollama/qwen） | P1 | 单 worker 无 fallback（SAPI 例外）；孤儿进程抢 ollama 曾发生 |
| 浏览器登录过期 | P2 | 采集依赖登录态；不入库不入 Git（卫生 OK） |
| 存储失败（C<50GB） | P1 | 纪律存在；C 目前 72.4GB 余量 |
| 运行时崩溃/断电 | P2 | 账本有、checkpoint 框架无（TD08） |

# 14 就绪度裁决 / 方案路线 / STOP DOING / 删除·归档·保留

## 14.1 Production Readiness（§45）：今天给运营人员 = 不可用
能做什么：只能看 reports/HTML 审阅包；Workbench 能打开既有 JSON 项目审阅/局部换镜。
不能做：无账号/项目管理、无脚本输入 UI、无渲染按钮、无发布。必须开发者介入：任何一次"新视频生成"（改脚本字段→跑 b007_v091_v2→人工 QA）；必须人工：L3 审核、候选裁决、内容最终判断。
可能错误 PASS 的地方：语义 QA 硬编码（TD04）→ **必须修**。

## 14.2 One Real Video 逐环节（§46，从零一条新片）
| 环节 | 状态 |
| --- | --- |
| 选脚本 | HUMAN（开发者编辑脚本字段） |
| 取干净源 | BROKEN(自动)/HUMAN（G1 未接入取材；关键词 SQL 仅样例） |
| 动作候选 | SHADOW（0 PASS；MMVV SHADOW） |
| Claim→镜头 | HUMAN/不可靠（G3 阻塞） |
| TTS | AUTO 但机械音（SAPI）；生产级=AWAIT 参考音 |
| 字幕/烧录 | AUTO ✅（已证） |
| BGM | NOT_READY |
| 渲染 | AUTO ✅（ffmpeg 链已证） |
| QA 技术 | AUTO ✅ |
| QA 语义 | **BROKEN（硬编码假设）** |
| 人工 Review→发布 | HUMAN ✅（审阅包流） |

## 14.3 Daily Production（§47）
1/天、5/天、多账号：**当前全部不可行**（无编排、无人工核批量、素材缺口、无 BGM/声、语义 QA 不可信）。不用理论估计冒充实测：审计期无任何"日常生产"运行记录。

## 14.4 Remediation Roadmap（§49，按证据重排，非沿用旧 Roadmap）
- **P0（先做，均为阻断/安全）**：①hub token 轮换（TD07，5min 人工）；②语义 QA 去硬编码：未验证项显式 NOT_VERIFIED（TD04，0.5-1d）；③动作素材缺口收敛：REVIEW_REQUIRED 高价值 157 人工核 + 定向补拍/素材请求（TD02，1-3d 含人工）；④MMVV ROI 方案 A/B/C 决策（TD03，待架构师）。
- **P1**：⑤单一 PipelineService+CLI（TD01，2-4d）；⑥runner 超时/进度/孤儿防护（TD08，1d）；⑦迁移基线 0010+（TD05，1d）；⑧G1 唯一取材闸收口（§5.2，1d）；⑨Voice 参考音+BGM 授权目录（输入依赖）；⑩b007_source_role asset_type/批量 L3（TD06，渐进）。
- **P2**：⑪状态源脚本化（TD12）；⑫L3 收敛（TD10）；⑬统一 RenderService（TD11）；⑭Workbench 生产入口（脚本输入/渲染/项目列表，2-4d）；⑮归档 LEGACY 视觉/脚本（TD09）。
- **P3**：报告大文件移出仓库；vector 检索评估；缓存帧。

## 14.5 STOP DOING（§50，本轮审计按证据确认）
- 在 ROI 未决时盲跑 Blind30-50 / 扩大 qwen 调用面（继续=烧时间无信息）。
- 过早 Enforcement（MMVV）。
- 过早 Pilot V3 / Stage9 / 模板扩张 / AutoPublish。
- 重复开发 UI（在无 PipelineService 前继续加前端）。
- 无证据的模型微调/训练（禁止）。
- 给旧脚本组继续叠一次性 runner（先收口 TD01 再扩展）。
- XHS 浏览器自动化深投（采集已够，主瓶颈在内容侧）。

## 14.6 DELETE/ARCHIVE/KEEP 建议（§51，只建议不执行）
- KEEP：services/{production_source, action_subclip, claim_visual, visual_beat, visual_understanding_v2, mmvl_master_v1, production_dedup, production_qa}.py、config/production.py、canonical Truth 表、b007_* 表、roadmap/MMV/Stage8 报告、tests/（含 xfail 诚实外化）。
- REFACTOR：output/{mp4,narration,production_narration}.py → 统一 Render/TTS 服务；b007_v091_v2.py 逻辑抽取；visual_cognition→V2 收敛。
- ARCHIVE：docs 01-36/PHASE/BRAIN/FRESH_HOLDOUT 历史组（标记"历史存档"）；visual_cognition/static_vision_v2/semantic_action_v1/v2/temporal_action_v2/people_analyzer_v2（若 V2/MMVV 上位）;business_cognition v1/v2；scripts 一次性组。
- DELETE_CANDIDATE（无 caller 核实后）：conflict_resolver(旧)/evidence_resolver/evidence_strength_v2 之一、review_center、空表对应模块（visual_clusters/shot_usage 若设计废弃）、duplicate_groups 等未接表 [GAP：逐个 caller 复核]。
- DO_NOT_TOUCH：素材盘、runtime DB（生产数据）、Z 备份、已冻结 G1 裁决、mmv 帧证据（负样本必须保留）。

## 14.7 设计质量总评（§41 BEST-SOLUTION 节选）
| 设计 | CURRENT→WHY | ALTERNATIVES | TRADEOFF | 判定/建议 |
| --- | --- | --- | --- | --- |
| SQLite 单库 | 便携/免服务/审计友好 | Postgres | 并发/大查询弱 | FFP（规模内）；补迁移纪律(TD05) |
| Qwen2.5VL(ollama CPU) | 无 GPU 约束、真实可用 | API 云模型 | 慢(20-60s)/单 worker | ABNO（现有规模可接受；勿扩调用面） |
| MMVV 模块化硬闸 | 防假 PASS 方向正确 | 单模型端到端 | 模块多、依赖 ROI | FFP(方向)/ROI 层需 REDESIGN(选项A/B/C) |
| ROI 获取 | qwen bbox 不可信→启发式 | A人工首帧/B轻检测/C维持 | A校准快但不可扩展；B需批准 | EXP→待架构师裁决 |
| Candidate Discovery 漏斗 | 宽召回→廉价→运动→qwen→门 | 直接 qwen 全量 | 成本/信息权衡 | ABNO（机制对；缺素材=外部约束） |
| Cross-Segment | 恢复切碎动作 | 改切点 | 稳定性 | FFP（候选层合并不动 canonical） |
| FFmpeg 直渲 | 可控可验证 | 剪映/pyJianYingDraft | 无工程化模板 | ABNO（V2 参数已验证；收敛封装 TD11） |
| Jianying 草稿 | pyJianYingDraft 可导入 | — | 无近期验证 | IE（勿写"支持剪映"；保留但不算能力） |
| SAPI TTS | 免依赖 | 云 TTS/克隆 | 机械音 | ABNO(降级位)；生产级=真人参考音 |
| Workbench | 本机审阅台 | 全套 Web 生产台 | 工期 | ABNO（先做 PipelineService 再扩 UI） |
| Browser Foundation | 采集/恢复只读 | 自动化发布 | 账号风险 | FFP（维持只读；勿扩） |

## 14.8 最终裁决
TreeCut 的**数据/Truth 底座（L1/L3、B007 双源事实、G1 表）是真实资产**；**技术渲染/QA/字幕链路在受控样例上真实成立**；但 **"内容生产"核心（动作候选→视觉匹配→语义 QA）仍处于 NEEDS_REPAIR/SHADOW**，**不存在运营级闭环**。本报告对"可用"的每一处判断都标注了证据级别；P0 级行动（token 轮换、语义 QA 去硬编码、素材缺口收敛、ROI 决策）必须先于任何"自动化日常生产"叙事。

# 15 附录

## 15.1 规格章节映射（任务 §56 的 40 章 → 本报告章节）
01 执行摘要→§00/§14.8；02 TreeCut是什么→§02；03 当前真实状态→§03；04 完整功能清单→§04；05 系统架构→§05.1；06 模块调用关系→§05.2；07 数据流→§05.3；08 数据库→§06；09 AI模型→§07.1；10 浏览器→§07.2；11 素材资产→§07.3；12 Visual Understanding→§08.1；13 MMVV→§08.2；14 Candidate Discovery→§08.3；15 G2/G3→§08.5/§08.6；16 Production Source→§08.7；17 Script/Beat/Claim→§09.6；18 Renderer→§09.2；19 TTS/Voice→§09.3；20 BGM→§09.4；21 QA→§09.5；22 UI→§10；23 UI兼容性→§10.6；24 性能→§11.1；25 稳定性→§11.2；26 存储→§11.3；27 安全→§11.4；28 Git/GitHub→§11.5；29 Legacy/Unmerged→§12.1；30 测试→§12.2/§12.3；31 当前阻塞→§14.1/14.2；32 技术债→§13.2；33 风险→§13.3；34 设计优劣→§14.7；35 Production Readiness→§14.1；36 问题解决方案→§14.4；37 P0-P3 Roadmap→§14.4；38 Stop Doing→§14.5；39 架构师需重点读的代码→TREECUT_ARCHITECT_READ_GUIDE_V1.md；40 最终裁决→§14.8。

## 15.2 本审计产出物
- docs/TREECUT_SYSTEM_MASTER_AUDIT_V1.md（本文件，中文主）
- docs/TREECUT_ARCHITECT_READ_GUIDE_V1.md（外部架构师读码入口）
- reports/storage/TREECUT_SYSTEM_MASTER_AUDIT_V1.json（机器可读状态）
- reports/storage/TREECUT_CODE_MANIFEST_V1.json（tracked 源码清单：路径/大小/hash/类别）
- reports/storage/TREECUT_ENTRYPOINT_MAP_V1.json（CLI/服务/脚本/UI/测试入口映射）
- reports/storage/audit_evidence/*.json（原始证据：_repo_stats/_db_counts/ev_layerA_imports/ev_db_dist/ev_db_dist2/ev_git_secrets/ev_tests）
- 安全修复：配置子机连接.cmd 的 token 清除（详见 §11.4）

## 15.3 审计边界与诚实声明
- 本次为 RECOVERY/SALVAGE 模式的收口审计：EV1-EV8 并行证据采集因会话调度中断未落盘；本报告由主代理以"自有探测证据（DB 只读/仓库统计/导入冒烟/密钥扫描/逐文件测试/关键调用链 grep）+ 上轮已验证会话记录 + canonical 文档"汇总而成；凡未能复核处均标注 [GAP] 或"记录"，无虚构。
- 未做：真实媒体新渲染、qwen 新推理、UI 实机交互矩阵、Blind50、Enforcement、任何产品逻辑改动。
- "能 import"≠"生产可用"在本报告全文严格区分（六层验证，§1.4）。

