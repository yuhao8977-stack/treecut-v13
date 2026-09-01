# -*- coding: utf-8 -*-
"""V0.6 — 最终前台验证：找带时长角标的视频卡 → 点击 → 笔记页 video 元素 + 媒体响应。"""
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
                        media.append({"safe": s, "ctype": ctype[:40], "len": response.headers.get("content-length")})
                except Exception:
                    pass

            ftab.on("response", on_media)
            ftab.goto("https://www.xiaohongshu.com/explore", timeout=60000)
            time.sleep(12)
            # 找带时长角标（mm:ss）的卡片
            badge = None
            for _ in range(15):
                badge = ftab.evaluate(
                    """() => {
                      const cards = Array.from(document.querySelectorAll('section.note-item, [class*=note-item], a[href*="/explore/"]'));
                      for (const c of cards) {
                        const t = (c.textContent || '');
                        const m = t.match(/(\\d{1,2}):(\\d{2})/);
                        const r = c.getBoundingClientRect();
                        if (m && r.width > 100) {
                          const link = c.querySelector('a[href*="/explore/"]') || c;
                          link.click();
                          return {badge: m[0], href: (link.getAttribute && link.getAttribute('href') || '').slice(0,120)};
                        }
                      }
                      window.scrollBy(0, 900);
                      return null;
                    }""")
                if badge:
                    break
                time.sleep(2)
            print("VIDEO_CARD =", json.dumps(badge, ensure_ascii=True))
            time.sleep(12)
            # 笔记页 video 检查
            info = ftab.evaluate(
                """() => {
                  const v = document.querySelector('video');
                  return {url: location.href.slice(0,140), has_video: !!v,
                          video_src: v && v.currentSrc ? v.currentSrc.slice(0,100) : null,
                          text_len: (document.body.innerText||'').length};
                }""")
            print("NOTE_PAGE =", json.dumps(info, ensure_ascii=True))
            # 点击播放按钮（若 video 存在）
            ftab.evaluate("""() => {
                const v = document.querySelector('video');
                if (v) { v.muted = true; v.play().catch(()=>{}); }
                const plays = Array.from(document.querySelectorAll('[class*=play], [class*=player]'));
                for (const p of plays) { const r = p.getBoundingClientRect(); if (r.width > 30 && r.height > 30) { p.click(); break; } }
              }""")
            time.sleep(15)
            ftab.remove_listener("response", on_media)
            print("MEDIA =", json.dumps(media[:8], ensure_ascii=True))
        runtime._in_browser(probe, timeout=500)
        return 0
    finally:
        runtime.close()
        print("FINAL_FE_PROBE_DONE")


if __name__ == "__main__":
    sys.exit(main())
