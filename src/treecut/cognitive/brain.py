"""AI Business Cognitive System — 认知引擎骨架。

调用链（对应七层）：
  Layer0 Asset（已有数据）
  Layer1 Perception（已有数据：probe/ASR/OCR/keyframes）
  Layer2 Vision（scene_semantics 语义，Phase1 实现规则版）
  Layer3 Industry（knowledge 知识库查询）
  Layer4 Content（内容分类，Phase2 实现）
  Layer5 Account（账号适配度，Phase2 实现）
  Layer6 Template（模板匹配，Phase2 实现）
  Layer7 Feedback（反馈学习，Phase4 实现）

Phase 0 提供骨架 + 各层数据接入点，规则引擎在后续 Phase 填充。
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from treecut.cognitive.knowledge import KnowledgeLoader
from treecut.cognitive.store import CognitiveStore


class Brain:
    """认知引擎：串行调用各层，输出结构化认知结果。"""

    def __init__(self, db_path: str | Path | None = None):
        self.store = CognitiveStore(db_path)
        self.store.ensure_schema()
        self.knowledge = KnowledgeLoader(db_path)

    # ------------------------------------------------------------------
    # Layer 0-1: 读取既有分析数据
    # ------------------------------------------------------------------

    def _layer01(self, asset_id: str) -> dict:
        """读取资产 + 感知数据（probe/ASR/OCR/keyframes/segments）。"""
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        asset = conn.execute(
            "SELECT * FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
        media = conn.execute(
            "SELECT * FROM media_files WHERE id=?", (asset["media_id"],)).fetchone() if asset else None
        source = conn.execute(
            "SELECT path FROM sources WHERE id=?", (media["source_id"],)).fetchone() if media else None
        asr = [r["text_raw"] for r in conn.execute(
            "SELECT text_raw FROM transcripts WHERE asset_id=? ORDER BY start_ms", (asset_id,))]
        ocr = [r["text"] for r in conn.execute(
            "SELECT text FROM ocr_text WHERE asset_id=? AND text != ''", (asset_id,))]
        kf_count = conn.execute(
            "SELECT COUNT(*) FROM keyframes WHERE asset_id=?", (asset_id,)).fetchone()[0]
        seg_count = conn.execute(
            "SELECT COUNT(*) FROM segments WHERE asset_id=?", (asset_id,)).fetchone()[0]
        conn.close()
        return {
            "asset_id": asset_id,
            "duration": asset["duration"] if asset else 0,
            "width": asset["width"] if asset else 0,
            "height": asset["height"] if asset else 0,
            "relative_path": media["relative_path"] if media else "",
            "source_path": source["path"] if source else "",
            "asr_text": " ".join(asr)[:2000],
            "ocr_text": " ".join(ocr)[:2000],
            "keyframe_count": kf_count,
            "segment_count": seg_count,
        }

    # ------------------------------------------------------------------
    # Layer 2: 场景语义（Phase1 填充规则引擎）
    # ------------------------------------------------------------------

    def _layer2(self, layer1: dict) -> dict:
        """基于 ASR/OCR 文本的粗语义（Phase 0 骨架）。"""
        text = (layer1["asr_text"] + " " + layer1["ocr_text"]).lower()
        semantics = []
        for entry in self.knowledge.query(domain="scene"):
            kws = json.loads(entry.get("keywords", "[]"))
            hit = [kw for kw in kws if kw and kw in text]
            if hit:
                semantics.append({
                    "semantic": entry["name"],
                    "confidence": min(0.9, 0.5 + 0.1 * len(hit)),
                    "matched": hit[:3],
                })
        return {"scene_semantics": semantics}

    # ------------------------------------------------------------------
    # Layer 3: 行业理解
    # ------------------------------------------------------------------

    def _layer3(self, layer1: dict) -> dict:
        """行业知识匹配：产品/材料/功能关键词命中。"""
        text = (layer1["asr_text"] + " " + layer1["ocr_text"]).lower()
        hits = {"product": [], "material": [], "function": []}
        for domain in ("product", "material"):
            for entry in self.knowledge.query(domain=domain):
                kws = json.loads(entry.get("keywords", "[]"))
                hit = [kw for kw in kws if kw and kw in text]
                if hit:
                    hits[domain].append({"name": entry["name"], "matched": hit[:3]})
        # 功能关键词来自 industry_tags 的 function 定义（此处用 product 域补充）
        return {"industry_hits": hits}

    # ------------------------------------------------------------------
    # Layer 4-6: 内容分类/账号/模板（Phase2 填充）
    # ------------------------------------------------------------------

    def _layer456(self, layer1: dict, layer3: dict) -> dict:
        """内容类型粗判 + 账号适配 + 模板（Phase 0 骨架，基于关键词）。"""
        text = (layer1["asr_text"] + " " + layer1["ocr_text"] + " " +
                layer1["relative_path"]).lower()
        content_types = []
        for entry in self.knowledge.query(domain="content_type"):
            kws = json.loads(entry.get("keywords", "[]"))
            hit = [kw for kw in kws if kw and kw in text]
            if hit:
                content_types.append({
                    "type": entry["name"],
                    "confidence": min(0.9, 0.5 + 0.1 * len(hit)),
                    "matched": hit[:3],
                })
        return {
            "content_types": sorted(content_types, key=lambda x: -x["confidence"]),
            "account_fit": None,   # Phase2
            "template_match": None,  # Phase2
        }

    # ------------------------------------------------------------------
    # 完整认知链
    # ------------------------------------------------------------------

    def analyze(self, asset_id: str) -> dict:
        """对单个素材运行完整认知链（Layer 0-6）。"""
        started = time.perf_counter()
        layer1 = self._layer01(asset_id)
        layer2 = self._layer2(layer1)
        layer3 = self._layer3(layer1)
        layer456 = self._layer456(layer1, layer3)
        result = {
            "asset_id": asset_id,
            "perception": {
                "duration": layer1["duration"],
                "resolution": f"{layer1['width']}x{layer1['height']}",
                "keyframes": layer1["keyframe_count"],
                "segments": layer1["segment_count"],
                "asr_preview": layer1["asr_text"][:200],
                "ocr_preview": layer1["ocr_text"][:200],
            },
            "scene_semantics": layer2["scene_semantics"],
            "industry": layer3["industry_hits"],
            "content": layer456["content_types"],
            "account_fit": layer456["account_fit"],
            "template": layer456["template_match"],
            "seconds": round(time.perf_counter() - started, 2),
        }
        return result

    def status(self) -> dict:
        """认知体系状态（表就绪 + 知识库统计）。"""
        self.store.ensure_schema()
        return self.knowledge.status()
