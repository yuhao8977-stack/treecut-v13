# PHASE4 STAGE 3A.6 — COVER + VIDEO RECOVERY REPORT

> 状态：**STAGE3A6_COVER_RECOVERED_VIDEO_PENDING · 155 封面全部恢复 · actual video 待 Pilot1 note-detail 侦察 · STOP**
> 日期：2026-08-30
> 输入：`B003_creator_media_metadata_safe_V2.json`（155 条，用户浏览器捕获）
> 纪律：未猜 query · 未补 token · 未保存 signed URL · 未 155 全量下载视频 · 未进入 Content DNA

---

## 1-4. V2 文件验证 ✅（Harness 本地独立核验）

| 项 | 结果 |
|---|---|
| records | **155** |
| unique note_id | **155**（0 重复）|
| date range | 2026-03-04 → 2026-08-30 |
| images_list | **155/155**（每条 1 封面 descriptor）|
| video_info.duration | **155/155**（与 DB published_content_v1 的 duration **0 不一致**）|
| 敏感字段（xsec/cookie/auth/session/signature）| **NONE** |
| 完整带 query signed URL | 无（已清理，只留 origin+path）|

**security_validation = PASS** ✅

## 5-7. Stage3A.5 状态修正 + Reference Asset 升级 ✅

- **STAGE3A5_METADATA_RECOVERED**（media_metadata_join = 155/155）
- **`B003_PLATFORM_REFERENCE_ASSETS_V3.json`**：155 条 → **COVER_RECOVERED**（封面 bytes+SHA256 已取得）
- 区分：COVER_RESOURCE_DISCOVERED（有 origin+path）→ **COVER_RECOVERED**（bytes 到手）
- cover 的 `signed_or_ephemeral=true` = Sanitizer 保守标记（UNKNOWN_EPHEMERAL_QUERY_PURPOSE，不推断）

## 8-11. Cover Retrieval：Pilot5 → 全量 155 ✅

**Pilot5（5/5 成功）**：`https://{origin}{path}` 直接 GET（无 query）→ HTTP 200 + image/jpeg + 37-60 万 bytes → **cover 公开可取**。

**全量 155/155 恢复** → `platform_reference/B003/covers/{note_id}.jpg`：
- SHA256 全部计算 · width/height 获取 · mime=image/jpeg
- `B003_PUBLISHED_COVER_REGISTRY_V3.json`（155 条 COVER_RECOVERED）

## 12-15. Cover 结果

- 无需 Browser fallback（公开路径直接成功）
- `B003_CREATOR_COVER_BYTE_RECOVERY_V1.js` **不需要生成**（Pilot5 全成功）
- Cover Registry V3 已建立（note_id/sha256/width/height/mime/local_path/retrieval_method=SANITIZED_PUBLIC_PATH）

## 16-17. Actual Published Video：仍未发现 ✅

- **video_info 仅 duration**（155/155）→ **actual video resource = 0/155**
- **posted list endpoint 不是实际视频媒体恢复入口**（不重复寻找不存在的字段）
- **旧 `tools/B003_CREATOR_PILOT20_MEDIA_RECOVERY.js` = BLOCKED_BY_MISSING_VIDEO_RESOURCE_DESCRIPTOR**（不删除，保留历史）

## 18-26. Video Discovery 改为 note-detail 路线 ✅

**`tools/B003_CREATOR_VIDEO_RESOURCE_DISCOVERY_V1.js`**（node 语法验证通过）：
- **Pilot1 技术侦察**：打开 1 条 Pilot note 的 Creator note-detail，观察页面自身网络请求
- 只记录 resource type/host/path pattern/mime/content-length/是否 blob/mp4/stream（不保存 signed query）
- `__B003VideoResult()` 返回分类：DIRECT_VIDEO_BYTES_AVAILABLE / BROWSER_AUTHENTICATED_VIDEO_BYTES_AVAILABLE / STREAM_ONLY / METADATA_ONLY / BLOCKED
- **禁止**：破解 signature / 逆向鉴权 / 伪造 session / 绕过访问控制

**Pilot1 成功后才生成 `B003_CREATOR_PUBLISHED_VIDEO_RECOVERY_V2.js` 并扩 Pilot20**；155 全量视频**暂不下载**（§38）。

## 27-33. 后续 Gate（已定义）

- EXACT_PUBLISHED_MEDIA（视频 bytes 来自该 note 自己的 Creator Published Note + SHA256/perceptual/audio/duration 核验）才进 Segment → Business Cognition
- Duration 再核验（ffprobe vs published，允许 container rounding；严重不一致 → MEDIA_IDENTITY_CONFLICT）
- Cover 与视频 keyframes 交叉核验（不一致 → IDENTITY_CONFLICT_REVIEW）

## 34-38. Z 盘 / Reverse / Repost ✅

- Z 盘继续保持 LEGACY_MIXED_MEDIA_POOL，**不参与正向搜索**
- Reverse Match 只在真实 Published Video Fingerprint 出现后（Asset DB → Local → Z fallback）
- Cover match alone 不认定 LOCAL_COPY_OF_PUBLISHED_MEDIA（需 video/audio/multimodal）
- Repost Detection：Pilot20 actual videos 恢复后比较 perceptual/audio → REPOST_CLUSTERS_V3

## 39-40. 产物

`B003_CREATOR_MEDIA_METADATA_SAFE_V2.json`（正式）· `B003_CREATOR_MEDIA_METADATA_JOIN_V2.json`（155）· `B003_PLATFORM_REFERENCE_ASSETS_V3.json`（155 COVER_RECOVERED）· `B003_COVER_RETRIEVAL_PILOT5_V1.json`（5/5）· `B003_PUBLISHED_COVER_REGISTRY_V3.json`（155）· `B003_VIDEO_RESOURCE_DISCOVERY_PILOT1_V1.json`（PENDING）· `B003_PUBLISHED_MEDIA_PILOT20_V3.json` · `B003_MEDIA_IDENTITY_CONFLICTS_V1.json`（0）· `B003_PLATFORM_MEDIA_RECOVERY_COVERAGE_V3.json` · `tools/B003_CREATOR_VIDEO_RESOURCE_DISCOVERY_V1.js` · 155 封面文件（`platform_reference/B003/covers/`）

## 41. 27 问答复

1. **V2 JSON 155 条？** → **是**（本地独立验证）2. **unique 155？** → **是** 3. **155/155 join？** → **是**（按 note_id）4. **duration 155/155 一致？** → **是**（0 冲突）5. **images_list 155/155？** → **是** 6. **每条 cover descriptor？** → **是** 7. **敏感 Credential 持久化？** → **NO**（security PASS）8. **Stage3A.5 = METADATA_RECOVERED？** → **是** 9. **Cover Pilot5 无需 query 恢复？** → **5/5** 10. **扩 155？** → **是**（已全量恢复）11. **恢复 cover bytes？** → **155** 12. **SHA256？** → **155** 13. **video_info 仅 duration？** → **是** 14. **posted list actual video resource？** → **0**（预期）15. **旧 Pilot20 工具 BLOCK？** → **是**（BLOCKED_BY_MISSING_VIDEO_RESOURCE_DESCRIPTOR）16. **Pilot1 note-detail 侦察？** → **待浏览器执行**（工具已生成）17-18. **actual video bytes 可合法恢复？** → **待 Pilot1 判定**（DIRECT/BROWSER_AUTHENTICATED/STREAM_ONLY/METADATA_ONLY/BLOCKED）19. **若可恢复生成 Pilot20 Tool？** → **Pilot1 成功后才生成** 20-23. **Pilot20/EXACT/Segment/Cognition？** → **0**（待视频）24. **identity conflict？** → **0** 25. **Local/Z Reverse Match 条件？** → **否**（无视频指纹）26. **需用户找 B003 成片目录？** → **不需要**（Creator 路线）27. **PHASE4_STAGE3B_READY？** → **FALSE**

## 42. 最终状态

**STAGE3A6_COVER_RECOVERED_VIDEO_PENDING** —— 封面 155/155 已恢复；actual video 待 Pilot1 侦察。

## 停点

**STOP** —— 等你用 `tools/B003_CREATOR_VIDEO_RESOURCE_DISCOVERY_V1.js` 做 Pilot1（打开 1 条 note-detail，执行 `__B003VideoResult()`），把分类结果发我。Pilot1 成功 → 生成 Pilot20 Recovery Tool；失败 → 判定 STREAM_ONLY/BLOCKED 后停。未 155 全量下载 · 未进 Content DNA / Template / Account DNA。
