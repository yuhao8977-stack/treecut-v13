# TreeCut XHS Work Browser — V0.1.1 Implementation Report（Three-Tab Foundation Repair）

- 阶段：PHASE 1 基础设施修订（V0.1.1，非 V0.2；不新增业务功能）
- 日期：2026-08-30
- 前版：V0.1（Single Work Tab，已废弃）→ 本版 V0.1.1（3 Fixed Functional Tabs）
- 测试：V0.1.1 套件 35 通过（含 Edge headless 三 Tab smoke）；全量回归 250 通过
- 安全审计：PASS
- **最终状态：XHS_WORK_BROWSER_V011_PASS_WITH_LIMITATIONS**

> Test A/B/C 真实站点版本（三站真实登录、真实账号检测、真实错误账号）属**人工验收路径**：
> Harness 不接触用户登录态/凭证，系统不自动登录。V0.1.1 已把对应**机制**全部自动化验证。

---

## 1. 本版修正内容（相对 V0.1）

| # | 修订 | V0.1 | V0.1.1 |
|---|---|---|---|
| 1 | Tab 结构 | Single Work Tab（废弃） | **3 Fixed Functional Tabs**（Creator/Spotlight/Frontend）+ 1 临时弹窗 |
| 2 | Session | 单一检测 | **三站独立检测**（expired/valid/login 分层，消除已登录误报 EXPIRED） |
| 3 | 账号身份 | 单 Account | **三身份分别绑定**：Creator（XHS ID 主锚）+ Spotlight（广告账户，名字可不同）+ Frontend（未确认不假装） |
| 4 | 任务状态机 | 无页面角色 | **required_tab + SELECT_TAB 首步**（聚光任务不会跑到 Creator Tab） |
| 5 | Tab 治理 | 无 | EXPECTED=3+1 弹窗、reconcile 只关空白页（不盲目关用户页）、Tab 崩溃重建 |
| 6 | UI | 可能阻塞 | **回调线程化，UI 不阻塞**；新增**日志面板**（用户日志可见） |
| 7 | 退出 | 关闭即退 | **安全退出**按钮（释放 Lock、关闭 Context） |
| 8 | 媒体路径 | 桌面下载 | 预留 `treecut_inbox/published_media/B007/*.part`（§18，V0.1.1 不下载） |
| 9 | 硬停 | 账号类 | 新增 **expected note_id ≠ actual → HARD STOP**（绝不猜） |

## 2. §28 已知问题修复状态

| 问题 | 修复 |
|---|---|
| 登录关闭重开失败 | 机制由 smoke `persistent_profile=PASS` 验证（持久 Profile 三站同源）；真实三站登录待人工验收 |
| Creator 已登录却判 SESSION_EXPIRED | 判定改为分层：expired 强信号 > valid > login > UNKNOWN；已登录页出现"登录"字样不再误报（单测覆盖） |
| 聚光已登录却判 SESSION_EXPIRED | 同上（spotlight 独立 markers + 分层） |
| Account UNKNOWN | 三身份 Detector 独立；Creator 以 XHS ID 为主锚（昵称可改）；聚光/前台未绑定即 UNKNOWN/UNCONFIRMED（不猜测） |
| UI 出现未响应 | 回调全部线程化，queue 回投状态，Tk 主循环仅事件驱动（`minimal_dashboard._invoke`） |
| 用户日志不可见 | 新增日志面板（logging handler → 面板）；同时输出控制台与 `data_root/logs` |
| Edge --no-sandbox 警告 | 我方不传 `--no-sandbox`（playwright 默认行为）；报告记录，不做绕过 |

## 3. 交付物

| 类别 | 路径 |
|---|---|
| 架构 | `docs/TREECUT_XHS_WORK_BROWSER_ARCHITECTURE_V1.md`（内容升级为 V2 三 Tab 修订，含冻结十条原则） |
| 报告 | 本文档 |
| 配置 | `configs/xhs_work_browser.yaml`（frontend URL、expected_tab_count=3、三站 markers 含 expired） |
| 模块 | `src/treecut/browser/`：新增 `tab_manager.py`；修订 `account_detector.py`（三 Detector）、`session_detector.py`、`task_engine.py`、`workspace_manager.py`（三身份绑定）、`errors.py`（NOTE_ID_MISMATCH）、`minimal_dashboard.py`（三区块+日志+非阻塞）、`main.py`（3 Tab 启动流+smoke）、`config.py`、`checkpoint_store.py`（required_tab）、`policies.py`（媒体 inbox） |
| 测试 | `tests/test_xhs_work_browser_v01.py`（35 项，含三 Tab smoke 集成） |
| 审计 | `scripts/security_audit_xhs_browser.py`（沿用，PASS） |

## 4. 测试结果（§27 三站登录持久化验收映射）

| 验收 | 内容 | 结果 |
|---|---|---|
| 三 Tab 固定 | 3 Fixed Tabs 创建，导航不新增 Tab（不为每条视频开新 Tab） | ✅ smoke + 单测 |
| Tab 治理 | 允许 1 弹窗；超限只关空白页；用户页不盲目关闭 | ✅ smoke + 单测 |
| Tab 崩溃重建 | 关掉 Frontend Tab → rebuild → 仍 3 Tab | ✅ smoke + 单测 |
| Session 独立性 | Creator LOGIN_REQUIRED 时 Spotlight/Frontend 仍各自判定（§23） | ✅ 单测 |
| Session 误报消除 | 已登录页出现"登录"字样 → SESSION_VALID（不再 EXPIRED） | ✅ 单测 |
| 三身份绑定 | Creator（ID 锚点，昵称可改仍 VALID）/ Spotlight（单独绑定）/ Frontend（UNCONFIRMED→confirm→VALID，错号 MISMATCH） | ✅ 单测 |
| note_id 硬停 | NoteIdMismatch → NEEDS_HUMAN（绝不猜） | ✅ 单测 |
| Crash Resume | 中途 PAUSED → 新引擎从断点继续（不从 SELECT_TAB） | ✅ 单测（Test E） |
| Local Bridge | CONNECTED / DISCONNECTED / 自动恢复 | ✅ 单测（Test D） |
| Profile Lock | 第二实例 → PROFILE_LOCKED | ✅ 单测（Test F） |
| 持久 Profile | 关闭重开 localStorage 仍在（三站登录态同源机制） | ✅ smoke |
| 真实三站登录 | Creator/Spotlight/Frontend 分别登录 → 安全退出 → 重开 → 三站 SESSION_VALID | ⏳ **人工验收** |

统计：V0.1.1 套件 `35 passed`；全量回归 `250 passed`（无回归）。

## 5. 人工验收清单（用户执行）

```text
python -m treecut.browser.main --workspace B007
```

1. **三站分别登录**：三个固定 Tab（Creator / Spotlight / 前台）分别人工登录。
2. **三身份绑定**：控制台「检查状态」→
   `--bind-account 昵称`（Creator 主身份）→ `--bind-spotlight "广告ID|名称"` → `--confirm-frontend 昵称`。
3. **安全退出** → 再次启动 → **三站 SESSION_VALID**，无需重新登录（只标失效的那一站）。
4. **串号验证**：故意切错账号 → 对应站 ACCOUNT_IDENTITY_MISMATCH + BLOCK。
5. **30 分钟**：三 Tab 数量稳定、内存无明显持续增长、UI 不卡顿、日志面板可见。

## 6. 启动命令

```text
python -m treecut.browser.main --workspace B007                              # 图形控制台 + 3 固定 Tab
python -m treecut.browser.main --workspace B007 --smoke                      # headless 自检（3 Tab/持久化/收束/重建）
python -m treecut.browser.main --workspace B007 --bind-account 昵称          # Creator 主身份绑定
python -m treecut.browser.main --workspace B007 --bind-spotlight "广告ID|名称" # 聚光绑定
python -m treecut.browser.main --workspace B007 --confirm-frontend 昵称      # 前台绑定确认
```

## 7. 已知限制（PASS_WITH_LIMITATIONS 依据）

- 真实三站登录/账号检测/串号验证 = 人工验收（Harness 不接触登录态）。
- Session/身份 marker 基于常见页面文案；真实页面结构变化按 PAGE_STRUCTURE_CHANGED → Adapter Repair。
- Checkpoint 为 at-least-once（断点步骤可能重放一次）；业务级幂等留 V0.2+。
- 【同步数据】【恢复训练媒体】为占位 NOT_IMPLEMENTED（V0.1.1 不抓业务数据）。

## 8. 最终状态

**XHS_WORK_BROWSER_V011_PASS_WITH_LIMITATIONS**

（用户完成三站登录持久化 + 身份绑定 + 串号/30 分钟人工验收后，可升级为 PASS。）
