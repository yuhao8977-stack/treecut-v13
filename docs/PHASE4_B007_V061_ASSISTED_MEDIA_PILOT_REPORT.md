# PHASE 4 — B007 V0.6.1 Assisted Media Pilot 报告

- 日期: 2026-09-01
- 状态: **V06_ASSISTED_PILOT1_PASS** ✅

## 1. 结论
USER_ASSISTED 技术链验证成功：点击 Creator 笔记管理中的目标卡片 → 打开前台详情页（带页面自有 xsec）→ 页面播放器请求真实 MP4（Range 分段）→ TreeCut 用浏览器会话下载完整字节 → ffprobe + ffmpeg 全解码 + SHA256 + 时长交叉校验 → 入 Z 盘。

## 2. Pilot 样本
- note_id: `69f9a0ac000000003701d937`（Sample20 C 组：Paid 高效率候选）
- Creator duration: 21s（manifest）
- 标题: 通透又显大的开放式厨房标配岛台🤔（2026-05-06 发布）

## 3. 技术链证据
| 环节 | 证据 |
|---|---|
| 定位 | note-manager「搜索已发布」输入标题核心词 → 唯一结果卡（00:21 时长角标）|
| 点击 | TreeCut 自动点击卡片本体（页面正常交互）→ **新开前台详情 tab** `explore/{note_id}?xsec_token=...` |
| 身份门 | 详情页 URL 含目标 note_id + `sns/web/v2/comment/page` 响应含目标 note_id → actual==expected ✅ |
| 媒体观察 | `sns-video-v3.xhscdn.com/stream/79/110/114/01e9f9a0ac135f484f0370019df71bffcf_114.mp4`（video/mp4；4 个 Range 206 分段，content-range 覆盖 0..1641506）|
| 下载 | 浏览器会话 `context.request.get(完整URL)`（临时签名 URL 仅内存使用，未持久化）→ 1,641,507 字节 |
| ffprobe | HEVC (hvc1) 720×1280 9:16, 30fps, 658 帧, AAC 音频, duration 21.966s |
| ffmpeg 全解码 | 从头到尾 decode 无 fatal error ✅ |
| SHA256 | `6df9062aa0fc95ab1f1386113695eada88dd6b682a7fd936208bd9efb8f0710e` |
| 时长交叉 | creator 21s vs ffprobe 21.97s（容差 5s 内）→ **MATCH_WITHIN_TOLERANCE** ✅ |
| 最终路径 | `Z:\TreeCut_Media\B007\published_media\69f9a0ac000000003701d937__6df9062aa0fc.mp4`（1,641,507B）|

## 4. 纪律落实
- 凭证：临时签名 URL 仅在内存用于立即下载，**未持久化**；Cookie/Authorization/xsec_token 未保存
- 存储：staging E（.part）→ PASS 后 Z；C 盘零媒体写入；E staging 已清空（文件已提升）
- 身份：note_id 硬门（actual==expected），标题相似不替代
- 模式：USER_ASSISTED_NAVIGATION + AUTOMATED_CAPTURE + AUTOMATED_VALIDATION（用户仅点击，无需下载/复制/上传）
- 未修改 Frontend 登录；未重建 Profile；三托管 Tab 架构保持

## 5. 发现（V0.6.2 批量可复用）
- 关键交互：**note-manager 卡片点击会打开前台详情页**（新 tab + 页面自有 xsec）→ 详情页播放器请求 `sns-video-v3.xhscdn.com/..._N.mp4`（N=114 表示码率档位）
- 媒体为 **Range 分段请求**（206），需用浏览器会话重新请求完整文件（context.request.get 携带会话，200 全量）
- 竖屏 720×1280 HEVC（hvc1），30fps
- 跨卷（E→Z）需用 `shutil.move`（os.replace 不支持跨卷）

## 6. 下一步（STOP）
- **Pilot1 PASS → STOP**（§23：不自动处理剩余 19 条）
- V0.6.2 ASSISTED BATCH RECOVERY：用户依次点击目标笔记卡，TreeCut 自动 capture/validate/promote/checkpoint（待架构师批准）
- V0.7 仍冻结（Asset/Segment/ASR/Cognition）
