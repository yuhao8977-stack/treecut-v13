"""AI Business Cognitive System — Phase 2b 视觉模型补齐（CLIP 零样本）。

对无 ASR/OCR 文本的纯画面素材，用 CLIP 零样本分类理解关键帧，
提取场景/产品标签，补充 content_classification 与 scene_semantics。

选 CLIP 而非 Florence：CLIP 是 transformers 5.x 原生支持（无 custom code），
加载稳定；Florence-2 custom config 与 transformers 5.x 不兼容。

流程：
  选取 content_classification 中无产品/材料命中的素材
  → 取关键帧图片
  → CLIP 零样本分类（中文标签：空间/产品/材料/功能场景）
  → 标签写回 content_classification.reasons + scene_semantics
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from treecut.cognitive.store import CognitiveStore

# CLIP 零样本分类标签（家具/岛台行业）
CLIP_LABELS = {
    "scene": [
        "客户家的厨房", "工厂车间生产", "家具展厅", "厨房岛台空间",
        "客厅空间", "安装施工现场", "餐厅区域", "装修完成的房间",
    ],
    "product": [
        "厨房岛台", "岩板台面岛台", "实木餐桌", "餐边柜", "橱柜",
        "吧台", "大理石台面", "岛台上的水槽",
    ],
    "material": [
        "岩板纹理", "大理石纹理", "木纹饰面", "黑色哑光台面",
        "白色亮光台面", "深色实木", "金属拉手", "肤感柜门",
    ],
    "function": [
        "抽屉打开收纳", "岛台伸缩功能", "轨道插座", "隐藏式电器",
        "水龙头水槽", "展示产品细节",
    ],
}


class VisionEngine:
    """视觉理解引擎（CLIP 零样本分类，CPU 安全）。"""

    def __init__(self, db_path: str | Path | None = None):
        self.store = CognitiveStore(db_path)
        self.store.ensure_schema()
        self._model = None
        self._processor = None
        self._labels_encoded = None

    # ------------------------------------------------------------------

    def _locate_clip(self) -> Path | None:
        """定位 CLIP 模型目录（HF 缓存 snapshots）。"""
        base = (Path.home() / ".cache" / "huggingface" / "hub"
                / "models--openai--clip-vit-base-patch32" / "snapshots")
        if base.exists():
            snaps = [s for s in base.iterdir() if s.is_dir()]
            if snaps:
                return snaps[0]
        return None

    def available(self) -> bool:
        try:
            return self._locate_clip() is not None
        except Exception:
            return False

    def _load(self) -> None:
        """懒加载 CLIP 模型（CPU，float32）。"""
        if self._model is not None:
            return
        model_dir = self._locate_clip()
        if not model_dir:
            raise RuntimeError("CLIP 模型未找到（HF 缓存）")
        import torch
        from transformers import CLIPModel, CLIPProcessor
        self._model = CLIPModel.from_pretrained(str(model_dir)).eval()
        self._processor = CLIPProcessor.from_pretrained(str(model_dir))
        # 预编码标签
        all_labels = []
        self._label_groups = {}
        for group, labels in CLIP_LABELS.items():
            for label in labels:
                self._label_groups[len(all_labels)] = (group, label)
                all_labels.append(label)
        with torch.inference_mode():
            inputs = self._processor(text=all_labels, return_tensors="pt", padding=True)
            text_feat = self._model.get_text_features(**inputs)
            # transformers 5.x 可能返回 BaseModelOutputWithPooling → 取 pooler_output
            self._labels_encoded = self._as_tensor(text_feat)

    @staticmethod
    def _as_tensor(output):
        """兼容 transformers 4.x（直接 tensor）与 5.x（BaseModelOutput）。"""
        if hasattr(output, "pooler_output"):
            return output.pooler_output
        if hasattr(output, "last_hidden_state"):
            return output.last_hidden_state
        return output

    # ------------------------------------------------------------------

    def understand_frames(self, image_paths: list[str]) -> list[dict]:
        """对关键帧做零样本分类。返回 [{group, label, score}]。"""
        if not image_paths:
            return []
        self._load()
        import torch
        from PIL import Image
        results = []
        for path in image_paths:
            if not Path(path).exists():
                continue
            try:
                image = Image.open(path).convert("RGB")
                inputs = self._processor(images=image, return_tensors="pt")
                with torch.inference_mode():
                    image_feat = self._as_tensor(self._model.get_image_features(**inputs))
                    image_feat = image_feat / image_feat.norm(dim=-1, keepdim=True)
                    labels_norm = self._labels_encoded / self._labels_encoded.norm(dim=-1, keepdim=True)
                    scores = (image_feat @ labels_norm.T).squeeze(0)
                top = scores.topk(5)
                frame_tags = []
                for score, idx in zip(top.values.tolist(), top.indices.tolist()):
                    group, label = self._label_groups[idx]
                    frame_tags.append({"group": group, "label": label,
                                       "score": round(score, 3)})
                results.append({"path": path, "tags": frame_tags})
                image.close()
            except Exception as exc:
                print(f"  [CLIP 帧失败] {path.split(chr(92))[-1]}: {type(exc).__name__}: {exc}")
                continue
        return results

    def _aggregate(self, frame_results: list[dict]) -> dict:
        """聚合多帧结果 → 场景/产品/材料/功能标签。"""
        agg = {"scene": [], "product": [], "material": [], "function": []}
        seen = set()
        for fr in frame_results:
            for tag in fr.get("tags", []):
                group, label, score = tag["group"], tag["label"], tag["score"]
                key = (group, label)
                if key in seen:
                    continue
                seen.add(key)
                if score >= 0.15:  # 阈值过滤弱信号
                    agg[group].append(label)
        return agg

    # ------------------------------------------------------------------
    # 补认知
    # ------------------------------------------------------------------

    def enrich_asset(self, asset_id: str, max_frames: int = 3) -> dict:
        """对单个素材补视觉认知（CLIP 分类）。"""
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        frames = [r[0] for r in conn.execute(
            "SELECT image_path FROM keyframes WHERE asset_id=? "
            "ORDER BY timestamp_ms LIMIT ?", (asset_id, max_frames))]
        conn.close()
        if not frames:
            return {"asset_id": asset_id, "status": "no_keyframes"}

        try:
            frame_results = self.understand_frames(frames)
        except Exception as e:
            return {"asset_id": asset_id, "status": "vision_failed", "error": str(e)}
        if not frame_results:
            return {"asset_id": asset_id, "status": "vision_failed"}
        tags = self._aggregate(frame_results)

        # 更新 content_classification
        conn = sqlite3.connect(str(self.store.db_path), timeout=30)
        row = conn.execute(
            "SELECT reasons, content_type FROM content_classification WHERE asset_id=?",
            (asset_id,)).fetchone()
        reasons = {}
        if row and row[0]:
            try:
                reasons = json.loads(row[0])
            except Exception:
                reasons = {}
        reasons["vision"] = tags
        reasons["vision_caption"] = "CLIP 零样本分类"
        # 内容类型推断
        content_type = row[1] if row and row[1] else ""
        if not content_type:
            scenes = tags["scene"]
            if any("客户家" in s or "装修完成" in s for s in scenes):
                content_type = "客户案例"
            elif any("工厂" in s for s in scenes):
                content_type = "工厂实力"
            elif tags["product"] or tags["material"]:
                content_type = "产品介绍"
            if content_type:
                conn.execute(
                    "UPDATE content_classification SET content_type=?, reviewed=0 "
                    "WHERE asset_id=?", (content_type, asset_id))
        conn.execute(
            "UPDATE content_classification SET reasons=? WHERE asset_id=?",
            (json.dumps(reasons, ensure_ascii=False), asset_id))
        conn.commit()

        # 写 scene_semantics
        semantics = [{"segment_id": None, "semantic": f"视觉:{label}",
                      "action": "", "lens_value": 0, "confidence": 0.7,
                      "model_version": "clip-vit-base-patch32"} 
                     for label in (tags["scene"] + tags["product"])[:4]]
        if semantics:
            self.store.save_scene_semantics(asset_id, semantics)
        conn.close()

        return {"asset_id": asset_id, "status": "enriched", "tags": tags}

    def batch_enrich(self, asset_ids: list[str], max_frames: int = 3,
                     progress=None) -> dict:
        """批量补视觉认知。"""
        results = []
        enriched = 0
        for i, aid in enumerate(asset_ids):
            r = self.enrich_asset(aid, max_frames)
            results.append(r)
            if r.get("status") == "enriched":
                enriched += 1
            if progress and (i + 1) % 5 == 0:
                progress(f"视觉补认知 {i + 1}/{len(asset_ids)}")
        return {"processed": len(results), "enriched": enriched,
                "by_status": {s: sum(1 for r in results if r.get("status") == s)
                              for s in ("enriched", "no_keyframes", "vision_failed")},
                "results": results}

    def candidates(self, limit: int = 100) -> list[str]:
        """选无产品/材料命中的素材（纯画面候选：reasons 无 products 或 ASR 缺失）。"""
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        rows = conn.execute("""
            SELECT c.asset_id FROM content_classification c
            WHERE (c.reasons IS NULL OR c.reasons = ''
                   OR c.reasons NOT LIKE '%"products": [%'
                   OR c.reasons LIKE '%"products": []%')
            ORDER BY RANDOM() LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [r[0] for r in rows]
