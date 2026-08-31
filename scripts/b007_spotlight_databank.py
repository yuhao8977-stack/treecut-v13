# -*- coding: utf-8 -*-
"""V0.3.1 — Playwright 真实点击「数据」nav → dump 报表页（子 tab + 日期控件 + 端点）。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

HOME = "https://ad.xiaohongshu.com/aurora/ad/manage/campaign"

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

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = response.headers.get("content-type") or ""
                    if "json" not in ctype:
                        return
                    s = _safe(u)
                    if any(h in s for h in ("leona", "light", "edith", "rtb")):
                        if s not in eps:
                            eps.append(s)
                except Exception:
                    pass

            tab.on("response", on_response)
            tab.goto(HOME, timeout=60000)
            time.sleep(8)
            # Playwright 真实点击 数据 nav
            try:
                loc = tab.locator(".topbar-new-nav-item-databank")
                print("DATA_NAV_COUNT =", loc.count())
                if loc.count() > 0:
                    loc.first.click(timeout=8000, force=True)
                    time.sleep(6)
            except Exception as e:
                print("data nav click fail", str(e)[:120])
            print("URL_AFTER =", tab.url[:150])
            # dump 页面 tab + 日期
            try:
                info = tab.evaluate(
                    """() => {
                      const tabs = [];
                      const els = Array.from(document.querySelectorAll('[class*=tab] span,[class*=tab] div,[class*=menu] span,[class*=report] span'));
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (t && t.length <= 10 && !tabs.includes(t)) tabs.push(t);
                      }
                      const dateEls = [];
                      const re = /2026-\\d{2}-\\d{2}|今日|昨天|近\\d+天|全部时间|自定义/;
                      const all = Array.from(document.querySelectorAll('*'));
                      for (const e of all) {
                        const t = (e.textContent||'').trim();
                        if (re.test(t) && t.length <= 30) {
                          const r = e.getBoundingClientRect();
                          if (r.width > 0 && r.height > 0) dateEls.push({t: t.slice(0,28), cls: (e.className||'').toString().slice(0,50)});
                        }
                      }
                      const du=[]; const ds=new Set();
                      for (const x of dateEls){ const k=x.t+'|'+x.cls; if(!ds.has(k)){ds.add(k);du.push(x);} }
                      return {url: location.href.slice(0,120), title:(document.title||'').slice(0,50),
                              tabs: tabs.slice(0,25), dates: du.slice(0,20),
                              text_len:(document.body.innerText||'').length};
                    }""")
                print("PAGE_INFO =", json.dumps(info, ensure_ascii=True)[:2000])
            except Exception as e:
                print("dump fail", str(e)[:80])
            tab.remove_listener("response", on_response)
            print()
            print("NEW_EPS =", json.dumps(eps[:40], ensure_ascii=True))
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("DATA_BANK_DONE")


def _safe(url):
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


if __name__ == "__main__":
    sys.exit(main())
