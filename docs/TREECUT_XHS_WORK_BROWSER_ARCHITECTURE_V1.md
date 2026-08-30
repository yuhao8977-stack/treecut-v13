# TreeCut XHS Work Browser — Architecture V1

- 版本：V0.1（PHASE 1 — Persistent Account Workspace Foundation）
- 日期：2026-08-30
- 状态：已实现并测试（见 `TREECUT_XHS_WORK_BROWSER_V01_IMPLEMENTATION_REPORT.md`）

---

## 1. 定位与边界

TreeCut 小红书工作浏览器 = **一个统一 XHS Work Browser**（§1A），账号通过 Workspace/Profile 隔离，**不是** B003/B007/B010 多套程序。

职责边界（§1C/D/E）：

| 层 | 职责 |
|---|---|
| Browser | 仅 Capture / Navigation / Web Action / Download；**不得**做业务判断、Content DNA、Winner 判断、AI 认知 |
| TreeCut Core | Truth / Validation / Database / Join / Asset / Segment / ASR / Cognition / DNA |
| Harness | Development / Orchestration / Audit / Report / Repair |

## 2. 技术选型（§2）

- **Runtime：Playwright + Persistent Chromium/Edge Context**（`launch_persistent_context`，`channel="msedge"` 复用本机已装 Edge，无需下载 Chromium）。
- **不使用自研 Browser Extension**：V0.1 需要的 persistent profile / tab control / download control / response observation / localhost 通信 / checkpoint recovery 由 Playwright 原生覆盖。
- **不重写现有 Browser Framework**：TreeCut 现有 `src/treecut/platform/single_instance.py`（SingleInstanceLock）直接复用于 Profile Lock（§33/34）。
- CDP 仅在后续确需时按需启用（本阶段未使用）。

## 3. 目录与数据约定（§4/28）

```
{data_root}/                       # RuntimePaths.data_root（TREECUT_DATA_ROOT）
  browser_profiles/
    B007/                          # 每账号一个物理隔离 Persistent Profile
      account_binding.json         # §9 绑定记录（无凭证）
      .profile.lock                # §33/34 Profile Lock
      ...                          # Edge user_data_dir（cookie/localStorage/cache 等，仅本地）
  config/
    xhs_work_browser.yaml          # 运行时配置（首次自动生成）
  browser/
    checkpoints/{task_id}.json     # §20 Checkpoint
    inbox/
      creator/ spotlight/ media_metadata/ published_media/ processed/ quarantine/   # §28
```

- Profile 目录**关闭后不删除**；Git 不追踪（`.gitignore` 已加 `browser_profiles/`、`*.part`、浏览器登录数据文件）。
- 仓库内 `configs/xhs_work_browser.yaml` = 默认配置模板（无敏感信息）。

## 4. 安全纪律（§5）

**禁止**写入 Git / JSON 业务报告 / 日志 / 数据库 / debug dump：
cookie、Authorization、xsec_token、session token、signed URL、完整 request headers、密码、二维码 credential。

- Profile 本身只保存在本地（`.gitignore` 双层保护）。
- 日志只记录结构化关键事件（§26），如 `19:00 B007 PROFILE_STARTED`。
- Debug logs 可临时生成、任务结束或周期后自动清理（§27），不做永久巨量保留。

## 5. 启动与登录流（§6/7）

```
用户启动 treecut-xhs-browser --workspace B007
  → 加载 config（browser_profiles/B007：存在则复用，不存在则创建）
  → acquire_lock（PROFILE_LOCKED 阻止第二实例，§33/34）
  → Local Bridge health（§17/46）
  → launch_persistent_context（固定 Edge profile）
  → Single Work Tab（§13/15/16）
  → 极简控制台（§14）
```

首次登录：状态 `CREATOR_SESSION_UNKNOWN / SPOTLIGHT_SESSION_UNKNOWN` → 打开 Creator 登录页 → **用户人工**扫码/验证码/登录；系统不自动绕过、不自动处理验证码（§7）。登录后检测真实账号（§8）。

## 6. Account Identity（§8/9/10）

- `AccountDetector` 尽力获取：platform_account_name / xiaohongshu_id（页面可安全取得时）/ current page indicator / source page / detected_at。
- **不得仅凭 Profile 目录名认定账号身份**——expected 只来自人工确认后的 Binding Record。
- 首次检测到真实账号 → 显示 Detected Account → **用户人工确认一次**（`--bind-account 昵称`）→ 保存 Binding Record（无凭证）。
- 每次启动 Identity Gate：expected（B007 绑定）vs detected（页面实际）：
  - 一致 → `ACCOUNT_IDENTITY_VALID`
  - 不一致 → `ACCOUNT_IDENTITY_MISMATCH` → **BLOCK_SYNC，不得继续任务**（绝不自动猜测/改写）。

## 7. Session 检测（§11/12）

状态：`SESSION_VALID / SESSION_EXPIRED / LOGIN_REQUIRED / SESSION_UNKNOWN`。
**页面能打开 ≠ SESSION_VALID**：基于登录态 marker vs 登录页 marker 判定；无信号 → UNKNOWN。
Session 失效 → `LOGIN_REQUIRED` 停止所有任务；用户重新登录后重跑 Identity Gate 再 Resume。

## 8. Task Engine / Checkpoint / Retry（§19-25）

- 状态机：IDLE / RUNNING / PAUSED / SUCCESS / FAILED / NEEDS_HUMAN。
- 内部步骤：START → VERIFY_SESSION → VERIFY_ACCOUNT → NAVIGATE → WAIT_READY → ACTION → VALIDATE → SAVE → COMMIT → DONE（V0.1 用 Mock handler，无真实业务 Action）。
- 每步后写 checkpoint（task_id/workspace_id/task_type/state/step/target/attempt/created_at/updated_at/last_error；无凭证）。
- **Crash Resume**：重新打开 → 发现 unfinished task → 从 Checkpoint 步骤继续，不从头重跑（at-least-once，业务幂等留 V0.2+，§30）。
- **Bounded Retry**：attempt1 normal → attempt2 延时重试 → attempt3 refresh/reset → 仍失败 FAILED/NEEDS_HUMAN；禁止无限循环。
- 错误分类：NETWORK_TIMEOUT / PAGE_LOAD_TIMEOUT / SESSION_EXPIRED / ACCOUNT_IDENTITY_MISMATCH / TREECUT_DISCONNECTED / PAGE_STRUCTURE_CHANGED / CAPTCHA_VERIFICATION / UNKNOWN_ERROR。
  - 硬停（NEEDS_HUMAN）：SESSION_EXPIRED / ACCOUNT_IDENTITY_MISMATCH / captcha / PAGE_STRUCTURE_CHANGED 且无法可靠判断。
  - 自动恢复：NETWORK_TIMEOUT / PAGE_LOAD_TIMEOUT / work tab crash（bounded retry / refresh / renavigate）。

## 9. Local Bridge（§17/18）

- `LocalBridge`：`GET {treecut_local_url}/health` → CONNECTED / DISCONNECTED。
- 断开 → `TREECUT_DISCONNECTED`，**不得继续任何未来数据 Commit**（浏览器可保持登录）；服务恢复后下次 health 自动恢复 CONNECTED。
- `LocalServiceStub`：V0.1 参考实现（Test D 与人工演示用）；真实 TreeCut Local Service 后续按 `/health` 契约接入。

## 10. 极简控制台（§13/14/31）

两个主要区域：A. TreeCut Control Panel（Tkinter） B. Single Work Tab（浏览器窗口）。
仅显示：Workspace / Creator / Spotlight / Account / TreeCut Local / Current Task / Last Checkpoint。
按钮：打开 Creator / 打开聚光 / 检查账号 / 重新检查登录 / 继续任务 / 查看错误。
无 Dashboard / 动画 / 图表；状态更新事件驱动（queue + after），不做高频轮询。

## 11. 资源与单实例（§15/16/32/33/34/35）

- Single Worker / Single Active Task / **Single Work Tab**（V0.1 禁止并发多 Tab）。
- Work Tab 崩溃自动重建（§25），Tab 数量保持 1。
- Profile Lock：同一 Workspace 同时只允许一个 Active Browser Instance（PROFILE_LOCKED）。
- 多账号兼容：目录结构支持 B003/B007/B008/B010，但 V0.1 只测试 B007，不开发并行运行。

## 12. Adapter 接口（§36/37）

统一契约 `prepare() / verify_account() / execute() / validate() / save_snapshot() / report()`。
CreatorExportAdapter / CreatorObservationAdapter / SpotlightExportAdapter / MediaRecoveryAdapter
**V0.1 全部 NOT_IMPLEMENTED**（禁止提前实现）。

## 13. 数据策略（§28-30/38-40）

- Inbox：`creator / spotlight / media_metadata / published_media / processed / quarantine`（V0.1 可空，只建目录+接口）。
- Quarantine：异常数据不得丢失，统一入 `quarantine/`（reason/source/workspace/task_id/timestamp）。
- RAW SNAPSHOT = IMMUTABLE；MEDIA ATOMIC（`<name>.part` → 完成并验证 → 最终名）；Validation Gate（Browser → Inbox → 校验 → PASS→TreeCut / FAIL→Quarantine）；Idempotency（idempotency_key 设计，业务去重 V0.2+）。

## 14. B003 迁移保护（§41）

B003 = `PAUSED_BY_BUSINESS_PRIORITY_SHIFT`；Work Browser 开发**不得**修改 B003 历史数据，Pilot1 成果保留。
V0.1 全部代码为新增模块（`src/treecut/browser/`），不触碰 Stage3A 产物。
