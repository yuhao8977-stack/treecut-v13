# -*- coding: utf-8 -*-
"""V0.2 — B007 CREATOR RESPONSE SCHEMA CAPTURE（Schema Audit 证据捕获）。

目标：捕获 galaxy/v2/creator/note/user/posted 的完整响应体（redacted），
逐页（page=0..N）记录 schema：id/title/time/media_type/duration/cover 覆盖率，
并观察分页机制（has_more / 滚动触发）→ 支撑 B007_CREATOR_RESPONSE_SCHEMA_MAP_V1.json。

安全纪律：只保存 note_id/title/publish_time/media_type/duration/cover(origin+path)；
图片 URL 一律 sanitize（去 query/signed 参数）；不保存 cookie/token/xsec/session。

用法：
  set TREECUT_DATA_ROOT=<用户数据根>
  python scripts/b007_schema_capture.py --workspace B007 [--headless] [--url <note_list_url>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from treecut.browser.config import load_config  # noqa: E402
from treecut.browser.main import BrowserRuntime  # noqa: E402
from treecut.browser.creator_sync import (  # noqa: E402
    NOTE_ID_RE, normalize_title, normalize_publish_time, sanitize_url, extract_cover_meta,
)

POSTED_PATH_RE = re.compile(r"/api/galaxy/v2/creator/note/user/posted")
DEFAULT_LIST_URL = "https://creator.xiaohongshu.com/new/note-manager"


def redact_body(body: dict) -> dict:
    """保留业务字段，剥离凭证/签名。返回可入库的 schema 证据。"""
    if not isinstance(body, dict):
        return {"_non_dict": True}
    out = {}
    for k, v in body.items():
        if k in ("code", "success", "msg", "message", "request_id", "cost"):
            out[k] = v
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    out["data_keys"] = sorted(k for k in data.keys() if not k.startswith("_"))
    notes = data.get("notes") or data.get("note_list") or data.get("list") or []
    out["page"] = data.get("page")
    out["has_more"] = data.get("has_more")
    out["hasMore"] = data.get("hasMore")
    out["cursor"] = data.get("cursor")
    safe_notes = []
    for n in notes[:500]:
        if not isinstance(n, dict):
            continue
        nid = n.get("note_id") or n.get("id")
        if not (isinstance(nid, str) and NOTE_ID_RE.match(nid)):
            continue
        vi = n.get("video_info") or n.get("video") or {}
        vi_dur = vi.get("duration") if isinstance(vi, dict) else None
        cover = extract_cover_meta(
            n.get("images_list") or n.get("image_list") or n.get("cover") or n.get("imageInfo"))
        safe_notes.append({
            "note_id": nid,
            "title": normalize_title(n.get("display_title") or n.get("displayTitle") or n.get("title") or n.get("desc")),
            "publish_time": normalize_publish_time(n.get("publish_time") or n.get("time") or n.get("lastUpdateTime")),
            "media_type": str(n.get("type") or n.get("media_type") or ""),
            "duration": vi_dur if vi_dur is not None else (n.get("duration") if isinstance(n.get("duration"), (int, float)) else None),
            "cover": cover,
            "engagement": {
                "view_count": n.get("view_count"),
                "likes": n.get("likes"),
                "comments_count": n.get("comments_count"),
                "shared_count": n.get("shared_count"),
                "collected_count": n.get("collected_count"),
            },
            "_raw_keys": sorted(k for k in n.keys() if not k.startswith("_")),
        })
    out["notes"] = safe_notes
    return out


def capture(runtime: BrowserRuntime, url: str, max_pages: int = 40) -> dict:
    """executor 线程内：挂载完整响应体捕获 → reload → 滚动分页 → 收集。"""
    tab = runtime.ensure_tabs().get("CREATOR")
    captured: list[dict] = []          # 每个 posted 响应一个 redacted 记录
    body_by_page: dict[int, dict] = {}
    order: list[int] = []
    seen_pages: set[int] = set()
    galaxy_responses: list[str] = []   # 诊断：所有 galaxy JSON 端点

    def on_response(response):
        try:
            u = response.url or ""
            ctype = response.headers.get("content-type") or ""
            if "json" not in ctype:
                return
            if "galaxy" in u:
                safe = sanitize_url(u)
                if safe and safe not in galaxy_responses:
                    galaxy_responses.append(safe)
            if not POSTED_PATH_RE.search(u):
                return
            body = response.json()
            m = re.search(r"[?&]page=(\d+)", u)
            page = int(m.group(1)) if m else 0
            red = redact_body(body)
            captured.append({"page": page, "url_safe": sanitize_url(u), "schema": red})
            if page not in seen_pages:
                seen_pages.add(page)
                body_by_page[page] = red
                order.append(page)
        except Exception:
            return

    tab.on("response", on_response)
    try:
        try:
            tab.goto(url, timeout=60000)
        except Exception as e:
            print(f"NAV_FAIL {str(e)[:120]}")
        time.sleep(3)
        try:
            print(f"URL_AFTER_NAV = {sanitize_url(tab.url or '')}")
        except Exception:
            pass
        # 点击「已发布」tab（语义文本，禁固定坐标）
        for _try in range(2):
            try:
                clicked = tab.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('div,span,li,a,button'));"
                    " const t = els.find(e => (e.textContent||'').trim() === '已发布' && e.children.length <= 2);"
                    " if (t) { t.click(); return true; } return false; }")
                print(f"CLICK_PUBLISHED_TAB = {clicked}")
            except Exception as e:
                print(f"CLICK_FAIL {str(e)[:100]}")
                clicked = False
            if clicked:
                time.sleep(2.0)
                break
        # 关键：挂载监听后 reload 触发页面自身 posted 请求（最多重试 3 次）
        posted_fired = False
        for _r in range(3):
            try:
                tab.reload(timeout=60000)
                time.sleep(3)
            except Exception as e:
                print(f"RELOAD_FAIL {str(e)[:120]}")
            if captured:
                posted_fired = True
                print(f"POSTED_FIRED after reload try {_r + 1}: {len(captured)} response(s)")
                break
            # 再点一次已发布（SPA 可能重置）
            try:
                tab.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('div,span,li,a,button'));"
                    " const t = els.find(e => (e.textContent||'').trim() === '已发布' && e.children.length <= 2);"
                    " if (t) { t.click(); return true; } return false; }")
            except Exception:
                pass
            time.sleep(1.0)
        if not posted_fired:
            print("POSTED_NEVER_FIRED")
            print(f"GALAXY_ENDPOINTS_SEEN = {galaxy_responses}")
        # 诊断分页 UI（页码/上一页/下一页 控件）
        try:
            pag = tab.evaluate(
                "() => { const out = [];"
                " const btns = Array.from(document.querySelectorAll('button,a,[class*=page],[class*=pagin]'));"
                " for (const b of btns) { const t=(b.textContent||'').trim();"
                "   if (t && t.length<=6) out.push(t); }"
                " return Array.from(new Set(out)).slice(0,30); }")
            print(f"PAGINATION_UI = {pag}")
        except Exception as e:
            print(f"PAG_DIAG_FAIL {str(e)[:80]}")
        # 滚动分页：滚所有可滚动容器 + 窗口（触发 posted?page=N），有界
        last_total = 0
        no_new_streak = 0
        for it in range(max_pages):
            before = len(captured)
            try:
                tab.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('*'));"
                    " const sc = els.filter(e => e.scrollHeight > e.clientHeight + 100"
                    "   && getComputedStyle(e).overflowY !== 'visible');"
                    " for (const e of sc) e.scrollTop = e.scrollHeight;"
                    " window.scrollTo(0, document.body.scrollHeight); }")
            except Exception:
                pass
            time.sleep(2.2)
            if len(captured) == before:
                # 滚动无新响应 → 尝试点击「下一页」（若 UI 存在）
                try:
                    nxt = tab.evaluate(
                        "() => { const btns = Array.from(document.querySelectorAll('button,a,[class*=btn],[class*=page]'));"
                        " const n = btns.find(b => { const t=(b.textContent||'').trim();"
                        "   return /下一页|next/i.test(t) || /next/i.test(b.className||''); });"
                        " if (n) { n.click(); return true; } return false; }")
                    if nxt:
                        time.sleep(2.5)
                except Exception:
                    pass
            if len(captured) > last_total:
                last_total = len(captured)
                no_new_streak = 0
            else:
                no_new_streak += 1
                if no_new_streak >= 3:   # §13 穷尽规则：连续 3 轮无新增
                    print(f"EXHAUSTED after {it + 1} rounds (no new posted response)")
                    break
        # 兜底：最后一次尝试点击“下一页”按钮
        try:
            tab.evaluate(
                "() => { const btns = Array.from(document.querySelectorAll('button,a,[class*=btn],[class*=page]'));"
                " const nxt = btns.find(b => /下一页|next/i.test((b.textContent||'').trim()) || /next/i.test(b.className||''));"
                " if (nxt) { nxt.click(); return true; } return false; }")
            time.sleep(2.0)
        except Exception:
            pass
    finally:
        tab.remove_listener("response", on_response)

    # 汇总
    all_notes: dict[str, dict] = {}
    page_stats: dict[int, dict] = {}
    for page in order:
        red = body_by_page[page]
        notes = red.get("notes", []) or []
        for n in notes:
            all_notes.setdefault(n["note_id"], {})
            for f in ("title", "publish_time", "media_type", "duration", "cover"):
                if n.get(f):
                    all_notes[n["note_id"]][f] = n[f]
            if n.get("engagement") and any(v is not None for v in n["engagement"].values()):
                all_notes[n["note_id"]]["engagement"] = n["engagement"]
        n = len(notes)
        page_stats[page] = {
            "record_count": n,
            "id": n,
            "title": sum(1 for x in notes if x.get("title")),
            "publish_time": sum(1 for x in notes if x.get("publish_time")),
            "media_type": sum(1 for x in notes if x.get("media_type")),
            "duration": sum(1 for x in notes if x.get("duration") is not None),
            "cover": sum(1 for x in notes if x.get("cover")),
            "has_more": red.get("has_more"),
            "hasMore": red.get("hasMore"),
            "cursor": red.get("cursor"),
            "data_keys": red.get("data_keys", []),
            "sample_raw_keys": (notes[0].get("_raw_keys", []) if notes else []),
        }
    return {
        "captured": captured,
        "page_stats": page_stats,
        "pages_in_order": order,
        "unique_notes": len(all_notes),
        "notes_union": all_notes,
    }


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(prog="b007-schema-capture")
    ap.add_argument("--workspace", default="B007")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--url", default=DEFAULT_LIST_URL)
    ap.add_argument("--max-pages", type=int, default=70)
    args = ap.parse_args(argv)

    config = load_config()
    config.workspace_id = args.workspace
    config.validate()

    runtime = BrowserRuntime(config)
    print("== B007 SCHEMA CAPTURE ==")
    print("profile_dir =", runtime.workspace.workspace_dir)
    binding = runtime.workspace.load_binding()
    print("binding =", bool(binding),
          "creator_xhs_id =", binding.creator_xhs_id if binding else None)
    try:
        runtime.workspace.acquire_lock()
    except RuntimeError as error:
        print(f"PROFILE_LOCKED: {error}")
        return 2
    try:
        runtime.start_browser(headless=args.headless)
        # 等待浏览器就绪
        for _ in range(30):
            try:
                if runtime.ensure_tabs():
                    break
            except Exception:
                pass
            time.sleep(1.0)
        result = runtime._in_browser(lambda: capture(runtime, args.url, args.max_pages), timeout=1800)
        # 落盘：证据 + 汇总
        inbox = Path(runtime.workspace.workspace_dir) / "treecut_inbox" / "creator" / "raw" / "creator"
        ev_dir = inbox / "schema_evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        run_dir = ev_dir / stamp
        run_dir.mkdir(parents=True, exist_ok=True)
        for i, page in enumerate(result["pages_in_order"]):
            f = run_dir / f"posted_page_{page}.json"
            f.write_text(json.dumps(result["captured"][i], ensure_ascii=False, indent=1), encoding="utf-8")
            (run_dir / f"{f.name}.sha256").write_text(
                hashlib.sha256(f.read_bytes()).hexdigest(), encoding="utf-8")
        summary = {
            "run": stamp,
            "url_safe": sanitize_url(args.url),
            "pages_in_order": result["pages_in_order"],
            "unique_notes": result["unique_notes"],
            "page_stats": result["page_stats"],
            "exhaustion_rule": "3 consecutive scroll rounds with no new posted response",
        }
        sf = run_dir / "summary.json"
        sf.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        # 归一化汇总（供后续 union/enrichment）
        nf = run_dir / "notes_union.json"
        nf.write_text(json.dumps(result["notes_union"], ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"EVIDENCE_DIR = {run_dir}")
        print(f"pages = {result['pages_in_order']}")
        print(f"unique_notes = {result['unique_notes']}")
        for page in result["pages_in_order"]:
            print(f"  page {page}: {result['page_stats'][page]}")
        return 0
    finally:
        runtime.close()
        print("SCHEMA_CAPTURE_DONE")


if __name__ == "__main__":
    sys.exit(main())
