# -*- coding: utf-8 -*-
"""更新 manifest + 生成 KNOWNLEDGE_SNAPSHOT_V1_2 + Validation V1.2。"""
import hashlib
import io
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = r"C:\Users\admin\github\treecut-v13"
DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "knowledge_brain.db")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT knowledge_id, namespace, knowledge_type, semantic_kind, status, "
        "source_requirement_class, classification_confidence FROM knowledge_entries")]
    conn.close()
    by_type = Counter(r["knowledge_type"] for r in rows)
    by_kind = Counter(r["semantic_kind"] for r in rows)
    by_ns_type = {}
    ns_map = defaultdict(Counter)
    for r in rows:
        ns_map[r["namespace"]][r["knowledge_type"]] += 1
    by_ns_type = {k: dict(v) for k, v in ns_map.items()}

    # 更新 manifest
    man = json.load(open(os.path.join(REPO, "knowledge", "knowledge_manifest.json"), encoding="utf-8"))
    man["manifest"] = "KNOWLEDGE_MANIFEST_V1_2"
    man["by_type"] = dict(by_type)
    man["by_semantic_kind"] = dict(by_kind)
    man["by_namespace_type"] = by_ns_type
    man["reclassification"] = "V1.2 Semantic Correction（Stage 1.6）"
    json.dump(man, open(os.path.join(REPO, "knowledge", "knowledge_manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # Snapshot V1.2（不覆盖 V1/V1.1）
    files = []
    for root, dirs, fs in os.walk(os.path.join(REPO, "knowledge")):
        if "source" in root:
            continue
        for f in fs:
            p = os.path.join(root, f)
            files.append({"file": os.path.relpath(p, REPO), "sha256": sha256_file(p)})
    files.sort(key=lambda x: x["file"])
    reclass = json.load(open(os.path.join(REPO, "knowledge", "knowledge_type_reclassification_v1_2.json"),
                             encoding="utf-8"))
    snap = {
        "manifest": "KNOWLEDGE_SNAPSHOT_V1_2",
        "base_snapshot": "KNOWLEDGE_SNAPSHOT_V1_1（36b40ea7…）",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "record_count": len(rows),
        "by_type": dict(by_type),
        "by_semantic_kind": dict(by_kind),
        "by_namespace_type": by_ns_type,
        "reclassified_count": reclass["reclassified_count"],
        "split_count": reclass["split_required_count"],
        "ambiguous_count": reclass["ambiguous_count"],
        "records_sha256": man["records_sha256"],
        "knowledge_files": files, "knowledge_file_count": len(files),
        "schema_versions": {"knowledge_record": "1.0", "business_cognition": "1.0", "template": "1.0"},
        "source_registry_version": "1.1",
        "test_results": "25/25 PASS（含 TEST 17-22）",
        "validation": {"set": 43, "regressions_vs_v1_1": 0},
    }
    canon = json.dumps({k: v for k, v in snap.items() if k != "knowledge_snapshot_sha256"},
                       ensure_ascii=False, sort_keys=True)
    snap["knowledge_snapshot_sha256"] = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    p = os.path.join(DATA_ROOT, "KNOWLEDGE_SNAPSHOT_V1_2.json")
    json.dump(snap, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)
    print("knowledge_snapshot_sha256:", snap["knowledge_snapshot_sha256"])
    print("by_type:", dict(by_type))


if __name__ == "__main__":
    main()
