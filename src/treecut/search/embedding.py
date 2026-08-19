"""P4: Embedding + FAISS 向量索引（BGE-M3，离线复用已验证模型）。

- 每 segment 生成文本 embedding（transcript + OCR + 标签拼接）
- FAISS 索引存 data/indexes/segment_embeddings.index，DB 只存引用
- 复用已验证 BGE-M3（v12 真实索引 material_bge_m3.index 已实测可检索）
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.platform.paths import RuntimePaths


@dataclass(frozen=True)
class EmbeddingResult:
    indexed: int = 0
    seconds: float = 0.0
    dim: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class EmbeddingIndexer:
    """BGE-M3 segment embedding + FAISS index build/query."""

    MODEL_NAME = "BAAI/bge-m3"

    def __init__(self, paths: RuntimePaths | None = None,
                 model_name: str = MODEL_NAME):
        self.paths = paths or RuntimePaths.discover()
        self.model_name = model_name
        self._model = None
        self._index = None
        self._id_map: list[str] = []

    def _ensure_indexes_dir(self) -> Path:
        d = self.paths.data_root / "indexes"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _lazy_model(self):
        if self._model is None:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            user_hf = str(Path.home() / ".cache" / "huggingface")
            current_hf = os.environ.get("HF_HOME", "")
            if not (Path(current_hf) / "hub" / "models--BAAI--bge-m3").exists() and \
               (Path(user_hf) / "hub" / "models--BAAI--bge-m3").exists():
                os.environ["HF_HOME"] = user_hf
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._lazy_model()
        vecs = self._model.encode(texts, normalize_embeddings=True,
                                  show_progress_bar=False, batch_size=32)
        return [v.tolist() for v in vecs]

    def build_index(self, vectors: list[list[float]], ids: list[str],
                    force: bool = True) -> Path:
        """构建/重建 FAISS 索引（中文路径兼容：临时 ASCII 目录写入后移动）。"""
        import faiss
        import numpy as np
        import shutil
        import tempfile
        if not vectors:
            raise ValueError("无向量可建索引")
        dim = len(vectors[0])
        index = faiss.IndexFlatIP(dim)  # 内积 = cosine（已归一化）
        index.add(np.array(vectors, dtype=np.float32))
        out = self._ensure_indexes_dir() / "segment_embeddings.index"
        idmap = self._ensure_indexes_dir() / "segment_embeddings_idmap.json"
        # faiss C++ 层不处理中文路径 → 临时 ASCII 目录写入再移动
        tmpdir = tempfile.mkdtemp(prefix="faiss_")
        try:
            tmp_index = os.path.join(tmpdir, "index.bin")
            faiss.write_index(index, tmp_index)
            shutil.move(tmp_index, str(out))
            idmap.write_text(json.dumps(ids, ensure_ascii=False), encoding="utf-8")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        return out

    def load_index(self) -> bool:
        import faiss
        import shutil
        import tempfile
        out = self._ensure_indexes_dir() / "segment_embeddings.index"
        idmap = self._ensure_indexes_dir() / "segment_embeddings_idmap.json"
        if not out.exists() or not idmap.exists():
            return False
        tmpdir = tempfile.mkdtemp(prefix="faiss_")
        try:
            tmp_index = os.path.join(tmpdir, "index.bin")
            shutil.copy2(str(out), tmp_index)
            self._index = faiss.read_index(tmp_index)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        self._id_map = json.loads(idmap.read_text(encoding="utf-8"))
        return True

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """向量检索 TopK，返回 (segment_id, score)。"""
        import numpy as np
        if self._index is None:
            if not self.load_index():
                return []
        vec = self.encode_texts([query])[0]
        scores, idxs = self._index.search(np.array([vec], dtype=np.float32), min(top_k, len(self._id_map)))
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0 or idx >= len(self._id_map):
                continue
            results.append({"segment_id": self._id_map[idx], "score": float(score)})
        return results

    def stats(self) -> dict:
        if self._index is None:
            self.load_index()
        return {
            "loaded": self._index is not None,
            "ntotal": self._index.ntotal if self._index else 0,
            "dim": self._index.d if self._index else 0,
            "id_map": len(self._id_map),
        }
