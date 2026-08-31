# -*- coding: utf-8 -*-
"""V0.2 — B007 Creator 自动同步管线（§4/9/10/18/20/31/32）。

两条源路：
  A. OFFICIAL_EXPORT   —— 官方导出（Performance 优先；DOM 依赖，失败记 limitation）
  B. PAGE_OWNED_RESPONSE_OBSERVATION —— 页面自有响应观察（note_id/cover/duration/media_type）

安全纪律：只保存 note_id/title/publish_time/media_type/duration/cover origin+path 等安全字段；
禁止保存 xsec_token/cookie/authorization/signed query/session。
Raw Snapshot IMMUTABLE；解析失败进 quarantine（reason/task_id/source/timestamp）。
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from treecut.services.b007_creator_adapter import B007CreatorImportAdapterV1

log = logging.getLogger("treecut.browser.creator")

NOTE_ID_RE = re.compile(r"^[0-9a-fA-F]{24}$")
XHS_ID_PATTERN_RE = re.compile(r"小红书号[:：]?\s*([0-9a-zA-Z]{6,})")


# ============================================================
# 归一化（§19：NFKC + 标题/时间标准化）
# ============================================================
def normalize_title(title: Any) -> str:
    if title is None:
        return ""
    text = unicodedata.normalize("NFKC", str(title))
    return re.sub(r"\s+", " ", text).strip()


def normalize_publish_time(value: Any) -> str:
    """标准化为 B003 既有格式 'YYYY-MM-DD HH:MM'；无法解析返回原样（证据保留）。"""
    if value is None:
        return ""
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            import datetime
            return datetime.datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    # 时间戳（秒/毫秒）
    if text.isdigit():
        ts = int(text)
        if ts > 10**12:
            ts = ts // 1000
        try:
            import datetime
            return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    return text


def sanitize_url(url: Any) -> str:
    """只保留 origin + path（去除 query/signed 参数），无 cookie/token。"""
    if not url:
        return ""
    try:
        parts = urlsplit(str(url))
        return f"{parts.scheme}://{parts.netloc}{parts.path}"
    except Exception:
        return ""


def extract_cover_meta(value: Any) -> dict:
    """cover 提取：取首个图片 URL 的 origin+path（去 query）。"""
    urls = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                u = item.get("url") or item.get("urlDefault") or item.get("url_pre")
                if u:
                    urls.append(u)
            elif isinstance(item, str):
                urls.append(item)
    elif isinstance(value, str):
        urls = [value]
    elif isinstance(value, dict):
        for k in ("url", "urlDefault", "url_pre"):
            if value.get(k):
                urls = [value[k]]
                break
    for u in urls:
        s = sanitize_url(u)
        if s:
            return {"cover_url_safe": s, "cover_origin": urlsplit(s).netloc,
                    "cover_path": urlsplit(s).path}
    return {}


# ============================================================
# Response Observation（§10/11：页面自有响应 → 安全字段）
# ============================================================
class CreatorResponseObserver:
    """挂到 creator 页面：观察页面自己的 note-list 响应，提取安全字段。

    在浏览器 owner 线程内 attach；Playwright response 事件即该线程回调。
    过滤放宽：只排除明显非内容端点（log/track/upload 等）；解析有上限（防大页卡顿）。
    同时记录命中的端点（origin+path，无 query）供诊断。
    """

    MAX_PARSE = 300

    SKIP_HINTS = ("/log", "/track", "upload", "collect", "/report", "analytics",
                  "sentry", "monitor", "beacon", "/search", "suggest")

    def __init__(self, page):
        self._page = page
        self.notes: dict[str, dict] = {}
        self.observed_responses = 0
        self.parsed = 0
        self.endpoints: list[str] = []
        self._attached = False

    def attach(self) -> None:
        if self._attached:
            return
        self._page.on("response", self._on_response)
        self._attached = True

    def detach(self) -> None:
        if self._attached:
            self._page.remove_listener("response", self._on_response)
            self._attached = False

    def _on_response(self, response) -> None:
        try:
            url = response.url or ""
            ctype = (response.headers.get("content-type") or "")
            if "json" not in ctype and not url.endswith(".json"):
                return
            low = url.lower()
            if any(s in low for s in self.SKIP_HINTS):
                return
            self.observed_responses += 1
            safe = sanitize_url(url)
            if safe and safe not in self.endpoints:
                self.endpoints.append(safe)
            if self.parsed >= self.MAX_PARSE:
                return
            body = response.json() if hasattr(response, "json") else None
            self.parsed += 1
        except Exception:
            return
        self._scan(body)

    def _scan(self, node: Any) -> None:
        if isinstance(node, dict):
            note_id = node.get("note_id") or node.get("id")
            if isinstance(note_id, str) and NOTE_ID_RE.match(note_id):
                self.notes.setdefault(note_id, {})
                entry = self.notes[note_id]
                if "note_id" not in entry:
                    entry["note_id"] = note_id
                    entry["title"] = normalize_title(
                        node.get("display_title") or node.get("title") or node.get("desc"))
                    entry["publish_time"] = normalize_publish_time(
                        node.get("publish_time") or node.get("time"))
                    entry["media_type"] = str(node.get("type") or node.get("media_type") or "")
                    dur = node.get("video", {})
                    if isinstance(dur, dict):
                        duration = dur.get("duration") or dur.get("durationSec")
                    else:
                        duration = node.get("duration")
                    if duration is not None:
                        try:
                            entry["duration"] = round(float(duration), 3)
                        except (TypeError, ValueError):
                            pass
                    cover = extract_cover_meta(node.get("image_list") or node.get("cover")
                                               or node.get("imageInfo"))
                    if cover:
                        entry["cover"] = cover
            for value in node.values():
                self._scan(value)
        elif isinstance(node, list):
            for item in node:
                self._scan(item)

    def take(self) -> list[dict]:
        return [self.notes[k] for k in sorted(self.notes)]


# ============================================================
# Raw Snapshot Store（§6/20：IMMUTABLE）
# ============================================================
class RawSnapshotStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def new_run_dir(self, kind: str = "observation") -> Path:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        run = self.root / "creator" / kind / stamp
        run.mkdir(parents=True, exist_ok=True)
        return run

    def save_immutable(self, run_dir: Path, name: str, payload: dict) -> dict:
        path = run_dir / name
        raw = json.dumps(payload, ensure_ascii=False, indent=1)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        path.write_text(raw, encoding="utf-8")
        (run_dir / (name + ".sha256")).write_text(digest, encoding="utf-8")
        return {"file": str(path), "sha256": digest, "bytes": len(raw)}


# ============================================================
# 官方导出（§5/§6：Source Route A，Performance 优先）
# ============================================================
class OfficialExportDriver:
    """在 note-manager 等当前页寻找「导出/下载」按钮并触发平台官方导出。

    导出流程是平台自身功能（下载官方生成的文件），通常不受笔记列表 API 的
    自动化软阻断影响。找不到按钮 → EXPORT_BUTTON_NOT_FOUND（PAGE_STRUCTURE_CHANGED 类）。
    """

    TRIGGER_TEXTS = ("导出", "下载报表", "下载数据", "导出报表")

    def __init__(self, page, raw_dir):
        self._page = page
        self._raw_dir = raw_dir

    def run(self) -> dict:
        try:
            target = None
            for text in self.TRIGGER_TEXTS:
                try:
                    loc = self._page.get_by_text(text, exact=False).first
                    if loc.count() > 0:
                        target = loc
                        break
                except Exception:
                    continue
            if target is None:
                return {"status": "EXPORT_BUTTON_NOT_FOUND",
                        "note": "当前页未找到 导出/下载 按钮（PAGE_STRUCTURE_CHANGED 类，需 DOM 校准）"}
            with self._page.expect_download(timeout=20000) as dl_info:
                try:
                    target.click(timeout=8000)
                except Exception:
                    return {"status": "EXPORT_CLICK_FAILED",
                            "note": "按钮点击失败（可能需要先选择时间范围等）"}
            download = dl_info.value
            self._raw_dir.mkdir(parents=True, exist_ok=True)
            target_path = self._raw_dir / (download.suggested_filename or "creator_export.xlsx")
            download.save_as(str(target_path))
            return {"status": "EXPORT_DOWNLOADED", "file": str(target_path),
                    "filename": download.suggested_filename or ""}
        except Exception as error:
            return {"status": "EXPORT_ERROR", "error": str(error)[:200]}


# ============================================================
# Creator Sync Runner
# ============================================================
@dataclass
class CreatorSyncResult:
    status: str = "RUNNING"
    gate: dict = field(default_factory=dict)
    account_snapshot: dict = field(default_factory=dict)
    published_count: int = 0
    performance_count: int = 0
    note_id_cover: int = 0
    title_cover: int = 0
    publish_time_cover: int = 0
    media_type_cover: int = 0
    duration_cover: int = 0
    cover_metadata_cover: int = 0
    cover_bytes_cover: int = 0
    join: dict = field(default_factory=dict)
    unmatched: int = 0
    review_required: int = 0
    quarantine: list = field(default_factory=list)
    exceptions: list = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    raw_snapshot: dict = field(default_factory=dict)
    message: str = ""


class CreatorSyncRunner:
    """本地侧管线（观察在 executor 内执行；解析/校验/入库在本线程）。"""

    def __init__(self, workspace, data_root: Path, db_path: str | None = None,
                 inbox_root: Path | None = None, artifact_root: Path | None = None,
                 export_enabled: bool = False, note_list_url: str | None = None):
        self.workspace = workspace
        self.data_root = Path(data_root)
        self.db_path = db_path or str(self.data_root / "database" / "materials.db")
        self.adapter = B007CreatorImportAdapterV1(self.db_path)
        inbox = inbox_root or (self.data_root / "treecut_inbox")
        self.raw_store = RawSnapshotStore(inbox / "creator" / "raw")
        self.inbox_creator = inbox / "creator"
        self.quarantine_dir = inbox / "quarantine" / "B007" / "creator"
        self.artifact_root = artifact_root or self.data_root
        self.export_enabled = export_enabled
        if note_list_url:
            # 用户提供真实笔记列表页 URL 时优先使用（覆盖默认候选）
            self.NOTE_LIST_CANDIDATES = (note_list_url, "https://creator.xiaohongshu.com/")

    # ---- §8 Identity Gate（快速检测 + 已确认绑定复用，冲突才硬停） ----
    def identity_gate(self, runtime, session_status: str | None = None) -> dict:
        binding = self.workspace.load_binding()

        def _detect_fast():
            tab = runtime.ensure_tabs().get("CREATOR")
            return runtime.creator_detector.detect(tab, selector_timeout=2000) if tab else None

        detected = runtime._in_browser(_detect_fast)  # 2s 快速探测，秒级
        status, reason = runtime.creator_detector.gate(detected)  # gate 纯逻辑

        if status == "ACCOUNT_IDENTITY_UNKNOWN" and binding and \
                session_status == "SESSION_VALID":
            # 检测未命中但：SESSION_VALID + 存在人工确认过的绑定 → 复用绑定（证据充分，非猜测）
            status = "ACCOUNT_IDENTITY_VALID"
            reason = ("SESSION_VALID + 已确认绑定复用（DOM 快速检测未命中昵称；"
                      "绑定为人工确认事实）")
        return {"status": status, "reason": reason,
                "binding_creator_xhs_id": binding.creator_xhs_id if binding else None,
                "detected_primary_id": detected.primary_id if detected else None,
                "detected_display_name": detected.display_name if detected else None,
                "expected_xhs_id": binding.creator_xhs_id if binding else None}

    # ---- §7 Account Snapshot ----
    def account_snapshot(self, runtime) -> dict:
        binding = self.workspace.load_binding()
        return {
            "workspace_id": "B007",
            "platform": "XIAOHONGSHU",
            "platform_account_id": binding.creator_xhs_id if binding else None,
            "display_name": binding.creator_display_name if binding else None,
            "follower_count": None,  # 页面未稳定取得 → UNKNOWN（不猜）
            "like_favorite_total": None,
            "account_status": "BOUND",
            "snapshot_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    # ---- 观察（executor 内） ----
    NOTE_LIST_CANDIDATES = (
        "https://creator.xiaohongshu.com/note/list",
        "https://creator.xiaohongshu.com/note/list?source=official",
        "https://creator.xiaohongshu.com/data/overview",
        "https://creator.xiaohongshu.com/",
    )

    def run_observation(self, runtime) -> list[dict]:
        """在 executor 内：attach observer → （必要时）导航笔记列表页 → 滚动加载 → 收集。

        若当前 Creator 页已是内容页（用户手动停在笔记管理），不导航，直接滚动观察。
        仅当捕获到"实质数据"（title/cover/duration 之一）才视为成功；
        否则自动回退到前台个人主页公开笔记列表（user/profile/{xhs_id}）。"""
        tab = runtime.ensure_tabs().get("CREATOR")
        notes = self._observe_page(tab, runtime)
        if any(n.get("title") or n.get("cover") or n.get("duration") is not None for n in notes):
            return notes
        # 回退：前台公开笔记列表（SSR 首屏状态含 note 列表；非视频播放，合规）
        binding = self.workspace.load_binding()
        xhs_id = binding.creator_xhs_id if binding else None
        if xhs_id:
            log.info("观察回退：前台个人主页 user/profile/%s", xhs_id)
            front = runtime.ensure_tabs().get("FRONTEND")
            notes = self._observe_page(front, runtime,
                                       url=f"https://www.xiaohongshu.com/user/profile/{xhs_id}")
        return notes

    def _observe_page(self, tab, runtime, url: str | None = None) -> list[dict]:
        observer = CreatorResponseObserver(tab)
        observer.attach()
        try:
            # 显式 URL（前台回退）或用户提供的 note_list_url 覆盖 → 总是导航（跳过 stay）
            forced = url is not None or getattr(self, "note_list_url", None)
            if url is None and not forced:
                try:
                    current = tab.url or ""
                except Exception:
                    current = ""
                stay = "creator.xiaohongshu.com" in current and "publish/publish" not in current
                if not stay:
                    for cand in self.NOTE_LIST_CANDIDATES:
                        try:
                            tab.goto(cand, timeout=45000)
                            break
                        except Exception:
                            continue
                else:
                    log.info("观察：保留当前 Creator 内容页 %s", sanitize_url(current))
            else:
                target = url or self.note_list_url
                try:
                    tab.goto(target, timeout=60000)
                except Exception as error:
                    log.warning("观察导航失败 %s：%s", target, str(error)[:120])
            # 滚动加载更多（给 SPA 渲染与分页留时间）
            for _ in range(8):
                try:
                    tab.evaluate("() => window.scrollBy(0, document.body.scrollHeight)")
                    import time as _t
                    _t.sleep(1.5)
                except Exception:
                    break
            # XHS 常把首屏数据内嵌 window.__INITIAL_STATE__（SSR），不走 JSON 响应 → 额外提取
            state_notes = self._extract_state_notes(tab)
            for note in state_notes:
                observer.notes.setdefault(note["note_id"], {}).update(note)
            # DOM 兜底：已渲染页面里 explore 链接的 note_id + 卡片标题
            dom_notes = self._extract_dom_notes(tab)
            for note in dom_notes:
                observer.notes.setdefault(note["note_id"], {}).update(note)
        finally:
            observer.detach()
        self._last_observation_diag = {
            "json_responses": observer.observed_responses,
            "parsed": observer.parsed,
            "endpoints": observer.endpoints,
            "state_extracted": len(state_notes),
            "dom_extracted": len(dom_notes),
        }
        log.info("观察：json响应=%s 解析=%s 端点=%s 笔记=%s 首屏=%s DOM=%s",
                 observer.observed_responses, observer.parsed,
                 len(observer.endpoints), len(observer.notes), len(state_notes), len(dom_notes))
        return observer.take()

    # ---- DOM 兜底：已渲染页面 explore 链接（面板里用户打开笔记管理后有效） ----
    @staticmethod
    def _extract_dom_notes(tab, cap: int = 500) -> list[dict]:
        try:
            raw = tab.evaluate(
                "() => {"
                "  const out = []; const seen = new Set();"
                "  const els = document.querySelectorAll('a[href*=\"/explore/\"]');"
                "  for (const a of els) {"
                "    if (out.length >= 500) break;"
                "    const m = (a.getAttribute('href') || '').match(/\\/explore\\/([0-9a-f]{24})/i);"
                "    if (!m || seen.has(m[1])) continue;"
                "    seen.add(m[1]); const card = a.closest('[class]');"
                "    let title = '';"
                "    if (card) { const t = card.querySelector('[class*=\"title\"], [class*=\"desc\"]');"
                "      if (t) title = (t.textContent || '').trim(); }"
                "    if (!title) title = (a.textContent || '').trim().slice(0, 60);"
                "    out.push({ note_id: m[1], title: title });"
                "  }"
                "  return out;"
                "}"
            )
        except Exception as error:
            log.warning("DOM 笔记提取失败：%s", str(error)[:120])
            return []
        notes = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("note_id"):
                    notes.append({"note_id": item["note_id"],
                                  "title": normalize_title(item.get("title"))})
        return notes

    # ---- SSR 首屏状态提取（window.__INITIAL_STATE__，支持 key 与值两种 id 形态） ----
    STATE_EXTRACT_JS = r"""() => {
  const out = []; const seen = new Set(); const seenObjs = new Set();
  const isId = (v) => typeof v === 'string' && /^[0-9a-f]{24}$/i.test(v);
  const grab = (rec, node) => {
    for (const f of ['title','display_title','displayTitle','type','media_type','time','publish_time','lastUpdateTime']) {
      if (node[f] !== undefined && node[f] !== null && rec[f] === undefined) rec[f] = node[f];
    }
    const nc = node.noteCard || node.noteDetail;
    if (nc && typeof nc === 'object') grab(rec, nc);
    const vi = node.video;
    if (vi && typeof vi === 'object' && vi.duration !== undefined) rec.duration = vi.duration;
    const im = node.image_list || node.cover || node.imageInfo || (node.coverList && node.coverList[0]);
    if (Array.isArray(im) && im[0] && im[0].url) rec.cover = im[0].url;
    else if (im && typeof im === 'object' && im.url) rec.cover = im.url;
    else if (im && typeof im === 'string') rec.cover = im;
  };
  const walk = (node) => {
    if (!node || typeof node !== 'object' || seenObjs.has(node) || out.length >= 500) return;
    seenObjs.add(node);
    if (Array.isArray(node)) { for (const it of node) walk(it); return; }
    for (const k of Object.keys(node)) {
      const v = node[k];
      if (isId(k) && v && typeof v === 'object' && !seen.has(k)) {
        seen.add(k); const rec = { note_id: k }; grab(rec, v); out.push(rec);
        walk(v); continue;
      }
      if (isId(v) && (k === 'note_id' || k === 'id' || k === 'noteId') && !seen.has(v)) {
        seen.add(v); const rec = { note_id: v }; grab(rec, node); out.push(rec);
      }
      if (v && typeof v === 'object') walk(v);
    }
  };
  walk(window.__INITIAL_STATE__ || window.__INITIAL_SSR_STATE__ || null);
  return out.slice(0, 500);
}"""

    @staticmethod
    def _extract_state_notes(tab, cap: int = 500) -> list[dict]:
        try:
            raw = tab.evaluate(CreatorSyncRunner.STATE_EXTRACT_JS)
        except Exception as error:
            log.warning("首屏状态提取失败：%s", str(error)[:120])
            return []
        notes = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict) or not item.get("note_id"):
                    continue
                note = {"note_id": item["note_id"],
                        "title": normalize_title(item.get("display_title")
                                                 or item.get("displayTitle") or item.get("title")),
                        "publish_time": normalize_publish_time(
                            item.get("publish_time") or item.get("time")
                            or item.get("lastUpdateTime")),
                        "media_type": str(item.get("media_type") or item.get("type") or "")}
                if item.get("duration") is not None:
                    try:
                        note["duration"] = round(float(item["duration"]), 3)
                    except (TypeError, ValueError):
                        pass
                cover = extract_cover_meta(item.get("cover"))
                if cover:
                    note["cover"] = cover
                notes.append(note)
        return notes

    # ---- 主流程 ----
    def run(self, runtime, task_id: str) -> CreatorSyncResult:
        result = CreatorSyncResult()
        result.gate = self.identity_gate(runtime)
        if result.gate["status"] != "ACCOUNT_IDENTITY_VALID":
            result.status = "ACCOUNT_IDENTITY_MISMATCH" if \
                result.gate["status"] == "ACCOUNT_IDENTITY_MISMATCH" else "GATE_UNKNOWN"
            result.message = result.gate.get("reason") or result.gate["status"]
            return result
        result.message = "账号门通过"

        # Account Snapshot
        result.account_snapshot = self.account_snapshot(runtime)

        # Observation（identity/cover/duration）
        try:
            notes = runtime._in_browser(lambda: self.run_observation(runtime))
        except Exception as error:
            notes = []
            result.exceptions.append({"stage": "OBSERVE", "error": str(error)[:200]})

        # 官方导出（Performance；在观察后的当前页上尝试导出按钮）
        export_result: dict = {"status": "SKIPPED"}
        if self.export_enabled:
            try:
                export_dir = self.raw_store.root / "creator" / "exports"
                export_result = runtime._in_browser(
                    lambda: OfficialExportDriver(
                        runtime.ensure_tabs().get("CREATOR"), export_dir).run())
            except Exception as error:
                export_result = {"status": "EXPORT_ERROR", "error": str(error)[:200]}

        # ---- 保存 Raw（IMMUTABLE） ----
        run_dir = self.raw_store.new_run_dir("observation")
        raw_payload = {
            "task_id": task_id, "gate": result.gate,
            "account_snapshot": result.account_snapshot,
            "observed_notes": notes, "export": export_result,
            "observation_diag": getattr(self, "_last_observation_diag", {}),
        }
        result.raw_snapshot = self.raw_store.save_immutable(run_dir, "creator_raw.json", raw_payload)
        result.artifacts["raw_snapshot"] = result.raw_snapshot

        # ---- 校验 + 归一化 + 入库（幂等） ----
        valid = []
        id_only: list[str] = []  # 仅有 note_id 无实质字段 → 诊断记录，不入库（防空记录污染）
        for note in notes:
            if not note.get("note_id"):
                result.exceptions.append({"stage": "VALIDATE", "reason": "missing note_id",
                                          "title": note.get("title", "")[:50]})
                continue
            substantive = (note.get("title") or note.get("cover")
                          or note.get("duration") is not None
                          or note.get("publish_time") or note.get("media_type"))
            if not substantive:
                id_only.append(note["note_id"])
                continue
            record = {
                "account_id": "B007",
                "note_id": note["note_id"],
                "note_url": f"https://www.xiaohongshu.com/explore/{note['note_id']}",
                "title": note.get("title", ""),
                "publish_time": note.get("publish_time", ""),
                "content_type": note.get("media_type", ""),
                "duration": note.get("duration"),
                "source_refs": ["OBSERVATION:" + task_id],
            }
            self.adapter.upsert_published_content(record)
            valid.append(note)
        if id_only:
            result.exceptions.append({"stage": "VALIDATE",
                                      "reason": "note_id_only_skipped",
                                      "count": len(id_only),
                                      "note_ids": id_only[:20]})
        result.published_count = len(valid)
        result.note_id_cover = len(valid)
        result.title_cover = sum(1 for n in valid if n.get("title"))
        result.publish_time_cover = sum(1 for n in valid if n.get("publish_time"))
        result.media_type_cover = sum(1 for n in valid if n.get("media_type"))
        result.duration_cover = sum(1 for n in valid if n.get("duration") is not None)
        result.cover_metadata_cover = sum(1 for n in valid if n.get("cover"))

        # ---- Performance（export 未实现 → 0，诚实） ----
        result.performance_count = 0
        result.join = {"note_id_join": 0, "normalized_match": 0,
                       "review_required": 0, "unmatched": 0}
        if export_result.get("status") not in ("SKIPPED", "NOT_IMPLEMENTED_DOM"):
            pass  # export 解析接入点在 V0.3 前按源实现；本轮如实记录

        # ---- 覆盖/异常/产物 ----
        total = max(len(valid), 1)
        coverage = {
            "published_count": result.published_count,
            "note_id_cover": result.note_id_cover,
            "title_cover": result.title_cover,
            "publish_time_cover": result.publish_time_cover,
            "media_type_cover": result.media_type_cover,
            "duration_cover": result.duration_cover,
            "cover_metadata_cover": result.cover_metadata_cover,
            "cover_bytes_cover": result.cover_bytes_cover,
            "performance_count": result.performance_count,
            "join": result.join,
        }
        self._write_artifacts(result, notes, export_result, coverage)
        result.status = "SUCCESS" if result.published_count else "NO_DATA"
        if export_result.get("status") == "NOT_IMPLEMENTED_DOM":
            result.status = "SUCCESS_WITH_LIMITATIONS"
        result.message = f"PublishedContent={result.published_count}"
        return result

    # ---- 产物（§35） ----
    def _write_artifacts(self, result, notes, export_result, coverage) -> None:
        root = self.artifact_root
        def save(name: str, payload: dict) -> None:
            path = root / name
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                            encoding="utf-8")
            result.artifacts[name] = str(path)

        save("B007_CREATOR_ACCOUNT_SNAPSHOT_V1.json", result.account_snapshot)
        save("B007_PUBLISHED_CONTENT_V1.json",
             {"records": notes, "count": len(notes)})
        save("B007_CREATOR_PERFORMANCE_RAW_MANIFEST_V1.json",
             {"export": export_result, "note": "官方导出待 DOM 校准（V0.3 或后续）"})
        save("B007_CREATOR_PERFORMANCE_V1.json", {"records": [], "count": 0})
        save("B007_CREATOR_MEDIA_METADATA_SAFE_V1.json",
             {"records": notes, "safety": "origin+path only, no query/token"})
        save("B007_CREATOR_CONTENT_JOIN_V1.json", result.join)
        save("B007_CREATOR_SYNC_COVERAGE_V1.json", coverage)
        save("B007_CREATOR_SYNC_EXCEPTIONS_V1.json",
             {"exceptions": result.exceptions, "quarantine": result.quarantine})
