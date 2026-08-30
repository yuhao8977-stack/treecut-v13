# TreeCut XHS Work Browser — Architecture V2（三工作页稳定架构修订）

- 版本：V0.1.1（THREE-TAB FOUNDATION REPAIR，基础设施修订，无业务功能新增）
- 日期：2026-08-30
- 前版：Architecture V1（Single Work Tab）——**正式废弃**（§2 修订）
- 状态：已实现并测试（见 `TREECUT_XHS_WORK_BROWSER_V011_IMPLEMENTATION_REPORT.md`）

---

## 1. 核心定义（冻结）

> **TreeCut XHS Work Browser = Account Workspace + Persistent Profile + Three Fixed Functional Tabs + Single Worker + Local TreeCut Bridge。**

```
B007 Workspace
└── Persistent Browser Profile：B007（browser_profiles/B007/）
    ├── Tab 1：Creator 创作服务平台（creator.xiaohongshu.com）
    ├── Tab 2：Spotlight 聚光后台（ad.xiaohongshu.com）
    └── Tab 3：Xiaohongshu 小红书前台（www.xiaohongshu.com）
    └── TreeCut Local 控制台（本机）
```

三个 Tab 共用同一个 B007 Profile，但 **Session 分别检测**（§6）。

## 2. 对 V1 的正式修正（§二/三十五）

废弃：`一个 Workspace + 一个 Persistent Profile + 一个 Work Tab`。
采用：`一个 Workspace + 一个 Persistent Profile + 三个固定 Work Tabs`。
理由：单 Tab 反复跳转会导致——Creator 当前页面状态被覆盖、聚光筛选状态被覆盖、
视频播放与数据采集频繁互切、Session 检测混乱、恢复任务时重复导航。

## 3. 三个 Tab 的职责与 Truth（§三/四/五）

| Tab | 域名 | 职责 | Truth 类型 |
|---|---|---|---|
| Creator | creator.xiaohongshu.com | 账号身份（XHS ID/昵称/粉丝）+ 已发布笔记（note_id/标题/时间/类型/duration/cover）+ Creator 表现（曝光/观看/CTR/赞藏评/完播…） | 内容身份与内容表现 Truth |
| Spotlight | ad.xiaohongshu.com | Campaign/广告组/单元/Creative/投放时间/消耗/展现/点击/CTR/CPC/CPM/私信/留资/转化成本 | 投流表现 Truth（Paid Performance Context） |
| Frontend | www.xiaohongshu.com | 真实笔记播放页（explore/{note_id}）→ 真实 MP4/Media Resource → Published Media Recovery | 真实发布媒体 Truth |

## 4. 三个页面 ≠ 三套登录系统（§六/七）

- 仍是**一个 B007 Workspace**、**一个 Profile**，三者共同保存在 `browser_profiles/B007/`。
- 三站 Session **分别检测**：`Creator / Spotlight / Frontend` 各自 VALID / LOGIN_REQUIRED / UNKNOWN。
- 某站失效只重登该站；不得因 Creator 已登录就认为其余两站一定登录。
- 首次：三 Tab 分别人工登录 → 安全退出 → 下次启动恢复三站（登录态由持久 Profile 保留）。

## 5. 三身份绑定（§八/九/十/十一）

| 身份 | 字段 | 绑定规则 |
|---|---|---|
| Creator Identity | XHS ID + Display Name | **主身份锚点**：XHS ID 不变 → 仍为 B007（昵称可改）；人工确认一次 |
| Spotlight Identity | Ad Account ID + Name | **单独绑定**：名字允许与 Creator 不一致，人工确认"这个广告账户就是 B007 的聚光账户" |
| Frontend Identity | User ID + Name | **单独绑定**：可与 Creator 不一致；检测不到 → 仅 FRONTEND_SESSION_VALID，Binding=UNCONFIRMED，绝不假装已确认（视频能播放 ≠ 账号正确） |

全部绑定到 `workspace_id = B007`；绑定记录（account_binding.json）**不含任何凭证**。

## 6. 技术选型（沿用 V1）

Playwright + Persistent Chromium/Edge Context（`channel="msedge"`，免下载 Chromium）；
复用 `treecut/platform/single_instance.py` 做 Profile Lock；不重写现有框架。

## 7. Tab 管理（§13/14/15/16/25/26）

- `EXPECTED_TAB_COUNT = 3`；允许 `temporary_popup = 1`（平台自弹，处理完立即关闭）。
- 三个 Tab 长期固定，任务之间只改网址（如 Frontend：首页 → explore/noteA → …），**不为每条视频开新 Tab**。
- `reconcile()`：Tab 数 > 预期+弹窗时，只关闭**空白临时页**（about:/newtab）；有真实内容的页面（用户页/平台弹窗）**绝不盲目关闭**。
- Tab 崩溃 → `rebuild(role)` 重建对应功能 Tab（§25 自动恢复），仍保持 3 Tab。
- 健康检查按事件触发（打开时/切换后/任务开始前/响应变化后/用户点检查），**不做每秒轮询**（§26）。

## 8. 任务引擎（带页面角色，§22）

```
任务 = {task_type, target, required_tab: CREATOR|SPOTLIGHT|FRONTEND, idempotency_key}
步骤：SELECT_TAB → VERIFY_SESSION → VERIFY_IDENTITY → NAVIGATE → WAIT_READY
      → ACTION → VALIDATE → SAVE → CHECKPOINT → DONE
```
- 聚光任务不会跑到 Creator Tab；Frontend 没登录不影响只同步 Creator 的任务（§23）。
- 每步 checkpoint（含 required_tab）；Crash Resume 从断点继续，不从头重跑。
- 3 Fixed Tabs + **1 Worker 串行**；绝不 3 Worker 并发（§21）。

## 9. 错误处理（§24/25）

自动恢复（Deterministic Recovery，**禁止 Autonomous Guessing**）：

```
第一次失败 → retry
第二次失败 → refresh
第三次失败 → renavigate
仍失败     → restore known page state
仍失败     → quarantine / NEEDS_HUMAN
```

| 自动 | 人工（HARD STOP） |
|---|---|
| 页面加载超时（等待→刷新→重导航） | Creator / Spotlight / Frontend 登录过期 |
| Tab 崩溃（重建对应功能 Tab） | CAPTCHA |
| 临时网络失败（bounded retry） | Creator 账号错 |
| 下载失败（重试当前 note） | Spotlight 广告账户错 |
| 已知弹窗（关闭） | **expected note_id ≠ actual**（绝不猜） |
| TreeCut 暂时断开（等待/重连） | 页面大改版（STOP + Adapter Repair） |

## 10. 本地桥（沿用 V1）

`GET {treecut_local_url}/health` → CONNECTED / DISCONNECTED；断开 → TREECUT_DISCONNECTED，
不得继续任何未来数据 Commit（浏览器可保持登录）；服务恢复自动回 CONNECTED。

## 11. 控制台（§12/14/26/28）

三区块：Creator / Spotlight / Frontend（各自 Session + Account + Binding）
+ TreeCut Local + Current Task + Last Checkpoint + **日志面板（用户日志可见）**。
按钮：同步数据 / 恢复训练媒体 / 继续任务 / 查看异常 / 检查状态 / 安全退出。
- **非阻塞**：浏览器/任务操作在线程执行，queue 回投状态，Tk 主循环仅事件驱动刷新。
- 【同步数据】【恢复训练媒体】= V0.1.1 **占位 NOT_IMPLEMENTED**（不抓业务数据）。

## 12. 数据流（§15/16/18/19/20）

```
Creator Tab → creator_snapshot        ─┐
Spotlight Tab → spotlight_snapshot    ─┼→ Local Inbox → Validation Gate → TreeCut Core
Frontend Tab → published_media(.part) ─┘        （PASS→TreeCut / FAIL→quarantine/）
```
- 媒体不进桌面/Downloads：`treecut_inbox/published_media/B007/B007_{note_id}_FULL.mp4.part` → ffprobe/size/duration/decode PASS → 去 .part；FAIL → quarantine。
- Browser 不直接写核心业务 DB（Validation Gate 兜底）。
- 数据源优先级：官方导出优先 → Page-owned Response Observation 补充 → Frontend Media 按需恢复。

## 13. 冻结的十条架构原则（§34）

1. 一个账号 Workspace = 一个 Persistent Browser Profile。
2. 一个 Workspace 固定三个功能 Tab：Creator / Spotlight / Frontend。
3. 三个 Tab 共用 Profile，但 Session 分别判断。
4. 三个 Tab 固定长期存在，不为每条视频创建新 Tab。
5. 三个 Tab，但只使用一个 Worker 串行执行。
6. Creator 负责内容身份+内容表现，Spotlight 负责 Paid，Frontend 负责真实发布媒体。
7. 官方导出优先，页面 Response Observation 补充，Frontend Media 只按需恢复。
8. Browser 只负责 Capture/Action，TreeCut Core 负责 Truth/Analysis。
9. 可确定错误自动恢复；账号、note 身份、验证码等真实性问题必须 Hard Stop。
10. 所有任务 Checkpoint 化、幂等化、可续跑、失败进 Quarantine。

## 14. B003 保护（沿用）

B003 = `PAUSED_BY_BUSINESS_PRIORITY_SHIFT`；Work Browser 开发不得修改 B003 历史数据，
Pilot1 成果保留。V0.1.1 全部为新增/修订 `src/treecut/browser/`，不触碰 Stage3A 产物。

## 15. 后续阶段（§32，等待人工验收后逐个进入）

V0.2 Creator Sync → V0.3 Spotlight Sync → V0.4 Creator+Spotlight Join → V0.5 Sample Selection
→ V0.6 Frontend Media Recovery → V0.7 Automated Validation Pipeline → Production V1。
