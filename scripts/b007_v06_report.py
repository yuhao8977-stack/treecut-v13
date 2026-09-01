# -*- coding: utf-8 -*-
"""V0.6 — 诚实收尾：注册表(20×FAILED) + 证据 + 输出 + 报告（平台阻断，NO FALSE PASS）。"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
REPO = Path(r"C:\Users\admin\github\treecut-v13")

BLOCKER = {
    "class": "PLATFORM_MEDIA_OBSERVATION_BLOCKED",
    "detail": [
        "direct explore/{note_id} → HTTP 404 error_code=300031（xsec 门控；含 B007 2022-2026 各年代与随机 feed 笔记）",
        "页面自有 xsec（creator posted 响应携带）用于 explore 导航仍 404（creator 域 token 不授权前台 web）",
        "前台 feed：滚动 ~45 卡片 0 个 video 元素/时长角标；无任何视频媒体响应",
        "前台笔记页（经 feed/搜索/主页点击成功导航后）：无 video 元素挂载，无媒体响应",
        "B007 主页（带 xsec 导航）：笔记卡渲染不稳定（偶现样本卡可点击，但点击后无视频）；特定样本经搜索不可达",
        "Creator note-manager / 数据中心：卡片点击/行点击无 video、无 note_detail_new 视频 master URL",
        "B003 的 DIRECT_VIDEO_BYTES_AVAILABLE 来自人工打开的 creator note-detail 页面，自动化无法复现该页面态",
    ],
    "implication": "本环境（前台 viewer=楚姐账号 + 自动化上下文）不呈现/不播放已发布视频；无法经页面自有响应取得真实 MP4。",
    "no_false_pass": True,
    "no_sample_swap": True,
}


def main() -> int:
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    manifest = json.loads((OUT / "B007_SAMPLE20_V1.json").read_text(encoding="utf-8"))
    samples = manifest["samples"]

    conn = sqlite3.connect(DB, timeout=30)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS b007_published_media_recovery_v1(
      note_id TEXT PRIMARY KEY, sample_id TEXT, expected_note_id TEXT, actual_note_id TEXT,
      recovery_status TEXT, source_type TEXT, container TEXT, byte_size INTEGER,
      sha256 TEXT, duration REAL, width INTEGER, height INTEGER, fps REAL,
      video_codec TEXT, audio_codec TEXT, creator_duration REAL, duration_match_status TEXT,
      final_path TEXT, recovered_at TEXT, validation_version TEXT,
      block_reason TEXT, attempts INTEGER, created_at REAL);
    """)
    conn.execute("DELETE FROM b007_published_media_recovery_v1")
    rows = []
    for s in samples:
        rows.append((s["note_id"], s["sample_id"], s["note_id"], None, "FAILED_NEEDS_HUMAN",
                     None, None, None, None, None, None, None, None, None, None,
                     s["duration"], None, None, ts, "V0.6",
                     "PLATFORM_MEDIA_OBSERVATION_BLOCKED（见 B007_V06_MEDIA_EXCEPTIONS_V1.json）",
                     3, now.timestamp()))
    conn.executemany(
        "INSERT INTO b007_published_media_recovery_v1("
        "note_id,sample_id,expected_note_id,actual_note_id,recovery_status,source_type,container,"
        "byte_size,sha256,duration,width,height,fps,video_codec,audio_codec,creator_duration,"
        "duration_match_status,final_path,recovered_at,validation_version,block_reason,attempts,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM b007_published_media_recovery_v1").fetchone()[0]
    conn.close()

    # ---- 输出 ----
    recovery = {
        "target_samples": 20, "identity_verified": 0, "media_observed": 0, "recovered_exact": 0,
        "already_recovered": 0, "quarantined": 0, "failed_needs_human": 20, "note_unavailable": 0,
        "samples": [{"sample_id": s["sample_id"], "note_id": s["note_id"], "stratum": s["primary_stratum"],
                     "status": "FAILED_NEEDS_HUMAN", "blocker": BLOCKER["class"]} for s in samples],
    }
    (OUT / "B007_SAMPLE20_MEDIA_RECOVERY_V1.json").write_text(
        json.dumps(recovery, ensure_ascii=False, indent=2), encoding="utf-8")

    tech = {"sha256_coverage": 0, "ffprobe_coverage": 0, "full_decode_coverage": 0,
            "duration_crosscheck_coverage": 0, "resolution_coverage": 0, "audio_coverage": 0,
            "note": "0/20 媒体恢复；无技术元数据（平台媒体观察被阻断）"}
    (OUT / "B007_SAMPLE20_MEDIA_TECH_METADATA_V1.json").write_text(
        json.dumps(tech, ensure_ascii=False, indent=2), encoding="utf-8")

    dups = {"unique_recovered_media_sha256": 0, "exact_duplicate_groups": [],
            "notes_sharing_media": [], "note": "无恢复媒体；Exact Duplicate 检测待媒体可得后执行"}
    (OUT / "B007_SAMPLE20_MEDIA_DUPLICATES_V1.json").write_text(
        json.dumps(dups, ensure_ascii=False, indent=2), encoding="utf-8")

    (OUT / "B007_SAMPLE20_MEDIA_EXCEPTIONS_V1.json").write_text(
        json.dumps({"blocker": BLOCKER, "probe_evidence": [
            "b007_v06_media_probe.py / access_probe.py / xsec_nav.py / fe_access.py / fe_click.py",
            "search_probe.py / video_ep.py / links_probe.py / prof_xsec.py / single_recovery.py",
            "feed_video.py / dual_probe.py / final_fe.py / creator_media_probe.py / creator_card.py",
            "creator_detail.py / creator_modal.py / profile_full.py",
        ], "autoplay_flag_added": "profile_manager.py --autoplay-policy=no-user-gesture-required（未改变结果）"},
        ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Review MD ----
    lines = [f"# B007 Sample20 媒体恢复评审（V0.6）",
             "",
             f"- 日期: {ts}",
             f"- 状态: **B007_V06_MEDIA_RECOVERY_NEEDS_REPAIR**（0/20；平台媒体观察被阻断）",
             "",
             "## 20 条状态",
             "",
             "| # | 组 | note_id | 状态 | 阻断原因 |",
             "|---|---|---|---|---|"]
    for i, s in enumerate(samples, 1):
        lines.append(f"| {i} | {s['primary_stratum'].split('_')[0]} | {s['note_id']} | FAILED_NEEDS_HUMAN | {BLOCKER['class']} |")
    lines += ["",
              "## 阻断证据（摘）",
              "- 前台 explore 直连全部 404（error_code=300031，xsec 门控）",
              "- 前台 feed/笔记页：0 视频元素、0 媒体响应（~45 卡片扫描 + 多次导航）",
              "- 带 xsec 的主页笔记卡偶现可点，点击后无视频；特定样本经搜索不可达",
              "- Creator 平台：note-manager/数据中心交互无视频 master URL",
              "",
              "## 纪律",
              "- **NO FALSE PASS**：未虚构任何恢复成功；未换样本",
              "- 注册表 20 条 FAILED_NEEDS_HUMAN（`b007_published_media_recovery_v1`）",
              "- 无凭证/无 signed URL 持久化；无 C 盘媒体写入",
              "",
              "## 建议（架构师决策）",
              "- 若平台对自动化上下文限制播放：需人工打开 creator note-detail 页面（B003 方式）作为受控输入",
              "- 或评估其它合法页面自有媒体入口后再重试；本报告保留全部探测证据",
              "- V0.7 暂不可启动（无已恢复媒体）"]
    (OUT / "B007_SAMPLE20_MEDIA_RECOVERY_REVIEW_V1.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- Report ----
    md = f"""# PHASE 4 — B007 V0.6 媒体恢复报告（诚实结论）

- 日期: {ts}
- 状态: **B007_V06_MEDIA_RECOVERY_NEEDS_REPAIR**

## 1. 结论
- Target 20 → 恢复 0；全部 **FAILED_NEEDS_HUMAN**（平台媒体观察被阻断）
- **NO FALSE PASS**：未虚构成功；未换样本；注册表如实记录

## 2. 阻断原因（技术证据）
{json.dumps(BLOCKER, ensure_ascii=False, indent=2)}

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
"""
    (REPO / "docs" / "PHASE4_B007_V06_MEDIA_RECOVERY_REPORT.md").write_text(md, encoding="utf-8")

    print(f"registry rows={n}; outputs written; status=NEEDS_REPAIR")
    print(json.dumps({"recovered": 0, "failed_needs_human": 20, "blocker": BLOCKER["class"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
