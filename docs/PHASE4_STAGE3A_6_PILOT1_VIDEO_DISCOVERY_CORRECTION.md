# PHASE4 STAGE 3A.6 — PILOT1 VIDEO DISCOVERY CORRECTION

> 状态：**STAGE3A6_VIDEO_DISCOVERY_VALIDATED · Pilot1 Recovery Tool 已生成 · 待实际字节恢复 · STOP**
> 日期：2026-08-30
> 纪律：不立即扩 Pilot20 · 不下载 155 · 不进 Content DNA · 不保存 signed URL / 凭证

---

## 1. Pilot1 浏览器侦察结果（HUMAN_BROWSER_RESULT）

```
note_id:            6a8d75aa000000002503e3e2
title:              2米8现代简约岛台😭十几人聚餐够用
published_duration: 59 seconds
侦察页面:           www.xiaohongshu.com/explore/{note_id}（Published Note Playback Page）
__B003VideoResult(): classification = DIRECT_VIDEO_BYTES_AVAILABLE · count = 1
实际观察:           MP4 media resource
```

**PILOT1_RESOURCE_DISCOVERY = VALIDATED** ✅
**STAGE3A6_VIDEO_DISCOVERY_VALIDATED = TRUE**

## 2. 关键修正（必须记录）

**SUPERSEDED**：Creator statistics/note-detail 数据页**不加载实际视频**（此前在该页面 BLOCKED/resources=0 属于**无效 Pilot 结果**）。

**正确路线**：
```
Creator Note Manager
→ 打开具体 Published Note
→ www.xiaohongshu.com/explore/{note_id}
→ 正常播放视频
→ observe actual media resource
```
不保存页面地址里的 xsec_token。

## 3. Pilot1 Actual Byte Recovery（下一步唯一动作）

**`tools/B003_PILOT1_PUBLISHED_VIDEO_RECOVERY_V1.js`**（node 语法验证通过）：
- 在**已打开并正常播放该 note 的浏览器页面**执行
- 从**浏览器内存中页面自己加载的 media resource** 取 bytes
- 保存：`B003_6a8d75aa000000002503e3e2.mp4`
- **安全纪律**：不持久保存 xsec_token/cookie/auth/session/signed query/完整临时 URL；若 MP4 带 query 仅内存使用；Console 不打印完整 URL；只保存 video bytes + note_id + 技术 metadata
- 执行命令：`__B003RecoverPilot1()`

## 4. 恢复后验证（Recovery 完成时执行）

1. 文件可正常解码
2. **ffprobe duration ≈ 59s**（允许 container rounding）
3. duration 明显不一致 → **MEDIA_IDENTITY_CONFLICT**（不得升级 EXACT）
4. 计算：SHA256 + perceptual video fingerprint + audio fingerprint + resolution + codec
5. 与已恢复 Published Cover 做视觉兼容检查

## 5. 身份升级

只有 Pilot1 真实视频保存成功 + duration/identity 核验通过：
- platform_reference_asset → **EXACT_PUBLISHED_MEDIA**
- PublishedContent → Actual Published Media **Pilot1 链路正式成立**

## 6. Segment / Pilot20 Gate

- Pilot1 成功后：允许仅对这一条跑 Actual Published Video → Asset registration → Segment Service → Business Cognition V2.1（验证链路技术可行，**不进 Content DNA**）
- Pilot20 Gate：只有 Pilot1 满足 VIDEO_BYTES_RECOVERED + DURATION_VALIDATED + HASH_CREATED + ASSET_REGISTERED，才生成 `B003_CREATOR_PUBLISHED_VIDEO_RECOVERY_V2.js` 并扩 Pilot20

## 产物
- `tools/B003_PILOT1_PUBLISHED_VIDEO_RECOVERY_V1.js`（恢复工具）
- `B003_VIDEO_RESOURCE_DISCOVERY_PILOT1_V2.json`（侦察结果正式记录）
- 本报告 `docs/PHASE4_STAGE3A_6_PILOT1_VIDEO_DISCOVERY_CORRECTION.md`

## 停点

**STOP** —— 等你执行 `__B003RecoverPilot1()` 保存 MP4 后，把文件位置告诉我，我执行 ffprobe/SHA256/fingerprint/cover 交叉核验 → EXACT_PUBLISHED_MEDIA → Pilot1 链路验证。未自动扩 Pilot20 · 未下载 155 · 未进 Content DNA。
