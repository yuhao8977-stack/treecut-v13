# -*- coding: utf-8 -*-
"""V0.6 — Creator note-manager → 打开笔记 → 观察 note_detail + 视频媒体响应。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

NOTE_MANAGER = "https://creator.xiaohongshu.com/new/note-manager"
SAMPLE = "69f9a0ac000000003701d937"  # C 组 2026-05


def _safe(url):
    try:
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    config = load_config()
    config.workspace_id = "B007"
    config.validate()
    runtime = BrowserRuntime(config)
    try:
        runtime.workspace.acquire_lock()
    except RuntimeError as error:
        print(f"PROFILE_LOCKED: {error}")
        return 2
    try:
        runtime.start_browser(headless=False)

        def probe():
            tab = runtime.ensure_tabs().get("CREATOR")
            media = []
            note_detail = []
            eps = []

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    body = None
                    if "json" in ctype:
                        try:
                            body = response.json()
                        except Exception:
                            body = None
                    s = _safe(u)
                    if s and s not in eps:
                        eps.append(s)
                    if "video" in ctype or ".mp4" in u.lower() or "video" in s.lower() or "media" in s.lower():
                        media.append({"safe": s, "ctype": ctype[:40],
                                      "len": response.headers.get("content-length")})
                    if "note_detail" in s or "latest_note" in s:
                        note_detail.append({"safe": s, "has_body": body is not None})
                except Exception:
                    pass

            tab.on("response", on_response)
            tab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(8)
            tab.reload(timeout=60000)
            time.sleep(8)
            # 点已发布 tab + 找目标 note 卡片
            clicked = tab.evaluate(
                """(nid) => {
                  const els = Array.from(document.querySelectorAll('div,span,li,a'));
                  const t = els.find(e => (e.textContent||'').trim() === '已发布' && e.children.length <= 2);
                  if (t) t.click();
                  return true;
                }""", SAMPLE)
            time.sleep(3)
            # 找 note 卡片（含目标 id 的链接/元素）
            found = tab.evaluate(
                """(nid) => {
                  const els = Array.from(document.querySelectorAll('*'));
                  const e = els.find(x => (x.textContent||'').includes(nid) && x.getBoundingClientRect().width > 100);
                  if (e) { e.scrollIntoView(); e.click(); return true; }
                  return false;
                }""", SAMPLE)
            print("FOUND_NOTE_CARD =", found)
            time.sleep(8)
            tab.remove_listener("response", on_response)
            print("URL_AFTER =", tab.url[:160])
            print("NOTE_DETAIL_HITS =", json.dumps(note_detail, ensure_ascii=True))
            print("MEDIA_HITS =", json.dumps(media[:10], ensure_ascii=True))
            print("EPS (media/note) =", json.dumps([e for e in eps if "video" in e.lower() or "media" in e.lower() or "detail" in e.lower() or "note" in e.lower()][:20], ensure_ascii=True))
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("CREATOR_MEDIA_PROBE_DONE")


if __name__ == "__main__":
    sys.exit(main())
