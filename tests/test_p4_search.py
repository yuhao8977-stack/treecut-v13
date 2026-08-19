# -*- coding: utf-8 -*-
"""P4 测试：Embedding/FAISS + FTS5 + 混合检索。"""
from __future__ import annotations

import os

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


def test_embedding_encode(isolated_env):
    """BGE-M3 真实编码（若模型不可用则跳过）。"""
    from treecut.search.embedding import EmbeddingIndexer
    idx = EmbeddingIndexer()
    try:
        vecs = idx.encode_texts(["伸缩岛台", "轨道插座 收纳"])
    except Exception as exc:
        pytest.skip(f"BGE-M3 不可用: {exc}")
    assert len(vecs) == 2
    assert len(vecs[0]) > 0
    # 归一化 → 内积≈cosine
    import math
    norm = math.sqrt(sum(x * x for x in vecs[0]))
    assert abs(norm - 1.0) < 0.01


def test_faiss_build_search(isolated_env):
    """FAISS 建索引 + 检索。"""
    from treecut.search.embedding import EmbeddingIndexer
    idx = EmbeddingIndexer()
    try:
        vecs = idx.encode_texts(["伸缩岛台", "轨道插座 收纳", "海棠角 工艺"])
    except Exception as exc:
        pytest.skip(f"BGE-M3 不可用: {exc}")
    idx.build_index(vecs, ["seg1", "seg2", "seg3"], force=True)
    assert idx.stats()["ntotal"] == 3
    results = idx.search("伸缩岛台", top_k=3)
    assert results and results[0]["segment_id"] == "seg1"
    assert results[0]["score"] > 0.3


def test_fts_index_and_search(isolated_env):
    from treecut.library import Catalog, AssetsManager
    from treecut.library.processing_state import ProcessingState
    from treecut.library.segments import SegmentStore
    from treecut.search.hybrid import HybridSearch

    cat = Catalog(db_path=os.path.join(isolated_env, "materials.db"))
    am = AssetsManager(catalog=cat)
    ps = ProcessingState(assets=am)
    store = SegmentStore(assets=am)
    src = isolated_env / "src"
    src.mkdir()
    (src / "v.mp4").write_bytes(os.urandom(1000))
    cat.scan(src)
    am.ensure_all_video_assets()
    aid = am.list_assets(limit=5)[0]["asset_id"]
    store.save_transcript(aid, {"segment_id": None, "start_ms": 0, "end_ms": 1000,
                                "text_raw": "客户家 伸缩岛台 全景", "text_corrected": "",
                                "language": "zh", "confidence": 0.9,
                                "model_name": "test", "model_version": "1"})
    hs = HybridSearch(assets=am)
    hs.index_texts()
    # FTS 查询
    hits = hs._fts_search("伸缩", limit=10)
    assert any(h["asset_id"] == aid for h in hits)


def test_hybrid_search_returns(isolated_env):
    """混合检索端到端（可能向量 0 命中但流程可跑）。"""
    from treecut.library import Catalog, AssetsManager
    from treecut.search.hybrid import HybridSearch
    cat = Catalog(db_path=os.path.join(isolated_env, "materials.db"))
    am = AssetsManager(catalog=cat)
    src = isolated_env / "src"
    src.mkdir()
    (src / "v.mp4").write_bytes(os.urandom(1000))
    cat.scan(src)
    am.ensure_all_video_assets()
    hs = HybridSearch(assets=am)
    result = hs.search("测试", top_k=5)
    assert isinstance(result.hits, tuple)
