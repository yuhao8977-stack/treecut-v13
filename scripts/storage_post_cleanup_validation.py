# -*- coding: utf-8 -*-
"""Post-cleanup validation V1 for Cleanup Gate A + write STORAGE_POST_CLEANUP_VALIDATION_V1.json."""
import json
import os
import sqlite3
import subprocess
from datetime import datetime

REPO = r"C:\Users\admin\github\treecut-v13"
REPORTS = os.path.join(REPO, "reports", "storage")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"

def free_gb(drive="C"):
    import ctypes
    free = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(drive + ":\\", None, None, ctypes.byref(free))
    return free.value / (1024 ** 3)

def run(cmd, env_extra=None, timeout=240):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")

def main():
    results = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "checks": {}}

    # 1. C free
    results["c_free_gb"] = round(free_gb("C"), 1)
    results["target_met"] = free_gb("C") >= 70.0

    # 2. deleted targets absent
    results["checks"]["old_copies_deleted"] = {
        "hf_hub_on_c": os.path.exists(r"C:\Users\admin\.cache\huggingface\hub"),
        "ollama_models_blobs_on_c": any(
            n.startswith("sha256-") for _, _, files in os.walk(r"C:\Users\admin\.ollama\models")
            for n in files
        ),
        "keep_intact": {
            "hf_modules": os.path.isdir(r"C:\Users\admin\.cache\huggingface\modules"),
            "hf_xet": os.path.isdir(r"C:\Users\admin\.cache\huggingface\xet"),
            "ollama_keys": os.path.exists(r"C:\Users\admin\.ollama\id_ed25519"),
            "ollama_history": os.path.exists(r"C:\Users\admin\.ollama\history"),
        },
    }

    # 3. HF from G (fresh process, offline)
    code, out = run(
        [r"C:\Users\admin\AppData\Local\Programs\Python\Python312\python.exe", "-c",
         "from huggingface_hub import snapshot_download; print(snapshot_download('Systran/faster-whisper-small', local_files_only=True))"],
        env_extra={"HF_HOME": r"G:\AI\hf_cache", "HF_HUB_CACHE": r"G:\AI\hf_cache\hub", "HF_HUB_OFFLINE": "1"},
    )
    results["checks"]["hf_from_g"] = {"exit": code, "path_in_g": "G:\\AI\\hf_cache" in out}

    # 4. ollama list from G + smoke (reuse running server; client env set)
    code2, out2 = run(["ollama", "list"], env_extra={"OLLAMA_MODELS": r"G:\AI\ollama_models"}, timeout=60)
    results["checks"]["ollama_list"] = {"exit": code2, "has_model": "qwen2.5vl:7b" in out2}

    # 5. DB counts + integrity
    c = sqlite3.connect(DB)
    b007 = c.execute("select count(*) from published_content_v1 where account_id='B007'").fetchone()[0]
    b003 = c.execute("select count(*) from published_content_v1 where account_id='B003'").fetchone()[0]
    snap = c.execute("select count(*) from performance_snapshot_v1").fetchone()[0]
    integ = c.execute("pragma integrity_check").fetchone()[0]
    c.close()
    results["checks"]["db"] = {"b007": b007, "b003": b003, "snapshots": snap, "integrity": integ}

    # 6. G model payload present
    g_blobs = 0
    gp = r"G:\AI\ollama_models\blobs"
    if os.path.isdir(gp):
        g_blobs = len([f for f in os.listdir(gp) if f.startswith("sha256-")])
    results["checks"]["g_payload"] = {
        "ollama_blobs": g_blobs,
        "hf_models_dir": os.path.isdir(r"G:\AI\hf_cache\hub\models--Systran--faster-whisper-small"),
    }

    results["all_pass"] = (
        not results["checks"]["old_copies_deleted"]["hf_hub_on_c"]
        and not results["checks"]["old_copies_deleted"]["ollama_models_blobs_on_c"]
        and all(results["checks"]["old_copies_deleted"]["keep_intact"].values())
        and results["checks"]["hf_from_g"]["path_in_g"]
        and results["checks"]["ollama_list"]["has_model"]
        and b007 == 471 and b003 == 155 and integ == "ok"
        and results["checks"]["g_payload"]["ollama_blobs"] >= 1
    )

    out = os.path.join(REPORTS, "STORAGE_POST_CLEANUP_VALIDATION_V1.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
