# -*- coding: utf-8 -*-
"""V0.6 — 页面自有 xsec 导航测试：creator posted → xsec → frontend explore 加载媒体。

xsec 来自页面自身响应（posted 列表，页面用于笔记链接的数据），仅用于页面正常导航。
不持久化 xsec；观察前台媒体响应。
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

NOTE_MANAGER = "https://creator.xiaohongshu.com/new/note-manager"
SAMPLE = "69f9a0ac000000003701d937"
TEST_WITH_XSEC = "6a92b9e8000000002501a357"


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
            ctab = runtime.ensure_tabs().get("CREATOR")
            ftab = runtime.ensure_tabs().get("FRONTEND")
            xsec = {}

            def on_response(response):
                try:
                    u = response.url or ""
                    if "note/user/posted" not in u:
                        return
                    body = response.json()
                    for nt in (body.get("data") or {}).get("notes", []) or []:
                        nid = nt.get("id") or nt.get("note_id")
                        if nid and nt.get("xsec_token"):
                            xsec[nid] = {"token": nt["xsec_token"], "source": nt.get("xsec_source", "")}
                except Exception:
                    pass

            ctab.on("response", on_response)
            ctab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(10)
            for _r in range(3):
                ctab.reload(timeout=60000)
                time.sleep(6)
                if xsec:
                    break
                # 点已发布 tab 再 reload
                try:
                    ctab.evaluate(
                        "() => { const els = Array.from(document.querySelectorAll('div,span,li,a,button'));"
                        " const t = els.find(e => (e.textContent||'').trim() === '已发布' && e.children.length <= 2);"
                        " if (t) { t.click(); return true; } return false; }")
                    time.sleep(3)
                except Exception:
                    pass
            ctab.remove_listener("response", on_response)
            print("xsec captured count:", len(xsec))
            target = SAMPLE if SAMPLE in xsec else (TEST_WITH_XSEC if TEST_WITH_XSEC in xsec else None)
            print("target with xsec:", target)
            if target is None:
                print("xsec keys sample:", list(xsec.keys())[:5])
                return
            xs = xsec[target]
            # 前台导航（页面自有 xsec 参数）
            url = f"https://www.xiaohongshu.com/explore/{SAMPLE}?xsec_token={xs['token']}&xsec_source={xs['source']}"
            media = []

            def on_media(response):
                try:
                    u = response.url or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    s = _safe(u)
                    if "video" in ctype or ".mp4" in u.lower() or ".m3u8" in u.lower() or "sns-video" in s:
                        media.append({"safe": s, "ctype": ctype[:40],
                                      "len": response.headers.get("content-length"),
                                      "range": response.headers.get("content-range", "")[:40]})
                except Exception:
                    pass

            ftab.on("response", on_media)
            try:
                ftab.goto(url, timeout=60000)
                time.sleep(8)
            except Exception as e:
                print(f"FE_NAV_FAIL {str(e)[:100]}")
            print("FE_URL =", ftab.url[:160])
            m = re.search(r"explore/([0-9a-fA-F]{24})", ftab.url or "")
            print("FE_NOTE_ID =", m.group(1) if m else None)
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
        print("XSEC_NAV_DONE")


if __name__ == "__main__":
    sys.exit(main())
