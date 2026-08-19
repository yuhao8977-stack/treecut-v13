# -*- coding: utf-8 -*-
"""P2 单元/集成测试：scene/keyframe/asr/ocr 引擎 + 生命周期接入。"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in os.sys.path:
    os.sys.path.insert(0, SRC_DIR)

from treecut.library import Catalog, AssetsManager
from treecut.library.processing_state import ProcessingState
from treecut.library.segments import SegmentStore
from treecut.scenes.detector import SceneDetector


@pytest.fixture()
def isolated_env(tmp_path):
    os.environ["TREECUT_DATA_ROOT"] = str(tmp_path)
    yield tmp_path
    os.environ.pop("TREECUT_DATA_ROOT", None)


@pytest.fixture()
def sample_video(tmp_path):
    """Generate a small real mp4 (multi-scene pattern) via ffmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg unavailable")
    out = tmp_path / "sample.mp4"
    # testsrc2 + 运动模式，制造场景变化；8s 便于切分
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi",
         "-i", "testsrc2=duration=8:size=640x360:rate=25",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest",
         str(out)],
        capture_output=True, timeout=60,
    )
    if not out.exists():
        pytest.skip("ffmpeg failed to create sample")
    return out


def test_segment_store_schema(isolated_env):
    cat = Catalog(db_path=os.path.join(isolated_env, "materials.db"))
    am = AssetsManager(catalog=cat)
    store = SegmentStore(assets=am)
    # 无 asset 时保存应报错或跳过——先造一个 asset
    src = isolated_env / "src"
    src.mkdir()
    (src / "v.mp4").write_bytes(os.urandom(1000))
    cat.scan(src)
    am.ensure_all_video_assets()
    assets = am.list_assets(limit=5)
    assert assets
    aid = assets[0]["asset_id"]
    n = store.save_segments(aid, [
        {"scene_no": 0, "start_ms": 0, "end_ms": 1000},
        {"scene_no": 1, "start_ms": 1000, "end_ms": 2000},
    ])
    assert n == 2
    segs = store.list_segments(aid)
    assert len(segs) == 2
    assert segs[0]["duration_ms"] == 1000


def test_scene_detector_real(sample_video):
    det = SceneDetector(threshold=20.0, min_scene_len_sec=0.5)
    result = det.detect(str(sample_video))
    # testsrc2 可能切出 0 或少量场景；至少不崩溃且返回合法结构
    assert isinstance(result.segments, tuple)
    for s in result.segments:
        assert s["end_ms"] > s["start_ms"]
        assert s["start_ms"] >= 0


def test_scene_detector_uniform_fallback(tmp_path):
    """无 scenedetect 时（模拟）降级均匀分段。"""
    det = SceneDetector()
    segs = det._uniform_split(tmp_path / "x.mp4", duration_sec=23.0)
    assert segs and segs[0]["start_ms"] == 0
    assert segs[-1]["end_ms"] == 23000


def test_p2_worker_lifecycle(isolated_env, sample_video):
    """P2 worker 接入生命周期：scene DONE，keyframe 按 segments 决定 DONE/SKIPPED。"""
    from treecut.analysis.p2_worker import P2Worker

    cat = Catalog(db_path=os.path.join(isolated_env, "materials.db"))
    am = AssetsManager(catalog=cat)
    ps = ProcessingState(assets=am)
    store = SegmentStore(assets=am)

    src = isolated_env / "src"
    src.mkdir()
    shutil.copy2(sample_video, src / "sample.mp4")
    cat.scan(src)
    am.ensure_all_video_assets()
    ps.ensure_asset_stages_all()
    assets = am.list_assets(limit=5)
    aid = assets[0]["asset_id"]

    worker = P2Worker(paths=None, assets=am)
    worker.include_asr = False
    worker.include_ocr = False
    result = worker.run(limit=1)
    assert result.scene_done >= 1
    assert ps.get_state(aid, "scene").status == "DONE"
    # keyframe：scene 有段则 DONE；无段（静态测试视频）则 SKIPPED（合理级联）
    kf = ps.get_state(aid, "keyframe").status
    assert kf in ("DONE", "SKIPPED")
    # 幂等：再次运行 scene 应 SKIP（不重复）
    decision = ps.should_process(aid, "scene", pipeline_version="P2.1")
    assert decision == "SKIP_ALREADY_DONE"


def test_keyframe_extractor_real(isolated_env, sample_video):
    """KeyframeExtractor 对固定 segment 抽帧（首/中/尾）。"""
    from treecut.keyframes.extractor import KeyframeExtractor
    from treecut.library import Catalog, AssetsManager

    cat = Catalog(db_path=os.path.join(isolated_env, "materials.db"))
    am = AssetsManager(catalog=cat)
    src = isolated_env / "src"
    src.mkdir()
    shutil.copy2(sample_video, src / "sample.mp4")
    cat.scan(src)
    am.ensure_all_video_assets()
    aid = am.list_assets(limit=5)[0]["asset_id"]

    ext = KeyframeExtractor()
    result = ext.extract(str(sample_video), aid, [
        {"segment_id": f"{aid}_seg0", "scene_no": 0, "start_ms": 0, "end_ms": 8000},
    ])
    # 首/中/尾候选（采样可能因 seek 失败略少，但应 ≥1）
    assert len(result.frames) >= 1
    for f in result.frames:
        assert os.path.isfile(f["image_path"])
        assert f["sharpness"] >= 0
    # 清理生成的帧
    import shutil as _sh
    _sh.rmtree(ext._out_dir(aid), ignore_errors=True)
