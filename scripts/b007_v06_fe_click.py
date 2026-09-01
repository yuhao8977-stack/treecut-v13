# -*- coding: utf-8 -*-
"""V0.6 — 前台真实点击 feed 卡片（SPA 注入 xsec）→ 笔记加载 → 观察视频媒体。"""
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
                        media.append({"safe": s, "ctype": ctype[:40],
                                      "len": response.headers.get("content-length")})
                except Exception:
                    pass

            ftab.on("response", on_media)
            ftab.goto("https://www.xiaohongshu.com/explore", timeout=60000)
            time.sleep(10)
            # 真实点击第一个可见 feed note 卡片
            try:
                clicked = ftab.evaluate(
                    """() => {
                      const links = Array.from(document.querySelectorAll('a[href*="/explore/"]'));
                      for (const a of links) {
                        const r = a.getBoundingClientRect();
                        if (r.width > 50 && r.height > 50) { a.click(); return a.getAttribute('href'); }
                      }
                      return null;
                    }""")
                print("CLICKED_CARD =", clicked)
                time.sleep(12)
            except Exception as e:
                print("card click fail", str(e)[:100])
            print("URL =", ftab.url[:180])
            m = re.search(r"/(?:explore|discovery/item)/([0-9a-fA-F]{24})", ftab.url or "")
            print("NOTE_ID =", m.group(1) if m else None)
            # 触发播放
            try:
                ftab.evaluate("() => { const v=document.querySelector('video'); if (v) { v.muted=true; v.play().catch(()=>{}); return true; } return false; }")
                time.sleep(10)
            except Exception:
                pass
            ftab.remove_listener("response", on_media)
            print("MEDIA =", json.dumps(media[:8], ensure_ascii=True))
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("FE_CLICK_DONE")


if __name__ == "__main__":
    sys.exit(main())
