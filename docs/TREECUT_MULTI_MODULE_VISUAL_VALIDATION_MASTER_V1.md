# TreeCut 多模块视觉验证层 Master V1
## 目标：把“看见什么 → 谁在动 → 怎么动 → 是否支持文案”拆成可验证、可回归、可解释的模块

> 本文件把此前所有视觉理解、动作判断、Candidate Discovery、TVRC、Motion Object Attribution、Cross-Segment Recovery、Claim→Visual、Dedup、真实案例、人审规则、Harness 集成规则与 Real Media Hardening 统一为一个主文档。
>
> 这不是 OpenAI/ChatGPT 视觉模型、权重、内部网络或隐藏推理的导出。它复现的是此前人工审片过程中已经明确、可外显、可编码、可测试的判断方法。

---

# 1. 当前项目状态与为什么要做这一层

当前 TreeCut 已经具备：

- ProductionSourceService / G1 Production Source Gate
- Asset / Segment / ASR / OCR
- Qwen2.5-VL 视觉候选
- ActionSubclipService
- ClaimVisualMatcher
- ProductionQAService
- Human L3
- Production Workbench
- Cross-Segment Recovery
- Window-scoped Review Memory
- Dedup / Narrative Near-Duplicate
- Visual Beat + Atomic Claim
- Renderer / TTS / SRT

但 Stage8 人审已经证明，当前单模型/单标签式视觉判断仍存在几类典型问题：

1. 请求 `EXTEND`，候选自己却是 `RETRACT`，仍能进 TopK；
2. 静态“已伸出状态”被当成“正在伸出”；
3. `DRAWER_OPEN` 与 `DRAWER_CLOSE`、`PUT_IN` 与 `TAKE_OUT` 混淆；
4. 人物手势运动被误当成产品结构运动；
5. 相机移动可能被误当成产品运动；
6. 文件名 / 路径 / ASR / OCR 语义被错误升级为动作事实；
7. Segment 边界可能切断完整动作；
8. G3 将文本 Claim 切得过碎，导致“第一/第二/第三”单独找镜头；
9. 没有有效候选时，系统过去会用“差不多”的画面硬顶；
10. Dedup 能抓真重复，但 Narrative Near-Duplicate 误报偏高；
11. Qwen 视觉结果只能是 L2 候选，不能自己成为真值；
12. synthetic test 只能证明代码逻辑，不等于真实视频视觉准确。

因此需要正式建立：

# `TreeCut Multi-Module Visual Validation Layer`

---

# 2. 总体架构

```text
ProductionSourceService
        ↓
Candidate Discovery
PATH / ASR / OCR / Embedding / Existing Tags / Motion
        ↓
Candidate Segment / Window
        ↓
Qwen / Visual Provider
Object / State / ROI / Hand Interaction / Dominant Visual
        ↓
Camera Motion Estimator
        ↓
ROI Tracking / Target Object Motion
        ↓
Object-Specific Motion Analyzer
        ↓
Temporal State Transition
before → motion → after
        ↓
Action Direction Validator
        ↓
Domain Claim Critic
        ↓
Evidence Fusion
        ↓
PASS / FAIL / UNSURE
        ↓
Production Matcher / QA
        ↓
Human L3
```

---

# 3. Truth 层级必须严格分开

建议保存：

- `L1_SOURCE`：源文件、时间戳、哈希、OCR、ASR、motion 原始证据
- `L2_QWEN`：Qwen 视觉候选
- `L2_CV_MOTION`：传统 CV / ROI / Camera Motion 结果
- `L2_TEMPORAL`：状态转移和动作方向候选
- `L2_CRITIC`：Claim / Action Critic 结论
- `L2_FUSION`：多模块融合结论
- `L3_HUMAN`：人工最终裁决，append-only

禁止：

- Qwen 覆盖 L1；
- CV 覆盖 Qwen 历史；
- Critic 覆盖 Human；
- 机器任何模块自动写 L3；
- 模型同意模型就宣称“人工准确率”。

---

# 4. 视觉理解必须拆成 7 条支线

## A. Object｜画面里有什么

高价值对象至少包括：

- `ISLAND`
- `TABLETOP`
- `EXTENSION_TABLETOP`
- `DRAWER`
- `UPPER_THIN_DRAWER`
- `CABINET`
- `TRACK_SOCKET`
- `SOCKET_MODULE`
- `SINK`
- `APPLIANCE_ZONE`
- `CHAIR`
- `PERSON`
- `HANDHELD_OBJECT`

---

## B. State｜对象当前是什么状态

例如：

- `TABLETOP_EXTENDED_STATE`
- `TABLETOP_RETRACTED_STATE`
- `DRAWER_OPEN_STATE`
- `DRAWER_CLOSED_STATE`
- `CABINET_OPEN_STATE`
- `CABINET_CLOSED_STATE`
- `SOCKET_VISIBLE_STATE`
- `OBJECT_INSIDE_STORAGE`
- `OBJECT_OUTSIDE_STORAGE`

关键原则：

> **State ≠ Action**

---

## C. Action｜到底发生了什么

高价值动作：

- `EXTEND`
- `RETRACT`
- `DRAWER_OPEN`
- `DRAWER_CLOSE`
- `CABINET_OPEN`
- `CABINET_CLOSE`
- `STORAGE_PUT_IN`
- `STORAGE_TAKE_OUT`
- `SOCKET_INSERT`
- `SOCKET_REMOVE`
- `SOCKET_ADJUST`
- `PRODUCT_MOVE`
- `PRODUCT_ROTATE`
- `STATIC`
- `UNKNOWN`

动作类必须优先使用时序证据：

```text
BEFORE
↓
MOTION
↓
AFTER
```

---

## D. Direction｜动作方向

反向动作必须确定性硬闸：

- `EXTEND ↔ RETRACT`
- `DRAWER_OPEN ↔ DRAWER_CLOSE`
- `CABINET_OPEN ↔ CABINET_CLOSE`
- `STORAGE_PUT_IN ↔ STORAGE_TAKE_OUT`
- `SOCKET_INSERT ↔ SOCKET_REMOVE`

如果候选明确是相反方向：

> `P0 HARD REJECT`

不需要再通过总分“碰运气”。

---

## E. Claim Support｜画面能支持哪句话

同一个画面可以支持 A，但不能支持 B。

例：

- 岩板可见 → 支持材质候选；
- 不自动支持“耐高温”；
- 抽屉存在 → 支持抽屉对象；
- 不自动支持“静音滑轨”；
- 轨道插座可见 → 支持“轨道插座”；
- 不自动支持“插拔顺手”；
- 桌面已伸出 → 支持功能/状态；
- 不自动支持“来客一拉就变宽”。

---

## F. Story / Continuity｜故事连续性

如果 `SINGLE_CASE`：

- 同案例
- 同产品
- 同空间
- 同人物

应尽量连续。

如果 `INFORMATION_MONTAGE`：

- 可以跨案例；
- 但每个 Beat 的功能语义必须正确；
- 不能用单案例口吻伪装成多案例拼接。

---

## G. Shot Role / Editing｜剪辑角色

建议：

- `HOOK`
- `OVERVIEW`
- `FEATURE_DETAIL`
- `ACTION_DEMO`
- `RESULT`
- `CTA`

正确画面也可能不适合当前位置。

---

# 5. 已确认的真实 Stage8 案例

这些案例必须成为长期 regression / example memory，而不是简单 whole-segment blacklist。

## 5.1 media 89

人工审片结论：

- 人物手势运动明显；
- 桌板几何变化未被证明；
- 机器 `EXTEND` 属 false positive。

应记录：

```text
PERSON_MOTION = HIGH
TABLETOP_MOTION = LOW / NOT_PROVEN
EXTEND = FAIL
RETRACT = FAIL
actual_semantics = STATIC_PRESENTATION + TABLETOP_VISIBLE
```

核心教训：

> **人物在动 ≠ 桌板在动。**

---

## 5.2 media 52

人工审片结论：

- Cross-Segment Recovery 恢复出明确抽屉向外运动；
- 可作为 `DRAWER_OPEN` 正例；
- 不是 EXTEND/RETRACT。

应记录：

```text
DRAWER_MOTION = PRESENT
before = CLOSED / RETRACTED
motion = OUTWARD
after = OPEN
DRAWER_OPEN = PASS / strong candidate
EXTEND = FAIL
```

这是当前最重要的真实动作正例之一。

---

## 5.3 media 109

人工审片结论：

- 抽屉从窗口开始就已经打开；
- 主要是人物讲解；
- 没有 closed→open 转换。

应记录：

```text
DRAWER_OPEN_STATE = TRUE
DRAWER_OPEN_ACTION = FAIL
```

---

## 5.4 media 51

人工审片结论：

- 人物讲解；
- 产品和桌面可见；
- 无明确产品结构运动。

应记录：

```text
STATIC_PRODUCT_PRESENTATION
EXTEND = FAIL
RETRACT = FAIL
```

---

## 5.5 segment 1985 / 1986

人工审片结论：

- 轨道插座 / 圆形插座模块；
- 手在操作/调节；
- 可支持 `SOCKET_ADJUST`；
- 不能支持伸缩桌面。

应记录：

```text
TRACK_SOCKET = TRUE
SOCKET_ADJUST = CANDIDATE
EXTEND = FAIL
RETRACT = FAIL
```

注意：

> 这些素材不是 BAD MATERIAL，它们只是对某些动作无效。

---

## 5.6 segment 1984

人工审片结论：

- 可以看到桌面处于已伸出状态；
- 没有明确 before→motion→after。

应记录：

```text
TABLETOP_EXTENDED_STATE = TRUE
EXTEND_ACTION = FAIL
RETRACT_ACTION = FAIL
```

---

## 5.7 segment 1

人工审片结论：

- 抽屉已打开；
- 人物讲解；
- 无明确打开过程。

应记录：

```text
DRAWER_OPEN_STATE = TRUE
DRAWER_OPEN_ACTION = FAIL
```

---

## 5.8 segment 37

人工审片结论：

- 当前证据更接近处理/关闭抽屉；
- 不应回答 `DRAWER_OPEN`。

---

## 5.9 segment 419

人工审片结论：

- 收纳空间可见；
- 无物体 outside→inside 转移。

应记录：

```text
STORAGE_PRESENT = TRUE
STORAGE_PUT_IN = FAIL
```

---

## 5.10 segment 3 / 4

人工审片结论：

- 更接近展示/拿出物体；
- 不应回答 `STORAGE_PUT_IN`。

---

## 5.11 segment 2482 / 2483 / 2484

人工审片结论：

- 人物+岛台讲解；
- 当前窗口没有明确完整 EXTEND/RETRACT；
- 不应同时被用于 EXTEND 和 RETRACT。

---

# 6. Negative Memory 必须是 Window-scoped，不是整段黑名单

Review Memory 建议字段：

```json
{
  "requested_action": "EXTEND",
  "segment_id": "1985",
  "reviewed_window_start": 2.78,
  "reviewed_window_end": 3.33,
  "review_scope": "SUBCLIP_WINDOW",
  "review_result": "BAD",
  "reason_codes": [
    "DOMINANT_VISUAL_MISMATCH",
    "NO_TABLETOP_GEOMETRY_CHANGE"
  ],
  "supports_other_semantics": [
    "TRACK_SOCKET",
    "SOCKET_ADJUST"
  ]
}
```

只有完整审完整个 Segment 才允许：

`review_scope = FULL_SEGMENT`

---

# 7. Candidate Discovery 与 Candidate Understanding 必须分开

## Candidate Discovery

回答：

> 正确素材有没有进入候选？

信号：

- PATH_HINT
- ASR
- OCR
- object label
- embedding
- existing motion
- duration
- scene
- source role

这些主要负责 Recall。

## Candidate Understanding

回答：

> 候选到底是不是这个动作？

使用：

- Qwen
- Camera Motion
- ROI Motion
- Temporal State
- Direction
- Claim Critic

---

# 8. Broad Retrieval 不允许随机10条就宣布无素材

对于 EXTEND / DRAWER / STORAGE / SOCKET：

正确漏斗：

```text
完整 broad pool
↓
全部 cheap scoring
↓
去重复 / diversity
↓
Top 30-50 temporal probe
↓
Top 10-15 temporal shortlist
↓
Top 5-10 Qwen
↓
Temporal Validator
↓
Domain Critic
↓
Top3
```

随机10可以做分布审计，但不能证明素材缺失。

---

# 9. RETRACT 不应依赖“RETRACT 文本标签”

应该先召回：

`FLEXIBLE_TABLE_MOTION_CANDIDATE`

然后时序层判断：

- 较短→较长 = EXTEND
- 较长→较短 = RETRACT
- 无变化 = STATIC
- 看不清 = UNKNOWN

---

# 10. Cross-Segment Recovery 必须保留

已证明 Segment 边界可能切断动作。

允许建立：

`MERGED_ACTION_WINDOW`

但：

- 不修改 canonical segment；
- 只是证据/生产窗口；
- 要做视觉连续性、相机连续性、对象连续性检查。

media52 已经证明 Cross-Segment Recovery 有真实价值。

---

# 11. Motion Object Attribution：核心是“谁在动”

必须区分：

- `GLOBAL_FRAME_MOTION`
- `CAMERA_MOTION`
- `PERSON_MOTION`
- `TABLETOP_MOTION`
- `DRAWER_MOTION`
- `CABINET_MOTION`
- `SOCKET_MODULE_MOTION`
- `HANDHELD_OBJECT_MOTION`

核心规则：

> **GLOBAL MOTION 不能直接升级为 Product Motion。**

---

# 12. Camera Motion 必须比平移更稳

第一层：

- Translation

如果 residual 仍高：

- Affine

高价值难例必要时：

- Homography / perspective

避免：

> 手机推近/旋转 → 桌板边缘变化 → 错判 EXTEND。

---

# 13. ROI 不能永远固定

动作中的目标会移动。

需要：

- 初始 ROI
- tracking
- periodic re-detection
- tracking confidence

可用低成本方法：

- LK feature tracking
- CSRT/KCF（如果环境已有）
- Qwen 间隔重新定位
- existing detector

第一版不需要额外下载大型 SAM。

---

# 14. Human Occlusion / Person overlap

如果手臂覆盖桌板 ROI：

不能把人的运动直接计入桌板运动。

建议记录：

- `PERSON_OVERLAP_RATIO`
- `TARGET_CORE_MOTION`
- `TARGET_EDGE_MOTION`

优先依赖目标自身边缘/几何变化。

---

# 15. 对不同对象必须有不同 Motion Analyzer

建议：

```text
TargetObjectMotionRouter
  ├─ TabletopMotionAnalyzer
  ├─ DrawerMotionAnalyzer
  ├─ CabinetMotionAnalyzer
  ├─ SocketMotionAnalyzer
  └─ ObjectTransferAnalyzer
```

不要一个通用 `roi_motion > threshold` 判断所有动作。

---

# 16. Tabletop Motion 具体合同

EXTEND：

```text
TABLETOP visible
+
camera/person-only motion excluded
+
before geometry more compact/short
+
tabletop edge/extent changes outward
+
after geometry more extended/long
```

RETRACT 反向。

静态已经展开：

只能支持 `TABLETOP_EXTENDED_STATE`。

---

# 17. Drawer Motion 具体合同

DRAWER_OPEN：

```text
drawer visible
+
before closed/less-open
+
drawer front outward displacement
+
inner depth/visibility increases
+
after more-open/open
```

DRAWER_CLOSE 反向。

---

# 18. Storage Put-In 具体合同

需要追踪：

- handheld object
- storage region

PUT_IN：

```text
outside
→ crosses boundary
→ inside
```

TAKE_OUT 反向。

如果小物体无法稳定跟踪：

> `UNKNOWN`

不能 PASS。

---

# 19. Socket 具体合同

必须区分：

- SOCKET_VISIBLE
- SOCKET_ADJUST
- SOCKET_INSERT
- SOCKET_REMOVE

手碰插座不等于插入。

1985/1986 应保留为 `SOCKET_ADJUST` 类证据。

---

# 20. Claim → Visual 具体合同

## 「上层薄抽」

必须看到：

- 上层位置
- 薄几何
- 抽屉结构

普通深抽不通过。

## 「打开就能拿到」

必须有：

- DRAWER_OPEN action
- 或至少清楚的动作边界

已打开状态不通过。

## 「轨道插座」

静态插座特写可以支持。

## 「插拔也顺手」

必须有：

- SOCKET_INSERT
- 或 SOCKET_REMOVE

静态插座不通过。

## 「来客时一拉就变宽」

必须：

- TABLETOP
- EXTEND
- target object motion
- before/after geometry change

轨道插座 close-up 直接 `DOMINANT_VISUAL_MISMATCH`。

## 「平时收起来不占位」

最好：

- before extended
- RETRACT
- after compact
- 有空间上下文

---

# 21. Atomic Claim 与 Visual Beat 必须两层同时保留

当前脚本建议视觉层压成约5个 Visual Beat：

1. Hook
2. Storage
3. Power
4. Flexible Tabletop
5. CTA

但内部仍保留细粒度 Atomic Claims。

例如 Flexible Beat：

- FUNCTION：伸缩桌面
- ACTION：一拉就变宽 / EXTEND
- ACTION_SPACE：收起来不占位 / RETRACT

一个 Visual Beat 可以使用 1-3 个镜头。

---

# 22. No Candidate 三级级联

不应一 NO_SOURCE 就直接 BLOCK。

顺序：

```text
SEARCH_MORE
↓
SEMANTIC_REWRITE
↓
DROP / BLOCK
```

例如：

原文：

> 插拔也顺手

如果没有真实插拔动作，但有静态轨道插座：

可以改为：

> 轨道插座就在手边，日常用电更方便。

前提是新文案仍有视觉证据。

---

# 23. Dedup 规则

## Hard Duplicate → P0

- same segment
- source time overlap
- 极强 pHash / exact visual duplicate
- 同一 subclip 重复使用

## Narrative Near Duplicate → P1 / rerank penalty

- same person
- same product
- same composition
- same shot role

只有多个强证据叠加才升级。

已人工确认：

- Pair01 = false positive
- Pair02 = true narrative near duplicate
- Pair03 = false positive
- Pair04 = false positive

---

# 24. Evidence Fusion 不允许简单多数票

错误：

```text
Qwen PASS
ASR PASS
Temporal FAIL
→ 2:1 PASS
```

不允许。

动作类应该使用：

## Mandatory Evidence

EXTEND/RETRACT：

1. Production source eligible
2. TABLETOP visible
3. target object motion present
4. camera/person-only motion excluded
5. direction supported
6. opposite direction absent

任意 mandatory fail：

> FAIL

## Optional Evidence

- Qwen action guess
- ASR
- OCR
- path hint
- embedding

只能提高召回/排序/置信度，不能救活 hard fail。

---

# 25. 阈值必须版本化，不可当真理

例如：

- `roi_motion_threshold`
- `edge_shift_threshold`

都只是 `PROVISIONAL`。

应该保存：

- threshold version
- calibration set
- date
- precision
- recall
- false-positive
- false-negative

---

# 26. Synthetic Test 与 Real Media Test 必须分开

## Synthetic

证明：

> 代码逻辑能运行。

## Known Real Cases

必须跑：

- 51
- 52
- 89
- 109
- 1985
- 1986

## Blind Real Set

建议：

30-50 个独立真实候选

覆盖：

- tabletop
- drawer
- socket
- storage
- static negative
- talking-head negative
- camera motion
- hard negative

然后人工审核。

---

# 27. Shadow Mode 必须先于 Enforcement

默认：

`MMVV_MODE = SHADOW`

新系统计算：

- OLD_DECISION
- NEW_DECISION
- DISAGREEMENT

但不改变当前 Production。

只有：

- known real cases 通过
- blind human review 完成
- hard negative rejection 达标
- false rejection 可接受
- 架构明确批准

才允许：

`MMVV_MODE = ENFORCEMENT`

---

# 28. Workbench 应显示多模块证据

用户点一个候选，应看到：

```text
Qwen: EXTEND
Camera Motion: LOW
Person Motion: HIGH
Tabletop Motion: LOW
State Transition: NONE
Direction: UNKNOWN
Critic: FAIL
Reason: PERSON_MOTION_ONLY
```

让系统从黑盒变成可解释。

---

# 29. Qwen Real Frame Payload 必须验证

Adapter 必须证明：

实际图像帧真的送进 Qwen。

每次调用记录：

- frame ids
- timestamps
- image hashes
- model name/version
- result id

测试：

`REAL_FRAME_PAYLOAD_VERIFIED`

不能只传：

- frame_count
- metadata
- text prompt

---

# 30. 当前不应该做

在 Real Media Validation 之前，不做：

- Pilot V3
- Stage9
- Voice/BGM正式生产
- Qwen训练
- LoRA
- 第二大 VLM
- SAM 等大型模型下载
- 全库重新扫描

---

# 31. 当前正式执行阶段

建议命名：

# `MMVV V1.1 REAL-MEDIA HARDENING`

目标：

> 先证明这套模块真的能在真实 TreeCut 视频上区分“人动”和“产品动”，而不是 synthetic demo 看起来正确。

---

# 32. Harness 具体执行指令

以下内容可直接交给 Harness：

---

## TASK

将随附单文件代码：

`TREECUT_MULTI_MODULE_VISUAL_VALIDATION_MASTER_V1.py`

映射进现有 TreeCut，不建立平行数据库，不立即启用 Production hard gate。

### A. 保留当前已完成架构

不要回滚：

- G1 ProductionSourceService
- Visual Understanding V2
- R1 opposite-direction gate
- Window-scoped Review Memory
- Cross-Segment Recovery
- Visual Beat + Atomic Claim
- NoCandidate cascade
- Dedup R7

### B. 接入映射

- `CameraMotionEstimator` → G2 temporal preprocessing
- `ROIMotionAttributor` → ActionSubclipService
- `TargetObjectMotionRouter` → 动作专用 analyzer
- `TemporalStateValidator` → TemporalActionValidator 增强
- `IslandClaimLibrary / DomainClaimCritic` → ClaimVisualMatcher
- `EvidenceFusionEngine` → ProductionQA / action consensus
- `VisualBeatGrouper` → Storyboard
- `NoCandidateResolver` → Production Planner
- `DuplicateCritic` → Dedup
- `ReviewExampleMemory` → Regression / external review memory

### C. Qwen

复用现有 Qwen2.5-VL / Ollama。

必须实际发送图像帧。

Qwen 是 `L2_QWEN`。

### D. Known Real Case 先验收

先跑：

- media51
- media52
- media89
- media109
- 1985
- 1986

预期：

#### media89
- PERSON_MOTION HIGH
- TABLETOP_MOTION LOW / NOT_PROVEN
- EXTEND FAIL

#### media52
- DRAWER_MOTION PRESENT
- DRAWER_OPEN PASS or strong UNSURE
- EXTEND FAIL

#### media109
- DRAWER_OPEN_STATE TRUE
- DRAWER_OPEN_ACTION FAIL

#### media51
- STATIC_PRODUCT_PRESENTATION
- EXTEND FAIL
- RETRACT FAIL

#### 1985/1986
- TRACK_SOCKET / SOCKET_ADJUST
- EXTEND FAIL
- RETRACT FAIL

### E. Real Evidence HTML

每个案例输出：

- input subclip
- before/mid/after
- target ROI
- person ROI
- camera motion
- target motion
- state transition
- module results
- final critic

### F. Blind Set

Known Cases 通过后再做：

- 30-50 real clips
- 人工结果提前隐藏
- 生成审核包

### G. Metrics

至少：

- target-object detection usable rate
- camera-motion false-positive rate
- person-motion false-positive rate
- state-vs-action false-positive
- action direction precision
- action direction recall
- hard-negative rejection
- Top1 usable
- Top3 contains usable

### H. Shadow Mode

默认：

`MMVV_MODE = SHADOW`

新模块不能直接改变 Production。

记录：

- OLD_DECISION
- NEW_DECISION
- DISAGREEMENT
- EVIDENCE

### I. Enforcement Gate

只有人审通过后，才允许进入 Enforcement。

### J. Tests

至少锁定：

- qwen_receives_real_frames
- camera_translation_not_product_motion
- camera_zoom_not_tabletop_extend
- person_gesture_not_tabletop_motion
- moving_roi_is_tracked
- media89_not_extend
- media52_drawer_open_candidate
- media109_open_state_not_open_action
- 1985_socket_adjust_not_extend
- mandatory_fail_cannot_be_overridden_by_optional_votes
- review_memory_is_window_scoped
- shadow_mode_does_not_change_production
- visual_beat_retains_atomic_claims
- no_candidate_search_rewrite_block
- cross_segment_window_does_not_mutate_canonical_segments

### K. 输出

生成：

- `TREECUT_MMV_REAL_CASES_V1.json`
- `TREECUT_MMV_CAMERA_MOTION_V1.json`
- `TREECUT_MMV_TARGET_ROI_TRACKING_V1.json`
- `TREECUT_MMV_OBJECT_MOTION_V1.json`
- `TREECUT_MMV_TEMPORAL_STATE_V1.json`
- `TREECUT_MMV_FUSION_RESULTS_V1.json`
- `TREECUT_MMV_DISAGREEMENTS_V1.json`
- `TREECUT_MMV_BLIND_SET_V1.json`
- `TREECUT_MMV_HUMAN_REVIEW_V1.html`
- `docs/TREECUT_MMV_REAL_MEDIA_VALIDATION_REPORT_V1.md`

### L. STOP

禁止：

- Pilot V3
- Stage9
- Voice/BGM正式生产
- Qwen训练
- 第二个大模型
- AutoPublish

完成真实视频验证后 STOP，等待人工审片。

---

# 33. 当前推荐状态

```text
G1 = PASS
Visual Understanding V2 = INTEGRATED
Candidate Discovery = PASS_WITH_LIMITATIONS
Cross-Segment Recovery = HUMAN_VALIDATED_USEFUL
MMVV = READY_FOR_REAL_MEDIA_SHADOW_VALIDATION
G2 = NEEDS_REPAIR
G3 = NEEDS_REPAIR
Dedup = NEEDS_TUNING / PROVISIONAL
Pilot V3 = BLOCKED
```

---

# 34. 成功标准

不是“模块越来越多”。

真正成功要看到：

## media89

```text
PERSON_MOTION = HIGH
TABLETOP_MOTION = LOW
EXTEND = FAIL
```

## media52

```text
DRAWER_MOTION = HIGH
CLOSED → OPEN
DRAWER_OPEN = PASS/CANDIDATE
EXTEND = FAIL
```

## 1985

```text
SOCKET_MODULE_MOTION = HIGH
TABLETOP_MOTION = LOW
SOCKET_ADJUST = PASS/CANDIDATE
EXTEND = FAIL
```

如果这些真实素材稳定成立，才说明 TreeCut 第一次拥有：

> **目标对象动作验证能力。**

然后再把它放回数百候选池进行 Candidate Discovery，才有真正意义。
