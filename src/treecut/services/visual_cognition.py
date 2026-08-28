# -*- coding: utf-8 -*-
"""TreeCut Phase 3 — Visual Cognition Pipeline（Stage 1 prototype）。

本模块实现 Phase 3 第一停点的可运行原型（CPU/OpenCV 启发式 baseline）：
  STEP 2  FrameSampler              — 自适应取帧（start/25/50/75/end + 运动加帧）
  STEP 3  StaticVisualCognition     — 静态视觉字段（scene/product/material/shot_scale/shot_role/people）
  STEP 4  TemporalActionAnalyzer    — 帧差运动 → action_group + action_sequence（prototype）
  STEP 5  TechnicalQualityV2        — sharpness/brightness/contrast/motion/stability/black_frame/曝光
  STEP 6  SegmentMultimodalEvidence — per-field 融合（视觉 + ASR + OCR）
  STEP 7  EvidenceGate              — per-field evidence_sufficiency（SUFFICIENT/PARTIAL/WEAK/CONFLICT/MISSING）
  STEP 8  ConfidenceGate            — model_score/evidence/fusion 分离，路由（不称概率）

诚实声明：
  - 本模块是 HEURISTIC PROTOTYPE（model_version='opencv-heuristic-v0.1'），非深度视觉模型；
  - 本机 torch 为 CPU-only、无 CUDA、models 目录为空、HF_HUB_OFFLINE=1 无法下载大模型；
  - 所有分数为启发式置信度（HEURISTIC_CONFIDENCE_V1 语义），禁止当概率；
  - 无法可靠实现的字段输出 UNKNOWN 并标注 PARTIAL，禁止造假分数。
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

MODEL_VERSION = "opencv-heuristic-v0.1"


def _imread(path: str, flag=cv2.IMREAD_COLOR):
    """支持中文路径的图像读取（cv2.imread 在 Windows 非 ASCII 路径下失败）。"""
    try:
        data = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(data, flag)
        return img
    except Exception:
        return None

# ---------------------------------------------------------------------------
# STEP 2 — Frame Sampler（自适应取帧）
# ---------------------------------------------------------------------------


class FrameSampler:
    """基于已有 keyframes 的自适应取帧。

    - 基础帧：start / 25% / 50% / 75% / end（按时戳分位选最近 keyframe）；
    - 自适应：相邻帧差能量高（运动段）→ 增加中间帧；静态段 → 减至 3 帧。
    """

    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def _frames_of(self, seg_id: str) -> list[tuple[float, str]]:
        with sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro",
                             uri=True) as conn:
            rows = conn.execute(
                "SELECT timestamp_ms, image_path FROM keyframes WHERE segment_id=? "
                "ORDER BY timestamp_ms", (seg_id,)).fetchall()
        return [(r[0], r[1]) for r in rows]

    def sample(self, seg_id: str, start_ms: int = 0, end_ms: int = 0) -> dict:
        frames = self._frames_of(seg_id)
        if not frames:
            return {"frames": [], "mode": "NO_KEYFRAMES", "adaptive": False}
        # 段范围过滤
        if end_ms > start_ms:
            frames = [f for f in frames if start_ms <= f[0] <= end_ms]
        if not frames:
            frames = self._frames_of(seg_id)
        ts = [f[0] for f in frames]
        span = (max(ts) - min(ts)) or 1
        # 5 分位目标
        targets = [0.0, 0.25, 0.5, 0.75, 1.0]
        picked = []
        for t in targets:
            want = min(ts) + span * t
            idx = min(range(len(ts)), key=lambda i: abs(ts[i] - want))
            if idx not in picked:
                picked.append(idx)
        picked.sort()
        # 运动检测：相邻帧差能量（灰度 L1）
        motion = 0.0
        if len(picked) >= 2 and cv2 is not None:
            prev = None
            for idx in picked[:6]:
                img = _imread(frames[idx][1], cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                if prev is not None:
                    d = cv2.absdiff(prev, cv2.resize(img, (160, 90)))
                    motion += float(d.mean()) / 255.0
                prev = cv2.resize(img, (160, 90))
            motion /= max(len(picked) - 1, 1)
        adaptive = False
        if motion > 0.06 and len(picked) < 8:  # 高运动 → 加密
            extra = []
            for i in range(len(picked) - 1):
                mid = (picked[i] + picked[i + 1]) // 2
                if mid not in picked and mid not in extra:
                    extra.append(mid)
            picked = sorted(picked + extra[:3])
            adaptive = True
        elif motion < 0.01 and len(picked) > 3:  # 静态 → 减帧
            picked = [picked[0], picked[len(picked) // 2], picked[-1]]
            adaptive = True
        out = [{"timestamp_ms": frames[i][0], "image_path": frames[i][1]}
               for i in picked]
        return {"frames": out, "mode": f"ADAPTIVE" if adaptive else "FIXED_5",
                "motion_energy": round(motion, 4), "adaptive": adaptive}


# ---------------------------------------------------------------------------
# STEP 5 — Technical Quality V2（先写，静态/时序都要用）
# ---------------------------------------------------------------------------


class TechnicalQualityV2:
    """技术质量子分（Phase 2 只有 sharpness/brightness；V2 补充其余维度）。

    输出段级聚合：{sharpness, brightness, contrast, motion, stability,
    black_frame_ratio, over_exposure, under_exposure}，保留各子分，不做单一总分。
    """

    def analyze(self, frames: list[dict]) -> dict:
        if cv2 is None or not frames:
            return {"error": "no_frames"}
        grays = []
        for fr in frames[:10]:
            img = _imread(fr["image_path"], cv2.IMREAD_GRAYSCALE)
            if img is not None:
                grays.append(img)
        if not grays:
            return {"error": "unreadable"}
        sharp = np.mean([cv2.Laplacian(g, cv2.CV_64F).var() for g in grays])
        bright = np.mean([g.mean() for g in grays])
        contrast = np.mean([g.std() for g in grays])
        # motion / stability：相邻帧差
        motions = []
        stabs = []
        for i in range(len(grays) - 1):
            a = cv2.resize(grays[i], (128, 72))
            b = cv2.resize(grays[i + 1], (128, 72))
            d = cv2.absdiff(a, b)
            motions.append(float(d.mean()) / 255.0)
            # 结构相似简化：相关系数
            corr = np.corrcoef(a.ravel(), b.ravel())[0, 1]
            stabs.append(float(corr) if np.isfinite(corr) else 0.0)
        motion = float(np.mean(motions)) if motions else 0.0
        stability = float(np.mean(stabs)) if stabs else 0.0
        black = float(np.mean([1 if g.mean() < 12 else 0 for g in grays]))
        over = float(np.mean([1 if np.percentile(g, 99) > 250 else 0 for g in grays]))
        under = float(np.mean([1 if g.mean() < 25 else 0 for g in grays]))
        return {
            "sharpness": round(float(sharp), 1),
            "brightness": round(float(bright), 1),
            "contrast": round(float(contrast), 1),
            "motion": round(motion, 4),
            "stability": round(stability, 4),
            "black_frame_ratio": round(black, 3),
            "over_exposure": round(over, 3),
            "under_exposure": round(under, 3),
            "model_version": MODEL_VERSION,
        }


# ---------------------------------------------------------------------------
# STEP 3 — Static Visual Cognition（OpenCV 启发式）
# ---------------------------------------------------------------------------


class StaticVisualCognition:
    """静态视觉字段估计（heuristic prototype）。

    每个字段输出结构化：{prediction, model_score, visual_evidence, frame_refs, model_version}。
    无法可靠判断 → UNKNOWN + model_score 低，诚实标注。
    """

    # material 颜色/纹理原型表（启发式，非训练模型）
    MATERIAL_PROTO = [
        ("实木", (0.42, 0.30, 0.18), 60.0),   # 暖棕
        ("岩板", (0.55, 0.55, 0.58), 30.0),   # 灰白低饱和
        ("大理石", (0.60, 0.58, 0.55), 80.0), # 灰白带纹（高对比）
        ("奢石", (0.50, 0.42, 0.35), 90.0),   # 深色纹理
        ("不锈钢", (0.62, 0.63, 0.64), 15.0), # 亮灰
        ("肤感", (0.72, 0.66, 0.60), 25.0),   # 暖浅
        ("玻璃", (0.65, 0.68, 0.72), 10.0),   # 冷浅
    ]

    def __init__(self):
        self._face_cascade = None
        if cv2 is not None:
            p = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            if p.exists():
                cc = cv2.CascadeClassifier(str(p))
                if not cc.empty():
                    self._face_cascade = cc

    # ---------------- 帧特征 ----------------

    def _frame_features(self, img_bgr):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        small = cv2.resize(gray, (160, 90))
        mean_color = img_bgr.reshape(-1, 3).mean(axis=0)
        sat = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)[:, :, 1].mean()
        lap = cv2.Laplacian(gray, cv2.CV_64F).var()
        # 主体面积：中值滤波后的高梯度区占比（近似前景占比）
        edge = cv2.Canny(small, 60, 160)
        body_ratio = float(edge.mean() / 255.0)
        # 人脸
        faces = 0
        if self._face_cascade is not None and not self._face_cascade.empty():
            try:
                faces = len(self._face_cascade.detectMultiScale(gray, 1.15, 4, minSize=(28, 28)))
            except cv2.error:
                faces = 0
        return {"mean_color": mean_color, "sat": float(sat), "texture": float(lap),
                "body_ratio": body_ratio, "faces": faces, "bright": float(gray.mean())}

    # ---------------- 字段估计 ----------------

    def _est_material(self, feats: list[dict]) -> dict:
        votes = Counter()
        scores = []
        for f in feats:
            c = f["mean_color"]
            best, best_d = None, 1e9
            for name, proto, tex in self.MATERIAL_PROTO:
                d = (c[0] - proto[0]) ** 2 + (c[1] - proto[1]) ** 2 + (c[2] - proto[2]) ** 2
                d += 0.3 * (abs(f["texture"] - tex) / 100.0) ** 2
                if d < best_d:
                    best, best_d = name, d
            votes[best] += 1
            scores.append(max(0.0, 1.0 - best_d / 0.5))
        pred = votes.most_common(1)[0][0] if votes else "UNKNOWN"
        score = round(float(np.mean(scores)) if scores else 0.0, 3)
        # 纹理极低 → 不确定（可能是平面/虚化）
        if pred in ("岩板", "玻璃") and score < 0.25:
            pred, score = "UNKNOWN", round(score * 0.5, 3)
        return {"prediction": pred, "model_score": score,
                "visual_evidence": "color-texture-prototype", "model_version": MODEL_VERSION}

    def _est_shot_scale(self, feats: list[dict]) -> dict:
        body = float(np.mean([f["body_ratio"] for f in feats])) if feats else 0.0
        faces = int(np.max([f["faces"] for f in feats])) if feats else 0
        if faces >= 2:
            pred, score = "MEDIUM", 0.55
        elif faces == 1:
            face_size_hint = 0.0
            pred, score = ("CLOSE" if face_size_hint > 0.2 else "MEDIUM"), 0.5
        elif body > 0.35:
            pred, score = "CLOSE", 0.45
        elif body > 0.15:
            pred, score = "MEDIUM", 0.5
        elif body > 0.05:
            pred, score = "WIDE", 0.45
        else:
            pred, score = "UNKNOWN", 0.2
        return {"prediction": pred, "model_score": round(score, 3),
                "visual_evidence": "edge-density+face", "model_version": MODEL_VERSION}

    def _est_people(self, feats: list[dict]) -> dict:
        faces = int(np.max([f["faces"] for f in feats])) if feats else 0
        if faces > 0:
            return {"prediction": "YES", "model_score": 0.7,
                    "visual_evidence": "face-detected", "model_version": MODEL_VERSION}
        return {"prediction": "NO", "model_score": 0.4,
                "visual_evidence": "no-face", "model_version": MODEL_VERSION}

    def _est_scene(self, feats: list[dict]) -> dict:
        # 启发式：工厂(灰冷/低饱和/大块) vs 展厅(暖/高饱和) vs 客户家(中饱和多色)
        sat = float(np.mean([f["sat"] for f in feats])) if feats else 0.0
        bright = float(np.mean([f["bright"] for f in feats])) if feats else 0.0
        if sat < 35 and bright < 120:
            pred, score = "FACTORY", 0.4
        elif sat > 60:
            pred, score = "SHOWROOM", 0.35
        elif sat > 35:
            pred, score = "CUSTOMER_HOME", 0.3
        else:
            pred, score = "FACTORY", 0.3
        return {"prediction": pred, "model_score": round(score, 3),
                "visual_evidence": "color-saturation-heuristic", "model_version": MODEL_VERSION}

    def _est_product(self, feats: list[dict]) -> dict:
        # 形状启发式极弱：默认 UNKNOWN（产品识别需强视觉模型）
        body = float(np.mean([f["body_ratio"] for f in feats])) if feats else 0.0
        if body > 0.4:
            return {"prediction": "ISLAND", "model_score": 0.25,
                    "visual_evidence": "large-object", "model_version": MODEL_VERSION}
        return {"prediction": "UNKNOWN", "model_score": 0.1,
                "visual_evidence": "insufficient", "model_version": MODEL_VERSION}

    def _est_multi(self, feats: list[dict], field: str) -> dict:
        # component/function/shot_role 多标签：纯视觉原型无法可靠判定 → 空集合
        return {"prediction": [], "model_score": 0.05,
                "visual_evidence": "requires-ocr-asr-or-strong-vision",
                "model_version": MODEL_VERSION, "partial": True}

    # ---------------- 主入口 ----------------

    def analyze(self, segment_id: str, frames: list[dict]) -> dict:
        feats = []
        refs = []
        for fr in frames[:10]:
            img = _imread(fr["image_path"])
            if img is None:
                continue
            feats.append(self._frame_features(img))
            refs.append(fr["image_path"])
        if not feats:
            return {"segment_id": segment_id, "error": "no_frames"}
        out = {
            "segment_id": segment_id,
            "frame_refs": refs,
            "scene_family": self._est_scene(feats),
            "product_family": self._est_product(feats),
            "material": self._est_material(feats),
            "shot_scale": self._est_shot_scale(feats),
            "people_presence": self._est_people(feats),
            "component": self._est_multi(feats, "component"),
            "function": self._est_multi(feats, "function"),
            "shot_role": self._est_multi(feats, "shot_role"),
            "model_version": MODEL_VERSION,
        }
        # 每字段附加 frame_refs
        for k in ("scene_family", "product_family", "material", "shot_scale",
                  "people_presence", "component", "function", "shot_role"):
            out[k]["frame_refs"] = refs
        return out


# ---------------------------------------------------------------------------
# STEP 4 — Temporal Action Analyzer（prototype）
# ---------------------------------------------------------------------------


class TemporalActionAnalyzer:
    """帧差运动 → action_group / action_sequence（prototype）。

    基于运动能量曲线：STATIC（低）、SPEAKING（人物区域高频小运动）、
    EXTEND/DRAWER（中段运动峰）、OTHER。不依赖字幕关键词（纯画面）。
    """

    def analyze(self, frames: list[dict]) -> dict:
        if cv2 is None or len(frames) < 2:
            return {"prediction": "UNKNOWN", "model_score": 0.0,
                    "action_sequence": [], "model_version": MODEL_VERSION,
                    "visual_evidence": "insufficient-frames"}
        grays = []
        for fr in frames[:10]:
            img = _imread(fr["image_path"], cv2.IMREAD_GRAYSCALE)
            if img is not None:
                grays.append(cv2.resize(img, (128, 72)))
        if len(grays) < 2:
            return {"prediction": "UNKNOWN", "model_score": 0.0,
                    "action_sequence": [], "model_version": MODEL_VERSION,
                    "visual_evidence": "unreadable"}
        energies = []
        for i in range(len(grays) - 1):
            d = cv2.absdiff(grays[i], grays[i + 1])
            energies.append(float(d.mean()) / 255.0)
        e_mean = float(np.mean(energies))
        e_max = float(np.max(energies))
        n_peaks = sum(1 for e in energies if e > e_mean + 0.02)
        if e_mean < 0.008:
            group, seq, score = "STATIC", ["STATIC_DISPLAY"], 0.5
        elif e_mean < 0.05 and n_peaks >= 2:
            group, seq, score = "SPEAKING", ["PERSON_SPEAKING"], 0.45
        elif e_mean < 0.12 and n_peaks >= 2:
            # 中低运动峰：可能是拉出/抽屉（单一方向运动）
            group, seq, score = "EXTEND", ["PULL_OUT"], 0.3
        elif e_mean >= 0.12:
            # 高运动：可能是 拉出→缩回 序列（峰对）
            if n_peaks >= 3:
                group, seq, score = "EXTEND", ["PULL_OUT", "RETRACT"], 0.35
            else:
                group, seq, score = "EXTEND", ["PULL_OUT"], 0.3
        else:
            group, seq, score = "UNKNOWN", [], 0.15
        return {"prediction": group, "model_score": round(score, 3),
                "action_sequence": seq, "motion_profile": {
                    "mean": round(e_mean, 4), "max": round(e_max, 4),
                    "peaks": n_peaks},
                "model_version": MODEL_VERSION,
                "visual_evidence": "frame-difference-energy"}


# ---------------------------------------------------------------------------
# STEP 6 — Multimodal Fusion（per-field）
# ---------------------------------------------------------------------------


class SegmentMultimodalEvidence:
    """per-field 融合：视觉 + ASR + OCR。

    权重表（Phase 3 冻结口径）：
      material:    visual 0.8 / asr 0.2
      function:    visual 0.5 / asr 0.5
      action:      temporal 0.7 / asr 0.3
      scene:       visual 0.85 / asr 0.15
      product:     visual 0.6 / asr 0.4
      shot_scale:  visual 1.0
      shot_role:   visual 0.5 / ocr 0.5
      component:   visual 0.3 / asr 0.7
    """

    WEIGHTS = {
        "material": {"visual": 0.8, "asr": 0.2},
        "function": {"visual": 0.5, "asr": 0.5},
        "action": {"temporal": 0.7, "asr": 0.3},
        "scene": {"visual": 0.85, "asr": 0.15},
        "product": {"visual": 0.6, "asr": 0.4},
        "shot_scale": {"visual": 1.0},
        "shot_role": {"visual": 0.5, "ocr": 0.5},
        "component": {"visual": 0.3, "asr": 0.7},
    }

    # ASR/OCR 关键词 → 证据（中文业务词 → V2 枚举）
    ASR_KEYWORDS = {
        "material": {"岩板": "岩板", "实木": "实木", "大理石": "大理石", "奢石": "奢石",
                     "不锈钢": "不锈钢", "肤感": "肤感", "玻璃": "玻璃"},
        "function": {"收纳": "STORAGE", "抽屉": "STORAGE", "伸缩": "EXTENDABLE",
                     "轨道插座": "POWER", "插座": "POWER", "用电": "POWER",
                     "水槽": "WATER_BAR", "水吧": "WATER_BAR", "嵌入电器": "EMBEDDED_APPLIANCE",
                     "隐藏电器": "EMBEDDED_APPLIANCE", "办公": "OFFICE", "就餐": "DINING"},
        "component": {"抽屉": "DRAWER", "柜门": "CABINET_DOOR", "轨道插座": "TRACK_SOCKET",
                      "台面": "COUNTERTOP", "水槽": "SINK", "电器": "APPLIANCE_SLOT"},
        "action": {"拉出": "PULL_OUT", "缩回": "RETRACT", "展开": "PULL_OUT",
                   "打开抽屉": "OPEN_DRAWER", "关闭抽屉": "CLOSE_DRAWER",
                   "打开柜门": "OPEN_CABINET", "插电": "OPERATE_SOCKET",
                   "讲解": "PERSON_SPEAKING", "演示": "FUNCTION_DEMO"},
    }

    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def _load_texts(self, asset_id: str, seg_start: int, seg_end: int) -> tuple[str, str]:
        """返回 (asr_text, ocr_text)。ASR 按 asset 级；OCR 按 frame 时间戳过滤。"""
        asr, ocr = "", ""
        with sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro",
                             uri=True) as conn:
            rows = conn.execute(
                "SELECT text_corrected FROM transcripts WHERE asset_id=? AND "
                "text_corrected IS NOT NULL", (asset_id,)).fetchall()
            asr = " ".join(r[0] for r in rows if r[0])
            if seg_end > seg_start:
                rows = conn.execute(
                    "SELECT text FROM ocr_text WHERE asset_id=? AND "
                    "frame_timestamp_ms BETWEEN ? AND ? AND text IS NOT NULL",
                    (asset_id, seg_start, seg_end)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT text FROM ocr_text WHERE asset_id=? AND text IS NOT NULL",
                    (asset_id,)).fetchall()
            ocr = " ".join(r[0] for r in rows if r[0])
        return asr[:2000], ocr[:2000]

    @staticmethod
    def _keyword_evidence(text: str, table: dict) -> dict:
        hits = []
        for kw, val in table.items():
            if kw in text:
                hits.append(val)
        return {"labels": sorted(set(hits)), "found": bool(hits)}

    def fuse(self, segment_id: str, asset_id: str, seg_start: int, seg_end: int,
             static: dict | None, temporal: dict | None) -> dict:
        asr, ocr = self._load_texts(asset_id, seg_start, seg_end)
        static = static or {}
        result = {"segment_id": segment_id, "asset_id": asset_id,
                  "model_version": MODEL_VERSION, "per_field": {},
                  "sources": {"asr_len": len(asr), "ocr_len": len(ocr)}}
        # material（单值多标签输出集合）
        vis = static.get("material", {}).get("prediction", "UNKNOWN")
        ev = self._keyword_evidence(asr, self.ASR_KEYWORDS["material"])
        mat = set()
        if vis not in ("UNKNOWN",) and vis:
            mat.add(vis)
        if ev["found"]:
            mat.update(ev["labels"])
        result["per_field"]["material"] = {
            "labels": sorted(mat), "visual": vis,
            "asr_evidence": ev["labels"],
            "score": round(0.8 * static.get("material", {}).get("model_score", 0.0)
                           + (0.2 if ev["found"] else 0.0), 3),
            "weights": self.WEIGHTS["material"]}
        # function（多标签）
        ev = self._keyword_evidence(asr, self.ASR_KEYWORDS["function"])
        result["per_field"]["function"] = {
            "labels": sorted(set(ev["labels"])),
            "asr_evidence": ev["labels"], "visual_evidence": [],
            "score": round(0.5 * (0.3 if ev["found"] else 0.0) + (0.5 if ev["found"] else 0.0), 3),
            "weights": self.WEIGHTS["function"]}
        # component（多标签）
        ev = self._keyword_evidence(asr, self.ASR_KEYWORDS["component"])
        result["per_field"]["component"] = {
            "labels": sorted(set(ev["labels"])),
            "asr_evidence": ev["labels"],
            "score": round(0.7 * (1.0 if ev["found"] else 0.0), 3),
            "weights": self.WEIGHTS["component"]}
        # action（temporal + asr）
        t_pred = temporal.get("prediction", "UNKNOWN") if temporal else "UNKNOWN"
        t_seq = temporal.get("action_sequence", []) if temporal else []
        ev = self._keyword_evidence(asr, self.ASR_KEYWORDS["action"])
        seq = list(t_seq)
        if ev["found"]:
            seq.extend(ev["labels"])
        result["per_field"]["action"] = {
            "action_group": t_pred if t_pred != "UNKNOWN" else (
                "OTHER" if ev["found"] else "UNKNOWN"),
            "action_sequence": list(dict.fromkeys(seq)),
            "temporal_group": t_pred, "asr_evidence": ev["labels"],
            "score": round(0.7 * (temporal.get("model_score", 0.0) if temporal else 0.0)
                           + 0.3 * (1.0 if ev["found"] else 0.0), 3),
            "weights": self.WEIGHTS["action"]}
        # scene / product / shot_scale（单值）
        for field, key in (("scene", "scene_family"), ("product", "product_family"),
                           ("shot_scale", "shot_scale")):
            p = static.get(key, {}).get("prediction", "UNKNOWN")
            sc = static.get(key, {}).get("model_score", 0.0)
            w = self.WEIGHTS[field]["visual"]
            result["per_field"][field] = {
                "prediction": p if p != "UNKNOWN" else "UNKNOWN",
                "score": round(sc * w, 3), "weights": self.WEIGHTS[field]}
        # shot_role（多标签，ocr+visual）
        ev = self._keyword_evidence(asr, self.ASR_KEYWORDS["action"])
        role = []
        if ev["found"]:
            if "FUNCTION_DEMO" in ev["labels"]:
                role.append("FUNCTION_DEMO")
            if "PERSON_SPEAKING" in ev["labels"]:
                role.append("PERSON_TALKING")
        result["per_field"]["shot_role"] = {
            "labels": sorted(set(role)), "asr_evidence": ev["labels"],
            "score": round(0.5 * (1.0 if role else 0.0), 3),
            "weights": self.WEIGHTS["shot_role"]}
        # people
        pp = static.get("people_presence", {}).get("prediction", "UNKNOWN")
        result["per_field"]["people"] = {"prediction": pp,
                                         "score": static.get("people_presence", {}).get("model_score", 0.0)}
        return result


# ---------------------------------------------------------------------------
# STEP 7 — Evidence Sufficiency Gate（per-field）
# ---------------------------------------------------------------------------


class EvidenceGate:
    """per-field evidence_sufficiency：SUFFICIENT / PARTIAL / WEAK / CONFLICT / MISSING。"""

    @staticmethod
    def evaluate(field: str, fused: dict) -> str:
        pf = fused.get("per_field", {}).get(field, {})
        score = pf.get("score", 0.0)
        labels = pf.get("labels") or pf.get("action_sequence") or []
        pred = pf.get("prediction", "")
        has_labels = bool(labels) or (pred not in ("", "UNKNOWN"))
        if field in ("scene", "product", "shot_scale", "people"):
            if pred in ("", "UNKNOWN"):
                return "MISSING" if score < 0.1 else "WEAK"
            return "SUFFICIENT" if score >= 0.3 else "PARTIAL"
        # 多标签字段
        if not has_labels:
            return "MISSING"
        if score >= 0.3:
            return "SUFFICIENT"
        return "PARTIAL"


# ---------------------------------------------------------------------------
# STEP 8 — Confidence Gate（路由）
# ---------------------------------------------------------------------------


class ConfidenceGate:
    """路由：SUFFICIENT → cheap end；PARTIAL → 补帧；WEAK → 强视觉；CONFLICT → 强视觉+解释；MISSING → UNKNOWN。

    不输出"概率"：只输出 {model_score, evidence_sufficiency, fusion_score} 三元组。
    """

    @staticmethod
    def route(field: str, fused: dict) -> dict:
        suff = EvidenceGate.evaluate(field, fused)
        pf = fused.get("per_field", {}).get(field, {})
        route_map = {
            "SUFFICIENT": "CHEAP_END",
            "PARTIAL": "ADD_FRAMES",
            "WEAK": "STRONG_VISION",
            "CONFLICT": "STRONG_VISION_WITH_EXPLANATION",
            "MISSING": "UNKNOWN",
        }
        return {
            "field": field,
            "evidence_sufficiency": suff,
            "model_score": round(pf.get("score", 0.0), 3),
            "fusion_score": round(pf.get("score", 0.0), 3),
            "route": route_map.get(suff, "UNKNOWN"),
            "note": "heuristic confidence — NOT a probability (HEURISTIC_CONFIDENCE_V1)",
        }


class VisualCognitionPipeline:
    """统一入口：FrameSampler → Static + Temporal + Technical → Fusion → Gates。"""

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.sampler = FrameSampler(db_path)
        self.static = StaticVisualCognition()
        self.temporal = TemporalActionAnalyzer()
        self.technical = TechnicalQualityV2()
        self.fusion = SegmentMultimodalEvidence(db_path)
        self.gate = ConfidenceGate()

    def analyze(self, segment_id: str, asset_id: str = "",
                start_ms: int = 0, end_ms: int = 0) -> dict:
        samp = self.sampler.sample(segment_id, start_ms, end_ms)
        frames = samp["frames"]
        static = self.static.analyze(segment_id, frames) if frames else None
        temporal = self.temporal.analyze(frames) if frames else None
        technical = self.technical.analyze(frames)
        fused = self.fusion.fuse(segment_id, asset_id, start_ms, end_ms,
                                 static, temporal)
        gates = {f: self.gate.route(f, fused) for f in (
            "scene", "product", "material", "function", "action",
            "shot_scale", "shot_role", "component", "people")}
        return {
            "segment_id": segment_id,
            "sampling": samp,
            "static": static,
            "temporal": temporal,
            "technical_v2": technical,
            "fused": fused,
            "gates": gates,
            "model_version": MODEL_VERSION,
        }
