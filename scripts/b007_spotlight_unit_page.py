# -*- coding: utf-8 -*-
"""V0.3 — Spotlight 单元/创意管理页 URL 探索 + 全部单元捕获。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

URLS = [
    "https://ad.xiaohongshu.com/aurora/ad/manage/unit",
    "https://ad.xiaohongshu.com/aurora/ad/manage/creative",
]

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
            unit_bodies = {}
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
                if s and s not in eps:
                    eps.append(s)
                if "unit/base/list" in s or "creative" in s or "idea/list" in s:
                    unit_bodies.setdefault(s, body)

            tab.on("response", on_response)
            for url in URLS:
                print(f"=== {url} ===")
                try:
                    tab.goto(url, timeout=60000)
                    time.sleep(8)
                except Exception as e:
                    print(f"  NAV_FAIL {str(e)[:80]}")
                    continue
                try:
                    tab.reload(timeout=60000)
                    time.sleep(8)
                except Exception as e:
                    print(f"  RELOAD_FAIL {str(e)[:80]}")
                try:
                    info = tab.evaluate(
                        "() => { return {url: location.href.slice(0,100), title:(document.title||'').slice(0,60),"
                        " text_len:(document.body.innerText||'').length, head:(document.body.innerText||'').slice(0,150)}; }")
                    print("  ", json.dumps(info, ensure_ascii=True))
                except Exception:
                    pass
            tab.remove_listener("response", on_response)

            print()
            print("=== UNIT/CREATIVE BODIES ===")
            for ep, body in unit_bodies.items():
                print(f"--- {ep} ---")
                data = (body.get('data') or {})
                lst = data.get('list') or data.get('dataList') or []
                print(f"  total={data.get('total') or data.get('totalCount')} len={len(lst)}")
                if lst:
                    print("  ", _shape(lst[0], 0)[:800])
            print()
            print("=== ALL EPS ===")
            for e in eps:
                print("  ", e)
        runtime._in_browser(probe, timeout=500)
        return 0
    finally:
        runtime.close()
        print("UNIT_PAGE_DONE")


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
        for k, v in list(node.items())[:14]:
            if isinstance(v, (dict, list)):
                parts.append(f"{k}:{_shape(v, depth + 1)}")
            else:
                parts.append(f"{k}={str(v)[:35]}")
        return "{" + ", ".join(parts) + "}"
    if isinstance(node, list):
        if not node:
            return "[]"
        return f"[{len(node)}] {_shape(node[0], depth + 1)[:250]}"
    return str(node)[:35]


if __name__ == "__main__":
    sys.exit(main())
