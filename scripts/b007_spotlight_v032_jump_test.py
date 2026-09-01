# -*- coding: utf-8 -*-
"""V0.3.2 — 验证「跳至页」输入：填页码+Enter → 报表跳转+响应。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

NOTE_REPORT = "https://ad.xiaohongshu.com/aurora/ad/datareports-basic/note"

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
            resps = []

            def on_resp(r):
                try:
                    if "rtb/common/data/report" in (r.url or ""):
                        d = (r.json().get("data") or {})
                        resps.append((d.get("page") or {}).get("pageIndex"))
                except Exception:
                    pass

            tab.on("response", on_resp)
            tab.goto(NOTE_REPORT, timeout=60000)
            time.sleep(9)
            print("pag:", tab.evaluate("() => { const p=document.querySelector('.d-pagination'); return p ? p.textContent.trim().slice(0,70) : 'none'; }"))
            # 找跳至页输入
            jump_info = tab.evaluate(
                """() => {
                  const div = Array.from(document.querySelectorAll('div')).find(d => /跳至页/.test(d.textContent||'') && d.children.length <= 3);
                  if (!div) return null;
                  const input = div.querySelector('input');
                  return input ? {cls: input.className} : null;
                }""")
            print("JUMP_INFO =", jump_info)
            # 填页码 5 + Enter
            try:
                r = tab.evaluate(
                    """() => {
                      const div = Array.from(document.querySelectorAll('div')).find(d => /跳至页/.test(d.textContent||'') && d.children.length <= 3);
                      if (!div) return false;
                      const input = div.querySelector('input');
                      if (!input) return false;
                      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                      setter.call(input, '5');
                      input.dispatchEvent(new Event('input', {bubbles:true}));
                      input.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true}));
                      input.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', bubbles:true}));
                      return true;
                    }""")
                print("JUMP_FILL =", r)
                time.sleep(5)
                print("resps:", resps)
                print("pag after:", tab.evaluate("() => { const p=document.querySelector('.d-pagination'); return p ? p.textContent.trim().slice(0,70) : 'none'; }"))
                # 当前 active 页码
                act = tab.evaluate(
                    """() => {
                      const pages = Array.from(document.querySelectorAll('.d-pagination-page'));
                      for (const p of pages) {
                        if (/bg-prima|active|current/i.test(p.className||'')) {
                          const sp = p.querySelector('span'); return sp ? (sp.textContent||'').trim() : '';
                        }
                      }
                      return 'none';
                    }""")
                print("ACTIVE_PAGE =", act)
            except Exception as e:
                print("jump fail", str(e)[:100])
            tab.remove_listener("response", on_resp)
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("JUMP_TEST_DONE")


if __name__ == "__main__":
    sys.exit(main())
