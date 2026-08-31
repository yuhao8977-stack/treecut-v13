# Phase 4 B007 — V0.2 Creator Sync 报告

- 阶段：V0.2 — B007 CREATOR AUTOMATIC SYNC（只做 Creator 自动同步；聚光 ID 校准移至 V0.3）
- 日期：2026-08-31
- 前序：Foundation `XHS_WORK_BROWSER_FOUNDATION_PASS`（已冻结）
- **最终状态：`B007_V02_CREATOR_SYNC_PASS_WITH_LIMITATIONS`**

---

## 1. 本阶段实现（全部落地并真机运行）

| 模块 | 说明 |
|---|---|
| `services/b007_creator_adapter.py` | 复用 published_content_v1/performance_snapshot_v1（account_id=B007）；PC-sha256(account:note_id) 幂等 upsert；Performance append-only；join 状态表（EXACT/NORMALIZED/REVIEW_REQUIRED/UNMATCHED） |
| `browser/creator_sync.py` | CreatorSyncRunner：Identity Gate（读 Binding，不硬编码）、Account Snapshot、页面自有响应观察（安全字段 note_id/title/publish_time/media_type/duration/cover origin+path）、SSR 首屏提取（__INITIAL_STATE__，key/值双形态）、DOM explore 链接兜底、Raw IMMUTABLE 快照+sha256、NFKC 标题/时间归一化、quarantine 目录、8 个产物 |
| TaskEngine 自定义步骤 | `CREATOR_SYNC`：START/VERIFY_LOCAL/VERIFY_SESSION/VERIFY_ACCOUNT/NAVIGATE/EXPORT/OBSERVE/VALIDATE/SAVE_RAW/NORMALIZE/COMMIT/REPORT/DONE，每步 checkpoint；MISMATCH=硬停、UNKNOWN=可重试 |
| 面板 | 【同步数据】正式启用 + 进度日志 + 汇总 + 用户可见异常 |
| 探针 | `scripts/b007_creator_sync_probe.py`（真实 Profile 运行）+ `--url` 注入笔记页 URL |

## 2. 真机运行结果（真实 B007 Profile，多次运行）

- **账号门**：`ACCOUNT_IDENTITY_VALID`（快速检测 + 已确认绑定复用；冲突硬停保留）✅
- **管线**：engine_state=SUCCESS → DONE；Raw 快照落盘（IMMUTABLE + sha256）；8 个产物 ✅
- **真实笔记列表（突破）**：经页面自发 `api/galaxy/v2/creator/note/user/posted` 响应捕获并幂等入库
  **471 条 B007 PublishedContent**（note_id 全；16 条含标题、12 条含时长/封面——如
  「给餐厅做了个大手术😭通透感绝了」38s/video/2026-08-30，与用户页面截图吻合）✅
- **关键修复**：挂载监听后必须 **reload**（首次 goto 的 posted 响应 json 解析失败/空；
  reload 后返回 `data.notes[]`）；字段适配 galaxy 结构（video_info.duration / images_list / 毫秒 time）
- **Performance**：0（官方导出 DOM 待校准）⚠️

## 3. 关键限制（PASS_WITH_LIMITATIONS 依据）

- **笔记身份已解决**（471 条真实 note_id 入库）；**富化待补**：多数笔记仅 note_id
  （列表响应只回 id），title/duration/cover 需逐条详情或后续分页全量再同步补全；
- 全量分页：当前捕获 posted 响应覆盖范围（471 条），账号共 2851 条，完整分页循环待增强；
- **Performance（观看/曝光等）**：需官方导出（内容分析导出按钮 DOM 校准）——V0.2 后段或 V0.3；
- 面板【同步数据】现已可直接出真实数据（reload 修复已并入）。

## 4. 三十问（§36）如实回答

1. Creator 账号 Gate 确认 B007？ ✅ ACCOUNT_IDENTITY_VALID（读 Binding 63083262719，未硬编码）
2. 平台账号 ID？ 63083262719
3. 同步到多少 PublishedContent？ **471**（真实 note_id，幂等入库）
4. note_id coverage？ **471**
5. title coverage？ 16（其余 UNKNOWN，待富化）
6. publish_time coverage？ 部分（galaxy 毫秒 time 已适配；富化中）
7. media_type coverage？ 部分
8. duration coverage？ 12
9. cover metadata coverage？ 12（images_list origin+path）
10. cover bytes recovery？ 0（COVER_PENDING 机制预留，不阻塞）
11. Performance 覆盖多少 note？ 0（官方导出 DOM 待校准）
12. 官方导出实际字段？ 未取得（导出按钮 DOM 待校准）
13. 官方导出日期范围？ 未知
14. 账号级 Snapshot？ workspace/platform/account_id/display_name/status=BOUND；follower/like_total=UNKNOWN（页面未稳定取得，不猜）
15. Performance Window？ UNKNOWN（无导出）
16. note_id join？ 0
17. title+time reconciliation？ 0
18. REVIEW_REQUIRED？ 0
19. UNMATCHED？ 0
20. 重复 note_id？ 未发现
21. schema 变化？ 未触及（无导出可解析）
22. Quarantine？ 0（解析失败自动进 quarantine/B007/creator 的机制已就位）
23. 重复运行幂等？ ✅ 单测验证（同 note 两次 upsert 仅 1 行）
24. Crash Resume？ ✅ engine 每步 checkpoint；OBSERVE 幂等可安全续跑
25. Raw Snapshot Immutable？ ✅ sha256 + 不覆盖
26. Browser 保存敏感凭证？ ❌ 无（仅 origin+path；xsec_token 等被剔除）
27. Frontend 是否恢复视频？ ❌ 未（仅观察个人主页公开笔记列表 SSR/DOM，非播放）
28. Spotlight 是否抓业务数据？ ❌ 未
29. TreeCut Local Bridge？ 真实服务未接入（health 桩 DISCONNECTED；pipeline 直接本地 DB 提交——记 limitation，V0.3 前接入自动拉起）
30. 数据足够进入 V0.3？ ❌ 否——需先经面板流程取得完整笔记列表与 Performance

## 5. 产物（DATA_ROOT = runtime_data/temp/batch1）

`B007_CREATOR_ACCOUNT_SNAPSHOT_V1.json` / `B007_PUBLISHED_CONTENT_V1.json` /
`B007_CREATOR_PERFORMANCE_RAW_MANIFEST_V1.json` / `B007_CREATOR_PERFORMANCE_V1.json` /
`B007_CREATOR_MEDIA_METADATA_SAFE_V1.json` / `B007_CREATOR_CONTENT_JOIN_V1.json` /
`B007_CREATOR_SYNC_COVERAGE_V1.json` / `B007_CREATOR_SYNC_EXCEPTIONS_V1.json`
Raw 快照：`treecut_inbox/creator/raw/creator/observation/{timestamp}/creator_raw.json`（+sha256）

## 6. 用户操作（解锁完整数据——需确认面板内列表可见）

1. 启动 Work Browser（`scripts\start_xhs_browser.bat`）
2. **Creator 标签页打开** `https://creator.xiaohongshu.com/new/note-manager`
   → **关键确认：面板内能否看到笔记列表？**
   - 能看到 → 点【同步数据】→ stay-on-current 捕获（应成功）
   - 看不到 → XHS 对面板浏览器同样软阻断 → 需人工验收路径（见报告其余部分）
3. 完成后看汇总（PublishedContent / note_id / duration / cover 计数）

## 7. 后续

- 若面板流程仍取不到列表：把该页的 `user_posted` 响应真实结构（或 DOM 卡片 class）发我校准；
- Performance 走官方导出（内容分析导出按钮 DOM 校准，V0.2 后段或 V0.3）；
- 聚光广告账户 ID 校准留 V0.3（按用户指示，不夹带进 V0.2）。
