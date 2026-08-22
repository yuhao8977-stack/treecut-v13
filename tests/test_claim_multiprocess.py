"""P2.5 多进程并发领取验证：2 个 spawn 进程同时 claim 同一批任务。

用法: python tests/test_claim_multiprocess.py
"""
from __future__ import annotations

import multiprocessing
import sqlite3
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from treecut.library.task_store import TaskStore  # noqa: E402

import os
os.environ["TREECUT_DATA_ROOT"] = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
os.environ["TREECUT_MODEL_ROOT"] = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\models"


def _make_db(tmp: Path, n: int = 200) -> Path:
    db = tmp / "mp_materials.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE assets (asset_id TEXT PRIMARY KEY, media_id INTEGER);
        CREATE TABLE media_files (id INTEGER PRIMARY KEY, source_id INTEGER,
            relative_path TEXT, media_type TEXT, available INTEGER);
        CREATE TABLE sources (id INTEGER PRIMARY KEY, path TEXT, online INTEGER);
    """)
    for i in range(n):
        conn.execute("INSERT INTO assets(asset_id, media_id) VALUES(?,?)",
                     (f"mp_{i:04d}", i))
        conn.execute(
            "INSERT INTO media_files(id, source_id, relative_path, media_type, available)"
            " VALUES(?,1,?, 'video', 1)", (i, f"clip_{i}.mp4"))
    conn.execute("INSERT INTO sources(id, path, online) VALUES(1, 'E:/tmp', 1)")
    conn.commit()
    conn.close()
    return db


def _claimer(db_path: str, wid: str, out_queue) -> None:
    store = TaskStore(db_path)
    store.migrate_if_needed()
    claimed = []
    while True:
        task = store.claim_task(wid, task_type="asr")
        if task is None:
            break
        claimed.append(task["task_id"])
    out_queue.put((wid, claimed))


if __name__ == "__main__":
    base = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\p25_selftest")
    base.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="p25_mp_", dir=str(base)))
    db = _make_db(tmp, n=200)
    store = TaskStore(db)
    store.migrate_if_needed()
    created = 0
    for i in range(200):
        created += store.create_task(f"mp_{i:04d}", "asr", stages="asr")
    print(f"创建任务: {created}")

    ctx = multiprocessing.get_context("spawn")
    out = ctx.Queue()
    p1 = ctx.Process(target=_claimer, args=(str(db), "worker_a", out))
    p2 = ctx.Process(target=_claimer, args=(str(db), "worker_b", out))
    p1.start(); p2.start(); p1.join(timeout=60); p2.join(timeout=60)

    results = {}
    for _ in range(2):
        wid, claimed = out.get(timeout=10)
        results[wid] = claimed
    all_claimed = results.get("worker_a", []) + results.get("worker_b", [])
    dupes = len(all_claimed) - len(set(all_claimed))
    print(f"worker_a 领取: {len(results.get('worker_a', []))}")
    print(f"worker_b 领取: {len(results.get('worker_b', []))}")
    print(f"总领取: {len(all_claimed)}  去重后: {len(set(all_claimed))}  重复: {dupes}")
    print(f"库中任务总数: {store.stats()['total']}")
    status = store.stats()["by_status"]
    print(f"状态分布: {status}")
    assert dupes == 0, "存在重复领取!"
    assert status.get("processing", 0) == 200, f"应全部被领取: {status}"
    print("PASS: 多进程并发无双领")

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
