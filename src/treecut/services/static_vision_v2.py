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

    # 候选标签（V2.1 枚举 → 用于匹配的自然语言描述）
    LABEL_PROMPTS = {
        "scene_family": {
            "FACTORY": "工厂车间/生产厂房内部场景", "CUSTOMER_HOME": "客户家里的客厅/家居场景",
            "SHOWROOM": "展厅/样板间展示场景", "INSTALLATION_SITE": "安装现场/施工现场",
            "OTHER": "其他场景", "UNKNOWN": "未知场景"},
        "scene_subtype": {
            "FACTORY_WORKSHOP": "工厂加工车间生产区域", "FACTORY_SHOWROOM": "工厂展厅展示区",
            "FACTORY_WAREHOUSE": "工厂仓库", "FACTORY_OTHER": "工厂其他区域",
            "NOT_APPLICABLE": "不适用", "UNKNOWN": "未知"},
        "product_family": {
            "ISLAND": "厨房岛台/中岛", "BAR": "吧台/高脚台",
            "SIDEBOARD": "餐边柜/边柜", "DINING_TABLE": "餐桌/茶桌",
            "OTHER": "其他家具", "UNKNOWN": "未知"},
        "product_variant": {
            "STANDARD_ISLAND": "标准固定岛台", "EXTENDABLE_ISLAND": "可伸缩岛台/拉伸岛台",
            "FLOATING_ISLAND": "悬浮岛台/悬挑岛台", "FLOOR_ISLAND": "落地岛台",
            "NOT_APPLICABLE": "不适用", "OTHER": "其他型号", "UNKNOWN": "未知"},
        "material": {
            "岩板": "岩板表面/陶瓷大板纹理", "实木": "实木木材纹理",
            "奢石": "奢石/名贵石材纹理", "大理石": "大理石纹理",
            "肤感": "肤感哑光饰面", "不锈钢": "不锈钢金属表面",
            "玻璃": "玻璃透明表面", "其他": "其他材质", "UNKNOWN": "未知"},
        "component": {
            "DRAWER": "抽屉", "CABINET_DOOR": "柜门", "TRACK_SOCKET": "轨道插座/滑轨电源",
            "COUNTERTOP": "台面/桌面", "SINK": "水槽/洗手池", "APPLIANCE_SLOT": "电器嵌入槽",
            "ACRYLIC_SUPPORT": "亚克力支撑/透明支架", "OTHER": "其他组件",
            "NOT_APPLICABLE": "不适用", "UNKNOWN": "未知"},
        "function": {
            "STORAGE": "收纳储物功能", "EXTENDABLE": "伸缩延展功能", "POWER": "用电供电功能",
            "DINING": "就餐用餐功能", "OFFICE": "办公功能", "WATER_BAR": "水吧功能",
            "EMBEDDED_APPLIANCE": "嵌入电器功能", "CHILD_SAFETY": "儿童安全功能",
            "OTHER": "其他功能", "NOT_APPLICABLE": "不适用", "UNKNOWN": "未知"},
        "shot_scale": {
            "WIDE": "全景远景大场景", "MEDIUM": "中景人物或物体半身",
            "CLOSE": "近景特写物体细节", "CLOSE_UP": "极特写微距", "UNKNOWN": "未知"},
        "shot_role": {
            "PERSON_TALKING": "有人在讲解说话", "FUNCTION_DEMO": "功能演示操作",
            "SPACE_OVERVIEW": "空间环境扫视", "PRODUCT_SHOWCASE": "产品展示",
            "DETAIL_SHOWCASE": "细节展示特写", "CRAFT_SHOWCASE": "工艺制作过程",
            "INSTALLATION": "安装施工过程", "OTHER": "其他", "UNKNOWN": "未知"},
        "people_presence": {"YES": "画面中有人物出现", "NO": "画面中没有人", "UNKNOWN": "未知"},
        "product_visibility": {"VISIBLE": "产品清晰可见", "PARTIAL": "产品部分可见",
                               "HIDDEN": "产品被遮挡隐藏", "UNKNOWN": "未知"},
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
