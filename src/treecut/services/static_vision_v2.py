# -*- coding: utf-8 -*-
"""TreeCut Stage 2 — StaticVisionAnalyzerV2（真实视觉认知）。

基于视觉 embedding（SigLIP 等）做 per-field zero-shot 图像-文本匹配：
  每字段候选标签（V2.1 中文/英文）→ text embedding；
  帧图像 → image embedding；相似度 → prediction + model_score。

字段：scene_family/scene_subtype/product_family/product_variant/
      material[]/component[]/function[]/shot_scale/shot_role[]/
      people_presence/product_visibility
纯视觉 Segment 独立输出；允许 UNKNOWN；禁止强猜。
每字段输出：prediction/model_score/frame_evidence/model_version/backend/created_at
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np

MODEL_VERSION = "siglip-base-patch16-224-v1"


class StaticVisionAnalyzerV2:
    """静态视觉字段分析器（embedding zero-shot）。"""

    # 候选标签（V2.1 枚举 → 英文自然语言描述；SigLIP 为英文训练，禁用中文 prompt）
    LABEL_PROMPTS = {
        "scene_family": {
            "FACTORY": "factory workshop interior, industrial production floor",
            "CUSTOMER_HOME": "customer home living room, residential interior",
            "SHOWROOM": "showroom display area, exhibition hall",
            "INSTALLATION_SITE": "installation site, construction work area",
            "OTHER": "other kind of scene", "UNKNOWN": "unclear scene"},
        "scene_subtype": {
            "FACTORY_WORKSHOP": "factory machining workshop production area",
            "FACTORY_SHOWROOM": "factory showroom display zone",
            "FACTORY_WAREHOUSE": "factory warehouse storage",
            "FACTORY_OTHER": "other factory area",
            "NOT_APPLICABLE": "not applicable", "UNKNOWN": "unclear"},
        "product_family": {
            "ISLAND": "kitchen island, central island counter",
            "BAR": "bar counter, high table",
            "SIDEBOARD": "sideboard cabinet, storage cabinet",
            "DINING_TABLE": "dining table, tea table",
            "OTHER": "other furniture", "UNKNOWN": "unclear"},
        "product_variant": {
            "STANDARD_ISLAND": "fixed standard kitchen island",
            "EXTENDABLE_ISLAND": "extendable kitchen island, pull-out island",
            "FLOATING_ISLAND": "floating cantilever island",
            "FLOOR_ISLAND": "floor standing island",
            "NOT_APPLICABLE": "not applicable", "OTHER": "other variant", "UNKNOWN": "unclear"},
        "material": {
            "岩板": "sintered stone slab surface, porcelain slab texture",
            "实木": "solid wood surface, wood grain texture",
            "奢石": "luxury stone, exotic marble texture",
            "大理石": "marble surface, marble veining",
            "肤感": "matte soft-touch surface finish",
            "不锈钢": "stainless steel metal surface",
            "玻璃": "glass transparent surface",
            "其他": "other material", "UNKNOWN": "unclear"},
        "component": {
            "DRAWER": "drawer of a cabinet",
            "CABINET_DOOR": "cabinet door",
            "TRACK_SOCKET": "track power socket, sliding power rail outlet",
            "COUNTERTOP": "countertop, table surface",
            "SINK": "kitchen sink, basin",
            "APPLIANCE_SLOT": "embedded appliance slot",
            "ACRYLIC_SUPPORT": "acrylic transparent support bracket",
            "OTHER": "other component", "NOT_APPLICABLE": "not applicable", "UNKNOWN": "unclear"},
        "function": {
            "STORAGE": "storage organization function",
            "EXTENDABLE": "extendable sliding function",
            "POWER": "power supply electric function",
            "DINING": "dining meal function",
            "OFFICE": "office work function",
            "WATER_BAR": "water bar beverage function",
            "EMBEDDED_APPLIANCE": "embedded appliance function",
            "CHILD_SAFETY": "child safety feature",
            "OTHER": "other function", "NOT_APPLICABLE": "not applicable", "UNKNOWN": "unclear"},
        "shot_scale": {
            "WIDE": "wide shot, full scene overview",
            "MEDIUM": "medium shot, person or object half body",
            "CLOSE": "close shot, object close view",
            "CLOSE_UP": "extreme close up, macro detail", "UNKNOWN": "unclear"},
        "shot_role": {
            "PERSON_TALKING": "a person talking explaining to camera",
            "FUNCTION_DEMO": "demonstrating a function by hand operation",
            "SPACE_OVERVIEW": "panning the room space overview",
            "PRODUCT_SHOWCASE": "showing the product",
            "DETAIL_SHOWCASE": "close up of product detail",
            "CRAFT_SHOWCASE": "showing craft production process",
            "INSTALLATION": "installation construction process",
            "OTHER": "other", "UNKNOWN": "unclear"},
        "people_presence": {"YES": "a person appears in the image", "NO": "no person in the image",
                            "UNKNOWN": "unclear"},
        "product_visibility": {"VISIBLE": "product clearly visible", "PARTIAL": "product partially visible",
                               "HIDDEN": "product hidden or occluded", "UNKNOWN": "unclear"},
    }

    def __init__(self, runtime, model_dir: str | Path | None = None):
        self.runtime = runtime
        self.model_dir = Path(model_dir) if model_dir else runtime.info.models_dir
        self._model = None
        self._proc = None
        self._text_emb = {}

    # ---------------- 模型懒加载 ----------------
    def _ensure_model(self):
        if self._model is not None:
            return
        from transformers import AutoModel, AutoProcessor
        t0 = time.time()
        self._model = AutoModel.from_pretrained(
            "google/siglip-base-patch16-224", cache_dir=str(self.model_dir))
        self._proc = AutoProcessor.from_pretrained(
            "google/siglip-base-patch16-224", cache_dir=str(self.model_dir))
        dev = self.runtime.device
        if dev.startswith("cuda"):
            self._model = self._model.to(dev)
            self._model.eval()
            if hasattr(self._model, "half"):
                self._model = self._model.half()
        self._cold_start_ms = (time.time() - t0) * 1000

    def _text_embedding(self, field: str, label: str):
        """候选标签文本 embedding（缓存）。"""
        key = (field, label)
        if key in self._text_emb:
            return self._text_emb[key]
        self._ensure_model()
        import torch
        desc = self.LABEL_PROMPTS.get(field, {}).get(label, label)
        inp = self._proc(text=[desc], padding="max_length", max_length=64,
                         truncation=True, return_tensors="pt")
        dev = self.runtime.device
        if dev.startswith("cuda"):
            inp = {k: v.to(dev) for k, v in inp.items()}
        with torch.no_grad():
            out = self._model.get_text_features(**inp)
        if hasattr(out, "pooler_output"):
            emb = out.pooler_output
        else:
            emb = out
        emb = emb.cpu().float().numpy()[0]
        emb = emb / (np.linalg.norm(emb) + 1e-9)
        self._text_emb[key] = emb
        return emb

    def _frame_image_embedding(self, img):
        import torch
        self._ensure_model()
        inp = self._proc(images=img, return_tensors="pt")
        dev = self.runtime.device
        if dev.startswith("cuda"):
            inp = {k: v.to(dev) for k, v in inp.items()}
        with torch.no_grad():
            out = self._model.get_image_features(**inp)
        if hasattr(out, "pooler_output"):
            emb = out.pooler_output
        else:
            emb = out
        emb = emb.cpu().float().numpy()[0]
        return emb / (np.linalg.norm(emb) + 1e-9)

    # ---------------- 单值字段（top-1 softmax 归一） ----------------
    def _classify_single(self, field: str, imgs) -> dict:
        scores = {}
        for label in self.LABEL_PROMPTS.get(field, {}):
            te = self._text_embedding(field, label)
            sims = []
            for img in imgs:
                ie = self._frame_image_embedding(img)
                sims.append(float(np.dot(ie, te)))
            scores[label] = float(np.mean(sims))
        best = max(scores, key=scores.get)
        # softmax 归一 → model_score（非概率，仅相对）
        vals = np.array(list(scores.values()))
        exp = np.exp((vals - vals.max()) * 4.0)
        probs = exp / exp.sum()
        score = float(probs[list(scores.keys()).index(best)])
        return {"prediction": best, "model_score": round(score, 3),
                "frame_evidence": len(imgs), "model_version": MODEL_VERSION,
                "backend": self.runtime.backend, "created_at": time.time(),
                "all_scores": {k: round(v, 3) for k, v in sorted(scores.items(), key=lambda x: -x[1])[:3]}}

    # ---------------- 多标签字段（阈值） ----------------
    def _classify_multi(self, field: str, imgs, threshold: float = 0.08) -> dict:
        labels = []
        label_scores = {}
        for label in self.LABEL_PROMPTS.get(field, {}):
            if label in ("UNKNOWN", "NOT_APPLICABLE"):
                continue
            te = self._text_embedding(field, label)
            sims = []
            for img in imgs:
                ie = self._frame_image_embedding(img)
                sims.append(float(np.dot(ie, te)))
            label_scores[label] = float(np.mean(sims))
        if label_scores:
            base = max(label_scores.values())
            for lab, s in label_scores.items():
                if s >= base - threshold:
                    labels.append(lab)
        if not labels:
            labels = ["UNKNOWN"]
        return {"prediction": labels, "model_score": round(max(label_scores.values(), default=0.0), 3),
                "frame_evidence": len(imgs), "model_version": MODEL_VERSION,
                "backend": self.runtime.backend, "created_at": time.time()}

    # ---------------- 主入口 ----------------
    def analyze(self, frames_paths: list[str]) -> dict:
        """输入帧图像路径列表 → 各字段预测（图像批量推理 + text 预计算）。"""
        from treecut.services.visual_cognition import _imread
        import torch
        imgs = []
        for p in frames_paths[:8]:
            img = _imread(p)
            if img is not None:
                imgs.append(img)
        if not imgs:
            return {"error": "no_frames"}
        self._ensure_model()
        dev = self.runtime.device
        # 1) 图像批量 embedding（一次 forward）
        inp = self._proc(images=imgs, return_tensors="pt")
        if dev.startswith("cuda"):
            inp = {k: v.to(dev) for k, v in inp.items()}
        with torch.no_grad():
            out = self._model.get_image_features(**inp)
        if hasattr(out, "pooler_output"):
            ie = out.pooler_output
        else:
            ie = out
        ie = ie.cpu().float().numpy()
        ie = ie / (np.linalg.norm(ie, axis=1, keepdims=True) + 1e-9)
        # 2) 各字段 text embedding（预计算全字段）
        for f in self.LABEL_PROMPTS:
            for lab in self.LABEL_PROMPTS[f]:
                self._text_embedding(f, lab)
        # 3) 每字段分类
        out = {"model_version": MODEL_VERSION, "backend": self.runtime.backend,
               "cold_start_ms": getattr(self, "_cold_start_ms", None)}
        for f in ("scene_family", "scene_subtype", "product_family",
                  "product_variant", "shot_scale", "people_presence", "product_visibility"):
            out[f] = self._classify_single_emb(f, ie)
        for f in ("material", "component", "function", "shot_role"):
            out[f] = self._classify_multi_emb(f, ie)
        return out

    def _classify_single_emb(self, field: str, ie: np.ndarray) -> dict:
        scores = {}
        for label in self.LABEL_PROMPTS.get(field, {}):
            te = self._text_emb.get((field, label))
            if te is None:
                continue
            scores[label] = float(np.mean(ie @ te))
        best = max(scores, key=scores.get)
        vals = np.array(list(scores.values()))
        exp = np.exp((vals - vals.max()) * 4.0)
        probs = exp / exp.sum()
        score = float(probs[list(scores.keys()).index(best)])
        return {"prediction": best, "model_score": round(score, 3),
                "frame_evidence": len(ie), "model_version": MODEL_VERSION,
                "backend": self.runtime.backend, "created_at": time.time(),
                "all_scores": {k: round(v, 3) for k, v in sorted(scores.items(), key=lambda x: -x[1])[:3]}}

    def _classify_multi_emb(self, field: str, ie: np.ndarray, threshold: float = 0.06) -> dict:
        label_scores = {}
        for label in self.LABEL_PROMPTS.get(field, {}):
            if label in ("UNKNOWN", "NOT_APPLICABLE"):
                continue
            te = self._text_emb.get((field, label))
            if te is None:
                continue
            label_scores[label] = float(np.mean(ie @ te))
        labels = []
        if label_scores:
            base = max(label_scores.values())
            for lab, s in label_scores.items():
                if s >= base - threshold:
                    labels.append(lab)
        if not labels:
            labels = ["UNKNOWN"]
        return {"prediction": labels, "model_score": round(max(label_scores.values(), default=0.0), 3),
                "frame_evidence": len(ie), "model_version": MODEL_VERSION,
                "backend": self.runtime.backend, "created_at": time.time()}

    def unload(self):
        if self._model is not None:
            del self._model, self._proc, self._text_emb
            self._model = self._proc = None
            self._text_emb = {}
            self.runtime.unload_all()
