# -*- coding: utf-8 -*-
"""V0.6 — Creator note-manager 卡片点击后：检查抽屉/模态/视频元素/预览。"""
from __future__ import annotations

import json
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
            windows_before = None

            def on_media(response):
                try:
                    u = response.url or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    s = _safe(u)
                    if "video" in ctype or ".mp4" in u.lower() or ".m3u8" in u.lower() or "sns-video" in s:
                        media.append({"safe": s, "ctype": ctype[:40], "len": response.headers.get("content-length")})
                except Exception:
                    pass

            tab.on("response", on_media)
            tab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(10)
            tab.reload(timeout=60000)
            time.sleep(8)
            # 点卡片（含可见 note 卡）
            clicked = tab.evaluate(
                """() => {
                  const cards = Array.from(document.querySelectorAll('[class*=note-card], [class*=card]'));
                  for (const c of cards) {
                    const r = c.getBoundingClientRect();
                    if (r.width > 150 && r.height > 100) { c.click(); return true; }
                  }
                  return false;
                }""")
            print("CLICKED =", clicked)
            time.sleep(8)
            # dump 模态/抽屉/video
            info = tab.evaluate(
                """() => {
                  const v = document.querySelector('video');
                  const modals = Array.from(document.querySelectorAll('[class*=modal], [class*=drawer], [class*=dialog], [class*=popup], [class*=preview]'))
                    .filter(e => e.getBoundingClientRect().width > 100).length;
                  const iframes = Array.from(document.querySelectorAll('iframe')).map(f => (f.src||'').slice(0,100));
                  const tabs = runtime_ctx_tabs();
                  return {has_video: !!v, modals: modals, iframes: iframes.slice(0,4),
                          text_len: (document.body.innerText||'').length,
                          head: (document.body.innerText||'').slice(0,120)};
                  function runtime_ctx_tabs(){ return []; }
                }""")
            print("AFTER_CLICK =", json.dumps(info, ensure_ascii=True))
            # 触发预览播放
            tab.evaluate(
                """() => {
                  const v = document.querySelector('video');
                  if (v) { v.muted = true; v.play().catch(()=>{}); }
                  const els = Array.from(document.querySelectorAll('[class*=play], [class*=preview], [class*=video]'));
                  for (const e of els) { const r = e.getBoundingClientRect(); if (r.width > 30 && r.height > 30) { e.click(); break; } }
                }""")
            time.sleep(10)
            tab.remove_listener("response", on_media)
            print("MEDIA =", json.dumps(media[:8], ensure_ascii=True))
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("CREATOR_MODAL_DONE")


if __name__ == "__main__":
    sys.exit(main())
