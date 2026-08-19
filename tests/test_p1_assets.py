# -*- coding: utf-8 -*-
"""P1 单元测试：hash_utils + AssetsManager + ProbeWorker（临时库，不碰生产）。"""
from __future__ import annotations

import os
import shutil
import tempfile

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


@pytest.fixture()
def sample_videos(tmp_path):
    """Generate tiny real mp4 files via ffmpeg if available, else stub bytes."""
    import subprocess
    ffmpeg = shutil.which("ffmpeg")
    videos = []
    if ffmpeg:
        for name, dur, size in (("a.mp4", 1, "640x360"), ("b.mp4", 1, "320x240")):
            out = tmp_path / name
            subprocess.run(
                [ffmpeg, "-y", "-f", "lavfi", "-i", f"testsrc2=duration={dur}:size={size}:rate=10",
                 "-c:v", "libx264", "-preset", "ultrafast", str(out)],
                capture_output=True, timeout=30,
            )
            if out.exists():
                videos.append(out)
    return videos


def test_hash_utils():
    from treecut.library.hash_utils import full_sha256, quick_fingerprint, verify_sha256

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "sample.bin")
        with open(path, "wb") as f:
            f.write(os.urandom(2 * 1024 * 1024))  # > 1MiB
        full = full_sha256(path)
        quick = quick_fingerprint(path)
        assert len(full) == 64
        assert len(quick) == 64
        assert verify_sha256(path, full)
        assert full != quick  # full vs quick must differ for >1MiB content


def test_assets_ensure_and_stats(isolated_env):
    from treecut.library import AssetsManager, Catalog

    db = os.path.join(isolated_env, "materials.db")
    cat = Catalog(db_path=db)
    am = AssetsManager(catalog=cat)
    assert am.stats()["total"] == 0

    # create a fake media row via catalog scan
    src = isolated_env / "src"
    src.mkdir()
    (src / "x.mp4").write_bytes(os.urandom(100))
    scan = cat.scan(src)
    assert scan.total >= 1
    media = cat.list_media(limit=10)
    for m in media:
        rec = am.ensure_asset(m["media_id"], m["absolute_path"])
        assert rec.asset_id
        assert rec.probe_status == "pending"
    assert am.stats()["total"] >= 1


def test_probe_retry_cap(isolated_env, sample_videos):
    from treecut.library import AssetsManager, Catalog

    if not sample_videos:
        pytest.skip("ffmpeg unavailable")

    db = os.path.join(isolated_env, "materials.db")
    cat = Catalog(db_path=db)
    am = AssetsManager(catalog=cat, max_probe_attempts=2)

    # broken file must fail and then skip after cap
    broken = isolated_env / "broken.mp4"
    broken.write_bytes(b"this is not a real video")
    cat.scan(isolated_env)
    media = cat.list_media(limit=50)
    for m in media:
        am.ensure_asset(m["media_id"], m["absolute_path"])

    # fail once (attempts 1 -> still failed), fail again (attempts 2 -> skipped)
    for m in media:
        if "broken" in m["relative_path"]:
            am.claim_probe(m["media_id"])
            am.fail_probe(m["media_id"], "bad file")
            am.claim_probe(m["media_id"])
            am.fail_probe(m["media_id"], "bad file")
    states = am.stats()["probe_status"]
    assert states.get("skipped", 0) >= 1


def test_recover_interrupted(isolated_env):
    from treecut.library import AssetsManager, Catalog

    db = os.path.join(isolated_env, "materials.db")
    cat = Catalog(db_path=db)
    am = AssetsManager(catalog=cat)
    src = isolated_env / "src"
    src.mkdir()
    (src / "y.mp4").write_bytes(os.urandom(100))
    cat.scan(src)
    for m in cat.list_media(limit=10):
        am.ensure_asset(m["media_id"], m["absolute_path"])
    # simulate crash: mark all running
    with am._connect() as conn:
        conn.execute("UPDATE assets SET probe_status='running'")
    recovered = am.recover_interrupted_probes()
    assert recovered >= 1
    assert am.stats()["probe_status"].get("pending", 0) >= 1
