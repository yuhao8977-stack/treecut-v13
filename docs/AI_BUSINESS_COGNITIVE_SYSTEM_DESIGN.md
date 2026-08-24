# TreeCut AI Business Cognitive System V1.0 技术设计文档

- **版本**：V1.0（设计稿）
- **日期**：2026-08-24
- **定位**：让 TreeCut 从"视觉识别工具"升级为"懂家具行业、懂小红书内容、懂账号目标、懂素材价值的 AI 运营助手"
- **关联**：docs/P2.5_ARCHITECTURE_DESIGN.md、docs/P2.7_QUALITY_VALIDATION_UI_DESIGN.md（本系统在既有分析链路之上构建）

---

## 1. 系统目标

### 现状（识别工具）
```
视频 → 识别画面 → 输出标签
```

### 目标（运营助手）
```
视频素材 → 基础感知 → 行业理解 → 内容理解 → 账号理解
        → 商业判断 → 模板匹配 → 生产决策 → 人工反馈学习 → 能力增长
```

**最终能力**：看见一个视频 → 理解里面是什么 → 判断商业价值 → 判断适合什么账号 → 判断适合什么内容模板 → 判断如何生产 → 根据人工反馈不断修正。

---

## 2. 七层认知架构

```
                ┌─────────────────────────────────┐
   Layer 7      │  人工运营经验层（Feedback）      │ ← 反馈学习，反哺所有层
                ├─────────────────────────────────┤
   Layer 6      │  模板生产理解层（Template）      │ ← 素材→爆款结构
                ├─────────────────────────────────┤
   Layer 5      │  账号DNA理解层（Account）        │ ← 账号目标→价值偏好
                ├─────────────────────────────────┤
   Layer 4      │  内容运营理解层（ContentType）   │ ← 案例/产品/工厂/避坑/设计
                ├─────────────────────────────────┤
   Layer 3      │  行业知识理解层（Industry）      │ ← 家具行业知识库（核心）
                ├─────────────────────────────────┤
   Layer 2      │  AI视觉理解层（Vision）          │ ← 场景语义/动作/镜头价值
                ├─────────────────────────────────┤
   Layer 1      │  机器基础感知层（Perception）    │ ← ffprobe/ASR/OCR/检测
                ├─────────────────────────────────┤
   Layer 0      │  素材资产层（Asset）             │ ← 资产/状态/重复/价值
                └─────────────────────────────────┘
```

**设计原则**：
1. **增量构建**：Layer 0-2 已有（P2.5/P2.6 完成），本系统重点构建 Layer 3-7
2. **数据驱动**：每层输出结构化数据，下层为上层提供输入，反馈层反哺全部
3. **不与现有系统冲突**：新增表/模块，不改既有分析结果

---

## 3. 分层数据模型设计

### Layer 0：素材资产层（已有，扩展）

现有 `assets` 表已含：asset_id/文件路径/大小/时长/分辨率/hash/分析状态。**新增**：

```sql
-- 素材业务状态（已有 asset_status，扩展 business_score 字段）
ALTER TABLE asset_status ADD COLUMN business_score INTEGER DEFAULT 0;  -- 商业评分 0-100
ALTER TABLE asset_status ADD COLUMN content_type TEXT DEFAULT '';     -- 内容类型（Layer4 输出）
ALTER TABLE asset_status ADD COLUMN account_fit TEXT DEFAULT '';      -- 适配账号（Layer5 输出）
```

**状态机**（已有）：未分析 → 分析中 → 已分析 → 人工审核 → 高价值/低价值/废弃/损坏

### Layer 1：机器感知层（已有）

| 能力 | 现有实现 | 数据 |
|---|---|---|
| 视频信息 | ffprobe（probe 阶段） | assets.duration/fps/分辨率/编码 |
| 人物/空间/产品检测 | P2/P2.5 视觉流水线 | segments/keyframes |
| ASR | faster-whisper（GPU） | transcripts |
| OCR | RapidOCR | ocr_text |

**本层无需新建，直接消费现有数据。**

### Layer 2：AI 视觉理解层（扩展）

在现有 segments/keyframes/transcripts/ocr_text 之上，新增**语义理解输出**：

```sql
CREATE TABLE IF NOT EXISTS scene_semantics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id      TEXT NOT NULL,
    segment_id    TEXT,                      -- 可空（整段语义）
    semantic      TEXT NOT NULL,             -- 场景语义：工厂生产/客户入户/产品展示/施工安装…
    action        TEXT NOT NULL DEFAULT '',  -- 动作：打开抽屉/展开岛台/展示材质/介绍尺寸…
    lens_value    INTEGER NOT NULL DEFAULT 0,-- 镜头价值 0-100（开场吸引/产品展示/细节/成交）
    confidence    REAL NOT NULL DEFAULT 0,
    model_version TEXT NOT NULL DEFAULT '',
    created_time  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scene_sem_asset ON scene_semantics(asset_id);
```

**生成方式**：基于现有 ASR 文本 + OCR 文本 + 关键帧视觉特征，通过规则引擎（V1）+ 后续 LLM 视觉（V2）生成。

### Layer 3：行业知识层（核心新增）

知识库目录结构（`TreeCut_AI_Brain/`）：

```
TreeCut_AI_Brain/
├── industry/          # 行业定义
├── product/           # 产品知识
├── material/          # 材料知识
├── scene/             # 场景知识
├── content_type/      # 内容类型规则
├── account/           # 账号 DNA
├── template/          # 爆款模板
├── evaluation/        # 评分标准
└── feedback/          # 人工经验（数据库）
```

**知识库数据表**（版本化，可热更新）：

```sql
CREATE TABLE IF NOT EXISTS knowledge_entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    domain       TEXT NOT NULL,      -- industry|product|material|scene|content_type|account|template|evaluation
    category     TEXT NOT NULL,      -- 一级分类
    name         TEXT NOT NULL,      -- 知识点名称
    aliases      TEXT NOT NULL DEFAULT '',  -- 别名/关键词（JSON 数组）
    description  TEXT NOT NULL DEFAULT '',  -- 说明
    keywords     TEXT NOT NULL DEFAULT '',  -- 触发关键词（JSON 数组）
    weight       REAL NOT NULL DEFAULT 1.0, -- 匹配权重
    version      TEXT NOT NULL DEFAULT '1.0',
    active       INTEGER NOT NULL DEFAULT 1,
    updated_time REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_knowledge_domain ON knowledge_entries(domain, category);
```

**行业知识示例**（详见 §4 知识库文本）：
- 岛台 = 开放式厨房独立功能台（操作/储物/就餐/社交）
- 岩板 = 高端定制卖点（高级感/耐磨/空间设计）
- 内容类型判断规则：客户姓名+城市+户型 → 客户案例；尺寸+材质+功能 → 产品介绍；机器+工人+加工 → 工厂实力

### Layer 4：内容运营层

```sql
CREATE TABLE IF NOT EXISTS content_classification (
    asset_id      TEXT PRIMARY KEY,
    content_type  TEXT NOT NULL,   -- 客户案例|产品介绍|工厂实力|装修方案|避坑知识
    sub_type      TEXT NOT NULL DEFAULT '',  -- 如 客户案例+产品介绍（组合）
    confidence    REAL NOT NULL DEFAULT 0,
    reasons       TEXT NOT NULL DEFAULT '',  -- 判断依据（JSON：命中的关键词/特征）
    model_version TEXT NOT NULL DEFAULT '',
    reviewed      INTEGER NOT NULL DEFAULT 0, -- 人工确认
    created_time  REAL NOT NULL
);
```

**判断规则**（V1 规则引擎，基于 ASR/OCR/路径关键词）：
| 内容类型 | 触发特征 | 目的 |
|---|---|---|
| 客户案例型 | 客户姓名+城市+户型+完工 | 建立信任 |
| 产品介绍型 | 尺寸+材质+功能 | 展示产品价值 |
| 工厂实力型 | 机器+工人+生产 | 降低顾虑 |
| 装修方案型 | 户型+空间规划+设计 | 吸引装修用户 |
| 避坑知识型 | 不要这样做/避坑/注意 | 获取搜索流量 |

### Layer 5：账号 DNA 层

```sql
CREATE TABLE IF NOT EXISTS account_dna (
    account_id    TEXT PRIMARY KEY,      -- 如 "kunbao_daotai"（坤宝岛台）
    account_name  TEXT NOT NULL,
    goal          TEXT NOT NULL DEFAULT '',  -- 账号目标：装修客户获客
    content_prefs TEXT NOT NULL DEFAULT '',  -- 内容偏好（JSON）
    high_value    TEXT NOT NULL DEFAULT '',  -- 高价值特征（JSON 关键词）
    mid_value     TEXT NOT NULL DEFAULT '',
    low_value     TEXT NOT NULL DEFAULT '',
    created_time  REAL NOT NULL
);
```

**坤宝岛台 DNA 示例**：
```json
{
  "account": "坤宝岛台",
  "goal": "装修客户获客",
  "content_prefs": ["客户案例", "尺寸展示", "功能展示", "收纳展示", "真实空间"],
  "high_value": ["客户案例", "尺寸展示", "功能展示", "收纳展示", "真实空间", "真人", "痛点解决"],
  "mid_value": ["材质介绍", "工厂展示"],
  "low_value": ["纯生产过程", "无产品说明", "纯空镜"]
}
```

**账号适配度计算**（Layer 5 输出）：`account_fit = Σ(命中的 high_value 权重) - Σ(命中的 low_value 权重)`，归一化 0-100。

### Layer 6：模板生产层

```sql
CREATE TABLE IF NOT EXISTS content_templates (
    template_id   TEXT PRIMARY KEY,    -- 001 客户案例 / 002 工厂实力 / 003 产品介绍 / 004 避坑
    template_name TEXT NOT NULL,
    content_type  TEXT NOT NULL,       -- 对应 Layer4 类型
    structure     TEXT NOT NULL,       -- 时间轴结构（JSON）
    slot_rules    TEXT NOT NULL DEFAULT '',  -- 槽位素材要求（JSON）
    cta           TEXT NOT NULL DEFAULT '',  -- 结尾行动号召
    version       TEXT NOT NULL DEFAULT '1.0',
    active        INTEGER NOT NULL DEFAULT 1
);
```

**模板 001：客户案例模板**：
```json
{
  "template_id": "T001",
  "name": "客户案例模板",
  "structure": [
    {"t": "0-3s",   "role": "结果展示",   "slot": "完工实景+客户反馈"},
    {"t": "3-13s",  "role": "客户背景",   "slot": "城市+户型+需求"},
    {"t": "13-33s", "role": "功能卖点",   "slot": "产品细节+功能演示"},
    {"t": "33-40s", "role": "CTA",        "slot": "咨询引导"}
  ]
}
```

**模板匹配**：根据素材的 content_type + account_fit + 镜头价值 → 推荐可用模板 + 槽位填充建议。

### Layer 7：反馈学习层

现有 `human_feedback` 表已捕获 AI vs 人工差异。**扩展为学习信号**：

```sql
-- 扩展 human_feedback：增加 error_type（错误类型）
ALTER TABLE human_feedback ADD COLUMN error_type TEXT DEFAULT '';
-- 新增经验表
CREATE TABLE IF NOT EXISTS learning_rules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,      -- 触发场景
    ai_output     TEXT NOT NULL,      -- AI 原判断
    human_output  TEXT NOT NULL,      -- 人工修正
    error_type    TEXT NOT NULL,      -- 误判类型（标签错/漏检/误检/价值误判）
    rule          TEXT NOT NULL DEFAULT '',  -- 提炼的修正规则
    weight        REAL NOT NULL DEFAULT 1.0, -- 规则权重
    applied_count INTEGER NOT NULL DEFAULT 0,
    created_time  REAL NOT NULL,
    updated_time  REAL NOT NULL
);
```

**学习闭环**：
```
人工修正 → error_type 归类 → 提炼规则 → 更新知识库权重/规则引擎 → 下次判断更准
```

---

## 4. 家具/岛台行业知识库 V1.0（基础文本）

### 4.1 行业定义
- **行业**：定制家具行业
- **产品**：厨房岛台
- **目标用户**：装修家庭（购买阶段：装修设计 → 厨房规划 → 全屋定制）

### 4.2 岛台产品知识
**定义**：开放式厨房中独立于墙体的功能台，用途：操作/储物/就餐/社交。

**核心卖点**：
| 卖点 | 关键词 | 视觉特征 |
|---|---|---|
| 空间利用 | 小户型/空间优化/动线/开放式厨房 | 客餐厨一体、岛台居中 |
| 收纳 | 抽屉/薄抽/隐藏收纳/分类收纳 | 抽屉开合、薄抽细节 |
| 功能 | 插座/充电/办公/吃饭/备餐 | 轨道插座、隐藏电器 |
| 颜值 | 岩板/高级感/极简/轻奢 | 岩板台面、无把手设计 |

### 4.3 内容判断规则
| 出现特征 | 判断 |
|---|---|
| 客户姓名+城市+户型+完工照片 | 客户案例 |
| 尺寸+高度+宽度+材质+功能 | 产品介绍 |
| 机器+工人+加工+生产 | 工厂实力 |
| 不要这样做+避坑+注意 | 知识内容 |

### 4.4 小红书运营价值判断
- **高价值**：至少满足 2 个（真人/真实空间/产品细节/功能解决方案/用户痛点）
- **低价值**：纯空镜/纯工厂/无解释画面

### 4.5 最终输出示例
```
素材: 001.mp4
AI理解: 浙江客户家潘多拉岩板岛台案例
内容类型: 客户案例+产品介绍
适合账号: 坤宝岛台
推荐模板: 客户案例模板001
商业价值: 92分
原因: 真人+真实家庭+尺寸+功能展示
```

---

## 5. 模块与目录设计

```
src/treecut/
├── cognitive/                    # 认知体系（新增）
│   ├── __init__.py
│   ├── brain.py                  # 认知引擎入口（串行调用各层）
│   ├── industry.py               # Layer3 行业知识引擎
│   ├── content.py                # Layer4 内容分类引擎
│   ├── account.py                # Layer5 账号DNA引擎
│   ├── template.py               # Layer6 模板引擎
│   └── learning.py               # Layer7 反馈学习引擎
├── quality_validation/           # 已有（P2.7）
├── feedback_learning/            # 已有（P2.7）
└── knowledge/                    # 知识库数据（新增）
    ├── industry_tags.json        # 已有基础标签（P2.7）
    └── TreeCut_AI_Brain/         # 认知知识库（§3 Layer3）
        ├── industry/ product/ material/ scene/
        ├── content_type/ account/ template/ evaluation/
        └── feedback/
```

**CLI 入口**（main.py 新增）：
```
--brain-analyze ASSET_ID     # 对单素材运行完整认知链
--brain-status               # 认知体系状态
--brain-knowledge reload     # 热加载知识库
--account-register           # 注册账号 DNA
--template-register          # 注册模板
```

---

## 6. Phase 实施计划

### Phase 0：数据库与知识库基座（3-5 天）
- [ ] 建 cognitive 相关表（scene_semantics / knowledge_entries / content_classification / account_dna / content_templates / learning_rules）
- [ ] TreeCut_AI_Brain 目录结构 + 知识库 JSON 种子数据（基于 §4 文本）
- [ ] 知识库加载/校验/热更新机制
- **验收**：`--brain-status` 显示各表就绪，知识库可查询

### Phase 1：行业知识引擎（4-6 天）
- [ ] Layer3 规则引擎（关键词匹配 + 权重）
- [ ] 基于 ASR/OCR/路径的行业特征抽取
- [ ] 行业知识→语义标签映射
- **验收**：对 100 素材生成行业语义，人工抽检准确率 ≥70%

### Phase 2：AI 判断层（5-8 天）
- [ ] Layer4 内容分类引擎（客户案例/产品/工厂/避坑/设计）
- [ ] Layer5 账号 DNA + 适配度计算
- [ ] Layer6 模板匹配 + 槽位建议
- [ ] Layer2 场景语义（基于 ASR+OCR 规则 V1）
- **验收**：单素材全链路输出（§4.5 格式），人工确认可修正

### Phase 3：UI（4-6 天）
- [ ] 认知结果展示面板（素材→内容类型→账号适配→模板推荐→商业评分）
- [ ] 人工修正入口（继承 P2.7 UI 风格）
- **验收**：运营人员可日常使用，反馈进入数据库

### Phase 4：反馈学习（3-5 天）
- [ ] 人工反馈→error_type 归类
- [ ] 规则提炼 + 知识库权重更新
- [ ] 学习效果评估（反馈前后准确率对比）
- **验收**：连续 500 条反馈后，分类准确率提升 ≥10%

### Phase 5：自动生产链路（6-10 天）
- [ ] 模板→素材槽位→粗剪→成片 自动链路
- [ ] 与 P2.6 输出模块（jianying/mp4）集成
- [ ] 批量生产 + 质量门禁
- **验收**：从素材库自动生成符合模板的成片

**总工期**：约 25-40 天（单人）

---

## 7. 技术选型

| 组件 | 选择 | 说明 |
|---|---|---|
| 数据库 | SQLite（沿用） | 单机便携，WAL 已启用 |
| 知识库 | JSON + SQLite | JSON 可版本化编辑，SQLite 存活跃规则 |
| 判断引擎 V1 | 规则引擎（Python） | 关键词+权重，可解释、可热更 |
| 判断引擎 V2 | LLM 视觉（可选） | 接入 Qwen-VL 提升语义理解（P2.6 已预留 models/vision_qwen） |
| 反馈学习 | 规则提炼 + 权重调整 | 不做黑盒模型，保持可解释 |
| UI | tkinter（沿用） | 与 P2.7 质量审核 UI 统一 |

---

## 8. 与现有系统集成

| 现有能力 | 认知体系消费方式 |
|---|---|
| assets/media_files | Layer 0 资产基础 |
| segments/keyframes | Layer 1/2 视觉特征 |
| transcripts（ASR） | Layer 2/3/4 语义与关键词 |
| ocr_text | Layer 2/3 文字特征（尺寸/材质/卖点） |
| labels/asset_types | Layer 3/4 标签基础 |
| human_feedback | Layer 7 反馈源 |
| asset_quality（100分） | Layer 5/6 价值基础 |
| P2.6 输出模块 | Phase 5 生产链路 |

**兼容性保证**：全部新增表/模块，不修改既有表结构（除 §3 标注的 2 个 ALTER ADD COLUMN，均加默认值向后兼容）。

---

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 规则引擎准确率不足 | V1 规则 + V2 LLM 双引擎，人工反馈持续调优 |
| 知识库覆盖不全 | 版本化 + 热更新，运营可自行补充 |
| OCR 竞态等历史问题影响语义 | 先修复再构建（P2.7 已修复 OCR 竞态） |
| 反馈数据不足 | P2.7 质量审核 UI 先行收集，认知系统直接消费 |
| 过度设计 | 每 Phase 有明确验收标准，先跑通再优化 |
