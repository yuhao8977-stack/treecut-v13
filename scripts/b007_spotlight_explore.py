# -*- coding: utf-8 -*-
"""V0.3 — Spotlight 多页面探索：计划/创意/数据报表页的 page-owned 端点 + DOM 结构。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

PAGES = [
    ("CAMPAIGN", "https://ad.xiaohongshu.com/aurora/ad/manage/campaign"),
    ("CREATIVE", "https://ad.xiaohongshu.com/aurora/ad/manage/creative"),
    ("REPORT", "https://ad.xiaohongshu.com/aurora/ad/data/overview"),
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
            eps_by_page = {}
            bodies = {}

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = response.headers.get("content-type") or ""
                    if "json" not in ctype:
                        return
                    if not any(h in u for h in ("leona", "edith", "light", "adsa4", "idea", "mcc")):
                        return
                    body = response.json()
                except Exception:
                    return
                s = _safe(u)
                if s not in bodies:
                    bodies[s] = body
                cur = getattr(on_response, "page", "")
                eps_by_page.setdefault(cur, []).append(s)

            tab.on("response", on_response)
            for name, url in PAGES:
                on_response.page = name
                try:
                    tab.goto(url, timeout=60000)
                    time.sleep(7)
                except Exception as e:
                    print(f"{name}: NAV_FAIL {str(e)[:80]}")
                    continue
                # 页面交互：滚动 + 点 tab
                try:
                    tab.evaluate("() => window.scrollTo(0, 400)")
                    time.sleep(1.5)
                    tab.evaluate("() => window.scrollTo(0, 0)")
                    time.sleep(1.5)
                except Exception:
                    pass
                # 页面结构 dump
                try:
                    info = tab.evaluate(
                        """() => {
                          const tabs = [];
                          const els = Array.from(document.querySelectorAll('[class*=tab] span,[class*=tab] div,[class*=tab] li,[class*=menu] span'));
                          for (const e of els) {
                            const t = (e.textContent||'').trim();
                            if (t && t.length <= 8 && !tabs.includes(t)) tabs.push(t);
                          }
                          const rows = document.querySelectorAll('[class*=table] [class*=row], [class*=list] [class*=item]').length;
                          return {tabs: tabs.slice(0,25), rows: rows,
                                  text_len: (document.body.innerText||'').length,
                                  head: (document.body.innerText||'').slice(0,300)};
                        }""")
                    print(f"--- {name} {url} ---")
                    print("  tabs:", json.dumps(info["tabs"], ensure_ascii=True))
                    print("  rows:", info["rows"], "text_len:", info["text_len"])
                except Exception as e:
                    print(f"{name}: dump fail {str(e)[:80]}")
            tab.remove_listener("response", on_response)

            print()
            print("=== ENDPOINTS PER PAGE ===")
            for name, eps in eps_by_page.items():
                uniq = list(dict.fromkeys(eps))
                print(f"--- {name} ({len(uniq)}) ---")
                for e in uniq:
                    print("  ", e)
            print()
            print("=== KEY BODY SHAPES ===")
            for ep, body in bodies.items():
                if any(k in ep.lower() for k in ("campaign", "adgroup", "creative", "promot", "note", "report", "overview", "data")):
                    print(f"--- {ep} ---")
                    print(_shape(body, 0)[:900])
        runtime._in_browser(probe, timeout=600)
        return 0
    finally:
        runtime.close()
        print("EXPLORE_DONE")


def _safe(url: str) -> str:
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
                parts.append(f"{k}={str(v)[:35]}")
        return "{" + ", ".join(parts) + "}"
    if isinstance(node, list):
        if not node:
            return "[]"
        return f"[{len(node)}] {_shape(node[0], depth + 1)[:250]}"
    return str(node)[:35]


if __name__ == "__main__":
    sys.exit(main())
