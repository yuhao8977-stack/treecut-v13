# TreeCut XHS Work Browser — V0.1.2 Implementation Report（Foundation Acceptance Patch）

- 阶段：PHASE 1 基础验收修补（V0.1.2；**不实现业务数据同步**）
- 日期：2026-08-30
- 前序真实验收：**三站真实登录持久化 PASS**（SAFE_SHUTDOWN → 重启免登录；Persistent Profile 架构 VALIDATED）
- 测试：V0.1.2 套件 37 通过（含 Edge headless smoke）；全量回归 250 通过（待确认）
- 安全审计：PASS
- **最终状态：XHS_WORK_BROWSER_V012_READY_FOR_ACCEPTANCE**

---

## 1. 本版修复内容（只修 §2 列出的 4 件事，不重构持久化）

| # | 问题（真实验收发现） | 修复 |
|---|---|---|
| 1 | 三站已登录但 Dashboard 全 UNKNOWN | **启动后自动检测**（Single Worker 串行，不要求先点按钮）；Session 检测升级为**多信号**（expired 强信号 > 登录页 URL > 功能页正信号 > 登录 marker > UNKNOWN）；marker 扩充（聚光 campaign/spend/impression 等）；Creator/聚光身份选择器扩充；[重新检测状态] 手动刷新 |
| 2 | 三身份检测与绑定 UX | 面板内**绑定按钮**：[绑定当前 Creator 为 B007] / [绑定为 B007 聚光账户]（检测到未绑定时自动启用）；Creator 以 XHS ID 为主锚（同 ID 昵称变更仍 VALID + 更新显示名）；聚光名字允许 ≠ Creator |
| 3 | 实际出现 4 个 Tab（重复 Frontend） | TabManager **role ownership 去重**（§12）：同托管域非 canonical 页 → 确认 TreeCut 创建 → 关闭；用户页（非托管域/有内容）一律不动；启动与 reconcile 均执行；严格 3 托管 Tab |
| 4 | 日志空白 + `--no-sandbox` + 英文 UI | 日志修复（insert 前临时 NORMAL）；启动事件全量入面板（面板先建、日志 handler 早挂）；**生产启动路径移除 `--no-sandbox`**（自启 Edge 参数完全可控 + CDP 接管，实证子进程命令行不再含该参数）；控制台**全中文** |

## 2. `--no-sandbox` 根因与修复（§19）

- 实证：Playwright `launch_persistent_context` 会向 Edge **注入 `--no-sandbox`**（子进程命令行可见）→ Edge 顶部出现"不受支持的命令行标志"警告。
- 修复：弃用 playwright 的 launch_persistent_context，改为 **自启 Edge**：
  `--user-data-dir=<profile> --remote-debugging-port=0 --no-first-run --lang=zh-CN`（headless 加 `--headless=new`）→ 读 `DevToolsActivePort` → `connect_over_cdp` 接管。
  参数完全由本模块控制，**生产路径不含 `--no-sandbox`**（smoke 实证 Edge 命令行无该参数）。
- 关闭顺序修正：先干净断开 CDP → taskkill 整树 → 等进程完全退出（避免 Edge SingletonLock 干扰同 Profile 立即重启；避免 playwright 后台任务残留导致退出码 1）。

## 3. Tab 治理（§11/12/13/14）

- `EXPECTED_TAB_COUNT = 3`，`allow_temporary_popup = 1`。
- `dedupe_managed()`：会话恢复/历史残留产生的同托管域重复页 → 关闭（保留 canonical）；**无法确认 ownership 的用户页不盲目关闭**（单元测试：example.com 用户页不动）。
- `reconcile()` = 去重 + 超限只关空白临时页。
- smoke 实证：`duplicate_tab_deduped=PASS` / `tab_reuse_no_new_tabs=PASS` / `tab_crash_rebuild=PASS`。

## 4. 状态检测与显示（§4/5/6/15）

启动后自动串行检测三站（不要求用户先点按钮）；结果经 queue 事件入面板：
- Creator：登录状态 / 账号昵称 / 小红书号（XHS ID）/ 账号绑定（B007）
- Spotlight：登录状态 / 广告账户 / 广告账户ID / 账户绑定（B007）
- Frontend：登录状态 / 视频浏览状态 / 绑定=**可选**（不作 B007 硬性要求；媒体身份以 note_id 为 Gate）
- TreeCut Local（未连接属允许，与站点状态**独立**）/ 当前任务（空闲）/ 上次进度（暂无）

Session 判定分层（消除误报 + 提高命中）：
`expired 强信号 → SESSION_EXPIRED` > `登录页 URL → LOGIN_REQUIRED` > `功能页正信号 → SESSION_VALID` > `登录 marker → LOGIN_REQUIRED` > `无信号 → SESSION_UNKNOWN`。

## 5. 绑定 UX（§7/8/9）

- Creator：检测到 XHS ID → 未绑定显示"待绑定"并启用 [绑定当前 Creator 为 B007]；绑定后同 ID → B007 ✅；同 ID 昵称变更 → 仍 VALID（主锚=ID）；不同 ID → MISMATCH 阻断。
- Spotlight：检测到广告账户 → [绑定为 B007 聚光账户]；名字允许 ≠ Creator；绑定后不同广告账户 → 对 paid sync HARD STOP。
- Frontend：绑定可选；不因 Viewer 账号非 B007 阻止 Published Media Recovery。

## 6. 控制台中文化（§14/15/22/23）

标题「TreeCut 小红书工作浏览器 — 工作账号 B007」；区块：创作服务平台 / 聚光后台 / 小红书前台 / TreeCut / 运行日志。
状态翻译：已登录 ✅ / 需要登录 / 登录已过期 / 状态未知 / 已确认 ✅ / 账号不匹配（已阻断）/ 待绑定 / 已连接 ✅ / 未连接 / 空闲 / 暂无。
按钮：同步数据（下一阶段，disabled）/ 恢复训练视频（下一阶段，disabled）/ 继续上次任务 / 查看异常 / 重新检测状态 / 安全退出。

## 7. 测试结果

| 项 | 结果 |
|---|---|
| 三 Tab 固定 + 重复页去重（§12） | ✅ 单测 + smoke |
| 用户页不盲目关闭 | ✅ 单测（非托管域保留） |
| Tab 复用不新增 | ✅ smoke |
| Tab 崩溃重建 | ✅ smoke |
| 持久 Profile（关闭重开） | ✅ smoke |
| Session 多信号（登录 URL 优先/误报消除/三站独立） | ✅ 单测 |
| 三身份 gate（Creator 主锚/Spotlight 单独/前台可选） | ✅ 单测 |
| note_id 不匹配硬停 | ✅ 单测 |
| Crash Resume / Local Bridge / Profile Lock | ✅ 单测 |
| `--no-sandbox` 移除 | ✅ 实证（Edge 命令行无该参数） |
| 安全审计 | ✅ PASS |

统计：V0.1.2 套件 `37 passed`；全量回归 `250 passed`（无回归）。

## 8. 真实验收清单（用户执行，§24）

A. 启动 B007 Workspace → B. 三站无需登录 → C. Dashboard 自动显示三站「已登录 ✅」
D. Creator 自动显示：昵称 + 小红书号（63083262719）→ E. Spotlight 自动显示广告账户
F. Tab 稳定为 3 → G. 日志面板有事件 → H. Edge 无 `--no-sandbox` 警告 → I. UI 操作不卡顿。
（§25：**不要**故意切 B003/B010 破坏 B007 Profile；Mismatch Gate 由自动测试覆盖。）

## 9. 最终状态

**XHS_WORK_BROWSER_V012_READY_FOR_ACCEPTANCE**

真实验收（A–I）通过后 → **XHS_WORK_BROWSER_FOUNDATION_PASS** → 才进入 V0.2 Creator Sync（本轮不实现）。
