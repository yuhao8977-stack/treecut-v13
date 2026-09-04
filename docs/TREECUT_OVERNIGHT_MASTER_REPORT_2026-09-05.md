# TreeCut Overnight Run V1 — Master Report 2026-09-05

- run_id: OVERNIGHT_RUN_V1 · 生成: 2026-09-04 19:44:48
- baseline: 4fa7612 → head: b76fce5
- A3 预测执行: **NO**（缺 Human ROI + blind 已建；runner FAIL_CLOSED）
- A3 holdout 状态: **A3_HOLDOUT_6_FROZEN**（SEALED，未用于调参）

## 第一屏（10 项）

- **1_distance_to_goal**：素材 Truth→理解→检索→选镜→自动成片→QA→人工终审：前端(源/语义/检索/MMVV 校准集) 已到 TESTED_REAL_DATA/HUMAN_VALIDATED 层；后端组装(shot→timeline→渲染→3候选) 仍 CODE_EXISTS→TESTED_SYNTHETIC，未闭环
- **2_done_tonight**：A3 blind 严格化(输入/密钥/runner/scoring)+可观测性审计+ROI 页硬化；契约盘点21能力；漏斗/基准池13k；缺口地图；dry-run 计划；49 文件回归(48过1隔离缺陷)
- **3_new_capabilities**：blind machine input + 防泄漏测试 + fail-closed runner + scorer 分离；ROI 页快捷键/草稿；observability 审计工具
- **4_code_only**：Subtitle(CODE_EXISTS), 3候选/Workbench(CODE_EXISTS), E2E 编排(CODE_EXISTS), BGM(NOT_FOUND)
- **5_real_media_validated**：G1 池/漏斗(DB), A3 盲帧字节绑定, observability(盲帧真实计算), Core5/A2.2 既往
- **6_human_validated**：A1 ROI 200框(A1), A3 筛选(架构师), 对象/动作校准语料(历史 stage3/4)
- **7_missing_links**：MMVV 强制化→泛化验证(A3 blind 作答) → shot_usage 落库 → 模板×素材契约 → 渲染/QA 真实成片 → 3候选编排
- **8_top5_blockers**：[{'rank': 1, 'gap': 'MMVV 只 SHADOW（MMVV_ENFORCEMENT 硬阻断）', 'evidence': 'MMVV_ENFORCEMENT 硬阻断；A3 泛化待验证', 'affects': '动作证据无法自动阻断错误选镜；最终成片正确性依赖人工'}, {'rank': 2, 'gap': 'A3 泛化未验证（冻结算法未在 unseen 上作答）', 'evidence': '缺 Human ROI；blind 已建，明日起可标', 'affects': 'EXTEND 检索/几何判断是否可泛化未知'}, {'rank': 3, 'gap': '检索语义缺口：RETRACT 路径召回=0；路径关键词误导桶存在', 'evidence': 'funnel keyword recall RETRACT=0；EXTEND 358 命中/190 家族，最大桶「11.29 产品视频拍摄」28', 'affects': '动作召回完整性；误召回'}, {'rank': 4, 'gap': '生产组装链未闭环（shot_usage=0、模板 4、E2E 编排 CODE_EXISTS）', 'evidence': '模板-素材契约未在真实剪辑闭环验证', 'affects': '脚本→3 候选成片未实现'}, {'rank': 5, 'gap': '无授权 Voice/BGM 输入', 'evidence': 'VOICE_PRODUCTION_INPUT_REQUIRED / BGM_LIBRARY_INPUT_REQUIRED', 'affects': '成片音轨只能 fallback/诊断'}]
- **9_next_priority**：['A3 人工 ROI(30帧)→blind 预测→scoring(先哈希)', '检索语义层补齐(RETRACT/误导桶)', 'shot/timeline/渲染真实闭环(诊断 rough cut)', '自动 ROI 差距实验(A1, 禁碰 A3)', 'test_stage2_vision 隔离修复']
- **10_human_actions_tomorrow**：['① A3 30 帧 Human ROI(/a3/roi, blind H001–H006)', '② A3 时间可观测性人工判断(HTML 单选)', '③ 批准 blind 预测/评分 + 可选 BGM/Voice 生产输入']

## 今夜提交

- `b76fce5 overnight(production-dryrun): calibration beat dry-run plan (stages x contract x missing/broken; no rough cut - chain not complete, honest) + code-quality inventory (310 scripts, duplicate families listed, read-only)`
- `721d9f2 overnight(contract-probe,candidate-benchmark): contract probe 21 capabilities x six-level evidence + source funnel + non-holdout pool 13460(sample 300, seed fixed) + gap map (5 blockers) + auto-ROI gap report (NOT_SCORABLE, qwen ROI blocked)`
- `7c0891e overnight(eval-harness): blind ROI page (opaque H001-H006, A/D/S/Delete, copy-prev draft w/ confirm, no auto submit) + server blind endpoints w/ bounds+hash checks + runner ROI gate: 0-box or hash mismatch fails closed`
- `727420b overnight(a3-observability): temporal observability audit on blind inputs (frame-diff/flow/camera proxy/static ratio, TEMPORAL_SIGNAL only, no verdicts) + Chinese human review HTML (no GT/POS/NEG)`
- `355612f overnight(a3-integrity): blind machine input H001-H006 (no pos/neg/extend/media/source tokens) + private case key + allowlist runner fail-closed A3_ROI_REQUIRED + scorer separation + 9 integrity tests`

## 回归（逐文件 bounded pytest）

- 49 文件：**48 pass / 1 fail** / 0 timeout
- quarantine: ['test_stage2_vision.py']（test_stage2_vision 7 断言=文件内状态干扰，单测各自通过；今夜未触碰 src）

## A3 Evaluation Integrity

- blind manifest: opaque H001–H006，无 POS/NEG/EXTEND/伸缩/media_id/源路径/客户词元（9 项测试全过，帧字节=源帧）
- case key: `TREECUT_MMVV_A3_CASE_KEY_PRIVATE.json`（scoring 专用）
- runner `run_a3_blind.py`: allowlist；缺 ROI 或 0 框 → `A3_ROI_REQUIRED`(exit 3)；帧哈希绑定
- scorer `score_a3_after_prediction.py`: 预测 sha 先于 GT 打开，缺 sha 拒绝

## Temporal Observability（盲帧，只读信号，非 verdict）

| case | TEMPORAL_SIGNAL | 帧差均值/最大 | 静态比 |
|---|---|---|---|
| H001 | STRONG_CHANGE | 0.1745/0.2156 | 0.0 |
| H002 | STRONG_CHANGE | 0.1143/0.1406 | 0.0 |
| H003 | STRONG_CHANGE | 0.1762/0.2051 | 0.0 |
| H004 | STRONG_CHANGE | 0.1445/0.1712 | 0.0 |
| H005 | STRONG_CHANGE | 0.1259/0.1523 | 0.0 |
| H006 | STRONG_CHANGE | 0.1328/0.1451 | 0.0 |

> 结论：6 案例冻结 5 帧全部 STRONG_CHANGE（帧间强变化，含相机运动 30–76px）。「桌板位移过程是否被 5 帧覆盖」无法仅凭强度信号判定 → 人工审阅页已备（单选导出），明天人工回答。

## 契约盘点（21 能力 × 六层）

| 能力 | 最高层 | 状态 |
|---|---|---|
| 素材导入/资产指纹 | TESTED_REAL_DATA | PARTIAL |
| 素材去重 | TESTED_REAL_DATA | PARTIAL |
| ASR | TESTED_REAL_DATA | PARTIAL |
| OCR/字幕检测 | TESTED_REAL_DATA | PARTIAL |
| Segment(切分) | TESTED_REAL_DATA | PARTIAL |
| 动作识别(语义/人员) | HUMAN_VALIDATED | PARTIAL |
| 对象识别/ROI | HUMAN_VALIDATED | PARTIAL |
| Camera(运动补偿) | TESTED_REAL_DATA | PARTIAL |
| 方向/状态(几何) | TESTED_REAL_DATA | SHADOW_ONLY |
| Candidate Discovery | TESTED_REAL_DATA | PARTIAL |
| G2(action subclip) | TESTED_SYNTHETIC | PARTIAL |
| G3(claim→visual) | TESTED_SYNTHETIC | PARTIAL |
| Story/Timeline | TESTED_SYNTHETIC | PARTIAL |
| Voice(TTS fallback) | TESTED_SYNTHETIC | PARTIAL |
| Subtitle | CODE_EXISTS | PARTIAL |
| BGM | NOT_FOUND | BROKEN |
| Render(ffmpeg) | TESTED_REAL_DATA | PARTIAL |
| Production QA(技术/内容分离) | TESTED_SYNTHETIC | PARTIAL |
| Human Review | HUMAN_VALIDATED | PARTIAL |
| 3 候选输出/Workbench | CODE_EXISTS | PARTIAL |
| End-to-end 编排 | CODE_EXISTS | PARTIAL |

## 漏斗（X1 + B007）

- mp4 23253（5 源：src1=3025/src2=3569/src3=332/src4=21170/src5=156）；G1 eligible≈13700；review APPROVED=88
- 路径关键词召回（候选非真值）：EXTEND 358（190 家族）、DRAWER 704、SOCKET 485、STORAGE 1597、RETRACT **0**、静态 7749
- B007 发布 30 note：segment 609 / ASR 866 / OCR 2980 全覆盖

## 非 holdout 基准池

- size=13460（排除 excluded_known_ids 全集；A3 6 案例不在池内）；固定种子分层样本 300

## Gap Map（Top5）

- **1** MMVV 只 SHADOW（MMVV_ENFORCEMENT 硬阻断） — MMVV_ENFORCEMENT 硬阻断；A3 泛化待验证
- **2** A3 泛化未验证（冻结算法未在 unseen 上作答） — 缺 Human ROI；blind 已建，明日起可标
- **3** 检索语义缺口：RETRACT 路径召回=0；路径关键词误导桶存在 — funnel keyword recall RETRACT=0；EXTEND 358 命中/190 家族，最大桶「11.29 产品视频拍摄」28
- **4** 生产组装链未闭环（shot_usage=0、模板 4、E2E 编排 CODE_EXISTS） — 模板-素材契约未在真实剪辑闭环验证
- **5** 无授权 Voice/BGM 输入 — VOICE_PRODUCTION_INPUT_REQUIRED / BGM_LIBRARY_INPUT_REQUIRED

## Production Dry-run（PLAN_ONLY）

- G1 源资格: OK(TESTED_REAL_DATA) — missing=[] broken=[]
- G2 action subclip: TESTED_SYNTHETIC — missing=['真实媒体校准重跑(避 A3)'] broken=[]
- G3 claim→visual: TESTED_SYNTHETIC — missing=['真实 claim 匹配证据'] broken=[]
- MMVV SHADOW evidence: SHADOW_ONLY — missing=['人工 ROI', 'blind 预测授权'] broken=['MMVV_ENFORCEMENT 硬阻断']
- Dedup: OK(TESTED_SYNTHETIC) — missing=['shot_usage 为空(生产未消费)'] broken=[]
- Timeline schema: CODE_EXISTS — missing=['模板-素材契约未在真实剪辑验证'] broken=[]
- Narration availability: TESTED_SYNTHETIC — missing=['VOICE_PRODUCTION_INPUT_REQUIRED'] broken=[]
- Subtitle plan: CODE_EXISTS — missing=['字幕样式端到端证据'] broken=[]
- Render preflight: OK(TESTED_SYNTHETIC) — missing=[] broken=[]
- G5 QA: TESTED_SYNTHETIC — missing=['内容 QA 真实成片校准'] broken=[]

- 诊断 rough cut：**不生成** — 链未全通：MMVV SHADOW_ONLY(无 ROI→无证据)、shot_usage=0、Voice/BGM 无生产输入。按 §28 条件(所有 source contracts+技术路径完整)不满足 → 不生成诊断成片（避免“为工作量而开发”）。

## 明天人工任务（≤3）

1. **A3 30 帧 Human ROI**：http://127.0.0.1:8933/a3/roi（blind H001–H006，A/D/S/Delete；复制上帧框需人工确认）
2. **A3 时间可观测性人工判断**：`TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY_REVIEW.html`（每案例单选后导出 JSON）
3. **批准后续**：blind 预测+评分（先预测哈希），及可选 BGM/Voice 生产输入

## 证据路径

- docs/TREECUT_OVERNIGHT_MASTER_REPORT_2026-09-05.md · reports/storage/TREECUT_OVERNIGHT_MASTER_REPORT_2026-09-05.json
- reports/storage/TREECUT_OVERNIGHT_PYTEST_MATRIX_V1.json · _FUNNEL_V1.json · _NON_HOLDOUT_BENCHMARK_POOL_V1.json
- reports/storage/TREECUT_PRODUCTION_CONTRACT_PROBE_V1.json · _GAP_MAP_V1.json · _PRODUCTION_DRYRUN_V1.json
- reports/storage/TREECUT_OVERNIGHT_AUTO_ROI_GAP_REPORT.json · TREECUT_MMVV_A3_MACHINE_INPUT_BLIND_V1.json · _CASE_KEY_PRIVATE.json
- reports/storage/TREECUT_MMVV_A3_TEMPORAL_OBSERVABILITY.json + _REVIEW.html · TREECUT_OVERNIGHT_RUN_STATE_V1.json