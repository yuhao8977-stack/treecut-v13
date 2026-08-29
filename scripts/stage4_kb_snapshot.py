# -*- coding: utf-8 -*-
"""Phase 4 Stage 1 — KNOWLEDGE_SNAPSHOT_V1（知识库快照锁）。"""
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
    # 收集 knowledge/ 下所有文件（排除 source 原文件？包含，作为 source hash）
    files = []
    for root, dirs, fs in os.walk(os.path.join(REPO, "knowledge")):
        for f in fs:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, REPO)
            files.append({"file": rel, "sha256": sha256_file(p)})
    files.sort(key=lambda x: x["file"])

    manifest = json.load(open(os.path.join(REPO, "knowledge", "knowledge_manifest.json"), encoding="utf-8"))
    snapshot = {
        "manifest": "KNOWLEDGE_SNAPSHOT_V1",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "knowledge_files": files,
        "knowledge_file_count": len(files),
        "record_count": manifest["record_count"],
        "records_sha256": manifest["records_sha256"],
        "source_files": manifest["source_files"],
        "schema_versions": {
            "knowledge_record": "1.0", "business_cognition": "1.0", "template": "1.0"},
        "source_registry_version": "1.0",
        "index_versions": {"sqlite_fts": "v1", "embedding": "siglip-base-patch16-224"},
    }
    canon = json.dumps({k: v for k, v in snapshot.items() if k not in ("knowledge_snapshot_sha256",)},
                       ensure_ascii=False, sort_keys=True)
    snapshot["knowledge_snapshot_sha256"] = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    p = os.path.join(DATA_ROOT, "KNOWLEDGE_SNAPSHOT_V1.json")
    json.dump(snapshot, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)
    print("knowledge_snapshot_sha256:", snapshot["knowledge_snapshot_sha256"])
    print("文件数:", len(files), "| 知识条数:", manifest["record_count"])


if __name__ == "__main__":
    main()
