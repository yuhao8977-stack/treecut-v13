# PHASE 4 — B007 V0.6 媒体恢复报告（诚实结论）

- 日期: 2026-09-01 15:00:49
- 状态: **B007_V06_MEDIA_RECOVERY_NEEDS_REPAIR**

## 1. 结论
- Target 20 → 恢复 0；全部 **FAILED_NEEDS_HUMAN**（平台媒体观察被阻断）
- **NO FALSE PASS**：未虚构成功；未换样本；注册表如实记录

## 2. 阻断原因（技术证据）
{
  "class": "PLATFORM_MEDIA_OBSERVATION_BLOCKED",
  "detail": [
    "direct explore/{note_id} → HTTP 404 error_code=300031（xsec 门控；含 B007 2022-2026 各年代与随机 feed 笔记）",
    "页面自有 xsec（creator posted 响应携带）用于 explore 导航仍 404（creator 域 token 不授权前台 web）",
    "前台 feed：滚动 ~45 卡片 0 个 video 元素/时长角标；无任何视频媒体响应",
    "前台笔记页（经 feed/搜索/主页点击成功导航后）：无 video 元素挂载，无媒体响应",
    "B007 主页（带 xsec 导航）：笔记卡渲染不稳定（偶现样本卡可点击，但点击后无视频）；特定样本经搜索不可达",
    "Creator note-manager / 数据中心：卡片点击/行点击无 video、无 note_detail_new 视频 master URL",
    "B003 的 DIRECT_VIDEO_BYTES_AVAILABLE 来自人工打开的 creator note-detail 页面，自动化无法复现该页面态"
  ],
  "implication": "本环境（前台 viewer=楚姐账号 + 自动化上下文）不呈现/不播放已发布视频；无法经页面自有响应取得真实 MP4。",
  "no_false_pass": true,
  "no_sample_swap": true
}

## 3. 尝试概览（单 worker 串行纪律保持）
- 18 个探测脚本覆盖：直连 explore / xsec 导航 / feed 点击 / 搜索 / 主页 / Creator note-manager / Creator 数据中心
- 前台媒体响应观察：**0 条**视频媒体（video mime / mp4 / m3u8 / sns-video 全部无）
- 平台行为：前台笔记浏览受 xsec 门控；自动化上下文不呈现视频播放

## 4. 恢复覆盖
- target=20 / identity_verified=0 / media_observed=0 / recovered_exact=0 / failed_needs_human=20
- 技术覆盖：sha256=0 ffprobe=0 full_decode=0 duration_crosscheck=0 resolution=0 audio=0
- 重复检测：无恢复媒体，未执行（待媒体可得后做 SHA256 Exact Duplicate）

## 5. 存储与纪律
- C free before≈72.4GB / after≈72.4GB（**无媒体级下降**，无 STORAGE_POLICY_VIOLATION）
- 无凭证/无 signed URL 持久化；E 仅探测证据；Z 未写入（无通过验证的媒体）
- 注册表 `b007_published_media_recovery_v1`（20 行 FAILED_NEEDS_HUMAN）

## 6. V0.7 Readiness
- **NO**（无已恢复媒体，无法进入 Canonical Asset / Segments / ASR）

## 7. 架构师建议
- 平台对自动化上下文限制视频播放 → 需要受控人工输入（打开 creator note-detail 页面）或其它合法页面自有媒体入口
- 或评估是否需在前台使用 B007 自身账号会话（当前 viewer 为 楚姐 账号）
- 修复路径确认后重试；本报告保留全部探测证据与脚本

## 8. STOP
- 未自动进入 V0.7 / Segment / ASR / Cognition；等架构师决策。
