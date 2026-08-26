"""TreeCut Segment 认知层（Phase 2）— SegmentCognitionService。

核心：
  SegmentEvidenceBuilder — 按 segment 时间范围聚合 L1 证据（ASR/OCR/关键帧/场景/上下文）
  SegmentCognitionService — L2 语义解释写入 semantic_annotations（versioned）

宪法 3：L1 机器证据 / L2 AI 解释 / L3 人工裁决 严格分层，禁止覆盖。
宪法 4：所有 AI 判断记录完整版本。
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from treecut.cognitive.industry import IndustryEngine, simplify_traditional

# 版本常量（Phase 2 第一版）
ALGORITHM_VERSION = "segment-cognition-v1"
KNOWLEDGE_VERSION = "knowledge-v1"
MODEL_NAME = "rules+clip-v1"
MODEL_VERSION = "1.0"
PROMPT_VERSION = "NONE"


@dataclass
class SegmentEvidence:
    """L1 机器证据（按 segment 时间范围过滤后）。"""
    segment_id: str
    asset_id: str
    start_ms: int
    end_ms: int
    asr_text: str = ""
    asr_hits: list = field(default_factory=list)      # [(start_ms, text)]
    ocr_text: str = ""
    keyframes: list = field(default_factory=list)     # [{timestamp_ms, image_path}]
    scene_semantics: list = field(default_factory=list)
    asset_context: dict = field(default_factory=dict)  # asset 级认知
    clip_tags: list = field(default_factory=list)      # asset 级 CLIP 标签
    technical: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id, "asset_id": self.asset_id,
            "start_ms": self.start_ms, "end_ms": self.end_ms,
            "asr_text": self.asr_text[:300], "asr_hits": self.asr_hits[:5],
            "ocr_text": self.ocr_text[:200], "keyframes": self.keyframes[:4],
            "scene_semantics": self.scene_semantics[:3],
            "asset_context": self.asset_context,
            "clip_tags": self.clip_tags[:5], "technical": self.technical,
        }


class SegmentEvidenceBuilder:
    """聚合 segment 时间范围内的 L1 证据。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _ro(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def build(self, segment_id: str) -> SegmentEvidence | None:
        with self._ro() as conn:
            seg = conn.execute(
                "SELECT segment_id, asset_id, start_ms, end_ms FROM segments "
                "WHERE segment_id=?", (segment_id,)).fetchone()
            if not seg:
                return None
            sid, aid, start, end = seg["segment_id"], seg["asset_id"], \
                seg["start_ms"], seg["end_ms"]

            # ASR 按时间过滤：transcripts 有 start_ms/end_ms 吗？查表结构
            asr_rows = conn.execute(
                "SELECT * FROM transcripts WHERE asset_id=? AND text_raw != ''",
                (aid,)).fetchall()
            asr_cols = [d[1] for d in conn.execute("PRAGMA table_info(transcripts)")]
            asr_hits = []
            asr_text_parts = []
            for r in asr_rows:
                # 尝试按时间过滤（若表有 start_ms/end_ms）
                t_start = r["start_ms"] if "start_ms" in asr_cols else None
                t_end = r["end_ms"] if "end_ms" in asr_cols else None
                text = r["text_raw"] or ""
                if t_start is not None and t_end is not None:
                    # 有重叠才算命中本 segment
                    if t_end >= start and t_start <= end:
                        asr_hits.append((t_start, text[:80]))
                        asr_text_parts.append(text)
                else:
                    # 无时间戳：asset 级文本全部聚合（标注为 asset 级）
                    asr_text_parts.append(text)
            asr_text = " ".join(asr_text_parts)

            # OCR 按时间过滤（帧时间戳字段 frame_timestamp_ms）
            ocr_rows = conn.execute(
                "SELECT * FROM ocr_text WHERE asset_id=? AND text != ''",
                (aid,)).fetchall()
            ocr_cols = [d[1] for d in conn.execute("PRAGMA table_info(ocr_text)")]
            ocr_text_parts = []
            for r in ocr_rows:
                t = r["frame_timestamp_ms"] if "frame_timestamp_ms" in ocr_cols else None
                text = r["text"] or ""
                if t is not None:
                    if start - 1500 <= t <= end + 1500:  # ±1.5s 容差
                        ocr_text_parts.append(text)
                else:
                    ocr_text_parts.append(text)
            ocr_text = " ".join(ocr_text_parts)

            # 关键帧（时间范围内）
            kf_rows = conn.execute(
                "SELECT timestamp_ms, image_path FROM keyframes WHERE asset_id=? "
                "ORDER BY timestamp_ms", (aid,)).fetchall()
            kfs = [{"timestamp_ms": r["timestamp_ms"], "image_path": r["image_path"]}
                   for r in kf_rows
                   if start - 1500 <= (r["timestamp_ms"] or 0) <= end + 1500]

            # 场景语义（asset 级）
            sem = [r["semantic"] for r in conn.execute(
                "SELECT semantic FROM scene_semantics WHERE asset_id=?", (aid,))]

            # asset 级认知上下文
            ctx = {}
            cls = conn.execute(
                "SELECT content_type, content_elements, reasons FROM content_classification "
                "WHERE asset_id=?", (aid,)).fetchone()
            if cls:
                ctx["content_type"] = cls["content_type"]
                try:
                    ctx["elements"] = json.loads(cls["content_elements"] or "[]")
                except Exception:
                    ctx["elements"] = []
                try:
                    rr = json.loads(cls["reasons"] or "{}")
                    ctx["vision"] = rr.get("vision", {})
                except Exception:
                    ctx["vision"] = {}

            # 技术元数据
            tech = {}
            asset = conn.execute(
                "SELECT duration, width, height, fps FROM assets WHERE asset_id=?",
                (aid,)).fetchone()
            if asset:
                tech = {"asset_duration": asset["duration"], "width": asset["width"],
                        "height": asset["height"], "fps": asset["fps"]}

        return SegmentEvidence(
            segment_id=sid, asset_id=aid, start_ms=start, end_ms=end,
            asr_text=asr_text, asr_hits=asr_hits, ocr_text=ocr_text,
            keyframes=kfs, scene_semantics=sem, asset_context=ctx,
            clip_tags=ctx.get("vision", {}).get("scene", [])[:5] if isinstance(
                ctx.get("vision"), dict) else [],
            technical=tech,
        )


class SegmentTechnicalQuality:
    """Technical Quality Features（Phase 2.6）。

    基于 segment 时间范围内关键帧的 sharpness/brightness 聚合。
    能可靠计算的真实实现；不能可靠计算的标 PARTIAL，不伪造分数。
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _ro(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def compute(self, segment_id: str) -> dict:
        """计算 segment 技术质量特征。"""
        with self._ro() as conn:
            seg = conn.execute(
                "SELECT asset_id, start_ms, end_ms FROM segments WHERE segment_id=?",
                (segment_id,)).fetchone()
            if not seg:
                return {"segment_id": segment_id, "available": False}
            aid, start, end = seg["asset_id"], seg["start_ms"], seg["end_ms"]
            kfs = conn.execute(
                "SELECT sharpness, brightness FROM keyframes WHERE asset_id=? "
                "AND ? <= timestamp_ms AND timestamp_ms <= ?",
                (aid, start, end)).fetchall()
        sharp = [k["sharpness"] or 0 for k in kfs]
        bright = [k["brightness"] or 0 for k in kfs]
        n = len(sharp)
        if n == 0:
            return {
                "segment_id": segment_id, "available": True,
                "frame_count": 0, "sharpness_avg": None,
                "brightness_avg": None, "black_frame_ratio": None,
                "technical_quality_score": -1.0,  # 无法计算 → -1（unknown），不伪造
                "note": "无关键帧，技术质量无法计算（PARTIAL）",
            }
        sharp_avg = sum(sharp) / n
        bright_avg = sum(bright) / n
        black_ratio = sum(1 for b in bright if b < 10) / n  # 亮度<10 视为黑帧
        # 技术质量分：sharpness 与 brightness 归一化组合（0-100）
        # sharpness 范围约 0-100+，brightness 0-255
        s_score = min(100, sharp_avg * 2)
        b_score = min(100, bright_avg / 255 * 100)
        quality = round(0.7 * s_score + 0.3 * b_score, 1)
        return {
            "segment_id": segment_id, "available": True,
            "frame_count": n, "sharpness_avg": round(sharp_avg, 2),
            "brightness_avg": round(bright_avg, 1),
            "black_frame_ratio": round(black_ratio, 3),
            "technical_quality_score": quality,
            "note": "sharpness/brightness 已实现；contrast/motion/遮挡 未实现（PARTIAL）",
        }


class SegmentCognitionService:
    """L2 语义解释：基于证据生成 segment 认知，写入 semantic_annotations。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.evidence_builder = SegmentEvidenceBuilder(db_path)
        self._industry = None

    @property
    def industry(self):
        if self._industry is None:
            self._industry = IndustryEngine(self.db_path)
        return self._industry

    # ------------------------------------------------------------------
    # L2 语义推断（规则 + CLIP 标签，无 LLM）
    # ------------------------------------------------------------------

    def _infer(self, ev: SegmentEvidence) -> dict:
        """基于证据推断语义。无证据字段 = UNKNOWN（不强行猜测）。"""
        t = simplify_traditional(ev.asr_text + " " + ev.ocr_text)
        asset_ctx = ev.asset_context or {}
        vision = asset_ctx.get("vision", {}) or {}
        vis_text = " ".join(
            (vision.get("scene") or []) + (vision.get("product") or [])
            + (vision.get("material") or []) + (vision.get("function") or []))

        # scene
        scene = ""
        scene_kw = {
            "工厂": ["工厂", "车间", "机器", "加工"],
            "展厅": ["展厅", "样板间"],
            "安装现场": ["安装", "施工", "组装", "入户"],
            "厨房空间": ["厨房", "开放式"],
            "客户家": ["客户家", "家里", "客厅", "实景"],
        }
        for name, kws in scene_kw.items():
            if any(k in t for k in kws):
                scene = name
                break
        if not scene:
            scenes = ev.scene_semantics
            for s in scenes:
                if "视觉:" in s:
                    scene = s.replace("视觉:", "")
                    break
        if not scene:
            scene = "UNKNOWN"

        # product
        product = ""
        prod_kw = {
            "岛台": ["岛台", "导台", "中岛", "台面"],
            "伸缩岛台": ["伸缩", "拿出来", "拉出来", "变长"],
            "餐边柜": ["餐边柜", "餐柜"],
            "吧台": ["吧台", "水吧"],
            "餐桌": ["餐桌"],
        }
        for name, kws in prod_kw.items():
            if any(k in t for k in kws):
                product = name
                break
        if not product:
            for v in vision.get("product", []) or []:
                if "岛台" in v or "桌" in v or "柜" in v:
                    product = v
                    break
        if not product:
            product = "UNKNOWN"

        # material
        material = ""
        mat_kw = {
            "岩板": ["岩板", "哑光台面", "亮光台面"],
            "实木": ["实木", "黑胡桃", "原木", "木纹"],
            "奢石": ["奢石", "潘多拉", "寒江雪"],
            "大理石": ["大理石"],
            "肤感": ["肤感"],
            "不锈钢": ["不锈钢"],
        }
        for name, kws in mat_kw.items():
            if any(k in t for k in kws):
                material = name
                break
        if not material:
            for v in vision.get("material", []) or []:
                material = v
                break
        if not material:
            material = "UNKNOWN"

        # function
        function = ""
        func_kw = {
            "伸缩": ["伸缩", "拿出来", "拉出来", "变长", "延伸", "收进去"],
            "收纳": ["收纳", "储物", "薄抽", "抽屉", "上层", "筷子", "勺子",
                     "分区", "分类"],
            "抽屉": ["抽屉", "薄抽", "薄粗", "托底", "三节"],
            "轨道插座": ["轨道插座", "公牛轨道", "插座"],
            "隐藏电器": ["烤箱", "洗碗机", "隐藏", "嵌入"],
            "水吧": ["水吧", "水槽", "泡茶"],
        }
        for name, kws in func_kw.items():
            if any(k in t for k in kws):
                function = name
                break
        if not function:
            for v in vision.get("function", []) or []:
                if "收纳" in v or "伸缩" in v or "插座" in v:
                    function = v
                    break
        if not function:
            function = "UNKNOWN"

        # action（本 Phase 无视觉时序，仅 ASR 动作词）
        action = ""
        act_kw = {
            "拉出/展开": ["拉出", "展开", "拿出来", "伸缩"],
            "收纳/关闭": ["收进去", "关闭", "收纳"],
            "讲解/演示": ["演示", "讲解", "你看", "这款"],
            "安装": ["安装", "嵌入"],
        }
        for name, kws in act_kw.items():
            if any(k in t for k in kws):
                action = name
                break
        if not action:
            action = "UNKNOWN"

        # shot_type
        shot_type = "UNKNOWN"
        # people
        people = "unknown"
        if "真人讲解" in (asset_ctx.get("elements") or []) or \
                any(k in t for k in ("大家好", "我是", "你看", "来")):
            people = "yes"
        elif not t.strip() and not vis_text:
            people = "no"

        # quality（本 Phase 仅技术占位，-1 = 未计算）
        quality = -1.0

        # confidence：有 ASR 命中 → 较高；仅 asset 级 → 中；双弱 → 低
        # 修正：有 ASR 但所有语义字段均 UNKNOWN → 0.5（避免"有声音就高置信"假象）
        all_unknown = all(v in ("UNKNOWN", "", -1.0, -1) for v in
                          (scene, product, material, function, action))
        if all_unknown:
            confidence = 0.45
        elif ev.asr_hits:
            confidence = 0.85
        elif ev.asr_text.strip() or ev.ocr_text.strip():
            confidence = 0.7
        elif vis_text:
            confidence = 0.55
        else:
            confidence = 0.35

        return {
            "scene": scene, "product": product, "material": material,
            "function": function, "action": action, "shot_type": shot_type,
            "people_presence": people, "product_visibility": -1.0,
            "product_completeness": "UNKNOWN", "quality_score": quality,
            "content_role": "UNKNOWN", "business_value": -1.0,
            "confidence": round(confidence, 2),
            "evidence": {
                "asr_hits": ev.asr_hits[:5],
                "asr_text": ev.asr_text[:200],
                "ocr_text": ev.ocr_text[:120],
                "keyframes": [k["timestamp_ms"] for k in ev.keyframes[:4]],
                "clip_tags": ev.clip_tags[:5],
            },
        }

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def annotate(self, segment_id: str, persist: bool = True) -> dict | None:
        """生成 segment 认知（L2），versioned 写入 semantic_annotations。"""
        ev = self.evidence_builder.build(segment_id)
        if ev is None:
            return None
        infer = self._infer(ev)
        result = {
            "segment_id": segment_id, "asset_id": ev.asset_id,
            **{k: infer[k] for k in ("scene", "product", "material", "function",
                                     "action", "shot_type", "people_presence",
                                     "product_visibility", "product_completeness",
                                     "quality_score", "content_role",
                                     "business_value", "confidence")},
            "evidence": infer["evidence"],
            "versions": {
                "model_name": MODEL_NAME, "model_version": MODEL_VERSION,
                "prompt_version": PROMPT_VERSION,
                "knowledge_version": KNOWLEDGE_VERSION,
                "algorithm_version": ALGORITHM_VERSION,
            },
        }
        if persist:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            # 旧 candidate 标记 superseded
            conn.execute(
                "UPDATE semantic_annotations SET status='superseded' "
                "WHERE target_type='segment' AND target_id=? AND status='candidate'",
                (segment_id,))
            cur = conn.execute(
                "INSERT INTO semantic_annotations(target_type,target_id,scene,product,"
                "material,function,action,shot_type,people_presence,product_visibility,"
                "product_completeness,quality_score,content_role,business_value,"
                "confidence,evidence_refs_json,model_name,model_version,prompt_version,"
                "knowledge_version,algorithm_version,status,created_at) "
                "VALUES('segment',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'candidate', ?)",
                (segment_id, infer["scene"], infer["product"], infer["material"],
                 infer["function"], infer["action"], infer["shot_type"],
                 infer["people_presence"], infer["product_visibility"],
                 infer["product_completeness"], infer["quality_score"],
                 infer["content_role"], infer["business_value"],
                 infer["confidence"],
                 json.dumps(infer["evidence"], ensure_ascii=False),
                 MODEL_NAME, MODEL_VERSION, PROMPT_VERSION,
                 KNOWLEDGE_VERSION, ALGORITHM_VERSION, time.time()))
            result["annotation_id"] = cur.lastrowid
            conn.commit()
            conn.close()
        return result

    def get_annotation(self, segment_id: str) -> dict | None:
        """取最新 candidate 注释。"""
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM semantic_annotations WHERE target_type='segment' "
            "AND target_id=? AND status='candidate' ORDER BY annotation_id DESC LIMIT 1",
            (segment_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def add_human_adjudication(self, segment_id: str, annotation_id: int,
                               values: dict, operator: str = "") -> int:
        """L3 人工裁决写入 human_annotations（不覆盖 L2）。"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        cur = conn.execute(
            "INSERT INTO human_annotations(annotation_id,target_type,target_id,"
            "scene,product,material,function,action,shot_type,people_presence,"
            "product_visibility,quality_score,comment,operator,created_at) "
            "VALUES(?, 'segment', ?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (annotation_id, segment_id,
             values.get("scene", ""), values.get("product", ""),
             values.get("material", ""), values.get("function", ""),
             values.get("action", ""), values.get("shot_type", ""),
             values.get("people_presence", ""),
             values.get("product_visibility", -1), values.get("quality_score", -1),
             values.get("comment", ""), operator, time.time()))
        conn.commit()
        conn.close()
        return int(cur.lastrowid)
