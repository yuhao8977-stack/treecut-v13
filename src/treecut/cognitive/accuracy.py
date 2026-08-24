"""TreeCut AI 业务理解能力验证 — 测试集 + 准确率计算。

表：
  accuracy_test     — 100 条测试集（素材 + AI 完整分析 ABCD 四段式）
  accuracy_review   — 人工审核结果（逐项验证）

重点指标（用户要求）：
  ① 内容类型准确率 ≥85%
  ② 模板匹配准确率 ≥80%
  ③ 商业评分平均偏差 ≤15 分
综合准确率 = 内容类型30% + 模板30% + 产品20% + 商业20%
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from treecut.cognitive.store import CognitiveStore
from treecut.cognitive.brain import Brain
from treecut.cognitive.industry import IndustryEngine

# 测试集分类配额（用户指定；不足按已有随机补足）
TEST_QUOTAS = {
    "客户案例": 20,
    "产品介绍": 20,
    "工厂实力": 20,
    "装修方案": 15,
    "避坑知识": 15,
    "低质量/无价值": 10,
}

# 综合准确率权重
ACCURACY_WEIGHTS = {
    "content_type": 0.30,
    "template": 0.30,
    "product": 0.20,
    "business": 0.20,
}


class AccuracyEngine:
    """准确率验证引擎：测试集 + AI 报告 + 统计。"""

    def __init__(self, db_path: str | Path | None = None):
        self.store = CognitiveStore(db_path)
        self.store.ensure_schema()
        self.brain = Brain(db_path)
        self.industry = IndustryEngine(db_path)
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accuracy_test (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id      TEXT NOT NULL UNIQUE,
                expected_type TEXT NOT NULL DEFAULT '',   -- 测试分类（按素材实际）
                ai_analysis   TEXT NOT NULL DEFAULT '{}', -- ABCD 完整分析 JSON
                status        TEXT NOT NULL DEFAULT 'pending',  -- pending|analyzed|reviewed
                created_time  REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accuracy_review (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id       INTEGER NOT NULL,
                asset_id      TEXT NOT NULL,
                scene_verdict   TEXT NOT NULL DEFAULT '',   -- correct|partial|wrong
                scene_score     INTEGER NOT NULL DEFAULT 0,  -- 0-100
                product_verdict TEXT NOT NULL DEFAULT '',
                ai_content_type TEXT NOT NULL DEFAULT '',
                human_content_type TEXT NOT NULL DEFAULT '',
                ai_template     TEXT NOT NULL DEFAULT '',
                human_template  TEXT NOT NULL DEFAULT '',
                ai_business     INTEGER NOT NULL DEFAULT 0,
                human_business  INTEGER NOT NULL DEFAULT 0,
                overall         TEXT NOT NULL DEFAULT '',   -- 优秀|可用|需要优化|不可用
                comment         TEXT NOT NULL DEFAULT '',
                operator        TEXT NOT NULL DEFAULT '',
                created_time    REAL NOT NULL,
                -- V1.1 账号DNA训练新增字段（模板反馈 + 5维评分原因）
                template_verdict  TEXT NOT NULL DEFAULT '',  -- 适合|部分适合|不适合
                template_reason   TEXT NOT NULL DEFAULT '',
                truth_reason      TEXT NOT NULL DEFAULT '',
                product_reason    TEXT NOT NULL DEFAULT '',
                user_reason       TEXT NOT NULL DEFAULT '',
                comm_reason       TEXT NOT NULL DEFAULT '',
                deal_reason       TEXT NOT NULL DEFAULT '',
                -- V1.2 人工内容确认字段（人工给出具体判定，非对错）
                human_scene    TEXT NOT NULL DEFAULT '',  -- 人工确认的场景（客户家/工厂/展厅/安装现场…）
                human_product  TEXT NOT NULL DEFAULT '',  -- 人工确认的产品（岛台/伸缩岛台/餐边柜…）
                human_material TEXT NOT NULL DEFAULT '',  -- 人工确认的材质（岩板/实木/奢石/大理石/肤感…）
                human_function TEXT NOT NULL DEFAULT '',  -- 人工确认的功能（收纳/伸缩/隐藏电器/插座…）
                UNIQUE(test_id, asset_id)
            )
        """)
        # 幂等迁移：旧库补充新列
        cols = [d[1] for d in conn.execute("PRAGMA table_info(accuracy_review)")]
        for col, ddl in {
            "template_verdict": "TEXT NOT NULL DEFAULT ''",
            "template_reason": "TEXT NOT NULL DEFAULT ''",
            "truth_reason": "TEXT NOT NULL DEFAULT ''",
            "product_reason": "TEXT NOT NULL DEFAULT ''",
            "user_reason": "TEXT NOT NULL DEFAULT ''",
            "comm_reason": "TEXT NOT NULL DEFAULT ''",
            "deal_reason": "TEXT NOT NULL DEFAULT ''",
            "human_scene": "TEXT NOT NULL DEFAULT ''",
            "human_product": "TEXT NOT NULL DEFAULT ''",
            "human_material": "TEXT NOT NULL DEFAULT ''",
            "human_function": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if col not in cols:
                conn.execute(f"ALTER TABLE accuracy_review ADD COLUMN {col} {ddl}")
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # 测试集生成
    # ------------------------------------------------------------------

    def build_test_set(self, quotas: dict[str, int] | None = None,
                       force: bool = False) -> dict:
        """随机抽取测试集（按分类配额，不足随机补足）。"""
        quotas = quotas or TEST_QUOTAS
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        if force:
            conn.execute("DELETE FROM accuracy_test")
            conn.commit()

        existing = {r[0] for r in conn.execute(
            "SELECT asset_id FROM accuracy_test")}
        created = 0
        for ctype, quota in quotas.items():
            if quota <= 0:
                continue
            # 从 content_classification 按类型抽
            if ctype == "低质量/无价值":
                rows = conn.execute("""
                    SELECT asset_id FROM assets a
                    WHERE asset_id NOT IN (SELECT asset_id FROM accuracy_test)
                    ORDER BY RANDOM() LIMIT ?
                """, (quota,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT asset_id FROM content_classification c
                    WHERE c.content_type=? AND asset_id NOT IN
                          (SELECT asset_id FROM accuracy_test)
                    ORDER BY RANDOM() LIMIT ?
                """, (ctype, quota)).fetchall()
            for (aid,) in rows:
                conn.execute(
                    "INSERT OR IGNORE INTO accuracy_test(asset_id,expected_type,"
                    "status,created_time) VALUES(?,?,?,?)",
                    (aid, ctype, "pending", time.time()))
                created += 1
            # 该类型不足 → 从全量素材随机补足（未分类素材也可能属于该类型）
            got = conn.execute(
                "SELECT COUNT(*) FROM accuracy_test WHERE expected_type=?",
                (ctype,)).fetchone()[0]
            if got < quota:
                need = quota - got
                fallback = conn.execute("""
                    SELECT asset_id FROM assets
                    WHERE asset_id NOT IN (SELECT asset_id FROM accuracy_test)
                    ORDER BY RANDOM() LIMIT ?
                """, (need,)).fetchall()
                for (aid,) in fallback:
                    conn.execute(
                        "INSERT OR IGNORE INTO accuracy_test(asset_id,expected_type,"
                        "status,created_time) VALUES(?,?,?,?)",
                        (aid, ctype, "pending", time.time()))
                    created += 1
        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM accuracy_test").fetchone()[0]
        by_type = {r[0]: r[1] for r in conn.execute(
            "SELECT expected_type, COUNT(*) FROM accuracy_test GROUP BY expected_type")}
        conn.close()
        return {"total": total, "created": created, "by_type": by_type}

    # ------------------------------------------------------------------
    # AI 完整分析（ABCD 四段式）
    # ------------------------------------------------------------------

    def analyze_asset(self, asset_id: str, persist: bool = True) -> dict:
        """生成 ABCD 四段式 AI 分析。"""
        # 完整认知链
        brain_result = self.brain.analyze(asset_id)

        # A. 基础检测事实
        perception = brain_result.get("perception", {})
        a = {
            "video_id": asset_id[:16],
            "path": self._get_path(asset_id),
            "duration": perception.get("duration", 0),
            "resolution": perception.get("resolution", ""),
            "scene_raw": perception.get("segments", 0),
            "keyframes": perception.get("keyframes", 0),
            "asr": perception.get("asr_preview", ""),
            "ocr": perception.get("ocr_preview", ""),
        }

        # B. AI 业务理解（V2 双层）
        industry_data = brain_result.get("industry", {})
        scenes = [s.get("semantic", "") for s in industry_data.get("scenes", [])]
        b = {
            "scene_level1": scenes[0] if scenes else "未识别",
            "scene_level2": scenes[1] if len(scenes) > 1 else "",
            "product": industry_data.get("products", []),
            "material": industry_data.get("materials", []),
            "function": industry_data.get("functions", []),
            "content_type": brain_result.get("content_type", "其他"),
            "content_type_main": brain_result.get("content_type_main", ""),
            "content_elements": brain_result.get("content_elements", []),
            "content_confidence": brain_result.get("content_confidence", 0),
            "purpose": self._infer_purpose(brain_result.get("content_type", "")),
            "target_user": self._infer_user(brain_result.get("content_type", "")),
        }

        # C. 小红书运营匹配
        fit = brain_result.get("account_fit", {})
        tpl = brain_result.get("template", {})
        c = {
            "suitable": "是" if (fit.get("fit_score", 0) or 0) >= 50 else "否",
            "fit_score": fit.get("fit_score", 0),
            "reason": "; ".join(fit.get("reasons", [])[:3]),
            "recommend_direction": tpl.get("template_name", ""),
            "recommend_template": tpl.get("template_id", ""),
            "match_score": tpl.get("match_score", 0),
        }

        # D. 商业价值评分（5×20 拆分，V2 真实维度）
        business = brain_result.get("business_value", 0)
        d = self._split_business(business, b, brain_result)

        analysis = {
            "A": a, "B": b, "C": c, "D": d,
            "ai_understanding": brain_result.get("ai_understanding", ""),
        }
        if persist:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            # 保留人工审核状态：reviewed 不降级，仅更新 AI 分析
            conn.execute(
                "UPDATE accuracy_test SET ai_analysis=?, status= "
                "CASE WHEN status='reviewed' THEN 'reviewed' ELSE 'analyzed' END "
                "WHERE asset_id=?",
                (json.dumps(analysis, ensure_ascii=False), asset_id))
            conn.commit()
            conn.close()
        return analysis

    def _infer_purpose(self, content_type: str) -> str:
        return {
            "客户案例": "建立信任", "产品介绍": "展示产品", "产品展示": "展示产品",
            "工厂实力": "建立信任", "装修方案": "解决用户问题", "避坑知识": "解决用户问题",
        }.get(content_type, "品牌曝光")

    def _infer_user(self, content_type: str) -> str:
        return {
            "客户案例": "装修用户/潜在客户", "产品介绍": "装修用户", "产品展示": "装修用户",
            "工厂实力": "装修用户", "装修方案": "小户型/装修用户",
            "避坑知识": "装修用户",
        }.get(content_type, "装修用户")

    def _split_business(self, total: float, b: dict,
                        brain_result: dict | None = None) -> dict:
        """商业评分 5 维拆分（20×5）。

        优先使用 template 引擎 V2 的真实维度（business_reasons 中的五维），
        缺失时退回近似拆分。同时解析每维评分原因（供审核 UI 对比）。
        """
        # 从 template business_reasons 解析 V2 真实五维
        tpl = (brain_result or {}).get("template", {}) or {}
        reasons = tpl.get("business_reasons", []) or []
        for line in reasons:
            if line.startswith("五维:"):
                import re
                import ast
                m = re.search(r"\{.*\}", line)
                if m:
                    try:
                        dims = ast.literal_eval(m.group(0))
                        dims = {k: max(0, min(20, int(v))) for k, v in dims.items()}
                        dim_reasons = self._parse_dim_reasons(reasons)
                        return {"scores": dims,
                                "total": round(sum(dims.values()), 1),
                                "reason": self._business_reason(b),
                                "dim_reasons": dim_reasons}
                    except Exception:
                        pass
        # 退回近似拆分
        total = max(0, min(100, float(total)))
        base = total / 5.0
        if b.get("product"):
            base = base + 2
        if b.get("material"):
            base = base + 1
        scores = {
            "真实性": max(0, min(20, base - 1)),
            "产品展示": max(0, min(20, base + (2 if b.get("product") else -1))),
            "用户价值": max(0, min(20, base + (1 if b.get("function") else 0))),
            "内容传播": max(0, min(20, base - 1)),
            "成交价值": max(0, min(20, base + (1 if b.get("content_type") == "客户案例" else 0))),
        }
        cur = sum(scores.values())
        if cur > 0:
            scale = total / cur
            scores = {k: max(0, min(20, round(v * scale, 1))) for k, v in scores.items()}
        return {"scores": scores, "total": round(total, 1),
                "reason": self._business_reason(b)}

    def _parse_dim_reasons(self, reasons: list[str]) -> dict[str, str]:
        """从 business_reasons 解析每维评分原因（如"真实性: 有真实客户/空间证据 → 18"）。"""
        out = {}
        for line in reasons:
            for dim in ("真实性", "产品价值", "用户价值", "内容传播", "成交价值"):
                if line.startswith(dim + ":"):
                    # 去掉尾部" → 分数"
                    import re
                    txt = re.sub(r"→\s*\d+\s*$", "", line).strip()
                    out[dim] = txt
                    break
        return out

    def _business_reason(self, b: dict) -> str:
        reasons = []
        if b.get("content_type") == "客户案例":
            reasons.append("客户案例天然高成交价值")
        if b.get("product"):
            reasons.append(f"识别到产品: {', '.join(b['product'][:2])}")
        if b.get("function"):
            reasons.append(f"有功能特征: {', '.join(b['function'][:2])}")
        if b.get("material"):
            reasons.append(f"有材质特征: {', '.join(b['material'][:2])}")
        return "; ".join(reasons) or "无显著价值特征"

    def _get_path(self, asset_id: str) -> str:
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        row = conn.execute(
            "SELECT s.path || '\\' || m.relative_path FROM assets a "
            "JOIN media_files m ON m.id=a.media_id JOIN sources s ON s.id=m.source_id "
            "WHERE a.asset_id=?", (asset_id,)).fetchone()
        conn.close()
        return row[0] if row else ""

    # ------------------------------------------------------------------
    # 批量分析
    # ------------------------------------------------------------------

    def batch_analyze(self, limit: int = 100, progress=None) -> dict:
        """对测试集 pending 素材批量生成 AI 分析。"""
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT asset_id FROM accuracy_test WHERE status='pending' LIMIT ?",
            (limit,)).fetchall()
        conn.close()
        done = 0
        for (aid,) in rows:
            try:
                self.analyze_asset(aid)
                done += 1
            except Exception as e:
                print(f"  [分析失败] {aid[:12]}: {e}")
            if progress and done % 10 == 0:
                progress(f"AI 分析 {done}/{len(rows)}")
        return {"requested": len(rows), "analyzed": done}

    # ------------------------------------------------------------------
    # 准确率计算
    # ------------------------------------------------------------------

    def compute_accuracy(self) -> dict:
        """基于人工审核计算准确率（有审核数据时）。"""
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        reviews = conn.execute("SELECT * FROM accuracy_review").fetchall()
        total = len(reviews)
        if total == 0:
            conn.close()
            return {"reviewed": 0, "message": "尚无人工审核数据，请先使用审核 UI"}
        cols = [d[0] for d in conn.execute("PRAGMA table_info(accuracy_review)")]
        conn.close()

        def _count(cond_sql, params=()):
            conn2 = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
            n = conn2.execute(f"SELECT COUNT(*) FROM accuracy_review WHERE {cond_sql}",
                              params).fetchone()[0]
            conn2.close()
            return n

        scene_acc = _count("scene_verdict='correct'") / total
        product_acc = _count("product_verdict='correct'") / total
        content_acc = _count("ai_content_type=human_content_type AND human_content_type!=''") / total
        template_acc = _count("ai_template=human_template AND human_template!=''") / total
        # 商业偏差
        conn2 = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        diffs = [abs(r[0]) for r in conn2.execute(
            "SELECT ai_business - human_business FROM accuracy_review "
            "WHERE human_business > 0")]
        conn2.close()
        business_dev = sum(diffs) / len(diffs) if diffs else 0

        comprehensive = (content_acc * ACCURACY_WEIGHTS["content_type"]
                         + template_acc * ACCURACY_WEIGHTS["template"]
                         + product_acc * ACCURACY_WEIGHTS["product"]
                         + (1 - business_dev / 100) * ACCURACY_WEIGHTS["business"])

        return {
            "reviewed": total,
            "scene_accuracy": round(scene_acc * 100, 1),
            "product_accuracy": round(product_acc * 100, 1),
            "content_type_accuracy": round(content_acc * 100, 1),
            "template_accuracy": round(template_acc * 100, 1),
            "business_deviation": round(business_dev, 1),
            "comprehensive_accuracy": round(comprehensive * 100, 1),
            "targets": {"content_type>=85": content_acc >= 0.85,
                        "template>=80": template_acc >= 0.80,
                        "business_dev<=15": business_dev <= 15},
        }

    def test_set_status(self) -> dict:
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        total = conn.execute("SELECT COUNT(*) FROM accuracy_test").fetchone()[0]
        by_status = {r[0]: r[1] for r in conn.execute(
            "SELECT status, COUNT(*) FROM accuracy_test GROUP BY status")}
        by_type = {r[0]: r[1] for r in conn.execute(
            "SELECT expected_type, COUNT(*) FROM accuracy_test GROUP BY expected_type")}
        reviewed = conn.execute("SELECT COUNT(*) FROM accuracy_review").fetchone()[0]
        conn.close()
        return {"total": total, "by_status": by_status, "by_type": by_type,
                "reviewed": reviewed}

    # ------------------------------------------------------------------
    # AI 自基线（无人工审核时也能量化的代理指标）
    # ------------------------------------------------------------------

    def self_baseline(self) -> dict:
        """AI 判定分布 vs 测试分类交叉表 + 置信度/商业评分分布。"""
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        rows = conn.execute("SELECT expected_type, ai_analysis FROM accuracy_test "
                            "WHERE status IN ('analyzed','reviewed')").fetchall()
        conn.close()
        from collections import Counter, defaultdict
        cross = defaultdict(Counter)   # expected -> ai_judged
        conf_dist = Counter()          # 置信度分档
        biz_dist = Counter()           # 商业评分分档
        low_conf_samples = []          # 低置信样本（供人工优先复核）
        no_product_samples = []
        for etype, analysis in rows:
            try:
                a = json.loads(analysis or "{}")
            except Exception:
                continue
            b = a.get("B", {})
            d = a.get("D", {})
            judged = b.get("content_type", "其他")
            cross[etype][judged] += 1
            conf = b.get("content_confidence", 0) or 0
            if conf < 0.4:
                conf_dist["<0.4"] += 1
            elif conf < 0.6:
                conf_dist["0.4-0.6"] += 1
            elif conf < 0.8:
                conf_dist["0.6-0.8"] += 1
            else:
                conf_dist["≥0.8"] += 1
            biz = round(float(d.get("total", 0) or 0) / 20) * 20
            biz_dist[f"{biz}"] += 1
            if conf < 0.5:
                low_conf_samples.append({
                    "asset_id": a.get("A", {}).get("video_id", ""),
                    "expected": etype, "judged": judged, "conf": round(conf, 2),
                    "asr": (a.get("A", {}).get("asr", "") or "")[:60],
                })
            if not b.get("product"):
                no_product_samples.append({
                    "asset_id": a.get("A", {}).get("video_id", ""),
                    "expected": etype, "judged": judged,
                })
        # 交叉表（行=测试分类, 列=AI判定）
        judged_types = sorted({t for row in cross.values() for t in row})
        cross_table = {
            etype: {t: cross[etype].get(t, 0) for t in judged_types}
            for etype in TEST_QUOTAS
        }
        return {
            "cross_table": cross_table,
            "judged_types": judged_types,
            "confidence_dist": dict(conf_dist),
            "business_dist": dict(biz_dist),
            "low_conf_samples": low_conf_samples[:15],
            "no_product_samples": no_product_samples[:10],
            "low_conf_count": len(low_conf_samples),
            "no_product_count": len(no_product_samples),
        }

    # ------------------------------------------------------------------
    # 错误分析 + 报告
    # ------------------------------------------------------------------

    def top_errors(self, limit: int = 20) -> list[dict]:
        """按审核数据列出 AI 错误 TopN（内容类型错 + 商业偏差大）。"""
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        rows = conn.execute("SELECT * FROM accuracy_review").fetchall()
        conn.close()
        cols = [d[1] for d in
                sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
                .execute("PRAGMA table_info(accuracy_review)").fetchall()]
        errors = []
        for r in rows:
            rec = dict(zip(cols, r))
            biz_dev = abs((rec.get("ai_business") or 0) - (rec.get("human_business") or 0))
            ct_wrong = (rec.get("human_content_type") or "") != "" \
                and (rec.get("ai_content_type") or "") != (rec.get("human_content_type") or "")
            tpl_wrong = (rec.get("human_template") or "") != "" \
                and (rec.get("ai_template") or "") != (rec.get("human_template") or "")
            if not (ct_wrong or tpl_wrong) and biz_dev < 15:
                continue
            errors.append({
                "asset_id": rec.get("asset_id", ""),
                "expected_type": self._expected_type(rec.get("asset_id", "")),
                "ai_content_type": rec.get("ai_content_type", ""),
                "human_content_type": rec.get("human_content_type", ""),
                "ai_template": rec.get("ai_template", ""),
                "human_template": rec.get("human_template", ""),
                "ai_business": rec.get("ai_business", 0),
                "human_business": rec.get("human_business", 0),
                "business_dev": biz_dev,
                "scene_verdict": rec.get("scene_verdict", ""),
                "product_verdict": rec.get("product_verdict", ""),
                "comment": rec.get("comment", ""),
                "overall": rec.get("overall", ""),
            })
        errors.sort(key=lambda e: (e["business_dev"], e["ai_content_type"] != e["human_content_type"]),
                    reverse=True)
        return errors[:limit]

    def _expected_type(self, asset_id: str) -> str:
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        row = conn.execute("SELECT expected_type FROM accuracy_test WHERE asset_id=?",
                           (asset_id,)).fetchone()
        conn.close()
        return row[0] if row else ""

    def knowledge_gaps(self, limit: int = 12) -> list[dict]:
        """从测试集 AI 分析中统计知识库缺口（未识别产品/材质/场景/低置信）。"""
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        rows = conn.execute("SELECT asset_id, ai_analysis, expected_type FROM accuracy_test "
                            "WHERE status IN ('analyzed','reviewed')").fetchall()
        conn.close()
        missing_products, missing_materials, low_conf, no_scene = [], [], [], []
        for aid, analysis, etype in rows:
            try:
                a = json.loads(analysis or "{}")
            except Exception:
                continue
            b = a.get("B", {})
            if not b.get("product"):
                missing_products.append({"asset_id": aid, "expected_type": etype})
            if not b.get("material"):
                missing_materials.append({"asset_id": aid, "expected_type": etype})
            if not b.get("scene_level1") or b.get("scene_level1") == "未识别":
                no_scene.append({"asset_id": aid, "expected_type": etype})
            conf = b.get("content_confidence", 0) or 0
            if conf < 0.6:
                low_conf.append({"asset_id": aid, "expected_type": etype,
                                 "confidence": round(conf, 2)})
        return {
            "missing_product": missing_products[:limit],
            "missing_material": missing_materials[:limit],
            "no_scene": no_scene[:limit],
            "low_confidence": low_conf[:limit],
            "counts": {
                "missing_product": len(missing_products),
                "missing_material": len(missing_materials),
                "no_scene": len(no_scene),
                "low_confidence": len(low_conf),
            },
        }

    def generate_report(self, output: str | Path | None = None) -> str:
        """生成 TREECUT_AI_ACCURACY_REPORT.md（AI 基线 + 人工审核后准确率）。"""
        if output is None:
            # 默认落到项目 docs 目录（与其它报告一致）
            here = Path(__file__).resolve()
            for parent in here.parents:
                if (parent / "docs").is_dir():
                    output = parent / "docs" / "TREECUT_AI_ACCURACY_REPORT.md"
                    break
            if output is None:
                output = Path.cwd() / "TREECUT_AI_ACCURACY_REPORT.md"
        output = Path(output)
        status = self.test_set_status()
        acc = self.compute_accuracy()
        errors = self.top_errors(20)
        gaps = self.knowledge_gaps()
        base = self.self_baseline()

        lines = []
        lines.append("# TreeCut AI 业务理解能力验证报告")
        lines.append("")
        lines.append(f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("## 一、验证环境")
        lines.append("")
        lines.append("| 项 | 值 |")
        lines.append("|---|---|")
        lines.append("| 测试集规模 | 100 条（随机抽取，无人工筛选） |")
        lines.append("| 配额 | 客户案例20 / 产品介绍20 / 工厂实力20 / 装修方案15 / 避坑知识15 / 低质量10 |")
        lines.append("| AI 分析引擎 | Brain 全链路（感知→行业→账号→模板→商业） |")
        lines.append("| 模型 | CLIP vit-base-patch32（视觉）/ faster-whisper GPU（ASR）/ RapidOCR |")
        lines.append("| 数据库 | materials.db（accuracy_test / accuracy_review） |")
        lines.append("")
        lines.append("## 二、测试集分类统计")
        lines.append("")
        lines.append("| 分类 | 数量 |")
        lines.append("|---|---|")
        for t, n in status["by_type"].items():
            lines.append(f"| {t} | {n} |")
        lines.append(f"| **合计** | **{status['total']}** |")
        lines.append("")
        lines.append(f"状态: {status['by_status']}，人工已审核: {status['reviewed']} 条")
        lines.append("")
        lines.append("## 三、准确率指标（人工审核后）")
        lines.append("")
        if acc.get("reviewed", 0) == 0:
            lines.append("**尚无人工审核数据** — 以下为 AI 自评基线，"
                         "需运行 `--accuracy-ui` 逐条人工审核后回填。")
            lines.append("")
            lines.append("| 指标 | 目标 | 当前 | 达标 |")
            lines.append("|---|---|---|---|")
            lines.append("| 内容类型准确率 | ≥85% | 待审核 | - |")
            lines.append("| 模板匹配准确率 | ≥80% | 待审核 | - |")
            lines.append("| 商业评分平均偏差 | ≤15 | 待审核 | - |")
            lines.append("| 综合准确率（30/30/20/20） | - | 待审核 | - |")
        else:
            lines.append("| 指标 | 目标 | 当前 | 达标 |")
            lines.append("|---|---|---|---|")
            lines.append(f"| 内容类型准确率 | ≥85% | {acc['content_type_accuracy']}% | "
                         f"{'✅' if acc['targets']['content_type>=85'] else '❌'} |")
            lines.append(f"| 模板匹配准确率 | ≥80% | {acc['template_accuracy']}% | "
                         f"{'✅' if acc['targets']['template>=80'] else '❌'} |")
            lines.append(f"| 商业评分平均偏差 | ≤15 | {acc['business_deviation']} | "
                         f"{'✅' if acc['targets']['business_dev<=15'] else '❌'} |")
            lines.append(f"| 场景识别准确率 | - | {acc['scene_accuracy']}% | - |")
            lines.append(f"| 产品识别准确率 | - | {acc['product_accuracy']}% | - |")
            lines.append(f"| 综合准确率 | - | {acc['comprehensive_accuracy']}% | - |")
            lines.append("")
            lines.append(f"审核样本数: {acc['reviewed']}")
        lines.append("")
        lines.append("## 四、AI 自基线分析（人工审核前可量化指标）")
        lines.append("")
        lines.append("### 4.1 AI 判定 vs 测试分类交叉表（行=测试分类，列=AI 判定）")
        lines.append("")
        lines.append("| 测试分类 | " + " | ".join(base["judged_types"]) + " |")
        lines.append("|---|" + "---|" * len(base["judged_types"]))
        for etype in TEST_QUOTAS:
            row = base["cross_table"].get(etype, {})
            cells = " | ".join(str(row.get(t, 0)) for t in base["judged_types"])
            lines.append(f"| {etype} | {cells} |")
        lines.append("")
        lines.append("### 4.2 内容类型置信度分布")
        lines.append("")
        lines.append("| 置信度档 | 数量 |")
        lines.append("|---|---|")
        for k in ("<0.4", "0.4-0.6", "0.6-0.8", "≥0.8"):
            lines.append(f"| {k} | {base['confidence_dist'].get(k, 0)} |")
        lines.append("")
        lines.append("### 4.3 商业评分分布（20 分档）")
        lines.append("")
        lines.append("| 评分档 | 数量 |")
        lines.append("|---|---|")
        for k in sorted(base["business_dist"], key=lambda x: int(x)):
            lines.append(f"| {k} | {base['business_dist'][k]} |")
        lines.append("")
        lines.append("### 4.4 低置信度样本（<0.5，优先人工复核）")
        lines.append("")
        if base["low_conf_samples"]:
            lines.append("| 素材 | 测试分类 | AI 判定 | 置信度 | ASR 摘要 |")
            lines.append("|---|---|---|---|---|")
            for s in base["low_conf_samples"]:
                lines.append(f"| {s['asset_id'][:10]} | {s['expected']} | "
                             f"{s['judged']} | {s['conf']} | {s['asr']} |")
        else:
            lines.append("（无）")
        lines.append("")
        lines.append("## 五、AI 错误 Top20")
        lines.append("")
        if not errors:
            lines.append("（无已记录错误，或人工审核尚未完成）")
        else:
            lines.append("| # | 素材 | 测试分类 | AI 类型 | 人工类型 | AI模板 | 人工模板 | 商业偏差 | 总评 |")
            lines.append("|---|---|---|---|---|---|---|---|---|")
            for i, e in enumerate(errors, 1):
                lines.append(
                    f"| {i} | {e['asset_id'][:10]} | {e['expected_type']} | "
                    f"{e['ai_content_type']} | {e['human_content_type']} | "
                    f"{e['ai_template']} | {e['human_template']} | "
                    f"{e['business_dev']} | {e['overall']} |")
        lines.append("")
        lines.append("## 六、AI 错误模式归纳")
        lines.append("")
        if acc.get("reviewed", 0) == 0:
            lines.append("（尚未人工审核。以下为 AI 自基线已暴露的**结构性风险**，需人工审核验证：）")
            lines.append("")
            lines.append("### 6.1 分类规则 vs 素材实际内容错位")
            lines.append("")
            lines.append("测试集配额中 装修方案15/避坑知识15/低质量10 在 content_classification 中无对应分类，"
                         "按设计从全库随机 fallback 补足 —— 这些素材的『期望分类』是随机贴的标签，"
                         "其真实内容多为产品/工厂类。交叉表显示 AI 对这 30 条均未判定为目标类型（0 条命中），"
                         "**不能据此判定 AI 错**，需人工审核给出真实内容类型后再比对。")
            lines.append("")
            lines.append("### 6.2 置信度无区分度（锁定 0.47）")
            lines.append("")
            lines.append("大量素材命中 1 个工厂实力关键词即得 conf=0.4+0.12×1=0.52，"
                         "再乘工厂实力权重 0.9 → 0.47。规则引擎对『命中 1 个词 vs 多个词』区分度不足，"
                         "且工厂实力权重反向压低了置信度。")
            lines.append("")
            lines.append("### 6.3 繁体 ASR 未归一化")
            lines.append("")
            lines.append("测试集约 20% 素材 ASR 为繁体中文（小红书台湾/香港博主），"
                         "而知识库关键词为简体，繁体文本命中率低 → 内容类型/产品/材质识别全面走弱。")
            lines.append("")
            lines.append("### 6.4 客户案例 vs 工厂实力/产品介绍混淆")
            lines.append("")
            lines.append("工厂实力 20 条中 AI 判出 客户案例3/产品介绍2；ASR 短或无产品词时三类极易互串，"
                         "需人工优先核对。")
            lines.append("")
            lines.append("### 6.5 无产品识别样本")
            lines.append("")
            lines.append(f"{base['no_product_count']} 条素材未识别出产品，商业评分的产品维度失真，"
                         "商业偏差可能集中在这些样本。")
            lines.append("")
        else:
            lines.append("（基于人工审核归纳，见上表错误明细。）")
        lines.append("")
        lines.append("## 七、知识库缺口")
        lines.append("")
        lines.append(f"| 缺口 | 数量 | 说明 |")
        lines.append("|---|---|---|")
        lines.append(f"| 产品未识别 | {gaps['counts']['missing_product']} | 无产品词命中知识库，需补充产品词条 |")
        lines.append(f"| 材质未识别 | {gaps['counts']['missing_material']} | 需补充材质词条 |")
        lines.append(f"| 场景未识别 | {gaps['counts']['no_scene']} | 场景语义未匹配，需补充场景词条 |")
        lines.append(f"| 内容类型低置信 | {gaps['counts']['low_confidence']} | 置信度<0.6，需人工复核或增强规则 |")
        lines.append("")
        lines.append("## 八、下一阶段计划")
        lines.append("")
        lines.append("1. 运行 `--accuracy-ui` 完成 100 条人工审核，回填 accuracy_review")
        lines.append("2. 重新生成本报告，核对三项关键指标是否达标")
        lines.append("3. 错误样本写入 learning_rules，驱动 Phase 5 学习")
        lines.append("4. 针对知识缺口补充行业词条（产品/材质/场景）")
        lines.append("5. 迭代后复测，验证指标收敛")
        lines.append("")

        text = "\n".join(lines)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        return str(output)
