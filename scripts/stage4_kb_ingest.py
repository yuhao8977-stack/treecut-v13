# -*- coding: utf-8 -*-
"""Phase 4 Stage 1 — Knowledge Ingestion Engine（Excel → KnowledgeRecord）。

SOURCE INGESTION → PARSE → NORMALIZE → CLASSIFY → MAP → STORE → INDEX

输入：knowledge/source/TreeCut_行业认知知识库_V1.0.xlsx（01_知识主表）
输出：
  - knowledge/source_registry/source_registry.yaml（来源登记）
  - knowledge/<namespace>/*.json（每条知识一个文件或分组文件）
  - knowledge/knowledge_manifest.json（全量清单 + hash）
  - DATA_ROOT/knowledge_brain.db（SQLite 存储）

分类逻辑（知识类型）：
  - platform namespace → PLATFORM_RULE（TTL 30 天）
  - review_status 含"待数据验证"/"需盲测验证"/"待生产验证" → HYPOTHESIS
  - negative/source_type=production_rule → BUSINESS_RULE
  - 其余 → FACT（但 needs_source 标记按 source 是否可靠）
confidence 归一：0.9+→HIGH, 0.8+→MEDIUM_HIGH→用 Phase4 五档（VERY_HIGH/HIGH/MEDIUM/LOW/VERY_LOW）
"""
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = r"C:\Users\admin\github\treecut-v13"
KB_XLSX = os.path.join(REPO, "knowledge", "source", "TreeCut_行业认知知识库_V1.0.xlsx")
DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"

# namespace 映射：Excel namespace → Phase4 正式 namespace
NS_MAP = {
    "product": "product",
    "material": "materials_styles",
    "craft": "craft_trust",
    "function": "functions",
    "scene": "industry_taxonomy",   # 场景归入行业分类（指令 namespace）
    "user_need": "user_needs",
    "content_type": "content_types",
    "content_role": "content_roles",   # 内容角色独立
    "shot": "shot_ontology",
    "script": "semantic_mappings",  # 脚本节拍→语义映射
    "business_value": "business_value_rules",
    "negative": "negative_rules",
    "platform": "platform_compliance",
    "professional": "industry_taxonomy",  # 专业知识归行业分类
}

# source_type 归一
ST_MAP = {
    "业务词典": "business_dictionary",
    "运营业务模型": "operational_model",
    "运营假设": "operational_model",
    "生产规则": "production_rule",
    "平台官方": "platform_official",
    "专业机构参考": "professional_institution",
    "视频生产模型": "production_rule",
    "内容生产模型": "production_rule",
}

# confidence 0-1 → Phase4 五档
def conf_tier(c):
    try:
        c = float(c)
    except Exception:
        return "UNKNOWN"
    if c >= 0.9:
        return "HIGH"
    if c >= 0.8:
        return "MEDIUM"
    if c >= 0.6:
        return "LOW"
    return "VERY_LOW"


def classify_type(ns, review_status, source_type):
    if ns == "platform":
        return "PLATFORM_RULE"
    if any(k in (review_status or "") for k in ("待数据验证", "需盲测验证", "待生产验证", "待持续复核")):
        return "HYPOTHESIS"
    if source_type in ("production_rule",) or ns == "negative":
        return "BUSINESS_RULE"
    return "FACT"


def main():
    import openpyxl
    wb = openpyxl.load_workbook(KB_XLSX, read_only=True, data_only=True)
    ws = wb["01_知识主表"]
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    idx = {h: i for i, h in enumerate(header)}
    wb.close()

    records = []
    for r in rows[1:]:
        if not r or not r[idx["knowledge_id"]]:
            continue
        kid = str(r[idx["knowledge_id"]]).strip()
        ns_src = str(r[idx["namespace"]] or "").strip()
        ns = NS_MAP.get(ns_src, ns_src)
        title = str(r[idx["标准名称"]] or "").strip()
        statement = str(r[idx["定义/业务含义"]] or "").strip()
        alias = str(r[idx["别名/同义词"]] or "").strip()
        pos_ev = str(r[idx["正向证据"]] or "").strip()
        neg_ev = str(r[idx["反向/排除证据"]] or "").strip()
        usage = str(r[idx["适用场景"]] or "").strip()
        role = str(r[idx["关联内容角色"]] or "").strip()
        source_type_s = str(r[idx["source_type"]] or "").strip()
        source_url = str(r[idx["source_url"]] or "").strip()
        conf_raw = r[idx["confidence"]]
        review = str(r[idx["review_status"]] or "").strip()
        version = str(r[idx["version"]] or "1.0").strip()
        ttl = r[idx["ttl_days"]]
        note = str(r[idx["备注"]] or "").strip()

        st = ST_MAP.get(source_type_s, source_type_s or "UNKNOWN")
        kt = classify_type(ns_src, review, st)
        conf = conf_tier(conf_raw)
        # needs_source：无 URL 且 source_type 非业务词典/平台官方
        needs_source = (not source_url and st not in ("business_dictionary", "platform_official"))
        status = "ACTIVE" if kt == "FACT" else ("DRAFT" if kt == "HYPOTHESIS" else "ACTIVE")
        if kt == "PLATFORM_RULE":
            status = "ACTIVE"  # 动态规则（TTL 控制有效期）

        rec = {
            "knowledge_id": kid,
            "namespace": ns,
            "knowledge_type": kt,
            "title": title,
            "statement": statement,
            "structured_payload": {
                "aliases": [a.strip() for a in alias.split("|") if a.strip()],
                "positive_evidence": pos_ev, "negative_evidence": neg_ev,
                "usage_scene": usage, "content_roles": [x.strip() for x in role.split("|") if x.strip()],
                "category1": str(r[idx["一级分类"]] or "").strip(),
                "category2": str(r[idx["二级分类"]] or "").strip(),
            },
            "source": source_url or st,
            "source_type": st,
            "source_version": version,
            "confidence": conf,
            "status": status,
            "effective_date": "2026-08-26",
            "expires_at": None,
            "ttl_days": int(ttl) if ttl else None,
            "tags": [ns_src, kt, str(r[idx["一级分类"]] or "").strip()],
            "related_entities": [],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "updated_at": None,
            "supersedes": None, "superseded_by": None,
            "needs_source": needs_source,
            "note": note,
        }
        records.append(rec)

    print("导入知识条数:", len(records))
    print("按类型:", dict(Counter(r["knowledge_type"] for r in records)))
    print("按 namespace:", dict(Counter(r["namespace"] for r in records)))
    print("按 confidence:", dict(Counter(r["confidence"] for r in records)))
    print("NEEDS_SOURCE:", sum(1 for r in records if r["needs_source"]))

    # ---- 写入 knowledge/<namespace>/knowledge.json ----
    by_ns = defaultdict(list)
    for r in records:
        by_ns[r["namespace"]].append(r)
    total_files = 0
    for ns, recs in by_ns.items():
        d = os.path.join(REPO, "knowledge", ns)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "knowledge.json")
        json.dump({"namespace": ns, "count": len(recs), "records": recs},
                  open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        total_files += 1
    print("写入 namespace 文件:", total_files)

    # ---- SQLite ----
    db = os.path.join(DATA_ROOT, "knowledge_brain.db")
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE IF NOT EXISTS knowledge_entries(
        knowledge_id TEXT PRIMARY KEY, namespace TEXT, knowledge_type TEXT,
        title TEXT, statement TEXT, structured_payload TEXT,
        source TEXT, source_type TEXT, source_version TEXT,
        confidence TEXT, status TEXT, effective_date TEXT, expires_at TEXT,
        ttl_days INTEGER, tags TEXT, related_entities TEXT,
        created_at TEXT, updated_at TEXT, supersedes TEXT, superseded_by TEXT,
        needs_source INTEGER, note TEXT, source_sha256 TEXT)""")
    conn.execute("DELETE FROM knowledge_entries")
    for r in records:
        payload = json.dumps(r["structured_payload"], ensure_ascii=False)
        tags = json.dumps(r["tags"], ensure_ascii=False)
        conn.execute("""INSERT INTO knowledge_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (r["knowledge_id"], r["namespace"], r["knowledge_type"], r["title"],
                      r["statement"], payload, r["source"], r["source_type"], r["source_version"],
                      r["confidence"], r["status"], r["effective_date"], r["expires_at"],
                      r["ttl_days"], tags, json.dumps(r["related_entities"]),
                      r["created_at"], r["updated_at"], r["supersedes"], r["superseded_by"],
                      1 if r["needs_source"] else 0, r["note"], None))
    conn.commit()
    conn.close()
    print("SQLite ->", db, "| 条数:", len(records))

    # ---- Manifest ----
    canon = json.dumps(records, ensure_ascii=False, sort_keys=True)
    manifest = {"manifest": "KNOWLEDGE_MANIFEST_V1", "source_files": {
        "xlsx": {"file": "knowledge/source/TreeCut_行业认知知识库_V1.0.xlsx",
                 "sha256": "1175CF244FBA5716564B2979CB76E6595A14FEB2C7F2E2754667C4D5F92B23FB"},
        "docx": {"file": "knowledge/source/TreeCut_行业认知知识库_V1.0.docx",
                 "sha256": "DC3B004B09169314D6723ABFC63DE459AAF90CAC4287DBFE46E493FFADEA1EF8"}},
        "record_count": len(records),
        "by_type": dict(Counter(r["knowledge_type"] for r in records)),
        "by_namespace": dict(Counter(r["namespace"] for r in records)),
        "by_confidence": dict(Counter(r["confidence"] for r in records)),
        "needs_source_count": sum(1 for r in records if r["needs_source"]),
        "records_sha256": hashlib.sha256(canon.encode("utf-8")).hexdigest(),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
    mp = os.path.join(REPO, "knowledge", "knowledge_manifest.json")
    json.dump(manifest, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", mp)
    print("records_sha256:", manifest["records_sha256"])


if __name__ == "__main__":
    main()
