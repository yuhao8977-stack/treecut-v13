# -*- coding: utf-8 -*-
"""V0.6 — Creator 数据中心 笔记详情：note_detail_new 响应是否含 video master URL。"""
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

REPORT = "https://ad.xiaohongshu.com/aurora/ad/datareports-basic/note"
CREATOR_NOTE = "https://creator.xiaohongshu.com/new/note-manager"


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
            detail_bodies = []
            video_urls = []

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    s = _safe(u)
                    if "json" in ctype and ("detail" in s or "latest_note" in s or "video" in s):
                        try:
                            body = response.json()
                        except Exception:
                            body = None
                        # 找 video_info.master_url
                        if body:
                            found = []
                            def walk(n):
                                if isinstance(n, dict):
                                    vi = n.get("video_info") or n.get("videoInfo") or {}
                                    if isinstance(vi, dict):
                                        mu = vi.get("master_url") or vi.get("masterUrl") or vi.get("url")
                                        if mu:
                                            p = urlsplit(str(mu))
                                            found.append({"host": p.netloc, "path": p.path[:60],
                                                          "has_query": bool(p.query)})
                                    for v in n.values():
                                        walk(v)
                                elif isinstance(n, list):
                                    for x in n:
                                        walk(x)
                            walk(body)
                            if found:
                                video_urls.extend(found[:3])
                                detail_bodies.append({"safe": s, "video_master": found[:3]})
                except Exception:
                    pass

            tab.on("response", on_response)
            # 数据中心笔记报表（列行可点详情）
            try:
                tab.goto(REPORT, timeout=60000)
                time.sleep(10)
                # 点击一行
                clicked = tab.evaluate(
                    """() => {
                      const rows = Array.from(document.querySelectorAll('[class*=table] [class*=row], [class*=list] [class*=item]'));
                      for (const r of rows) {
                        const b = r.getBoundingClientRect();
                        if (b.width > 200 && b.height > 30) { r.click(); return true; }
                      }
                      return false;
                    }""")
                print("REPORT_ROW_CLICKED =", clicked)
                time.sleep(8)
            except Exception as e:
                print("report fail", str(e)[:80])
            # note-manager 点卡片 + 找预览按钮
            try:
                tab.goto(CREATOR_NOTE, timeout=60000)
                time.sleep(10)
                btns = tab.evaluate(
                    """() => {
                      const out = [];
                      for (const b of document.querySelectorAll('button, [class*=btn], [class*=preview], [class*=detail], [class*=view]')) {
                        const t = (b.textContent||'').trim();
                        if (/预览|查看|详情|数据/.test(t) && t.length <= 8) {
                          const r = b.getBoundingClientRect();
                          if (r.width > 0) out.push({t: t, cls: (b.className||'').toString().slice(0,50)});
                        }
                      }
                      const seen=new Set(); const uniq=[];
                      for (const x of out) { const k=x.t+'|'+x.cls; if (!seen.has(k)) { seen.add(k); uniq.push(x); } }
                      return uniq.slice(0,15);
                    }""")
                print("PREVIEW_BTNS =", json.dumps(btns, ensure_ascii=True))
            except Exception as e:
                print("nm fail", str(e)[:80])
            tab.remove_listener("response", on_response)
            print("DETAIL_BODIES =", json.dumps(detail_bodies[:5], ensure_ascii=True))
            print("VIDEO_URLS =", json.dumps(video_urls[:8], ensure_ascii=True))
        runtime._in_browser(probe, timeout=500)
        return 0
    finally:
        runtime.close()
        print("CREATOR_DETAIL_DONE")


if __name__ == "__main__":
    sys.exit(main())
