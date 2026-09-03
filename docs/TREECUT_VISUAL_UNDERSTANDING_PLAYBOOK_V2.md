# TreeCut Visual Understanding V2 — 具体视觉理解、分支判断与实现手册

## 0. 这版与上一版的差别

上一版 TVRC 主要给了“架构骨架”。

这一版把**具体看什么、怎么判断、什么算支持、什么不算支持、当前视频里每种典型错误到底是什么**全部拆出来，并附可执行 Python 与单元测试。

它仍然不包含 OpenAI/ChatGPT 的专有模型权重、内部视觉网络或隐藏推理；它提供的是**可外显、可复现的审片规则、视觉语义知识、时序状态机和当前视频负样本**。

---

# 1. 我对当前 G2/G3 审核视频的具体理解

## 1.1 1985 / 1986：不是“伸缩动作”

### 画面
核心主体是：
- 岛台侧面的轨道插座；
- 圆形插座模块；
- 手在触碰/旋转/调节插座模块。

### 可以支持
- `TRACK_SOCKET`
- `SOCKET_MODULE`
- `POWER_FUNCTION_VISIBLE`
- 若连续画面能确认旋转/移动，可候选 `SOCKET_ADJUST`

### 不能支持
- `EXTEND`
- `RETRACT`
- “来客时一拉就变宽”
- “平时收起来不占位”

### 为什么
视觉中心完全是电源模块，不是桌板几何变化。

因此不只是“分数低”，而应该是：
`DOMINANT_VISUAL_MISMATCH → P0 REJECT`

---

## 1.2 1984：能证明“桌面处于伸出状态”，不能证明“正在伸出”

### 画面
工厂全景，木色桌面明显伸出。

### 可以支持
- `TABLETOP`
- `TABLETOP_EXTENDED_STATE`
- “有伸缩/延伸结构”的弱功能证据

### 不能支持
- `EXTEND action`
- `RETRACT action`

除非同一 subclip 内明确看到：
`收起/较短 → 运动 → 伸出/较长`

### 核心规则
`STATE != ACTION`

这是当前 TreeCut 最重要的一个视觉理解原则。

---

## 1.3 2482 / 2483 / 2484：人物+产品展示，不足以证明伸缩方向

### 画面
黄色衣服人物站在岛台旁讲解/比划；桌面和产品可见。

### 可以支持
- `PERSON`
- `ISLAND`
- `TABLETOP`
- 产品介绍/讲解镜头
- 若能看到延伸结构，可支持 `FLEXIBLE_TABLE_FUNCTION candidate`

### 当前选窗不能稳定支持
- `EXTEND`
- `RETRACT`
- “一拉就变宽”
- “收起来不占位”

### 关键
如果人物手势很大，但桌板几何没有改变，不能把“人物动作”误当成“产品动作”。

---

## 1.4 Segment 1：抽屉已经打开 ≠ 打开抽屉

### 画面
人物在抽屉旁，抽屉已经处于打开状态。

### 支持
- `DRAWER`
- `DRAWER_OPEN_STATE`
- 收纳空间存在

### 不支持
- `DRAWER_OPEN action`

### 必须看到
`关/较闭 → 抽屉向外移动 → 打开`

---

## 1.5 Segment 37：可能更接近关抽屉/处理抽屉，不应给 DRAWER_OPEN

如果现有 L2 已经给 `DRAWER_CLOSE`，而请求是 `DRAWER_OPEN`：

**在 TopK 前直接 reject。**

不需要再让第二模型“猜一次”。

---

## 1.6 Segment 419：空的开放式收纳，不等于“放进去”

### 画面
柜体/抽屉处于打开状态，内部可见。

### 支持
- 收纳结构存在
- 柜体/抽屉开放状态

### 不支持
- `STORAGE_PUT_IN`
- `STORAGE_TAKE_OUT`

除非有物体的位置转移。

---

## 1.7 Segment 3 / 4：展示/拿取 ≠ 放入

如果连续画面是：
`物体从抽屉里出来 → 到手里`

就是 `STORAGE_TAKE_OUT`。

即使脚本想要“收纳小物”，也不能反转动作方向说它是 `PUT_IN`。

---

# 2. 视觉理解必须拆成 7 条支线

## 支线 A｜Object
画面里到底有什么：
- 岛台
- 桌板
- 抽屉
- 上层薄抽
- 轨道插座
- 水槽
- 柜门
- 电器区
- 人物

这是静态视觉最适合做的层。

---

## 支线 B｜State
对象现在是什么状态：
- 桌板已伸出
- 桌板已收回
- 抽屉已打开
- 抽屉已关闭
- 柜门已开
- 插座可见

State 不能自动升级 Action。

---

## 支线 C｜Action
必须看时间：
- EXTEND
- RETRACT
- DRAWER_OPEN
- DRAWER_CLOSE
- PUT_IN
- TAKE_OUT
- SOCKET_INSERT
- SOCKET_REMOVE
- SOCKET_ADJUST

要求：
`before → motion → after`

---

## 支线 D｜Direction
动作方向必须显式判断。

高价值反向对：
- EXTEND ↔ RETRACT
- OPEN ↔ CLOSE
- PUT_IN ↔ TAKE_OUT
- INSERT ↔ REMOVE

如果候选明确是反向：
**P0 Hard Reject**

---

## 支线 E｜Claim Support
同一个画面可以支持 A，但不能支持 B。

例：
- 看到岩板 → 支持材质候选；
- 不自动支持“耐高温”；
- 看到抽屉 → 支持抽屉存在；
- 不自动支持“静音滑轨”；
- 看到轨道插座 → 支持插座存在；
- 不自动支持“插拔顺手”。

---

## 支线 F｜Story / Continuity
如果脚本是单案例：
- 产品
- 场景
- 人物
- 案例
要尽量连续。

如果脚本是信息流 Montage：
可以跨案例，但每个 Beat 的功能语义必须正确。

---

## 支线 G｜Shot Role / Editing
一个正确视觉也可能不适合当前位置。

Shot Role：
- HOOK
- OVERVIEW
- FEATURE_DETAIL
- ACTION_DEMO
- RESULT
- CTA

结尾 CTA 不应复用前面高度相似的抽屉人物镜头。

---

# 3. 当前 8 个最重要的确定性硬闸

1. `requested EXTEND && observed RETRACT → REJECT`
2. `requested RETRACT && observed EXTEND → REJECT`
3. `DRAWER_OPEN && observed DRAWER_CLOSE → REJECT`
4. `PUT_IN && observed TAKE_OUT → REJECT`
5. `action claim && only static state → REJECT/UNKNOWN`
6. `filename/path hit && no visual proof → cannot support`
7. `ASR/OCR says action && no visual motion → cannot support`
8. `core claim && no valid candidate → REWRITE/DROP/BLOCK`

这些规则比多跑几百次 Qwen 更应该先落地。

---

# 4. 为什么 G3 的 16 Beat 切法不对

当前句子被切成：
- 第一
- 上层薄抽
- 收纳小物不弯腰
- 打开就能拿到

这四个文本原子可以作为 Claim，
但不应该强迫系统换四次镜头。

应该分两层：

## Atomic Claim
用于事实校验。

## Visual Beat
用于剪辑。

推荐当前脚本压成 5 个视觉 Beat：
1. Hook
2. 收纳
3. 电源
4. 伸缩
5. CTA

这样才能让画面稳定、减少跳切和重复。

---

# 5. Claim→Visual 的具体合同

## “上层薄抽”
必须看到：
- 抽屉在上层；
- 厚度明显偏薄；
- 是抽屉结构。

普通深抽：
不通过。

## “打开就能拿到”
必须：
- 有打开动作；
- 或至少前后状态清楚；
- 内容区域可见。

## “轨道插座”
静态特写就可以。

## “插拔也顺手”
必须：
- 插入/拔出动作；
- 手接触不够。

## “一拉就变宽”
必须：
- 桌板；
- before较短/收起；
- 运动；
- after变宽/伸出。

## “收起来不占位”
理想：
- before展开；
- retract；
- after紧凑；
- 最好还有空间全景。

---

# 6. 模型应该怎么配合

## 第一层：Cheap retrieval
- path
- ASR/OCR
- embedding
- object labels

只负责找可能候选。

## 第二层：Qwen
看候选画面：
- object
- state
- scene
- rough action

是 L2。

## 第三层：Temporal analyzer
连续帧识别：
- before
- motion
- after
- direction
- completeness

## 第四层：TVRC
把“候选看起来像”变成：
- PASS
- FAIL
- UNSURE
并给 reason code。

## 第五层：Human L3
只审：
- 模型冲突；
- WEAK；
- 高价值难例；
- 新类型。

---

# 7. 当前不要做什么

- 不要立刻 LoRA Qwen；
- 不要把 20 个样本扩成几千帧就说训练量变大；
- 不要让 TVRC 自己变 Ground Truth；
- 不要把模型同意模型当准确率；
- 不要为了“有候选”强行把错画面塞进去。

---

# 8. 后续真正的学习路线

### Phase 1
规则 + 时序 + Critic
用当前负样本修 bug。

### Phase 2
积累 100–300 个独立 Segment 级 L3。

### Phase 3
训练轻量动作方向分类器 / preference ranker。

### Phase 4
如果仍有明显上限，再做 LoRA 或第二 VLM ensemble。

---

# 9. 这版代码如何用

随包：
- `TREECUT_VISUAL_UNDERSTANDING_ENGINE_V2.py`
- `TREECUT_VISUAL_SEMANTIC_KB_V1.json`
- `test_treecut_visual_understanding_engine_v2.py`

Harness 不应整文件复制后平行建立新系统，而应把：
- TemporalActionValidator → 接到 ActionSubclipService
- IslandClaimLibrary / DomainVisualCritic → 接到 ClaimVisualMatcher
- DuplicateCritic → 接到 ProductionDedup
- VisualBeatGrouper → 接到 Script→Storyboard
- NoCandidateResolver → 接到 Production Planner

---

# 10. 人工验收标准保持不变

G2：
- Hard negative rejection = 100%
- Top3 contains usable ≥85%
- Top1 usable ≥70%
- boundary usable ≥80%

G3：
- P0 core mismatch = 0
- Top3 suitable ≥90%
- Top1 suitable ≥80%
- unsupported core claim pass = 0

没有达到，不进入 Pilot V3。
