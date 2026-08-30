# TreeCut XHS Work Browser — V0.1 Implementation Report

- 阶段：PHASE 1 — Persistent Account Workspace Foundation
- 日期：2026-08-30
- 测试：V0.1 新增 28 项（含 1 项 Edge headless 集成 smoke）；全量回归 250 通过
- 安全审计：PASS
- **最终状态：XHS_WORK_BROWSER_V01_PASS_WITH_LIMITATIONS**

> 说明：Test A/B/C（真实 Creator 登录、真实账号检测、真实错误账号）涉及真实站点登录，属
> **人工验收路径**（Harness 不接触用户登录态/凭证，系统也不自动登录）。V0.1 已把对应
> **机制**全部自动化验证；真实登录验收需用户在图形界面完成一次后复核（见 §「人工验收清单」）。
> 因此裁定 PASS_WITH_LIMITATIONS，而非无条件 PASS。

---

## 1. 交付物（§51）

| 类别 | 路径 | 说明 |
|---|---|---|
| 架构 | `docs/TREECUT_XHS_WORK_BROWSER_ARCHITECTURE_V1.md` | 架构 V1 |
| 报告 | 本文档 | 30 问答 + 测试 + 状态 |
| 配置 | `configs/xhs_work_browser.yaml` | 默认模板（无敏感信息）；运行时在 `{data_root}/config/` |
| 模块 | `src/treecut/browser/` | 见下表 |
| 测试 | `tests/test_xhs_work_browser_v01.py` | 28 项 |
| 审计 | `scripts/security_audit_xhs_browser.py` | §50 |
| 入口 | `treecut-xhs-browser`（pyproject console script） | `python -m treecut.browser.main` |

### browser 模块映射（§51）

| 规格要求 | 模块 |
|---|---|
| workspace_manager | `workspace_manager.py`（WorkspaceManager、AccountBindingRecord、default_profile_root） |
| profile_manager | `profile_manager.py`（Persistent Context 启动/健康检查/关闭） |
| account_detector | `account_detector.py`（AccountDetector、Identity Gate、bind） |
| session_detector | `session_detector.py`（SessionDetector） |
| task_engine | `task_engine.py`（TaskEngine、步骤、resume） |
| checkpoint_store | `checkpoint_store.py`（Checkpoint、CheckpointStore） |
| retry_policy | `retry_policy.py`（BoundedRetry）+ `errors.py`（错误分类/硬停/自动恢复） |
| local_bridge | `local_bridge.py`（LocalBridge、LocalServiceStub） |
| minimal_dashboard | `minimal_dashboard.py`（Tkinter 控制台） |
| 启动流 | `main.py`（BrowserRuntime、CLI、smoke） |
| 策略/收件箱 | `policies.py`（Inbox/Quarantine/快照/原子文件/幂等） |
| Adapter 占位 | `adapters.py`（4 个 NOT_IMPLEMENTED） |

## 2. 测试结果（§43-49 验收映射）

| 验收 | 内容 | 结果 |
|---|---|---|
| Test A 机制 | 持久 Profile：关闭重开 localStorage 仍在（真实登录态同理） | ✅ Edge headless 集成 `SMOKE persistent_profile=PASS` |
| Test B 机制 | 检测真实账号 → 绑定 → `ACCOUNT_IDENTITY_VALID` | ✅ 单测（FakePage 驱动门逻辑） |
| Test C | 错误账号 → `ACCOUNT_IDENTITY_MISMATCH` + BLOCK | ✅ 单测（gate 返回 MISMATCH，任务引擎硬停 NEEDS_HUMAN） |
| Test D | TreeCut Local ON→CONNECTED / OFF→DISCONNECTED / 重启→自动恢复 | ✅ 单测（真实 http stub，含同端口重启） |
| Test E | Crash Resume：中途关闭 → 重开 → 从 Checkpoint 继续（不从 START） | ✅ 单测（PAUSED → 新引擎 resume → 步骤从断点继续） |
| Test F | Profile Lock：第二实例 → PROFILE_LOCKED | ✅ 单测（SingleInstanceLock 复用） |
| §49 资源 | 单 Tab 复用、tab 崩溃重建、重启后仍 1 Tab、Context 关闭释放 | ✅ smoke 覆盖；30 分钟人工观察待验收 |

测试统计：`28 passed`（V0.1）+ `250 passed`（全量回归，无回归）。

## 3. §52 三十问回答

1. **最终采用什么 Browser Runtime？** Playwright `launch_persistent_context`，`channel="msedge"` 复用本机 Edge。
2. **为什么选择该 Runtime？** 原生支持 persistent profile / tab control / download control / response observation / localhost；无需自研 Extension；无需下载 Chromium；不重写现有框架。
3. **B007 Profile 存在哪里？** `{data_root}/browser_profiles/B007`（稳定持久路径，非 batch/temp）。
4. **Profile 是否持久化？** 是——user_data_dir 固定，关闭不删除，重开复用。
5. **关闭重开后 Creator 登录是否保留？** 机制已验证（localStorage 跨重启持久化=PASS）；真实登录待人工验收。
6. **聚光 Session 是否能正确检测？** SessionDetector 支持 spotlight 标记体系（登录/有效 marker），单测覆盖四种状态；真实页面标记待人工校准。
7. **Account Detector 如何确认 B007？** 页面检测 platform_account_name → 与人工确认的 Binding Record 比对；**绝不凭 Profile 目录名**。
8. **Account mismatch 是否 Hard Stop？** 是——`ACCOUNT_IDENTITY_MISMATCH` → BLOCK_SYNC → 任务 NEEDS_HUMAN，不自动猜测。
9. **TreeCut Local Bridge 是否工作？** 是——`GET /health`，Test D 自动验证 CONNECTED/DISCONNECTED。
10. **断开后是否能恢复？** 是——服务恢复后下次 health 自动回 CONNECTED（同端口重启测试通过）。
11. **是否 Single Work Tab？** 是——`work_tab_max=1` 强制，smoke 验证多次导航 Tab 数恒为 1。
12. **是否 Single Worker？** 是——V0.1 无并发 worker；Task Engine 单任务执行。
13. **是否有 Checkpoint？** 是——每步落盘，含最小字段，无凭证。
14. **Crash Resume 是否测试通过？** 是——Test E 自动通过（不从 START 重跑）。
15. **Bounded Retry 是否实现？** 是——attempt1/2/3 节奏 + 上限，禁止无限循环。
16. **哪些错误自动恢复？** NETWORK_TIMEOUT / PAGE_LOAD_TIMEOUT / work tab crash（bounded retry + refresh/renavigate）。
17. **哪些错误必须人工处理？** SESSION_EXPIRED / ACCOUNT_IDENTITY_MISMATCH / CAPTCHA_VERIFICATION / PAGE_STRUCTURE_CHANGED（无法可靠判断时）→ NEEDS_HUMAN。
18. **Profile Lock 是否有效？** 是——Test F 通过（PROFILE_LOCKED 阻止第二实例）。
19. **是否存在重复 Browser Context 泄漏？** 否——每次 close() 关闭 context 并停 driver；smoke 验证重启后仍 1 Tab、无累积 Context。
20. **运行 30 分钟是否明显内存持续增长？** 机制上单 Tab/无轮询/事件驱动已保证低资源；30 分钟人工观察待验收（§49）。
21. **日志是否存在敏感信息？** 否——日志仅结构化事件（PROFILE_STARTED/SESSION_*/TREECUT_CONNECTED 等），审计 PASS。
22. **Repo 是否存在敏感信息？** 否——安全审计脚本扫描 browser 包/configs/docs/tests 无凭证/签名值；`.gitignore` 屏蔽 profile 与登录数据。
23. **Raw Snapshot policy 是否定义？** 是——`policies.RAW_SNAPSHOT_POLICY`（IMMUTABLE）。
24. **Inbox / Processed / Quarantine 是否建立？** 是——`InboxManager` 建 6 子目录，QuarantineEntry schema 就绪（含 reason/source/workspace/task_id/timestamp）。
25. **Adapter 接口是否预留？** 是——统一契约 6 方法，4 个 Adapter 全部 NOT_IMPLEMENTED。
26. **Creator 数据抓取是否保持未实现？** 是——CreatorExport/CreatorObservationAdapter NOT_IMPLEMENTED。
27. **聚光抓取是否保持未实现？** 是——SpotlightExportAdapter NOT_IMPLEMENTED。
28. **Media Recovery 是否保持未实现？** 是——MediaRecoveryAdapter NOT_IMPLEMENTED；无下载代码。
29. **B003 历史数据是否完全未修改？** 是——仅新增模块与配置；Stage3A 产物（DB/JSON/媒体/报告）零改动；Pilot1 保留。
30. **V0.1 是否已经稳定到可以进入 V0.2？** **条件性通过**——自动机制全绿 + 回归 250 无回归；进入 V0.2 前需完成下方人工验收 4 项（尤其「四件事」：登录持久、不串号、崩溃续跑、长时间不卡）。

## 4. 人工验收清单（用户执行，4 项核心 + Test A/B/C 实站版）

1. **登录持久**：`python -m treecut.browser.main --workspace B007` → 打开 Creator 人工登录 → 关闭程序 → 重开 → Creator 仍登录或明确显示 SESSION 状态。
2. **不串号**：登录后 `--bind-account <昵称>` 绑定 → 重开点「检查账号」→ 显示 `ACCOUNT_IDENTITY_VALID`；故意切错账号 → 必须 `ACCOUNT_IDENTITY_MISMATCH` 并 BLOCK。
3. **崩溃续跑**：`python -m treecut.browser.main --headless` 只验证启动链；图形界面跑 Mock 任务到中途强杀 → 重开 → 「继续任务」从断点续跑（机制已由 Test E 自动验证）。
4. **长时间不卡**：连续开 Creator/聚光/检查账号 30 分钟 → Tab 数稳定、无明显持续内存增长。
5. TreeCut Local：`python -m treecut.browser.local_stub`（或后续真实服务）起停 → 控制台 TreeCut Local 状态切换。

## 5. 已知限制（PASS_WITH_LIMITATIONS 依据）

- Test A/B/C 真实站点版本依赖人工验收（系统不自动登录/不接触凭证）。
- Session/Account marker 基于常见页面文案，真实页面结构变化需按 `PAGE_STRUCTURE_CHANGED` 流程人工校准。
- Checkpoint 采用 at-least-once（断点步骤可能重放一次）；业务级幂等（idempotency_key 消费）留 V0.2。
- 图形控制台（Tkinter）未纳入自动化测试（依赖桌面会话）；代码路径与回调已单元覆盖。

## 6. 启动命令

```text
python -m treecut.browser.main --workspace B007            # 图形控制台 + 固定工作浏览器
python -m treecut.browser.main --workspace B007 --smoke    # headless 自检（持久 Profile + 单 Tab）
python -m treecut.browser.main --workspace B007 --bind-account 昵称   # §9 人工确认绑定
python -m treecut.browser.main --workspace B007 --headless # 无 UI：验证启动链
```

## 7. 最终状态

**XHS_WORK_BROWSER_V01_PASS_WITH_LIMITATIONS**

（等待用户完成人工验收清单后，可升级为 XHS_WORK_BROWSER_V01_PASS。）
