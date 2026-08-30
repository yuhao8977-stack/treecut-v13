# PHASE4 STAGE 3A.5 — B003 CREATOR MEDIA METADATA RECOVERY REPORT

> 状态：**STAGE3A5_NEEDS_BROWSER_CAPTURE · 安全捕获工具已生成 · 等待用户在 Creator 后台执行 · STOP**
> 日期：2026-08-30
> 前置：B003 PublishedContent=155 · Performance=155 · PlatformReferenceAsset 已降级为 STUB
> 纪律：不独立 fetch · 不保存凭证 · signed URL 不落盘 · 不假装已抓取 · 未进入 Content DNA

---

## 0-1. 155 条降级为 STUB ✅

**`B003_PLATFORM_REFERENCE_ASSETS_V2.json`**：155 条全部标记
- `media_recovery_state = METADATA_ONLY`
- `asset_readiness = STUB`
- 明确"仅 note_id+duration+identity，无 cover/video"——**不得解释为 actual recovered media asset**

155 条 note_id identity **保持不变**（不重匹配标题、不重抓 performance）。

## 2-4. 数据源与安全约束 ✅

- 目标接口：`/api/galaxy/v2/creator/note/user/posted`（此前确认返回 record 含 id/display_title/time/type/images_list/video_info）
- **禁止独立构造 fetch**（Creator 前端有请求签名，独立调用 406）→ 用 **PAGE-OWNED REQUEST OBSERVATION**（监听页面自身 XHR/fetch response）
- **不获取凭证**：不保存 cookie/authorization/xsec_token/session/sign/signature/secret/ticket/credential；不 Copy as cURL；不保存 HAR

## 5-9. 安全捕获工具 ✅（node 语法验证通过）

**`tools/B003_CREATOR_MEDIA_CAPTURE_SAFE.js`**（用户粘贴到 Creator 后台 Console 执行）：
- 拦截 fetch + XHR，只处理 `/note/user/posted` 响应
- **递归敏感字段 Sanitizer**：字段名含 token/cookie/auth/secret/session/sign/signature/ticket/credential/xsec → **DROP**（不是 mask）
- **URL 纪律**：SAFE_REFERENCE_URL 允许保存；**EPHEMERAL_SIGNED_URL 只记 url_origin+url_path+resource_type+signed_present，删除 query**
- 按 note_id 去重；只保留 KNOWN_B003_NOTE_IDS（155）交集
- Console 只显示累计数量，不打印 raw note/video_info/完整 URL
- 导出：`B003_creator_media_metadata_safe.json`（sanitized）

## 10-13. 捕获范围与操作 ✅

- **目标：全部 155 条媒体 metadata**（列表 API 成本低），不下载 155 个视频
- 用户操作：B003 Creator 后台 → 笔记管理 → 已发布 → **正常滚动页面**（页面自身发 posted?page=N，监听器自动收集）
- 不依赖 publish date 过滤（防置顶/混排），最终按 KNOWN_NOTE_IDS 交集

## 14-16. Known Note IDs + 导出 ✅

- `B003_KNOWN_NOTE_IDS_V1.json`（155 note_id，来自 published_content_v1）
- 浏览器安全导出 JSON（保留 sanitized images_list/video_info 结构）+ 可选 CSV（扁平摘要：note_id/title/publish_time/media_type/published_duration/cover_present/cover_count/thumbnail_present/video_info_present/video_resource_present/signed_video_resource_present/media_width/height/metadata_recovery_status）

## 17-18. Console 纪律 + Capture Gate ✅

- Console 只显示：累计捕获数 / 匹配 155 数 / cover 数 / video_info 数 / signed 数
- Capture 完成后输出 missing_note_ids[] / extra_note_ids[]（153/154/156 不自动猜）

## 19-24. Media Recovery 等级（升级规则已定义）✅

| 等级 | 条件 |
|---|---|
| METADATA_ONLY | 仅 duration/type（当前 155 全在此）|
| COVER_RECOVERED | cover/thumbnail 合法取得（下载 Reference Cover，SHA256+embedding）|
| MEDIA_RESOURCE_DISCOVERED | video_info 有 actual resource 但 URL 为 signed（不写 DB）|
| EXACT_PUBLISHED_MEDIA | 实际视频 bytes 从该 note 自己的 Creator Published Media 恢复（SHA256+perceptual+audio+duration+resolution）|
| UNAVAILABLE | 无法取得 |

**Segment Gate**：仅 EXACT_PUBLISHED_MEDIA 可进 Segment Service；**Business Cognition Gate**：仅 actual media + valid segments 后运行。

## 25-31. Pilot20 媒体恢复 ✅

- **`tools/B003_CREATOR_PILOT20_MEDIA_RECOVERY.js`**：只对 Pilot20（20 条）尝试下载 Published Reference Copy
- 命名 `B003_{note_id}.mp4`（title 仅 manifest metadata）
- 使用浏览器**内存中临时 resource**；不把 signed URL 写入文件
- m3u8/stream：不擅自绕过；能合法取 bytes 才保存，否则 STOP 该条
- 成功视频：ffprobe + SHA256 + perceptual fingerprint + audio fingerprint + ASR + sparse keyframes
- **Reference 文件意义**：DERIVED_FROM_PLATFORM_PUBLISHED_MEDIA（非 ORIGINAL_LOCAL_EXPORT / EDIT_PROJECT_SOURCE / RAW_ASSET）

## 34-39. Z 盘 / Reverse Lookup / Repost ✅

- Z 盘本 Stage **不参与正向搜索**
- Pilot20 产生 Published Video Fingerprint 后，才允许 Published Truth → Local/Z Reverse Lookup（顺序：Asset DB → 其它本地池 → Z 盘）
- Local Match 证据：EXACT_SHA256 > PERCEPTUAL_VIDEO_EXACT+AUDIO_MATCH > HIGH_CONFIDENCE_MULTIMODAL（duration 单独永远不够）
- Z 盘命中 1-2 条允许（只关联具体文件，不扩大到文件夹）
- Repost Detection：不同 note_id 同 perceptual video/audio → REPOST_CLUSTER

## 40-41. Stub 升级纪律 + 产物

- 155 stub 不得批量宣称 READY；必须逐条升级
- 产物：`tools/B003_CREATOR_MEDIA_CAPTURE_SAFE.js` · `tools/B003_CREATOR_PILOT20_MEDIA_RECOVERY.js` · `B003_CREATOR_MEDIA_CAPTURE_SPEC_V1.json` · `B003_CREATOR_MEDIA_METADATA_SAFE_V1.json`（空待 capture）· `B003_CREATOR_MEDIA_METADATA_JOIN_V1.json`（骨架）· `B003_PUBLISHED_COVER_REGISTRY_V2.json`（空）· `B003_MEDIA_RESOURCE_DISCOVERY_V1.json`（空）· `B003_PUBLISHED_MEDIA_PILOT20_V2.json` · `B003_PLATFORM_REFERENCE_ASSETS_V2.json`（155 STUB）· `B003_PLATFORM_MEDIA_RECOVERY_COVERAGE_V2.json` · `B003_KNOWN_NOTE_IDS_V1.json`

## 42. 26 问答复

1. **155 旧 Asset 降级为 STUB？** → **是**（V2 全部 METADATA_ONLY/STUB）
2. **155 note identity 不变？** → **是**
3. **安全 Browser Capture Tool 生成？** → **是**（node 语法验证通过）
4. **完全避免保存 cookie/auth/xsec/signature？** → **是**（递归 DROP）
5-10. **images_list/video_info/cover/thumbnail/actual resource/signed？** → **待浏览器捕获**（当前 0，工具已就绪）
11. **完整 signed URL 被持久保存？** → **NO**（纪律保证，signed URL 只记 origin/path）
12. **155 完成 media metadata join？** → **0**（待 capture）
13-16. **Pilot20 分级？** → 当前全 METADATA_ONLY（20）；COVER_RECOVERED/MEDIA_RESOURCE_DISCOVERED/EXACT_PUBLISHED_MEDIA = 0
17-18. **实际下载 Pilot Published Video？** → **否**（未执行，需用户浏览器操作）
19. **生成 Published Video fingerprint？** → **否**（无视频）
20-22. **可进 Segments/Business Cognition？** → **否**（需 EXACT_PUBLISHED_MEDIA）
23. **发现 Repost Candidate？** → **否**（无 fingerprint）
24. **有条件 Local/Z Reverse Lookup？** → **否**（无 Published Video fingerprint）
25. **仍需用户找 B003 成片目录？** → **不需要**（改为 Creator 后台媒体恢复）
26. **PHASE4_STAGE3B_READY？** → **FALSE**

## 43-44. 最终状态与停点

**STAGE3A5_NEEDS_BROWSER_CAPTURE** —— Harness 无法访问用户已登录的 Creator 浏览器会话，**不假装已抓取**。

**下一步（等你操作）**：按我给你的步骤在 Creator 后台执行 `B003_CREATOR_MEDIA_CAPTURE_SAFE.js`（粘贴 Console → 滚动已发布页 → `__B003Export()` 导出），把导出的 `B003_creator_media_metadata_safe.json` 给我，我完成 155 Join + 升级判定；然后 Pilot20 用 `B003_CREATOR_PILOT20_MEDIA_RECOVERY.js` 恢复真实视频。

**STOP** —— 未自动进入 Stage3B / Content DNA / Template Mining / Account DNA。
