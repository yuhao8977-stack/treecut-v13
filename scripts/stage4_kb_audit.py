# -*- coding: utf-8 -*-
"""Phase 4 Stage 1 — Knowledge Audit（指令 §63-65）。

输出：按 namespace/type/status/confidence 分布 + 重复/冲突/缺 source/需人工确认项。
"""
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = r"C:\Users\admin\github\treecut-v13"


def load_all():
    recs = []
    manifest = json.load(open(os.path.join(REPO, "knowledge", "knowledge_manifest.json"), encoding="utf-8"))
    for ns_dir in os.listdir(os.path.join(REPO, "knowledge")):
        p = os.path.join(REPO, "knowledge", ns_dir, "knowledge.json")
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            recs.extend(d["records"])
    return recs, manifest


def main():
    recs, manifest = load_all()
    print("总条数:", len(recs))
    print("by_type:", dict(Counter(r["knowledge_type"] for r in recs)))
    print("by_namespace:", dict(Counter(r["namespace"] for r in recs)))
    print("by_status:", dict(Counter(r["status"] for r in recs)))
    print("by_confidence:", dict(Counter(r["confidence"] for r in recs)))

    # 重复（knowledge_id 唯一性 + 语义重复：同 title 不同 id）
    ids = [r["knowledge_id"] for r in recs]
    dup_id = [k for k, v in Counter(ids).items() if v > 1]
    title_map = defaultdict(list)
    for r in recs:
        title_map[r["title"]].append(r["knowledge_id"])
    semantic_dup = {t: v for t, v in title_map.items() if len(v) > 1}
    print("\nduplicate knowledge_id:", dup_id if dup_id else "NONE")
    print("semantic duplicate (same title):", dict(semantic_dup) if semantic_dup else "NONE")

    # 冲突（同 title 不同 statement 或同 namespace 相反语义）
    conflicts = []
    by_title = defaultdict(list)
    for r in recs:
        by_title[r["title"]].append(r)
    for t, group in by_title.items():
        stmts = {r["statement"] for r in group}
        if len(stmts) > 1:
            conflicts.append({"title": t, "count": len(group),
                              "ids": [r["knowledge_id"] for r in group],
                              "statements": list(stmts)[:2]})
    print("conflicts:", len(conflicts))
    for c in conflicts[:5]:
        print("  ", c)

    # 缺 source
    no_source = [r for r in recs if not r.get("source") or r.get("source") in ("", "UNKNOWN")]
    needs_source = [r for r in recs if r.get("needs_source")]
    print("\n缺 source:", len(no_source))
    print("NEEDS_SOURCE:", len(needs_source))
    ns_by_ns = Counter(r["namespace"] for r in needs_source)
    print("NEEDS_SOURCE by namespace:", dict(ns_by_ns))

    # 需人工确认（HYPOTHESIS + needs_source 或 DISPUTED）
    manual = [r for r in recs if r["knowledge_type"] == "HYPOTHESIS" or r.get("needs_source")]
    print("\n需人工/外部确认项:", len(manual))

    # 平台规则 TTL 检查
    plat = [r for r in recs if r["knowledge_type"] == "PLATFORM_RULE"]
    no_ttl = [r["knowledge_id"] for r in plat if not r.get("ttl_days")]
    print("PLATFORM_RULE:", len(plat), "| 缺 TTL:", no_ttl if no_ttl else "NONE")

    audit = {"manifest": "KNOWLEDGE_AUDIT_V1",
             "total": len(recs),
             "by_type": dict(Counter(r["knowledge_type"] for r in recs)),
             "by_namespace": dict(Counter(r["namespace"] for r in recs)),
             "by_status": dict(Counter(r["status"] for r in recs)),
             "by_confidence": dict(Counter(r["confidence"] for r in recs)),
             "duplicate_ids": dup_id, "semantic_duplicates": semantic_dup,
             "conflicts": conflicts, "no_source_count": len(no_source),
             "needs_source_count": len(needs_source),
             "needs_source_by_namespace": dict(ns_by_ns),
             "manual_review_count": len(manual),
             "platform_rule_missing_ttl": no_ttl,
             "records_sha256": manifest["records_sha256"]}
    p = os.path.join(REPO, "knowledge", "knowledge_audit.json")
    json.dump(audit, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
