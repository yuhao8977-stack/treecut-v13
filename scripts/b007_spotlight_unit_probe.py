# -*- coding: utf-8 -*-
"""V0.3 — Spotlight 单元/创意指标端点发现：点计划行 → 观察触发的 data 端点 + 分页控件。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

SPOTLIGHT = "https://ad.xiaohongshu.com/aurora/ad/manage/campaign"

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
            eps = []
            bodies = {}

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = response.headers.get("content-type") or ""
                    if "json" not in ctype:
                        return
                    if not any(h in u for h in ("leona", "light", "edith")):
                        return
                    body = response.json()
                except Exception:
                    return
                s = _safe(u)
                if s and s not in eps:
                    eps.append(s)
                if any(k in s for k in ("unit", "creative", "note", "idea", "item")):
                    bodies.setdefault(s, body)

            tab.on("response", on_response)
            tab.goto(SPOTLIGHT, timeout=60000)
            time.sleep(8)
            tab.reload(timeout=60000)
            time.sleep(8)
            # 分页控件 dump
            try:
                pag = tab.evaluate(
                    """() => {
                      const out = [];
                      const els = Array.from(document.querySelectorAll('[class*=page],[class*=pagin],[class*=next],[class*=prev]'));
                      for (const e of els) {
                        const t = (e.textContent||'').trim().slice(0,10);
                        if (t || /next|prev|page/i.test(e.className||'')) out.push({t:t, c:(e.className||'').toString().slice(0,50)});
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out){ const k=x.t+'|'+x.c; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return uniq.slice(0,20);
                    }""")
                print("PAGINATION_UI =", json.dumps(pag, ensure_ascii=True))
            except Exception as e:
                print("pag fail", str(e)[:80])
            # 点击第一个计划行
            try:
                clicked = tab.evaluate(
                    """() => {
                      const rows = Array.from(document.querySelectorAll('[class*=table] [class*=row],[class*=list] [class*=item],[class*=campaign]'));
                      const r = rows.find(x => x.getBoundingClientRect().width > 0 && (x.textContent||'').includes('217346417'));
                      if (r) { r.click(); return true; }
                      return false;
                    }""")
                print("CLICK_CAMPAIGN_ROW =", clicked)
                time.sleep(8)
            except Exception as e:
                print("click row fail", str(e)[:80])
            # 再 dump 一次端点（点击后新触发）
            try:
                tab.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(3)
            except Exception:
                pass
            tab.remove_listener("response", on_response)

            print()
            print("=== NEW ENDPOINTS ===")
            for e in eps:
                print("  ", e)
            print()
            print("=== UNIT/CREATIVE/NOTE BODIES ===")
            for ep, body in bodies.items():
                print(f"--- {ep} ---")
                print(_shape(body, 0)[:700])
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("UNIT_EXPLORE_DONE")


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
        for k, v in list(node.items())[:10]:
            if isinstance(v, (dict, list)):
                parts.append(f"{k}:{_shape(v, depth + 1)}")
            else:
                parts.append(f"{k}={str(v)[:30]}")
        return "{" + ", ".join(parts) + "}"
    if isinstance(node, list):
        if not node:
            return "[]"
        return f"[{len(node)}] {_shape(node[0], depth + 1)[:200]}"
    return str(node)[:30]


if __name__ == "__main__":
    sys.exit(main())
