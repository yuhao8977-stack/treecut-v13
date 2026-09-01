# -*- coding: utf-8 -*-
"""V0.6 — 前台 explore 页媒体观察探针：note_id 门 + 视频响应捕获。

样本：682edce4000000001101e878 (38s, B 组, 2025-06)。
观察页面自有的视频媒体响应（content-type video/mp4 或 CDN 视频 URL）。
只记录 sanitized host/path（去 query/sign），不存 xsec_token/signed URL。
"""
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

SAMPLE_NOTE = "682edce4000000001101e878"
NOTE_ID_RE = re.compile(r"([0-9a-fA-F]{24})")


def _safe(url: str) -> str:
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
            tab = runtime.ensure_tabs().get("FRONTEND")
            media_hits = []
            all_eps = []

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    low = u.lower()
                    is_media = ("video" in ctype) or (".mp4" in low) or ("/video" in low) \
                        or ("xhscdn.com" in low and "video" in low)
                    s = _safe(u)
                    if s and s not in all_eps:
                        all_eps.append(s)
                    if is_media:
                        media_hits.append({
                            "url_safe": s,
                            "ctype": ctype[:60],
                            "size": response.headers.get("content-length"),
                            "status": response.status,
                        })
                except Exception:
                    pass

            tab.on("response", on_response)
            url = f"https://www.xiaohongshu.com/explore/{SAMPLE_NOTE}"
            print(f"GOTO {url}")
            try:
                tab.goto(url, timeout=60000)
                time.sleep(8)
            except Exception as e:
                print(f"NAV_FAIL {str(e)[:120]}")
            print("URL_AFTER =", tab.url[:160])
            # note_id 门
            m = NOTE_ID_RE.search(tab.url or "")
            print("URL_NOTE_ID =", m.group(1) if m else None)
            # 触发播放：点视频元素
            try:
                clicked = tab.evaluate(
                    """() => {
                      const v = document.querySelector('video');
                      if (v) { v.muted = true; v.play().catch(()=>{}); return true; }
                      const els = Array.from(document.querySelectorAll('[class*=video], [class*=player], [class*=cover]'));
                      const t = els.find(e => e.getBoundingClientRect().width > 50 && e.getBoundingClientRect().height > 50);
                      if (t) { t.click(); return true; }
                      return false;
                    }""")
                print("PLAY_TRIGGER =", clicked)
                time.sleep(8)
            except Exception as e:
                print(f"play fail {str(e)[:100]}")
            # reload 再观察一次
            try:
                tab.reload(timeout=60000)
                time.sleep(8)
                tab.evaluate("() => { const v=document.querySelector('video'); if (v) { v.muted=true; v.play().catch(()=>{}); } }")
                time.sleep(6)
            except Exception as e:
                print(f"reload fail {str(e)[:80]}")
            tab.remove_listener("response", on_response)

            print("MEDIA_HITS =", json.dumps(media_hits, ensure_ascii=True))
            print()
            print("VIDEO-ish EPS =", json.dumps([e for e in all_eps if "video" in e.lower() or "media" in e.lower()][:20], ensure_ascii=True))
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("MEDIA_PROBE_DONE")


if __name__ == "__main__":
    sys.exit(main())
