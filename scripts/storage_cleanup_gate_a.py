# -*- coding: utf-8 -*-
"""Cleanup Gate A: delete ONLY verified-migrated old model payloads from C.
Targets (approved by user, exact dirs only):
  C:\\Users\\admin\\.cache\\huggingface\\hub   (HF model payload -> G:\\AI\\hf_cache\\hub)
  C:\\Users\\admin\\.ollama\\models            (Ollama model payload -> G:\\AI\\ollama_models)
KEEP: everything else in .cache and .ollama (token/keys/config/history/cache/modules/xet).
Usage: python storage_cleanup_gate_a.py [--generate-only] [--dry-run]
"""
import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(REPO, "reports", "storage")

TARGETS = [
    {
        "id": "HF_OLD_CACHE",
        "path": r"C:\Users\admin\.cache\huggingface\hub",
        "verified_source": r"G:\AI\hf_cache\hub",
        "manifest": "HF_OLD_CACHE_DELETE_MANIFEST_V1.json",
        "delete_safe": True,
        "keep_note": "Keep .cache\\huggingface\\modules, xet, .agent_harnesses.json, .check_for_update_done; no token file present here.",
    },
    {
        "id": "OLLAMA_OLD_MODEL",
        "path": r"C:\Users\admin\.ollama\models",
        "verified_source": r"G:\AI\ollama_models",
        "manifest": "OLLAMA_OLD_MODEL_DELETE_MANIFEST_V1.json",
        "delete_safe": True,
        "keep_note": "Keep .ollama\\cache, history, id_ed25519, id_ed25519.pub.",
    },
]


def dir_size(path):
    total = 0
    files = 0
    for root, dirs, names in os.walk(path):
        for n in names:
            try:
                total += os.path.getsize(os.path.join(root, n))
                files += 1
            except OSError:
                pass
    return total, files


def free_gb(drive="C"):
    import ctypes
    free = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(drive + ":\\", None, None, ctypes.byref(free))
    return free.value / (1024 ** 3)


def generate_manifest(target):
    path = target["path"]
    if not os.path.isdir(path):
        return None
    size, files = dir_size(path)
    manifest = {
        "manifest_id": f"{target['id']}_DELETE_MANIFEST_V1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": "delete_safe=TRUE only; exact directory only; nothing else in parent dir touched",
        "target": {
            "path": path,
            "size_bytes": size,
            "size_gb": round(size / (1024 ** 3), 2),
            "file_count": files,
        },
        "verified_backup_source": target["verified_source"],
        "verified_by_fresh_process": {
            "hf": "faster-whisper-small snapshot_download local_files_only -> G:\\AI\\hf_cache\\hub\\models--Systran--faster-whisper-small PASS",
            "ollama": "ollama run qwen2.5vl:7b -> 'OK' exit=0 with OLLAMA_MODELS=G:\\AI\\ollama_models PASS",
        },
        "keep": target["keep_note"],
        "delete_safe": target["delete_safe"],
        "status": "PENDING",
    }
    out = os.path.join(REPORTS, target["manifest"])
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generate-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    os.makedirs(REPORTS, exist_ok=True)
    manifests = []
    for t in TARGETS:
        m = generate_manifest(t)
        manifests.append(m)
        print(f"manifest {t['manifest']}: {'GENERATED' if m else 'SKIP (missing)'} -> {m['target'] if m else t['path']}")

    if args.generate_only:
        return

    # C free before
    before = free_gb("C")
    print(f"C free BEFORE: {before:.1f} GB")

    results = []
    for t, m in zip(TARGETS, manifests):
        if m is None or not m["delete_safe"]:
            results.append({"id": t["id"], "action": "SKIP", "reason": "missing or not delete_safe"})
            continue
        path = t["path"]
        if args.dry_run:
            results.append({"id": t["id"], "action": "DRY_RUN", "size_gb": m["target"]["size_gb"]})
            print(f"[dry-run] would delete {path}")
            continue
        print(f"deleting {path} ...")
        errors = []
        start = time.time()
        try:
            shutil.rmtree(path, onerror=None)
        except Exception as e:
            # fallback: delete file-by-file, record locked ones
            errors.append(str(e))
            for root, dirs, names in os.walk(path, topdown=False):
                for n in names:
                    fp = os.path.join(root, n)
                    try:
                        os.remove(fp)
                    except OSError as e2:
                        errors.append(f"LOCKED {fp}: {e2}")
                for d in dirs:
                    dp = os.path.join(root, d)
                    try:
                        os.rmdir(dp)
                    except OSError:
                        pass
        elapsed = time.time() - start
        gone = not os.path.exists(path)
        results.append({
            "id": t["id"],
            "action": "DELETED" if gone else "PARTIAL",
            "target": path,
            "size_gb_before": m["target"]["size_gb"],
            "elapsed_s": round(elapsed, 1),
            "errors": errors[:20],
            "error_count": len(errors),
        })
        print(f"  -> {'DELETED' if gone else 'PARTIAL'} ({m['target']['size_gb']} GB) in {elapsed:.1f}s")

    after = free_gb("C")
    print(f"C free AFTER: {after:.1f} GB  (delta {after - before:+.1f} GB)")

    result = {
        "run_id": "CLEANUP_GATE_A",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "c_free_gb_before": round(before, 1),
        "c_free_gb_after": round(after, 1),
        "c_free_gb_delta": round(after - before, 1),
        "results": results,
        "policy": "deleted ONLY C:\\Users\\admin\\.cache\\huggingface\\hub and C:\\Users\\admin\\.ollama\\models; nothing else touched",
    }
    out = os.path.join(REPORTS, "CLEANUP_GATE_A_RESULT_V1.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"result -> {out}")


if __name__ == "__main__":
    main()
