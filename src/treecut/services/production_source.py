"""STAGE8 G1 — ProductionSourceService（Canonical 生产源资格服务，替代 pick_clean 临时过滤）。

G1 §24：消费者只问 is_production_eligible(asset_id/segment_id)，不复制 SQL/启发式。
数据层：b007_source_role_v1（角色与污染分离持久化）。
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Iterable

ELIGIBLE_ROLES = ("PRODUCTION_CLEAN_RAW", "PRODUCTION_CLEAN_SEMI")
CONTAM_FIELDS = ("burned_subtitle_present", "platform_watermark_present",
                 "old_title_overlay_present", "brand_overlay_present",
                 "unrelated_overlay_present")


def _default_db() -> str:
    root = os.environ.get("TREECUT_DATA_ROOT")
    if root:
        p = Path(root) / "database" / "materials.db"
        if p.exists():
            return str(p)
    p = os.environ.get("TREECUT_DB")
    if p:
        return p
    return r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"


class ProductionSourceService:
    """读取 b007_source_role_v1，判定生产资格。只读；人工裁决走 adjudicate()。"""

    def __init__(self, db_path: str | None = None):
        self.db = db_path or _default_db()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect("file:" + self.db.replace("\\", "/") + "?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        return c

    def role_row(self, entity_kind: str, entity_id: str | int) -> dict | None:
        with self._conn() as c:
            r = c.execute(
                "SELECT * FROM b007_source_role_v1 WHERE entity_kind=? AND entity_id=?",
                (entity_kind, str(entity_id))).fetchone()
            return dict(r) if r else None

    def is_production_eligible(self, entity_kind: str, entity_id: str | int,
                               strict: bool = True) -> tuple[bool, dict]:
        """资格 = 角色∈CLEAN* 且 未被 REJECTED；
        review_status=APPROVED（L3 人工核准干净）→ 覆盖机器污染候选（历史保留）；
        否则（PENDING/REVIEW_REQUIRED）：机器污染 PRESENT 一律排除；strict=True 时 UNCERTAIN 也不得入池（NO FALSE PASS）。
        """
        row = self.role_row(entity_kind, entity_id)
        if row is None:
            return False, {"reason": "NO_ROLE_ROW"}
        reasons = []
        ok = True
        role = row["source_role"]
        rev = row["review_status"]
        if role not in ELIGIBLE_ROLES:
            ok = False
            reasons.append(f"ROLE_NOT_ELIGIBLE:{role}")
        if rev == "REJECTED":
            ok = False
            reasons.append("HUMAN_REJECTED")
        if rev == "APPROVED":
            reasons.append("L3_HUMAN_APPROVED")
            return ok, {"eligible": ok, "reasons": reasons, "source_role": role,
                        "review_status": rev, "human_override": True}
        for f in CONTAM_FIELDS:
            v = row.get(f)
            if v == "PRESENT":
                ok = False
                reasons.append(f"{f}=PRESENT")
            elif strict and v == "UNCERTAIN":
                ok = False
                reasons.append(f"{f}=UNCERTAIN_STRICT_BLOCK")
        return ok, {"eligible": ok, "reasons": reasons, "source_role": role,
                    "review_status": rev, "human_override": False}

    def production_pool(self, strict: bool = True) -> Iterable[dict]:
        """全量合格生产池（media_file 维度）。"""
        with self._conn() as c:
            rows = c.execute(
                "SELECT entity_id, source_id, source_role, burned_subtitle_present, "
                "platform_watermark_present, unrelated_overlay_present, "
                "old_title_overlay_present, review_status, contamination_confidence "
                "FROM b007_source_role_v1 WHERE entity_kind='media_file'").fetchall()
        for r in rows:
            d = dict(r)
            ok, _ = self.is_production_eligible("media_file", d["entity_id"], strict=strict)
            if ok:
                yield d

    def select_clean_candidates(self, keywords: list[str], limit: int = 40,
                                strict: bool = True) -> list[dict]:
        """替代 V2 pick_clean：关键词过滤只作用于合格生产池（角色+污染双闸）。"""
        like = " OR ".join(["mf.relative_path LIKE ?"] * len(keywords))
        args = [f"%{k}%" for k in keywords]
        with self._conn() as c:
            rows = c.execute(
                f"""SELECT r.entity_id AS media_id, r.source_id, r.source_role,
                           mf.relative_path, a.asset_id
                    FROM b007_source_role_v1 r
                    JOIN media_files mf ON mf.id = r.entity_id
                    LEFT JOIN assets a ON a.media_id = mf.id
                    WHERE r.entity_kind='media_file' AND ({like}) AND mf.extension='.mp4'
                    GROUP BY mf.id LIMIT 200""", args).fetchall()
        out = []
        for r in rows:
            ok, info = self.is_production_eligible("media_file", r["media_id"], strict=strict)
            if ok:
                d = dict(r)
                d["eligible"] = True
                d["eligibility"] = info
                out.append(d)
                if len(out) >= limit:
                    break
        return out

    def adjudicate(self, entity_kind: str, entity_id: str | int, decision: str,
                   human_note: str, reviewer: str = "ARCHITECT") -> dict:
        """人工 L3 裁决（追加式，不覆盖机器证据历史）：
        在 contamination_evidence 中追加 human_adjudication 记录并更新 review_status。"""
        assert decision in ("approved", "rejected", "review_required")
        with sqlite3.connect(self.db, timeout=60) as c:
            row = c.execute("SELECT contamination_evidence, source_role FROM b007_source_role_v1 "
                            "WHERE entity_kind=? AND entity_id=?",
                            (entity_kind, str(entity_id))).fetchone()
            if row is None:
                return {"ok": False, "reason": "NO_ROLE_ROW"}
            ev = json.loads(row[0]) if row[0] else []
            ev.append({"human_adjudication": {"decision": decision, "note": human_note,
                                              "reviewer": reviewer,
                                              "at": time.strftime("%Y-%m-%d %H:%M:%S")}})
            c.execute("UPDATE b007_source_role_v1 SET contamination_evidence=?, "
                      "review_status=?, role_version=role_version+1, updated_at=? "
                      "WHERE entity_kind=? AND entity_id=?",
                      (json.dumps(ev, ensure_ascii=False),
                       decision.upper(), time.time(), entity_kind, str(entity_id)))
        return {"ok": True, "entity_id": str(entity_id), "decision": decision}
