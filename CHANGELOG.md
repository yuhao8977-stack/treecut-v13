# TreeCut v13 Changelog

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
