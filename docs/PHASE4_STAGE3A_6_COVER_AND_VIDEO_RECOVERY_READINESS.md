# PHASE4 STAGE 3A.6 — COVER + VIDEO RECOVERY — READINESS

> 状态：**WAITING_FOR_V2_JSON（处理管线就绪，等 B003_creator_media_metadata_safe_V2.json 到位）· STOP**
> 日期：2026-08-30
> 说明：用户已核验 V2 文件事实，但文件尚未出现在 Harness 可访问路径（Desktop/Downloads/Documents/DATA_ROOT 均未找到）

---

## 已确认的用户核验事实（§1-4）

| 项 | 用户核验 |
|---|---|
| records | 155 |
| unique note_id | 155（0 重复）|
| date range | 2026-03-04 → 2026-08-30 |
| 与 Stage3A.2 的 155 PublishedContent 对应 | ✅ |
| images_list | 155/155（每条 1 个封面资源描述）|
| video_info.duration | 155/155（与身份表 duration 155/155 一致，0 冲突）|
| cover url_path | 155 全部唯一 |
| actual video URL/resource | 0（video_info 仅 duration）|
| 敏感字段（xsec/cookie/auth/session/signature）| 无 |
| 完整带 query signed URL | 无（已清理）|

## 重要区分（§6-7）

- **COVER_RESOURCE_DISCOVERED（155）≠ COVER_RECOVERED（0）**——有 origin+path+note_id 关联，但**图片 bytes 未恢复**
- **video_info 存在 ≠ MEDIA_RESOURCE_DISCOVERED**——当前 video_info 仅 duration，无实际视频 URL/resource
- cover 的 `signed_or_ephemeral=true` 是 Sanitizer 保守标记（原 URL 有 query），**不得推断 query 一定是认证签名**（UNKNOWN_EPHEMERAL_QUERY_PURPOSE）

## 处理管线已就绪（V2 文件到位即执行）

1. **Metadata Join V2**：按 note_id Join capture ↔ published_content_v1（不重新 title/time 匹配）
2. **PlatformReferenceAssets V3 升级**：155 条 → COVER_RESOURCE_DISCOVERED（区分于 COVER_RECOVERED）
3. **Cover Retrieval Pilot5**：选 5 条（不同发布时间/URL path prefix/duration），`https://{origin}{path}` 直接 GET（不猜 query/不补 token）
   - 成功（HTTP success + image/* + 可解码）→ COVER_RECOVERED → 扩 155
   - 失败（403/401/404）→ COVER_BROWSER_BYTE_RECOVERY_REQUIRED → 生成 Browser 工具
4. **Cover Registry V3**：note_id/sha256/width/height/mime/local_path/retrieval_method（不保存 signed URL）
5. **Video Resource Discovery Pilot1**：Pilot20 中选 1 条（普通 video，30-90s）→ Creator note-detail 页面观察自身网络请求 → 判定 DIRECT_VIDEO_BYTES_AVAILABLE / BROWSER_AUTHENTICATED / STREAM_ONLY / METADATA_ONLY / BLOCKED
6. **旧 Pilot20 工具标记**：`tools/B003_CREATOR_PILOT20_MEDIA_RECOVERY.js` = **BLOCKED_BY_MISSING_VIDEO_RESOURCE_DESCRIPTOR**（不删除，保留历史）——因为 video_info 无视频资源

## 纪律保持（§21/26/38）

- 禁止破解 signature / 逆向鉴权 / 伪造 session / 批量未授权 API
- 禁止 155 全量视频自动下载（先 Pilot1 → Pilot20）
- 本地/Z 盘不参与正向搜索（等真实 Published Video Fingerprint）
- 未进入 Content DNA / Template Mining / Account DNA

## 需要你

**把 `B003_creator_media_metadata_safe_V2.json` 放到桌面或 Downloads**（READ ONLY），我立即执行完整管线（Join → Cover Pilot5 → 升级判定 → Video Pilot1 侦察）。

## 产物
- `STAGE3A6_READINESS.json`（本状态）
- `scripts/stage3a6_pipeline_ready.py`（V2 到位即跑的入口）

## 停点

**STOP** —— V2 文件未到位不假装处理。等你提供文件后继续 Stage3A.6。
