# -*- coding: utf-8 -*-
"""P1 单元测试：v12 -> v13 迁移（只读源、备份、标签导入）。"""
from __future__ import annotations

import os
import sqlite3

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in os.sys.path:
    os.sys.path.insert(0, SRC_DIR)


@pytest.fixture()
def isolated_env(tmp_path):
    os.environ["TREECUT_DATA_ROOT"] = str(tmp_path)
    yield tmp_path
    os.environ.pop("TREECUT_DATA_ROOT", None)


def _make_v12_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE materials (id INTEGER PRIMARY KEY, video_path TEXT, start_time REAL,"
        " end_time REAL, tags TEXT, objects TEXT, analyzed INTEGER, source_folder TEXT,"
        " duration REAL, file_size INTEGER, file_mtime REAL)"
    )
    conn.executemany(
        "INSERT INTO materials(video_path,start_time,end_time,tags,objects,analyzed,"
        "source_folder,duration,file_size,file_mtime) VALUES(?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_migrate_readonly_and_tags(isolated_env):
    from treecut.library import Catalog, V12Migrator

    src = isolated_env / "media"
    src.mkdir()
    real = src / "clip.mp4"
    real.write_bytes(os.urandom(200_000))
    missing = src / "ghost.mp4"

    v12_db = isolated_env / "v12.db"
    _make_v12_db(str(v12_db), [
        (str(real), 0.0, 5.0, "抽屉,收纳", "岛台", 1, str(src), 5.0, 200_000, 1750000000),
        (str(missing), 0.0, 3.0, "幽灵", "", 0, str(src), 3.0, 100, 1750000001),
    ])

    db = isolated_env / "materials.db"
    cat = Catalog(db_path=db)
    migrator = V12Migrator(catalog=cat)
    result = migrator.migrate(v12_db)

    assert result.skipped_missing_files == 1  # ghost skipped
    assert result.migrated_media >= 1
    assert result.backup_path is None or os.path.exists(result.backup_path)

    # source untouched
    conn = sqlite3.connect(f"file:{v12_db}?mode=ro", uri=True)
    assert conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 2
    conn.close()

    # tags imported onto the real file
    media = cat.list_media(limit=20)
    tagged = [m for m in media if m["relative_path"] == "clip.mp4"]
    assert tagged and "抽屉" in tagged[0]["tags"]


def test_migrate_missing_db_raises(isolated_env):
    from treecut.library import Catalog, V12Migrator

    cat = Catalog(db_path=isolated_env / "materials.db")
    with pytest.raises(FileNotFoundError):
        V12Migrator(catalog=cat).migrate(isolated_env / "no_such.db")
