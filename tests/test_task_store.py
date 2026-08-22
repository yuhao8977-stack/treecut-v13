"""P2.5 单元测试：TaskStore 原子领取防双领 + 迁移幂等 + 状态机。

使用临时数据库，不触碰生产 materials.db。运行方式：
  python tests/test_task_store.py
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from treecut.library.task_store import TaskStore  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def make_db(tmp: Path) -> Path:
    db = tmp / "test_materials.db"
    if db.exists():
        db.unlink()
    for suffix in ("-wal", "-shm"):
        p = Path(str(db) + suffix)
        if p.exists():
            p.unlink()
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE assets (asset_id TEXT PRIMARY KEY, media_id INTEGER);
        CREATE TABLE media_files (id INTEGER PRIMARY KEY, source_id INTEGER,
            relative_path TEXT, media_type TEXT, available INTEGER);
        CREATE TABLE sources (id INTEGER PRIMARY KEY, path TEXT, online INTEGER);
        CREATE TABLE asset_processing_state (
            asset_id TEXT, stage TEXT, status TEXT,
            pipeline_version TEXT DEFAULT '', algorithm_version TEXT DEFAULT '',
            model_name TEXT DEFAULT '', model_version TEXT DEFAULT '',
            input_fingerprint TEXT DEFAULT '', started_at REAL, completed_at REAL,
            retry_count INTEGER DEFAULT 0, error_code TEXT DEFAULT '',
            error_message TEXT DEFAULT '', result_count INTEGER DEFAULT 0,
            reviewed INTEGER DEFAULT 0, reviewed_at REAL, updated_at REAL,
            PRIMARY KEY (asset_id, stage));
    """)
    for i in range(10):
        conn.execute(
            "INSERT INTO assets(asset_id, media_id) VALUES(?,?)",
            (f"asset_{i:04d}", i))
        conn.execute(
            "INSERT INTO media_files(id, source_id, relative_path, media_type, available)"
            " VALUES(?,1,?, 'video', 1)", (i, f"clip_{i}.mp4"))
        conn.execute(
            "INSERT INTO asset_processing_state(asset_id, stage, status)"
            " VALUES(?,?, 'NEW')", (f"asset_{i:04d}", "scene"))
        conn.execute(
            "INSERT INTO asset_processing_state(asset_id, stage, status)"
            " VALUES(?,?, 'NEW')", (f"asset_{i:04d}", "asr"))
    conn.execute("INSERT INTO sources(id, path, online) VALUES(1, 'E:/tmp', 1)")
    conn.commit()
    conn.close()
    return db


def test_migration_idempotent(tmp: Path) -> None:
    print("[迁移幂等]")
    db = make_db(tmp)
    s1 = TaskStore(db)
    s1.migrate_if_needed()
    s1.migrate_if_needed()  # 第二次
    conn = sqlite3.connect(db)
    n = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='analysis_tasks'").fetchone()[0]
    ver = conn.execute(
        "SELECT version FROM schema_version WHERE name='analysis_tasks'").fetchone()
    check("analysis_tasks 表存在", n == 1)
    check("schema_version=1", ver and ver[0] == 1)
    # 旧表未动
    cols = [r[1] for r in conn.execute("PRAGMA table_info(asset_processing_state)")]
    check("旧表结构未变", "stage" in cols and "status" in cols and len(cols) == 17)
    conn.close()
    # 备份生成
    backups = list((db.parent / "backups").glob("*.db")) if (db.parent / "backups").exists() else []
    print(f"  备份文件数: {len(backups)}（首次迁移 1 份）")


def test_atomic_claim(tmp: Path) -> None:
    print("\n[原子领取防双领 - 10 线程并发]")
    db = make_db(tmp)
    store = TaskStore(db)
    store.migrate_if_needed()
    for i in range(10):
        store.create_task(f"asset_{i:04d}", "asr", stages="asr")

    claimed: dict[str, str] = {}
    lock = threading.Lock()
    errors: list[str] = []

    def worker(wid: str):
        try:
            for _ in range(50):
                task = store.claim_task(wid, task_type="asr")
                if task is None:
                    return
                with lock:
                    if task["task_id"] in claimed:
                        errors.append(f"双领! {task['task_id']} by {wid} & {claimed[task['task_id']]}")
                    claimed[task["task_id"]] = wid
        except Exception as e:  # noqa: BLE001
            errors.append(f"{wid}: {e}")

    threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    check("无双领", not errors, str(errors[:3]))
    check("10 个任务全部被领取", len(claimed) == 10, f"claimed={len(claimed)}")
    # 所有任务 processing 状态
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT status, COUNT(*) FROM analysis_tasks GROUP BY status").fetchall()
    check("全部 processing", dict(rows).get("processing") == 10, str(rows))
    conn.close()


def test_complete_fail_recover(tmp: Path) -> None:
    print("\n[完成/失败/重试/恢复]")
    db = make_db(tmp)
    store = TaskStore(db)
    store.migrate_if_needed()
    store.create_task("asset_0000", "asr", stages="asr")

    t = store.claim_task("w1", task_type="asr")
    check("领取成功", t is not None)
    store.complete_task(t["task_id"])
    check("完成后无 pending", store.pending_count() == 0)
    check("completed 计数", store.stats()["by_status"].get("completed") == 1)

    # 失败重试 3 次后 failed
    store.create_task("asset_0001", "asr", stages="asr")
    for attempt in range(1, 5):
        t = store.claim_task("w1", task_type="asr")
        if t is None:
            break
        store.fail_task(t["task_id"], "boom", retryable=True)
    stats = store.stats()
    check("3 次重试后 failed", stats["by_status"].get("failed") == 1,
          str(stats["by_status"]))
    check("retry 上限生效（无 pending）", store.pending_count() == 0)

    # recover_stale
    store.create_task("asset_0002", "asr", stages="asr")
    t = store.claim_task("w1", task_type="asr")
    # 伪造超时
    conn = sqlite3.connect(db)
    conn.execute("UPDATE analysis_tasks SET started_time=? WHERE task_id=?",
                 (time.time() - 99999, t["task_id"]))
    conn.commit()
    conn.close()
    n = store.recover_stale(max_age_seconds=60)
    check("失联任务被回收", n == 1)
    check("回收后回到 pending", store.pending_count() == 1)


def test_worker25_logging(tmp: Path) -> None:
    print("\n[Worker25 日志]")
    db = make_db(tmp)
    log = tmp / "worker_w_test.log"
    store = TaskStore(db)
    store.migrate_if_needed()
    store.create_task("asset_0000", "asr", stages="asr")
    check("任务创建", store.pending_count() == 1)
    # 只验证日志框架不炸（不真正跑分析）
    os.environ["TREECUT_DATA_ROOT"] = str(tmp)   # RuntimePaths 禁止 C 盘数据目录
    os.environ["TREECUT_MODEL_ROOT"] = str(tmp / "models")
    from treecut.analysis.worker_p25 import Worker25
    try:
        Worker25(worker_id="w_test", task_type="asr", stages=["asr"],
                 db_path=db, log_path=log)
        check("Worker25 可实例化", True)
        check("日志文件创建", log.exists())
    except Exception as e:  # noqa: BLE001
        check("Worker25 可实例化", False, str(e))


if __name__ == "__main__":
    # RuntimePaths 禁止 C 盘数据目录 → 测试临时目录放 E 盘运行时数据下
    # （batch1 同级目录，进程对该树有写权限）
    e_test_root = Path(
        r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\p25_selftest")
    e_test_root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="p25_test_", dir=str(e_test_root)))
    print(f"临时库目录: {tmp}")
    try:
        test_migration_idempotent(tmp)
        test_atomic_claim(tmp)
        test_complete_fail_recover(tmp)
        test_worker25_logging(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            e_test_root.rmdir()
        except OSError:
            pass
    print(f"\n结果: PASS={PASS} FAIL={FAIL}")
    sys.exit(1 if FAIL else 0)
