# -*- coding: utf-8 -*-
"""V0.3.1 — 探索「笔记报表」tab：页面自有响应中是否有 note 级 paid metrics。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

REPORT_URL = "https://ad.xiaohongshu.com/aurora/ad/datareports-basic/campaign"

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
            tab = runtime.ensure_tabs().get("SPOTLIGHT")
            bodies = {}
            eps = []

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = response.headers.get("content-type") or ""
                    if "json" not in ctype:
                        return
                    body = response.json()
                except Exception:
                    return
                s = _safe(u)
                if s not in eps:
                    eps.append(s)
                if any(k in s for k in ("report", "data/list", "note", "idea", "creative")):
                    bodies.setdefault(s, body)

            tab.on("response", on_response)
            tab.goto(REPORT_URL, timeout=60000)
            time.sleep(8)
            # 点击「笔记报表」tab
            clicked = tab.evaluate(
                """() => {
                  const els = Array.from(document.querySelectorAll('div,span,li,a,[class*=tab]'));
                  const t = els.find(e => (e.textContent||'').trim() === '笔记报表' && e.children.length <= 1);
                  if (t) { t.click(); return true; }
                  return false;
                }""")
            print("CLICK_NOTE_REPORT =", clicked)
            time.sleep(6)
            # 兜底 Playwright 真实点击
            if not clicked:
                try:
                    loc = tab.locator("[class*=tab]").filter(has_text="笔记报表").first
                    if loc.count() > 0:
                        loc.click(timeout=8000, force=True)
                        time.sleep(6)
                        print("PW_CLICK_NOTE_REPORT_OK")
                except Exception as e:
                    print("pw click fail", str(e)[:100])
            tab.remove_listener("response", on_response)

            print("URL =", tab.url[:140])
            print()
            print("=== NOTE/REPORT BODIES ===")
            for ep, body in list(bodies.items())[:15]:
                data = body.get('data')
                if isinstance(data, dict):
                    dl = data.get('dataList') or data.get('list') or []
                    print(f"--- {ep} | total={data.get('totalCount') or data.get('total')} len={len(dl)}")
                    if dl:
                        print("   ", _shape(dl[0], 0)[:500])
                elif isinstance(data, list):
                    print(f"--- {ep} | LIST len={len(data)}")
                    if data:
                        print("   ", _shape(data[0], 0)[:400])
                else:
                    print(f"--- {ep} | {type(data).__name__}")
            print()
            print("=== ALL EPS ===")
            for e in eps:
                print("  ", e)
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("NOTE_REPORT_DONE")


def _safe(url):
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


def _shape(node, depth=0):
    if depth > 3:
        return "..."
    if isinstance(node, dict):
        parts = []
        for k, v in list(node.items())[:12]:
            if isinstance(v, (dict, list)):
                parts.append(f"{k}:{_shape(v, depth + 1)}")
            else:
                parts.append(f"{k}={str(v)[:30]}")
        return "{" + ", ".join(parts) + "}"
    if isinstance(node, list):
        if not node:
            return "[]"
        return f"[{len(node)}] {_shape(node[0], depth + 1)[:220]}"
    return str(node)[:30]


if __name__ == "__main__":
    sys.exit(main())
