# TreeCut Production Grade Architecture V1.0 —— 架构宪法

> 版本: V1.0 | 生效日期: 2026-08-25
> 状态: **总控指令（不可随意偏离的总架构）**
> 约束: 从本文件生效起，所有开发只能在本文档定义的架构内扩展。
> 禁止: "新需求 → 随意新增独立模块/表/规则"的开发模式。

---

## 一、最终产品定义

TreeCut 只有一个最终目标：

> 输入一份视频脚本 + 可选参考声音 → TreeCut 理解脚本 → 从素材库寻找合适镜头 → 排列镜头 → 生成配音 → 匹配 BGM → 生成字幕 → 编排完整时间线 → 自动质检 → 输出 MP4 和可编辑剪映草稿 → 接收人工修改 → 从人工选择中学习。

```
脚本
 ↓
脚本理解
 ↓
分镜规划
 ↓
镜头需求
 ↓
素材语义检索
 ↓
Top-K 候选
 ↓
智能排序
 ↓
重复控制
 ↓
连续性优化
 ↓
完整镜头序列
 ↓
声音克隆/TTS
 ↓
字幕
 ↓
BGM
 ↓
SFX/特效
 ↓
多轨时间线
 ↓
渲染
 ↓
自动 QA
 ↓
人工修改
 ↓
反馈学习
 ↓
下一次更准确
```

**唯一优先级判断标准：**
以后所有功能开发都必须回答一个问题——

> 它是否让这条链路**更准确、更稳定、更快**？

如果答案是否定的，就不是当前优先级。

---

## 二、十条"架构宪法"（禁止违反）

### 宪法 1：一个大脑，不是一张大表

TreeCut 逻辑上只有一个：**TreeCut Brain**。
底层允许不同专业数据表，但：

```
以前：模块A自己搞一套 / 模块B自己搞一套 / 模块C自己搞一套

以后：所有模块 → Service Layer → 统一数据模型 → 统一身份 → 统一版本
```

用户看到的是一个大脑，程序内部可以有多个功能区。

### 宪法 2：Asset 负责"文件"，Segment 负责"生产"

**Asset** = 完整原视频（如 `A000123`，E:/素材/客户案例/001.mp4，时长 58 秒）
**Segment** = 真正用于剪辑的片段（如 `S000123-04`：asset=A000123, start=12.4s, end=16.8s, 语义=伸缩岛台展开, 镜头=人物侧身演示, 功能=伸缩, 价值=高）

- **Asset 不直接参加自动剪辑**
- **自动剪辑必须以 segment_id 为核心**
- 审计已证实：Phase5 仍是 Asset 级选材、粗剪才用 Segment——**必须统一**

### 宪法 3：原始检测永远不能被 AI 认知覆盖（三层严格分层）

```
L1 机器证据  → 不能改（ASR/OCR/CLIP 原始输出）
L2 AI 认知   → AI 理解结果（产品/功能/尺寸）
L3 人工裁决  → 人工确认/修正
```

- 三层历史全部保留
- **绝对禁止**：人工一修改就把原 AI 结果覆盖掉

### 宪法 4：所有 AI 判断必须有版本

任一 AI 结果至少记录：
`model_version` / `prompt_version` / `knowledge_version` / `algorithm_version` / `created_at`

审计已确认：大量 ASR/OCR/accuracy 结果**不具备完整版本追踪**，必须补齐。

### 宪法 5：脚本绝对不能直接拿去关键词搜素材

正确方式：

```
Script → Script Interpreter → Beat → Storyboard Requirement → Segment Retrieval
```

例：脚本"80平的小家，千万别急着塞一套餐桌"
- ❌ 错误：提取 "80平/小家/餐桌" 去搜索
- ✅ 正确：理解 Beat Type=Hook+Problem / 用户=小户型装修用户 / 问题=空间不足 / 叙事目的=制造空间冲突 / 所需镜头=小户型整体空间或收起状态岛台或空间前后对比
- **禁止**：工厂机器、材质特写、无空间关系镜头

### 宪法 6：自动选材永远先 Top-K，再决策

禁止"搜一下 → 拿第一名"。

```
一个脚本 Beat → 检索 Top-K → 候选验证 → 重排 → 选择
```

例：Beat 03 → Candidate 1..5（89.2 / 86.5 / 84.1 / 80.2 / 78.9）
这样才能有：自动替换 / 人工选择 / 偏好学习 / 局部重生成 的基础。

### 宪法 7：一个镜头"自己很好"不等于"放进去很好"

必须同时计算两种分数：

**单镜头分**：semantic_score / quality_score / business_score / hook_score / novelty_score / preference_score
**相邻镜头分**：scene_continuity / person_continuity / product_continuity / motion_continuity / color_continuity / shot_size_rhythm

最终选择不能是 Slot1 最高分 + Slot2 最高分 + Slot3 最高分，而必须是**整条视频总体最优**。
审计确认：六类连续性和全局序列优化**全部不存在**。

### 宪法 8：素材使用必须有"记忆"

每次生成记录：

| 字段 | 含义 |
|---|---|
| segment_id | 用过的片段 |
| visual_cluster_id | 视觉相似组 |
| production_id | 哪条视频 |
| account_id | 哪个账号 |
| script_beat | 哪个 Beat |
| used_at | 何时 |
| usage_count | 用了几次 |
| cooldown_until | 冷却到何时 |

正式表：**shot_usage**
解决：连续 10 条视频反复出现相同镜头。当前无 Segment 使用历史、reuse cooldown、视觉近重复机制。

### 宪法 9：反馈不能直接变永久规则

反馈状态机：

```
FEEDBACK → OBSERVATION → CANDIDATE → VALIDATED → ACTIVE → RETIRED
```

- 单次反馈 = 经验（仅限该上下文）
- 多次重复反馈 = 候选规律
- 独立盲测验证 = 稳定规则

审计：当前 237 条规则约 96% 来自单样本且存在明显冲突，必须按此状态机管理。

### 宪法 10：任何自动生产都必须经过 QA 闸门

```
Render → Production QA → PASS → Final Output
```

QA 至少检查：黑帧 / 无音频 / 音频削波 / 字幕越界 / 字幕遮挡 / 视频比例 / 重复镜头 / 近重复镜头 / 脚本覆盖率 / 镜头语义匹配 / 音画同步 / 配音字幕同步 / 隐私 / 敏感表达 / 平台规则
当前这一层**基本全部不存在**。

---

## 三、最终系统组织结构（固定八层）

```
┌──────────────────────────────┐
│ L8  Human & Learning         │ 人工反馈 / 偏好学习 / 经验记忆
├──────────────────────────────┤
│ L7  Production QA            │ 技术QA / 语义QA / 合规QA
├──────────────────────────────┤
│ L6  Timeline & Render        │ 视频/配音/BGM/字幕/SFX/FX
├──────────────────────────────┤
│ L5  Director Engine          │ 候选排序 / 连续性 / 全局排镜
├──────────────────────────────┤
│ L4  Script Intelligence      │ 脚本理解 / Beat / Storyboard
├──────────────────────────────┤
│ L3  Business Cognition       │ 产品/功能/价值/行业知识
├──────────────────────────────┤
│ L2  Segment Cognition        │ 每个镜头的语义与动作
├──────────────────────────────┤
│ L1  Perception               │ ASR/OCR/CLIP/Scene/Keyframe
├──────────────────────────────┤
│ L0  Asset Infrastructure     │ Asset/Segment/文件/任务/版本
└──────────────────────────────┘
```

---

## 四、数据主干（正式认定 19 个核心对象）

| # | 对象 | 职责 |
|---|---|---|
| 1 | **assets** | 完整视频身份，**唯一 Source of Truth** |
| 2 | **media_files** | 磁盘文件发现表，保留但**不再作为业务主身份** |
| 3 | **segments** | 真正剪辑单位：segment_id/asset_id/start_ms/end_ms/algorithm_version/active/created_at |
| 4 | **semantic_annotations** | Segment 业务认知：segment_id + scene/product/material/function/action/shot_type/people_presence/product_visibility/quality/content_role/business_value + confidence/model_version/knowledge_version |
| 5 | **knowledge_entries** | 行业知识（知识节点，非 39 条词典） |
| 6 | **knowledge_relations** | 知识关系：伸缩岛台 IS_A 岛台 / HAS_FUNCTION 伸缩 / SOLVES 多人就餐 / REQUIRES_SHOT 完整伸缩动作 |
| 7 | **script_projects** | 一次脚本生产项目 |
| 8 | **script_beats** | 脚本拆分 |
| 9 | **shot_candidates** | 每个 Beat 对应候选 Segment |
| 10 | **shot_usage** | 历史镜头使用 |
| 11 | **visual_clusters** | 近重复素材分组 |
| 12 | **production_runs** | 每一次生产 |
| 13 | **timeline_items** | 统一时间线 |
| 14 | **feedback_events** | 人工反馈事件 |
| 15 | **preference_pairs** | Context + preferred/rejected |
| 16 | **production_qa** | 成片 QA |
| 17 | **model_registry** | 模型版本 |
| 18 | **prompt_registry** | 提示词版本 |
| 19 | **schema_migrations** | 数据库版本 |

---

## 五、"一个大脑"的 Service Layer

以后 UI 和 CLI 不允许直接操作数据库业务。

```
CLI ─────┐
UI ──────┼→ Service Layer → Database
未来Web ─┘
```

服务清单：
AssetService / PerceptionService / CognitionService / KnowledgeService / ScriptService / RetrievalService / RankingService / SequenceService / AudioService / TimelineService / QAService / LearningService / EvaluationService

换界面不伤核心业务。

---

## 六、真正的学习体系（不再把 learning_rules 当大脑）

```
人工行为 → Feedback Event → Episodic Memory → Preference Pair
→ 经验检索 → 候选知识 → 规则验证 → Preference Ranker → 模型/排序能力提升
```

- 前期**不训练大模型**：RAG 经验 → Preference ranking → Learning-to-rank
- 数据足够后：LoRA / Fine-tune

---

## 七、联网学习属于 Knowledge Layer，不允许直接改代码

```
搜索 → 来源评级 → 提取知识 → 多来源验证 → Candidate Knowledge
→ 人工/规则审核 → Release → Embedding → 正式使用
```

- **绝对禁止**：网上看到什么直接变成永久规则
- 平台规则设置 **TTL**（如 30 天），过期重新联网核验

---

## 八、声音与 Timeline 最终架构

一条视频至少拥有：

| 轨 | 内容 |
|---|---|
| V1 | 主视频 |
| V2 | Overlay / B-roll |
| A1 | Voice |
| A2 | BGM |
| A3 | SFX |
| T1 | Subtitle |
| FX1 | Effects |

统一 **Timeline Engine**，控制：start_ms / end_ms / duration / volume / speed / transition / subtitle / effect / source

---

## 九、声音克隆

```
Reference Voice → Speaker Profile → Voice Clone/TTS → Narration.wav
→ Forced Alignment → Word Timing
```

- 必须使用**有授权的参考声音**
- 记录：speaker_profile_id / voice_model_version / reference_audio

---

## 十、字幕（正确链路）

```
原脚本 + 最终配音 → Forced Alignment → 字/词级时间 → 字幕断句 → 字幕布局
```

**不是**再拿 ASR 重新识别一遍。

---

## 十一、BGM

建立 **music_library**：bgm_id / path / bpm / mood / energy / style / beats / duration / usage_count

脚本分析（内容类型/情绪/节奏/镜头平均长度）决定 BGM；配音出现时自动 **Ducking** 降低 BGM。

---

## 十二、第一镜头单独建立 Hook Engine

Hook 评分（开头不能与普通镜头同一评分系统）：

| 维度 | 权重 |
|---|---|
| 脚本相关 | 25 |
| 视觉冲击 | 20 |
| 结果/变化 | 20 |
| 用户痛点 | 15 |
| 清晰度 | 10 |
| 历史数据表现 | 10 |

有真实发布数据后加入：3 秒留存 / 5 秒留存 / 完播 / 互动 / 私信。

---

## 十三、Evaluation 必须分三套数据（永久固定）

- **Calibration Set** —— 用于调整
- **Validation Set** —— 开发验证
- **Holdout Test Set** —— 最终考试（**不能参与任何规则设计**）

防止 TreeCut "背答案"。

---

## 十四、最终生产成熟目标

不看写了多少代码，看：**给 20 条真实脚本 → 第一次自动生成**。

| 指标 | 第一阶段生产级目标 |
|---|---|
| Script Beat 人工认可 | ≥90% |
| Top-5 存在可用镜头 | ≥90% |
| 第一推荐直接接受 | ≥75% |
| 镜头语义匹配 | ≥90% |
| 明显重复镜头 | <5% |
| 严重跳镜 | <10% |
| 配音字幕同步 | ≥98% |
| 技术 QA 通过 | ≥99% |
| 无需整条推翻 | ≥90% |
| 人工修改时间 | ≤30-60 分钟 |

---

## 总控指令（本文件生效即开始执行）

1. `assets` 是视频素材唯一 Canonical Asset。
2. `media_files` 只负责文件发现，不再作为业务主身份。
3. `segment_id` 是自动生产的最小单位。
4. 自动生产禁止直接以完整 asset 作为镜头选择单位。
5. 原始机器结果、AI 认知结果、人工裁决严格分层，禁止相互覆盖。
6. AI 结果必须记录 model/prompt/knowledge/algorithm version。
7. UI/CLI 不得继续直接承载业务逻辑，逐步统一进入 Service Layer。
8. 所有数据库改动必须通过 migration。
9. 禁止删除、移动、重命名或覆盖原始视频素材。
10. 禁止自动删除旧数据库表；旧链路必须采用兼容迁移。
11. 禁止人工反馈直接成为永久规则。
12. 所有生产必须经过 QA Gate。
13. 每个 Phase 必须：先备份 → migration → tests → regression → 文档 → Git 提交 → rollback 说明。
14. 未通过当前 Phase 验收，禁止进入下一 Phase。

---

*本宪法为 TreeCut 长期软件系统建设的总约束。所有开发只能在此架构内扩展。*
