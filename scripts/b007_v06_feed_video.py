# -*- coding: utf-8 -*-
"""V0.6 — feed 视频卡（自动播放）→ 视频媒体响应捕获验证。"""
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
            ftab = runtime.ensure_tabs().get("FRONTEND")
            media = []

            def on_media(response):
                try:
                    u = response.url or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    s = _safe(u)
                    if "video" in ctype or ".mp4" in u.lower() or ".m3u8" in u.lower() or "sns-video" in s:
                        media.append({"safe": s, "ctype": ctype[:40], "len": response.headers.get("content-length"),
                                      "range": response.headers.get("content-range", "")[:40]})
                except Exception:
                    pass

            ftab.on("response", on_media)
            ftab.goto("https://www.xiaohongshu.com/explore", timeout=60000)
            time.sleep(12)
            # feed 中视频卡：找带 video 元素或播放标记的卡片
            info = ftab.evaluate(
                """() => {
                  const vids = document.querySelectorAll('video');
                  const cards = document.querySelectorAll('section.note-item, [class*=note-item]');
                  return {videos_in_feed: vids.length, cards: cards.length,
                          first_card_has_video: cards.length ? !!cards[0].querySelector('video') : false};
                }""")
            print("FEED =", json.dumps(info, ensure_ascii=True))
            # 点击第一个含 video 的卡片
            clicked = ftab.evaluate(
                """() => {
                  for (const c of document.querySelectorAll('section.note-item, [class*=note-item]')) {
                    const v = c.querySelector('video');
                    const r = c.getBoundingClientRect();
                    if ((v || c.querySelector('[class*=play]')) && r.width > 150) { c.click(); return true; }
                  }
                  return false;
                }""")
            print("CLICKED_VIDEO_CARD =", clicked)
            time.sleep(15)
            # 页面 video 自动播放
            pl = ftab.evaluate("() => { const v=document.querySelector('video'); if (v) { v.muted=true; v.play().catch(()=>{}); return v.currentSrc ? v.currentSrc.slice(0,120) : 'no-src'; } return 'no-video'; }")
            print("PLAYER =", pl)
            time.sleep(12)
            ftab.remove_listener("response", on_media)
            print("MEDIA =", json.dumps(media[:10], ensure_ascii=True))
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("FEED_VIDEO_DONE")


if __name__ == "__main__":
    sys.exit(main())
