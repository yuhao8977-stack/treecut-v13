# TreeCut v13 Changelog

## [13.5.15] - 2026-08-25 — Phase 6 内容价值评估系统 + 账号DNA固化

### 背景
100 条人工审核完成（71 条内容确认 + 20 条商业评分）。用户决策：不进入自动生产，
先建立内容价值判断层（"什么素材值得用于生产"）。

### 新增
- **`cognitive/value.py`**（新）：`ContentValueEngine`
  - 五维评分 100 分：用户价值25 / 产品卖点25 / 信任价值20 / 传播价值20 / 转化价值10
  - 内容类型基准分锚定（客户案例75/产品介绍63/功能展示50/产品展示45/其他10）
  - 低价值惩罚：空洞话术封顶40 / 空镜按类型区分 / 承诺句式检测
  - 防误判：繁简归一化 + 品牌水印过滤（坤宝岛台/品控）
  - 素材池分类 ABCD（A直接生产/B需组合/C备用/D低价值）
  - `content_value` 表 + 批量评分 + 池统计
- **`main.py`**：`--value-run N`（批量评分）/ `--value-status`（池统计）
- **文档**：
  - `ACCOUNT_DNA_V1.md` — 账号 DNA 固化（高/低价值特征/爆款结构/不推荐内容）
  - `PHASE6_CONTENT_VALUE_DESIGN.md` — Phase6 设计稿（等待审核）

### 验证（100 条测试集）
- 价值评分 vs 人工评分相关系数 **0.631**
- 高/低分级一致率 **90%（18/20）**
- 空洞素材（人工10分）正确归 C 类；高价值素材（人工90分）正确归 A 类

### 路线确认
账号DNA → **内容价值模型**（本 Phase）→ 模板 → 自动生产（暂缓，等待价值系统确认）

## [13.5.14] - 2026-08-24 — 第一轮业务校准（P0 重构）

### 背景
20 条人工审核暴露核心认知缺陷：内容类型一致率 5%（1/20），AI 把工厂产品讲解视频一律判为客户案例。
用户批准 P0 修复（9 条规则中的 P0 部分），不继续扩大测试集。

### 内容类型系统 V2（P0-1/P0-2）
- **双层结构**：`content_type_main`（主体）+ `content_elements`（元素），替代单标签
- **证据机制**：客户案例需 ≥2 强证据（完工/实景/入户/前后对比/客户反馈）
- **反向排除**：女士/小姐/委托/定制 → 仅"客户案例背景"元素，不构成案例证据
- **内容意图判断**：有实质讲解（ASR≥12字）+ 产品词 → 产品介绍优先
- **多模态信号**：ASR + OCR + 路径（产品类/空镜）+ CLIP 视觉标签（function 优先）
- **繁简归一化**：繁体 ASR 转简体再匹配
- **置信度 V2**：`0.45+0.45×主分/(主分+次高分)`，消除 0.52 锁定

### 商业评分 V2（P0-3）
- 5×20 维度：真实性/产品价值/用户价值/内容传播/成交价值
- 账号 DNA 调节：纯工厂空镜 ×0.35，空镜无产品 ×0.5
- 人工校准基准：客户案例≈75 / 产品介绍≈63 / 功能展示≈50

### 验证结果（20 条，人工结果未动）
- 内容类型一致率：**5% → 80%**（客户案例误判 19→0）
- 置信度区分度：0.52 锁定 → 0.66-0.84
- 商业平均偏差：38 → 22.4（方向修正，需二次校准）

### 变更文件
- `cognitive/industry.py` — V2 分类 + 证据机制 + 元素 + 繁简 + 视觉信号
- `cognitive/template.py` — 商业评分 V2 + 模板置信度门槛
- `cognitive/store.py` — content_elements 列（幂等迁移）
- `cognitive/brain.py` / `accuracy.py` — V2 字段传递
- 文档：`CONTENT_TYPE_V2_DESIGN.md` / `BUSINESS_SCORE_V2_DESIGN.md` / `FIRST_ROUND_FIX_REPORT.md`

## [13.5.13] - 2026-08-24 — AI 业务理解能力验证（Accuracy Validation）

### 新增：准确率验证体系（用户指定：验证 AI 是否接近真实小红书家具运营判断）

- **`cognitive/accuracy.py`**（新）：`AccuracyEngine`
  - `accuracy_test` / `accuracy_review` 两表（asset_id UNIQUE，人工逐项审核）
  - `build_test_set()`：100 条随机测试集（客户案例20/产品介绍20/工厂实力20/装修方案15/避坑知识15/低质量10），
    配额不足从全量素材随机补足（无人工筛选）
  - `analyze_asset()`：ABCD 四段式 AI 分析（A 事实 / B 业务理解 / C 小红书适配 / D 商业 5×20）
  - `compute_accuracy()`：内容类型30%+模板30%+产品20%+商业20%；目标 内容类型≥85% / 模板≥80% / 商业偏差≤15
  - `top_errors()` / `knowledge_gaps()` / `self_baseline()`：TOP20 错误、知识缺口、无人工审核时可量化的自基线
  - `generate_report()`：`docs/TREECUT_AI_ACCURACY_REPORT.md`（环境/分类统计/交叉表/置信度/错误模式/缺口/计划）
- **`cognitive/accuracy_ui.py`**（新）：AI Accuracy Review UI（tkinter 三栏：素材信息+视频 / AI ABCD / 人工逐项审核）
  - 人工修正自动写入 `learning_rules`（Phase 5 学习），不修改任何 AI 分析结果
- **`main.py`**：新增 `--accuracy-build` / `--accuracy-run N` / `--accuracy-report` / `--accuracy-ui`

### 验证首轮基线发现（不调整结果，只记录）

- AI 判定仅覆盖 3 类（产品介绍/客户案例/工厂实力）；装修方案/避坑知识/低质量 为随机 fallback 素材，
  期望分类与真实内容错位，需人工审核后重评
- 置信度锁定 0.47：命中 1 词即 0.4+0.12×1，乘工厂权重 0.9 反向压低，规则无区分度
- 约 20% 素材 ASR 为繁体，简体关键词库命中率低
- 工厂实力 20 条中 AI 误判客户案例 3 / 产品介绍 2；产品未识别 41 条

### 文档

- `docs/TREECUT_AI_ACCURACY_REPORT.md` — 首轮 AI 自基线验证报告（待人工审核回填）

## [13.5.12] - 2026-08-23 — 认知体系全链路 + 优化

（Phase 0-5 认知系统、视觉补认知、生产链路等，见 13.5.12 提交）

## [13.5.11] - 2026-08-22 — P2.5 并行分析引擎

### 新增：多 Worker 任务调度系统（P2.5）

- **`library/task_store.py`**（新）：`analysis_tasks` 任务表 + `schema_version` 版本表
  - `BEGIN IMMEDIATE` 原子领取，多 Worker 绝无双领（16 项单元测试 + 2 进程 200 任务并发验证通过）
  - 任务状态机：pending → processing → completed | failed | skipped
  - 失败重试（≤3 次）、失联任务回收（recover_stale）、启动时兜底回收（recover_all_processing）
  - 幂等创建（UNIQUE(asset_id, task_type)）、迁移前自动备份
- **`analysis/worker_p25.py`**（新）：P2.5 阶段 Worker
  - 复用现有 SceneDetector / KeyframeExtractor / WhisperEngine / OcrEngine
  - 幂等护栏：已 DONE/SKIPPED 跳过；PROCESSING 占用标记 occupied 不抢
  - 每 Worker 独立日志（worker_id/asset_id/stage/耗时/结果）
- **`analysis/worker_pool.py`**（新）：多进程 Worker 池（spawn）
  - 默认 3 Worker 分片：视觉(scene+keyframe) / ASR / OCR
  - 修复 P1 pool 缺陷：`queue.get()` 加超时 + 进程存活检测 + close 时 terminate
- **`analysis/scheduler.py`**（新）：任务调度器
  - `sync_from_state()`：扫描未完成阶段幂等生成任务（已完成自动跳过）
  - 旧进程互斥：检测到旧 P2 正在处理时默认不抢跑（可 `--p2.5-force`）
- **`main.py`**：新增 `--p2.5-run` / `--p2.5-workers` / `--p2.5-stages` / `--p2.5-force` / `--p2.5-status`（旧参数全部保留）

### 文档

- `docs/P2.5_UPGRADE_AUDIT.md` — 架构审计（只读）
- `docs/P2.5_ARCHITECTURE_DESIGN.md` — 调度系统设计
- `docs/DATABASE_MIGRATION.md` — 数据库迁移
- `docs/WORKER_POOL_DESIGN.md` — Worker 池设计
- `docs/PERFORMANCE_REPORT.md` — 性能基准（3 Worker 1.47×，大任务量预期 2-3×）

### 测试

- `tests/test_task_store.py`（16 项：迁移幂等/原子领取防双领/重试/恢复/日志）
- `tests/test_claim_multiprocess.py`（2 进程 200 任务并发无双领）

### 兼容性

- 不修改任何既有表结构；不修改 `p2_worker.py` 旧逻辑；运行中旧 P2 进程（`--p2-run`）不受影响
- 数据库仅新增 `analysis_tasks` / `schema_version` 两表（幂等 CREATE IF NOT EXISTS）
