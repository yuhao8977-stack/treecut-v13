# -*- coding: utf-8 -*-
"""Phase 4 Stage 1.5 — KNOWLEDGE_SNAPSHOT_V1_1（V1.1 合并后快照，不覆盖 V1）。"""
import hashlib
import io
import json
import os
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = r"C:\Users\admin\github\treecut-v13"
DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    files = []
    for root, dirs, fs in os.walk(os.path.join(REPO, "knowledge")):
        if "source" in root:
            continue  # 源文件单独记录
        for f in fs:
            p = os.path.join(root, f)
            files.append({"file": os.path.relpath(p, REPO), "sha256": sha256_file(p)})
    files.sort(key=lambda x: x["file"])

    manifest = json.load(open(os.path.join(REPO, "knowledge", "knowledge_manifest.json"), encoding="utf-8"))
    audit = json.load(open(os.path.join(REPO, "knowledge", "knowledge_audit_v1_1.json"), encoding="utf-8"))
    snapshot = {
        "manifest": "KNOWLEDGE_SNAPSHOT_V1_1",
        "base_snapshot": "KNOWLEDGE_SNAPSHOT_V1（2111b0b3…）",
        "delta_source": {"file": "knowledge/source/TreeCut_V11_Phase4.xlsx",
                         "sha256": "07AE586D8655F5BB09EAD77012B5595D42AD09B03D00E3F4B0D302CBEABD7C0C",
                         "source_type": "USER_CURATED_STRUCTURED_KB"},
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "record_count": manifest["record_count"],
        "by_type": manifest["by_type"],
        "by_namespace": manifest["by_namespace"],
        "by_source_req": manifest["by_source_req"],
        "by_status": manifest["by_status"],
        "records_sha256": manifest["records_sha256"],
        "knowledge_files": files,
        "knowledge_file_count": len(files),
        "schema_versions": {"knowledge_record": "1.0", "business_cognition": "1.0", "template": "1.0"},
        "source_registry_version": "1.1",
        "test_results": "16/16 PASS（含 TEST 11-16）",
        "validation": {"set": 43, "regressions_vs_v1": 0},
        "audit_summary": {"conflicts": audit["conflicts"], "duplicate": audit["duplicate"],
                          "semantic_dup": len(audit["semantic_dup_candidates"]),
                          "external_required": audit["external_required_count"]},
    }
    canon = json.dumps({k: v for k, v in snapshot.items() if k != "knowledge_snapshot_sha256"},
                       ensure_ascii=False, sort_keys=True)
    snapshot["knowledge_snapshot_sha256"] = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    p = os.path.join(DATA_ROOT, "KNOWLEDGE_SNAPSHOT_V1_1.json")
    json.dump(snapshot, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)
    print("knowledge_snapshot_sha256:", snapshot["knowledge_snapshot_sha256"])
    print("条数:", manifest["record_count"], "| 文件数:", len(files))


if __name__ == "__main__":
    main()
