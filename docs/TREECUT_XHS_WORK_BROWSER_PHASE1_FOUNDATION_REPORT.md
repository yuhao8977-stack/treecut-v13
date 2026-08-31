# TreeCut XHS 工作浏览器 — Phase 1 底座验收报告（FOUNDATION PASS）

- 报告日期：2026-08-30
- 阶段：PHASE 1 — Persistent Account Workspace Foundation（V0.1 → V0.1.1 → V0.1.2）
- 最终状态：**XHS_WORK_BROWSER_FOUNDATION_PASS**
- 工作账号：B007（KUBON坤宝高端岛台工厂）

---

## 1. 最终架构（已冻结）

> **TreeCut XHS 工作浏览器 = 账号工作区 + 持久 Profile + 三个固定功能 Tab + 单 Worker 串行 + 本地 TreeCut 桥。**

```
B007 Workspace
└── 持久浏览器 Profile：browser_profiles/B007/（登录态物理隔离、关闭不删、重开复用）
    ├── Tab 1：Creator 创作服务平台（creator.xiaohongshu.com）→ 内容身份 + 内容表现 Truth
    ├── Tab 2：Spotlight 聚光后台（ad.xiaohongshu.com）→ 投流表现 Truth
    ├── Tab 3：小红书前台（www.xiaohongshu.com）→ 真实发布媒体 Truth
    └── TreeCut 本地控制台（简体中文面板）
```

- 三个 Tab 共用同一 Profile，**Session 分别检测**（互不误判）。
- **Single Worker 串行**执行所有任务；3 固定 Tab 长期存在，不为每条视频新建 Tab。
- 浏览器只负责采集/执行；TreeCut Core 负责 Truth/验证/DB/资产/认知；Harness 负责开发/审计/报告。
- 所有 Playwright 操作收敛到**单一线程**（BrowserExecutor），杜绝跨线程崩溃。

## 2. 技术选型

| 项 | 选择 |
|---|---|
| 浏览器运行时 | 自启 Edge（`--user-data-dir` 持久 Profile）+ CDP 接管（Playwright `connect_over_cdp`） |
| 无 --no-sandbox | ✅ 生产路径参数完全可控，实证 Edge 命令行不含该参数 |
| Profile 位置 | `{data_root}/browser_profiles/B007`（稳定持久路径） |
| 登录持久化 | Persistent Profile；关闭（CDP 优雅关闭落盘）→ 重启免登录 |
| 单实例 | Profile Lock（PROFILE_LOCKED 阻止第二实例） |
| 配置 | `configs/xhs_work_browser.yaml`；运行时 `{data_root}/config/` |
| 启动 | `scripts/start_xhs_browser.bat`（固定便携运行时 + 固定数据根） |

## 3. 真实验收结果（A–I）

| # | 验收项 | 结果 | 证据 |
|---|---|---|---|
| A | 启动 B007 Workspace | ✅ | 多次实测启动成功 |
| B | 三站无需重新登录 | ✅ | SAFE_SHUTDOWN → 重启三站免登录 |
| C | 三站自动显示「已登录 ✅」 | ✅ | 面板确认 + 探针日志 SESSION_VALID |
| D | Creator 自动显示昵称 + 小红书号 | ✅ | KUBON坤宝高端岛台工厂 / **63083262719**（人工确认落盘） |
| E | 聚光自动显示广告账户 | ✅ | T-KUBON坤宝高端岛台工厂-zx（人工确认落盘；账户 ID 留 V0.2 补） |
| F | 标签页稳定为 3 | ✅ | 探针实证 tabs_after_reconcile=3（重复页自动去重、用户页不误关） |
| G | 日志面板有事件 | ✅ | 面板日志区 + 文件日志 `{data_root}/logs/xhs_work_browser.log` |
| H | Edge 无 --no-sandbox 警告 | ✅ | 自启参数实证 |
| I | UI 操作不卡顿 | ✅ | 回调线程化 + 单线程 executor + 检测硬时限 40s |

## 4. 账号绑定记录（无任何凭证）

```json
{
  "workspace_id": "B007",
  "creator_xhs_id": "63083262719",
  "creator_display_name": "KUBON坤宝高端岛台工厂",
  "spotlight_ad_account_name": "T-KUBON坤宝高端岛台工厂-zx",
  "spotlight_ad_account_id": "（V0.2 校准补全）",
  "frontend": "可选（不作 B007 硬性要求；媒体身份以 note_id 为 Gate）"
}
```

- Creator 以 **XHS ID 为主锚**（ID 不变即仍为 B007，昵称可改）。
- 聚光账户名允许 ≠ Creator 名，单独人工确认。
- 前台 Viewer 账号**不强制**等于 B007；视频身份由 `expected note_id == actual note_id` 硬门保证。

## 5. 真实运行中发现并修复的问题

| 问题 | 根因 | 修复 |
|---|---|---|
| 面板全部 UNKNOWN | 检测未自动执行/页面未渲染完 | 启动后自动检测 + SPA 有界重试 + 多信号分层 |
| 三站已登录却全灰/未识别 | Playwright Sync API **跨线程调用**（greenlet 崩溃，把已读到的"KUBON坤宝高端岛台工厂"等结果全部打掉） | 所有浏览器操作收敛到 **BrowserExecutor 单线程** |
| 面板"上一操作仍在执行"假死 | 启动检测占用执行队列 + busy 门误报 | 点击改排队（per-key inflight）；检测硬时限 40s |
| 单站检测要 2 分钟 | XHS 大页面 `content()/innerText` 极慢 | textContent 轻量读取 |
| 绑定按钮灰色 | 未检测到账号时按钮禁用 | NONE/PENDING 均可点击（点击重试 + 输出诊断） |
| Edge 启动端口超时 | 上次进程被强杀后 **17 个孤儿 Edge** 占住 Profile | close 强制终止兜底 + 启动重试清陈旧锁 |
| 日志找不到 | 日志只进控制台 | 落盘 `logs/xhs_work_browser.log`（可随时调取） |
| 重复 Frontend Tab | 会话恢复/残留 | role-ownership 去重（同托管域非 canonical 关闭，用户页不误关） |

## 6. 测试与工程

- V0.1.2 套件 **44 项通过**（含 3 Tab 真实 Edge headless smoke：固定 Tab/去重/复用/崩溃重建/持久化全 PASS，退出码 0）
- 全量回归 **250 项通过**（无回归）
- 安全审计 **PASS**（无 cookie/authorization/xsec_token/签名值入库）
- 提交：`1a53f37`(工具就绪) → `17a3ecd`(样本定义修正) → `a541505`(V0.1) → `5e2d496`(V0.1.1) → `3d1f064/08f2c34/ed48bc4`(V0.1.2) → `7b95523`(探针) → `f6f4302`(面板管线) → `a060122`(启动脚本) → `934999f`(诊断轮) → `274efc2`(executor) → `9fe4283`(真实绑定轮) → `41037c5`(FOUNDATION PASS)

## 7. 与 B003 的关系

- B003 = `PAUSED_BY_BUSINESS_PRIORITY_SHIFT`；Pilot1 成果（EXACT 媒体/资产/分段/ASR/认知）**完整保留**，本阶段零改动。
- 浏览器底座后续可复用于 B003/B008/B010（架构按多账号兼容设计，V0.1.2 只验证 B007）。

## 8. 下一步（等待确认后启动）

**V0.2 Creator 自动同步**：
- 补全聚光广告账户 ID 的 DOM 校准
- B007 账号信息 → 已发布笔记 → note_id / 标题 / 发布时间 / 类型 / 时长 / 封面 → Creator 内容表现
- 官方导出优先、页面 Response Observation 补充；产物走 Local Inbox → Validation Gate → TreeCut Core

**之后**：V0.3 聚光同步 → V0.4 双源 Join → V0.5 样本挑选 → V0.6 前台媒体恢复 → V0.7 自动验证流水线 → 生产 V1。

---

*本报告由 Harness 依据会话内真实工具结果与用户验收反馈生成；不含任何登录凭证。*
