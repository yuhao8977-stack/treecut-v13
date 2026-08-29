# -*- coding: utf-8 -*-
"""Phase 4 Stage 1.5 — Knowledge Audit V1.1（STEP 12-13）。"""
import io
import json
import os
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = r"C:\Users\admin\github\treecut-v13"
DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "knowledge_brain.db")


def main():
    import sqlite3
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM knowledge_entries")]
    conn.close()
    print("总条数:", len(rows))
    print("knowledge_type:", dict(Counter(r["knowledge_type"] for r in rows)))
    print("namespace:", dict(Counter(r["namespace"] for r in rows)))
    print("source_requirement:", dict(Counter(r["source_requirement_class"] for r in rows)))
    print("status:", dict(Counter(r["status"] for r in rows)))
    print("confidence:", dict(Counter(r["confidence"] for r in rows)))
    print("validation_status:", dict(Counter(r["validation_status"] for r in rows)))

    # duplicate
    ids = [r["knowledge_id"] for r in rows]
    dup = [k for k, v in Counter(ids).items() if v > 1]
    print("duplicate:", dup if dup else "NONE")

    # conflict（同 title 不同 statement，且同 namespace —— 跨 namespace 是合法 RELATED）
    by_title = defaultdict(list)
    for r in rows:
        by_title[r["title"]].append(r)
    conflicts = []
    related_cross_ns = []
    semantic_dup = []  # 同 namespace 同概念（KB 主表 vs P4 Taxonomy），语义重复非逻辑冲突
    for t, g in by_title.items():
        if len({x["statement"] for x in g}) <= 1:
            continue
        ns_set = {x["namespace"] for x in g}
        entry = {"title": t, "n": len(g), "ids": [x["knowledge_id"] for x in g]}
        if len(ns_set) > 1:
            related_cross_ns.append(entry)
        else:
            # 同 namespace：判断是否语义重复（KB- 与 P4- 对）还是真冲突
            prefixes = {x["knowledge_id"].split("-")[0] for x in g}
            if len(prefixes) > 1:
                semantic_dup.append(entry)
            else:
                conflicts.append(entry)
    print("conflicts(同 namespace 同前缀):", len(conflicts))
    print("semantic_dup(KB vs P4 Taxonomy):", len(semantic_dup))
    print("related_cross_ns(合法跨层):", len(related_cross_ns))

    # stale platform rules（TTL 检查 —— 这里记录 TTL 已过期的，按导入日 2026-08-29 + TTL）
    from datetime import datetime, timedelta
    today = datetime(2026, 8, 29)
    stale = []
    for r in rows:
        if r["knowledge_type"] == "PLATFORM_RULE":
            ttl = r["ttl_days"]
            if ttl is None or ttl <= 0:
                stale.append({"id": r["knowledge_id"], "reason": "no_ttl"})
    print("platform stale:", stale if stale else "NONE（10 条全 TTL=30）")

    # needs external verification
    ext = [r for r in rows if r["needs_external_verification"]]
    ext_by_ns = Counter(r["namespace"] for r in ext)
    print("EXTERNAL_SOURCE_REQUIRED:", len(ext), dict(ext_by_ns))

    # HYPOTHESIS 是否全 DRAFT
    hyp_non_draft = [r["knowledge_id"] for r in rows
                     if r["knowledge_type"] == "HYPOTHESIS" and r["status"] != "DRAFT"]
    print("HYPOTHESIS 非 DRAFT:", hyp_non_draft if hyp_non_draft else "NONE（全部 DRAFT ✓）")

    # 未验证 FACT 不得 ACTIVE HIGH
    fact_active_high = [r["knowledge_id"] for r in rows
                        if r["knowledge_type"] == "FACT" and r["status"] == "ACTIVE"
                        and r["confidence"] == "HIGH" and r["needs_external_verification"]]
    print("未验证 FACT 却 ACTIVE HIGH:", fact_active_high if fact_active_high else "NONE ✓")

    out = {"manifest": "KNOWLEDGE_AUDIT_V1_1", "total": len(rows),
           "by_type": dict(Counter(r["knowledge_type"] for r in rows)),
           "by_namespace": dict(Counter(r["namespace"] for r in rows)),
           "by_source_req": dict(Counter(r["source_requirement_class"] for r in rows)),
           "by_status": dict(Counter(r["status"] for r in rows)),
           "by_confidence": dict(Counter(r["confidence"] for r in rows)),
           "by_validation_status": dict(Counter(r["validation_status"] for r in rows)),
           "duplicate": dup, "conflicts": conflicts, "related_cross_ns": related_cross_ns,
           "semantic_dup_candidates": semantic_dup,
           "stale_platform": stale,
           "external_required_count": len(ext),
           "external_by_namespace": dict(ext_by_ns),
           "hypothesis_all_draft": not hyp_non_draft,
           "unverified_fact_active_high": fact_active_high}
    p = os.path.join(REPO, "knowledge", "knowledge_audit_v1_1.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
