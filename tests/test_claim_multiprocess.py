"""P2.5 多进程并发领取验证：2 个 spawn 进程同时 claim 同一批任务。

用法: python tests/test_claim_multiprocess.py  或  pytest tests/test_claim_multiprocess.py
（Source Audit R1 P2：原实现逻辑全在 __main__ 导致 pytest 0 collected/rc=5；
 已包装为真 test 函数，可被 pytest 收集。）
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


def _run_concurrent_claim(tmp_dir: Path, n: int = 200) -> dict:
    """两个 spawn 进程并发领取 n 个任务；返回统计（重复数/状态分布）。"""
    db = _make_db(tmp_dir, n=n)
    store = TaskStore(db)
    store.migrate_if_needed()
    for i in range(n):
        store.create_task(f"mp_{i:04d}", "asr", stages="asr")

    ctx = multiprocessing.get_context("spawn")
    out = ctx.Queue()
    p1 = ctx.Process(target=_claimer, args=(str(db), "worker_a", out))
    p2 = ctx.Process(target=_claimer, args=(str(db), "worker_b", out))
    p1.start(); p2.start()
    p1.join(timeout=90); p2.join(timeout=90)
    assert p1.exitcode == 0 and p2.exitcode == 0, f"worker 异常退出: {p1.exitcode}/{p2.exitcode}"

    results = {}
    for _ in range(2):
        wid, claimed = out.get(timeout=15)
        results[wid] = claimed
    all_claimed = results.get("worker_a", []) + results.get("worker_b", [])
    dupes = len(all_claimed) - len(set(all_claimed))
    return {"db": db, "dupes": dupes, "claimed_total": len(all_claimed),
            "claimed_unique": len(set(all_claimed)),
            "by_status": store.stats()["by_status"]}


def test_concurrent_claim_no_duplicate(tmp_path):
    # Source Audit R1 P2: 真 pytest（原 __main__ 版 rc=5 零收集）；断言无重复领取、全部被领
    res = _run_concurrent_claim(tmp_path, n=200)
    assert res["dupes"] == 0, f"存在重复领取: dupes={res['dupes']}"
    assert res["by_status"].get("processing", 0) == 200, f"应全部被领取: {res['by_status']}"


if __name__ == "__main__":
    base = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\p25_selftest")
    base.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="p25_mp_", dir=str(base)))
    try:
        res = _run_concurrent_claim(tmp, n=200)
        print(f"总领取: {res['claimed_total']}  去重后: {res['claimed_unique']}  重复: {res['dupes']}")
        print(f"状态分布: {res['by_status']}")
        assert res["dupes"] == 0, "存在重复领取!"
        assert res["by_status"].get("processing", 0) == 200, f"应全部被领取: {res['by_status']}"
        print("PASS: 多进程并发无双领")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
