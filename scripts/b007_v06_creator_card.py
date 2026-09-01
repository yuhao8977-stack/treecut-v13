# -*- coding: utf-8 -*-
"""V0.6 — Creator note-manager 卡片结构 + 点击 → 详情/视频加载路径。"""
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
            detail = []

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    s = _safe(u)
                    if "video" in ctype or ".mp4" in u.lower() or "sns-video" in s or ".m3u8" in u.lower():
                        media.append({"safe": s, "ctype": ctype[:40], "len": response.headers.get("content-length")})
                    if "detail" in s or "latest_note" in s or "video" in s:
                        detail.append(s)
                except Exception:
                    pass

            tab.on("response", on_response)
            tab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(10)
            # dump 卡片 href 结构
            cards = tab.evaluate(
                """() => {
                  const out = [];
                  for (const a of document.querySelectorAll('a[href]')) {
                    const href = a.getAttribute('href') || '';
                    if (/(\\d{24})/.test(href) && /note|edit|preview|detail/.test(href)) out.push(href.slice(0,150));
                  }
                  const seen=new Set(); const uniq=[];
                  for (const x of out) { if (!seen.has(x)) { seen.add(x); uniq.push(x); } }
                  return {count: uniq.length, sample: uniq.slice(0,6)};
                }""")
            print("CARD_HREFS =", json.dumps(cards, ensure_ascii=True))
            # 点击第一个可见 note 卡片（含 24hex 的容器）
            clicked = tab.evaluate(
                """() => {
                  const els = Array.from(document.querySelectorAll('[class*=note-card], [class*=card]'));
                  for (const e of els) {
                    const r = e.getBoundingClientRect();
                    if (r.width > 200 && r.height > 100) { e.click(); return true; }
                  }
                  return false;
                }""")
            print("CLICKED_CARD =", clicked)
            time.sleep(10)
            print("URL_AFTER =", tab.url[:200])
            # 触发播放
            try:
                tab.evaluate("() => { const v=document.querySelector('video'); if (v) { v.muted=true; v.play().catch(()=>{}); return true; } return false; }")
                time.sleep(8)
            except Exception:
                pass
            tab.remove_listener("response", on_response)
            print("MEDIA =", json.dumps(media[:8], ensure_ascii=True))
            print("DETAIL_EPS =", json.dumps(detail[:10], ensure_ascii=True))
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("CREATOR_CARD_DONE")


if __name__ == "__main__":
    sys.exit(main())
