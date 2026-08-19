# -*- coding: utf-8 -*-
"""P6 测试：AI 排序建议 + FFmpeg 粗剪输出可追溯。"""
from __future__ import annotations

import os
import shutil
import subprocess

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
def real_env(isolated_env):
    """真实视频 + segments + 选镜的环境。"""
    from treecut.library import Catalog, AssetsManager
    from treecut.library.processing_state import ProcessingState
    from treecut.library.segments import SegmentStore
    from treecut.templates.engine import TemplateEngine

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg unavailable")

    cat = Catalog(db_path=os.path.join(isolated_env, "materials.db"))
    am = AssetsManager(catalog=cat)
    ps = ProcessingState(assets=am)
    store = SegmentStore(assets=am)
    te = TemplateEngine(assets=am)

    src = isolated_env / "src"
    src.mkdir()
    v1 = src / "v1.mp4"
    v2 = src / "v2.mp4"
    # 不同尺寸 → 不同文件大小 → 不同 quick fingerprint → 2 个 canonical asset
    for v, size, dur in ((v1, "320x240", 4), (v2, "640x480", 4)):
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", f"testsrc2=duration={dur}:size={size}:rate=10",
             "-c:v", "libx264", "-preset", "ultrafast", str(v)],
            capture_output=True, timeout=60)
    cat.scan(src)
    am.ensure_all_video_assets()
    assets = am.list_assets(limit=10)
    assert len(assets) >= 2, f"需要 2 个 asset，实际 {len(assets)}"
    aid1 = assets[0]["asset_id"]
    aid2 = assets[1]["asset_id"]
    store.save_segments(aid1, [
        {"segment_id": f"{aid1}_s0", "scene_no": 0, "start_ms": 0, "end_ms": 2000}])
    store.save_segments(aid2, [
        {"segment_id": f"{aid2}_s0", "scene_no": 0, "start_ms": 0, "end_ms": 2000}])
    # 选镜：CT01 槽位 1/2
    te.save_selection("PRJ-TEST", "CT01", "1.0", 1, f"{aid1}_s0", "selected", score=0.8)
    te.save_selection("PRJ-TEST", "CT01", "1.0", 2, f"{aid2}_s0", "selected", score=0.7)
    return cat, am, ps, store, te, src


def test_sort_advisor(real_env):
    from treecut.roughcut import SortAdvisor
    cat, am, ps, store, te, src = real_env
    advisor = SortAdvisor(roughcut=RoughCutEngineProxy(am))
    suggestion = advisor.advise("PRJ-TEST")
    assert suggestion.order == (1, 2)
    assert suggestion.first_3s_segment  # 首镜非空


def test_roughcut_output(real_env):
    from treecut.roughcut import RoughCutEngine
    cat, am, ps, store, te, src = real_env
    out_dir = os.path.join(os.environ["TREECUT_DATA_ROOT"], "output")
    engine = RoughCutEngine(assets=am)
    result = engine.build("PRJ-TEST", out_dir)
    assert os.path.isfile(result.output)
    assert os.path.isfile(result.timeline)
    assert os.path.isfile(result.cuts_csv)
    assert result.clip_count == 2
    # timeline 可追溯
    import json
    tl = json.loads(open(result.timeline, encoding="utf-8").read())
    assert len(tl["clips"]) == 2
    for c in tl["clips"]:
        assert c["asset_id"] and c["segment_id"] and c["source"] and c["start_ms"] >= 0


class RoughCutEngineProxy:
    """轻量代理：只暴露 assets（供 SortAdvisor 用）。"""
    def __init__(self, assets):
        self.assets = assets
        from treecut.library.segments import SegmentStore
        self.store = SegmentStore(assets=assets)

    def _resolve_segment(self, segment_id):
        from treecut.roughcut.engine import RoughCutEngine
        eng = RoughCutEngine(assets=self.assets)
        return eng._resolve_segment(segment_id)
