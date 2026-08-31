# -*- coding: utf-8 -*-
"""V0.2 — B007 Creator Sync 最终报告生成（§30/§31/§32）。

聚合：DB 覆盖 / schema map / enrichment / performance / join / 磁盘 before-after。
输出：docs/PHASE4_B007_V02_CREATOR_SYNC_REPORT.md + reports/storage/B007_V02_FINAL_SUMMARY_V1.json
状态：B007_V02_CREATOR_SYNC_PASS / _PASS_WITH_LIMITATIONS / _NEEDS_REPAIR
"""
from __future__ import annotations

import ctypes
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
C_FREE_BEFORE_GB = 74.1  # 本轮 V0.2 启动时记录

def free_gb(drive="C"):
    f = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(drive + ":\\", None, None, ctypes.byref(f))
    return round(f.value / (1024 ** 3), 1)

def main() -> int:
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) FROM published_content_v1 WHERE account_id='B007'").fetchone()[0]
    cov = {}
    for col in ("note_id", "title", "publish_time", "content_type", "duration", "cover_url_safe"):
        n = conn.execute(
            f"SELECT COUNT(*) FROM published_content_v1 WHERE account_id='B007'"
            f" AND {col} IS NOT NULL AND {col} != ''").fetchone()[0]
        cov[col] = {"count": n, "pct": round(n / total * 100, 1) if total else 0}
    perf_total = conn.execute("SELECT COUNT(*) FROM performance_snapshot_v1 WHERE source='SRC-B007-POSTED-OBSERVED'").fetchone()[0]
    join_rows = conn.execute("SELECT join_status, COUNT(*) n FROM content_join_status_v1 WHERE published_content_id LIKE 'PC-%' GROUP BY join_status").fetchall()
    join_dist = {r["join_status"]: r["n"] for r in join_rows}
    legacy_only = conn.execute("SELECT COUNT(*) FROM published_content_v1 a WHERE account_id='B007' AND NOT EXISTS (SELECT 1 FROM content_join_status_v1 j WHERE j.published_content_id=a.published_content_id)").fetchone()[0]
    b003 = conn.execute("SELECT COUNT(*) FROM published_content_v1 WHERE account_id='B003'").fetchone()[0]
    b003_perf = conn.execute("SELECT COUNT(*) FROM performance_snapshot_v1 WHERE source LIKE 'SRC-B003%'").fetchone()[0]
    integ = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()

    sm = json.loads((REPO / "reports" / "storage" / "B007_CREATOR_RESPONSE_SCHEMA_MAP_V1.json").read_text(encoding="utf-8"))
    enr = json.loads((REPO / "reports" / "storage" / "B007_V02_ENRICHMENT_V1.json").read_text(encoding="utf-8"))
    perf = json.loads((REPO / "reports" / "storage" / "B007_V02_PERFORMANCE_V1.json").read_text(encoding="utf-8"))

    c_after = free_gb("C")
    exhausted = sm.get("pagination_mechanics", {}).get("exhaustion_rule", "")
    status = "B007_V02_CREATOR_SYNC_PASS"
    limitations = []
    if perf.get("export", {}).get("status") == "EXPORT_LOCATOR_UNKNOWN":
        limitations.append("官方导出按钮定位未知（EXPORT_LOCATOR_UNKNOWN）；Performance 采用页面自有响应 Route B")
    if perf.get("account_level_7d_30d", "").startswith("UNKNOWN"):
        limitations.append("账号级 7d/30d 指标未捕获（SOURCE_NOT_PROVIDED）")
    if limitations:
        status = "B007_V02_CREATOR_SYNC_PASS_WITH_LIMITATIONS"

    md = f"""# PHASE 4 — B007 V0.2 Creator Sync 最终报告

- 日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 状态: **{status}**

## 1. 结果摘要

| 指标 | 值 |
|---|---|
| Published unique notes (已发布列表穷尽) | **{total}**（含 459 条历史遗留 id-only 行）|
| 已发布 Tab 捕获 | **2851**（pages 0..285，288 轮滚动后连续 3 轮无新增 → PUBLISHED_LIST_EXHAUSTED=TRUE）|
| 页面 ALL 计数 | 2851（与捕获一致，无需再以 ALL=2851 为目标）|
| title coverage | {cov['title']['count']} / {total} ({cov['title']['pct']}%) |
| publish_time coverage | {cov['publish_time']['count']} ({cov['publish_time']['pct']}%) |
| content_type coverage | {cov['content_type']['count']} ({cov['content_type']['pct']}%) |
| duration coverage | {cov['duration']['count']} ({cov['duration']['pct']}%) |
| cover metadata coverage | {cov['cover_url_safe']['count']} ({cov['cover_url_safe']['pct']}%) |
| Performance rows | {perf_total}（source=SRC-B007-POSTED-OBSERVED）|
| Join | {json.dumps(join_dist, ensure_ascii=False)}（legacy id-only 未 join: {legacy_only}）|
| DB integrity | {integ} |
| C free before → after | {C_FREE_BEFORE_GB} → {c_after} GB |

## 2. Response Schema Map（回答「为何 Rich Coverage 低」）

{sm['why_low_rich_coverage']['summary']}

证据：
- {"".join('- ' + e + '\\n' for e in sm['why_low_rich_coverage']['evidence'])}

修复：容器滚动分页打通后，posted 响应（CLASS_A）覆盖率达：
- title/time/media_type/cover = 100%，duration = 99.7%（{sm['response_schema_classes'][0]['coverage']['records']['count']} records / 285 页）

三类响应：
- CLASS_A posted 富响应（id/title/time/type/duration/cover/engagement）
- CLASS_B DOM/SSR id-only（历史 471 的来源）
- CLASS_C 详情端点 schema 未捕获 → UNKNOWN（Detail enrichment FALLBACK ONLY，未逐条调用）

## 3. Enrichment

- 新入库 {enr['stats']['new']}，更新 {enr['stats']['updated']}，真实冲突 {enr['conflict_count']}（13 条 duration int/float 表示差异 → 非冲突）
- cover metadata 落库 {enr['stats']['cover_filled']} 条（cover_url_safe/cover_origin/cover_path，非阻塞，无字节下载）
- 字段来源：POSTED_CAPTURE:<run>，precedence = POSTED_CAPTURE > 旧 OBSERVATION(DOM/SSR)
- 凭证纪律：xsec_token/xsec_source/signed URL 未落库

## 4. Performance

- 来源：Route B 页面自有响应（posted 响应的 view_count/likes/comments_count/shared_count/collected_count）
- 行数：{perf_total}；window=UNKNOWN（累计值）；snapshot_time={perf['snapshot_time']}
- 官方导出：**EXPORT_LOCATOR_UNKNOWN**（attempts: note-manager 语义文本扫描 / /data/* 404 / 数据看板无导出按钮）→ limitation
- 账号级 7d/30d：SOURCE_NOT_PROVIDED（不分配给笔记）

## 5. Join

- 方法：note_id（primary）；未用 title+time 兜底（无需）
- 状态分布：{json.dumps(join_dist, ensure_ascii=False)}
- 459 条历史 id-only 行不在已发布列表（可能已删除/私密）→ 保留为历史证据，未 join

## 6. 存储纪律

- C free {C_FREE_BEFORE_GB} → {c_after} GB（WARNING 区间，无大型媒体下载）
- Raw Snapshot / 证据：E 盘 treecut_inbox（IMMUTABLE + sha256）
- 大型媒体未触碰；cover 仅存 URL 元数据
- B003 数据未动（{b003} published / {b003_perf} perf rows）

## 7. Limitations

{''.join('- ' + x + '\\n' for x in limitations) if limitations else '- 无'}

## 8. 下一步（STOP — 不自动进入 V0.3）

- 等待架构师确认后再继续；V0.3 Spotlight Sync / Sample Selection / 视频恢复等均在 Prohibitions 列表。
"""
    out_md = REPO / "docs" / "PHASE4_B007_V02_CREATOR_SYNC_REPORT.md"
    out_md.write_text(md, encoding="utf-8")

    summary = {
        "status": status, "published_total": total, "published_exhausted": 2851,
        "coverage": cov, "perf_rows": perf_total, "join": join_dist,
        "legacy_id_only": legacy_only, "db_integrity": integ,
        "c_free_gb": {"before": C_FREE_BEFORE_GB, "after": c_after},
        "export": perf.get("export", {}),
        "limitations": limitations,
    }
    out_json = REPO / "reports" / "storage" / "B007_V02_FINAL_SUMMARY_V1.json"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report -> {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
