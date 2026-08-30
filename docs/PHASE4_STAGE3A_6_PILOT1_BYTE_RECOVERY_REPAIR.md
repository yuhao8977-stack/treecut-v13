# PHASE4 STAGE 3A.6 — PILOT1 BYTE RECOVERY REPAIR（Range-Aware V2）

> 状态：**PILOT1_RANGE_RECOVERY_TOOL_READY · 待用户浏览器执行 Probe + Reconstruct · STOP**
> 日期：2026-08-30
> 前置：Pilot1 Video Discovery = VALIDATED（DIRECT_VIDEO_BYTES_AVAILABLE）；但 V1 字节恢复 = PARTIAL_INVALID
> 纪律：不扩 Pilot20 · 不 155 · 不进 Segment/Cognition/Content DNA · 不绕过访问控制

---

## 0-2. V1 文件验证：确认非完整 MP4 ✅

| 项 | 结果 |
|---|---|
| file_size | **413921 bytes（≈404KB）** |
| SHA256 | `ff327aa3d668433d8cc577296e43e1ea4e613b3085024cfc89efb53e2d9ab79d` |
| ffprobe | **moov atom not found · Invalid data** |
| container atoms | ftyp/moov/mdat **全部 NOT_FOUND** |

**EXACT_PUBLISHED_MEDIA = FALSE** → 禁止 Asset/Segment/Cognition。

**故障分层**：RESOURCE_DISCOVERY 仍 VALIDATED；故障在 **BYTE_RECOVERY_LAYER**。状态 = **PARTIAL_OR_RANGE_FRAGMENT**（404KB 高度疑似 HTTP byte-range response 或 media fragment，非完整 59s 视频对象）。

## 3-4. V1 脚本审计 + 安全日志纪律 ✅

`B003_PILOT1_RECOVERY_V1_FAILURE_ANALYSIS.json` 记录 V1 问题：
- fetch 捕获任意 video/mp4 response 直接 blob()，未检查 HTTP status（206 只含单段）
- 未检查 Content-Range/Accept-Ranges/Content-Length
- 未校验 MP4 container（ftyp/moov/mdat）
- 未做 range 重建

安全日志纪律：允许 status/content_type/content_length/content_range/accept_ranges/total_media_bytes/chunk_count；**禁止**完整 URL/query/xsec/cookie/auth/session/signature。

## 5-16. Range-Aware Recovery V2 ✅

**`tools/B003_PILOT1_RANGE_AWARE_RECOVERY_V2.js`**（node 语法验证通过，只处理 Pilot1）：

**Step1 `__B003RangeProbe()`**：请求已发现的 media resource → 输出安全摘要（status/content-type/content-length/content-range/accept-ranges），不打印 URL
- HTTP 200 → 保存完整 response bytes
- HTTP 206 → 解析 Content-Range 得 TOTAL

**Step2 `__B003RangeReconstruct(probe)`**：
- **首块从 byte 0 开始**（V1 最大疑点），验证 **ftyp 存在**；无 ftyp → `NOT_STANDARD_MP4_RESOURCE`，STOP 不继续
- 2MB/chunk、**并发 1**（避免瞬时大量请求）
- 每块验证 206 + Content-Range 一致；missing/overlap/unexpected → 立即 STOP
- 按 byte offset **严格顺序拼接**（ArrayBuffer/Uint8Array 高效合并，不用 Base64）
- 输出 `B003_6a8d75aa000000002503e3e2_FULL.mp4`（**不覆盖旧 V1**，旧文件保留标 FAILED_PARTIAL_RECOVERY_ARTIFACT）
- Browser-side container gate：ftyp + moov + mdat 或 moof+mdat（fragmented MP4 允许，但 ffprobe 必须可解码）

**Range 纪律**：只使用当前 Published Playback Page 已合法加载的 resource；标准 HTTP Range 顺序下载；不破解 signature/不伪造 token/不绕过。

**Range 失败** → `RANGE_RECONSTRUCTION_BLOCKED`（不绕过）；Playback Capture（captureStream+MediaRecorder）**暂不实现**（V2 明确 BLOCKED 后才考虑，且结果 = PLAYBACK_CAPTURE_REFERENCE 非 EXACT）。

## 17-22. 下载后 Harness 本地核验（FULL 文件到位时执行）

1. ffprobe：format/duration/width/height/video codec/audio codec/fps/bitrate/file size
2. **Duration Gate**：预期 ≈59s（允许 container rounding，约 58-60s）；明显偏离 → `MEDIA_IDENTITY_CONFLICT`
3. **Decode Gate**：ffmpeg decode validation 无 fatal error
4. **Hashes**：通过 Container+Duration+Decode 后才算 SHA256 + perceptual video fingerprint + audio fingerprint
5. **Cover Cross Validation**：note 6a8d75aa 已恢复 cover ↔ FULL video sparse keyframes 视觉兼容；明显不同 → IDENTITY_CONFLICT_REVIEW

**EXACT 升级条件（全满足）**：A 资源来自该 note 实际 Playback · B 完整 bytes · C valid MP4 · D duration≈59s · E decode PASS · F cover 兼容 → identity_confidence = EXACT_PUBLISHED_MEDIA

## 27-28. 状态修正

```
STAGE3A6_VIDEO_DISCOVERY_VALIDATED = TRUE
VIDEO_BYTE_RECOVERY = PARTIAL_INVALID
EXACT_PUBLISHED_MEDIA = 0
PHASE4_STAGE3B_READY = FALSE
Pilot20 / 155 / Segment / Cognition = 冻结
```

## 30. 20 问答复（当前状态）

1. **V1 非完整 MP4？** → **是**（无 ftyp/moov/mdat）2. **size=413921 记录？** → **是** 3. **旧文件 SHA256 记录？** → **是**（ff327aa3…）4. **ffprobe 失败？** → **是**（moov not found）5. **V1 是否 HTTP 206？** → **待 Probe 确认**（高度疑似）6. **Content-Range？** → 待 Probe 7. **Total media size？** → 待 Probe 8. **Accept-Ranges？** → 待 Probe 9. **首块 byte0 ftyp？** → 待 Reconstruct 10. **可 range reconstruct？** → 待 Probe（若 206 + total 可用）11-17. **FULL 文件相关** → 待浏览器执行 18. **EXACT 升级？** → 待核验 19. **失败类型** → 待定（RANGE_BLOCKED / NOT_STANDARD_MP4 / INCOMPLETE / IDENTITY_CONFLICT）20. **扩 Pilot20？** → **否**（Pilot1 FULL 完成前冻结）

## 31. 最终状态

**PILOT1_RANGE_RECOVERY_TOOL_READY**

## 产物
- `B003_PILOT1_RECOVERY_V1_FAILURE_ANALYSIS.json`（V1 失败分析）
- `B003_PILOT1_HTTP_RANGE_PROBE_V1.json`（探测模板，待浏览器填）
- `tools/B003_PILOT1_RANGE_AWARE_RECOVERY_V2.js`（Range 重建工具）
- `B003_PILOT1_FULL_MEDIA_VALIDATION_V1.json`（核验模板）
- 本报告 `docs/PHASE4_STAGE3A_6_PILOT1_BYTE_RECOVERY_REPAIR.md`

## 停点

**STOP** —— 等你浏览器执行 `__B003RangeProbe()` → 发我 Probe 摘要 → 我判断 200/206 路线 → 你执行 `__B003RangeReconstruct(probe)` → 保存 FULL.mp4 → 发我核验。未自动扩 Pilot20 · 未进 Content DNA。
