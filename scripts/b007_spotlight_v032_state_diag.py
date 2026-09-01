# -*- coding: utf-8 -*-
"""V0.3.2 — 分页状态逐轮诊断：April 页 1，dump icons/active/disabled。"""
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
            tab.goto(NOTE_REPORT, timeout=60000)
            time.sleep(9)
            # 设 100/页 + April
            tab.locator(".d-select-wrapper").first.click(timeout=8000, force=True)
            time.sleep(2)
            tab.evaluate("""() => { const els = Array.from(document.querySelectorAll('[class*=select-option], [class*=dropdown] li, [class*=dropdown] div'));
              const t = els.find(e => (e.textContent||'').trim() === '100 条/页'); if (t) { t.click(); return true; } return false; }""")
            time.sleep(4)
            tab.keyboard.press("Escape")
            time.sleep(1)
            tab.locator(".d-daterangepicker-content, .report-date-range-picker").first.click(timeout=8000, force=True)
            time.sleep(2.5)
            tab.evaluate("""(d) => {
              const ins = Array.from(document.querySelectorAll('.d-daterangepicker input.d-text, .d-daterangepicker-input-filter input'));
              if (ins.length >= 2) {
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(ins[0], d.start); ins[0].dispatchEvent(new Event('input', {bubbles:true}));
                setter.call(ins[1], d.end); ins[1].dispatchEvent(new Event('input', {bubbles:true}));
                return true; }
              return false; }""", {"start": "2026-04-01", "end": "2026-04-30"})
            time.sleep(3)
            tab.keyboard.press("Enter")
            time.sleep(2)
            try:
                tab.evaluate("() => { const el=document.activeElement; if (el) el.blur(); document.body.click(); }")
            except Exception:
                pass
            time.sleep(5)
            print("pag:", tab.evaluate("() => { const p=document.querySelector('.d-pagination'); return p ? p.textContent.trim().slice(0,80) : 'none'; }"))
            # dump 分页元素详情
            det = tab.evaluate(
                """() => {
                  const pages = Array.from(document.querySelectorAll('.d-pagination-page'));
                  return pages.map(p => ({t: (p.textContent||'').trim().slice(0,6),
                    disabled: p.hasAttribute('disabled') || /disabled/.test(p.className||''),
                    hasIcon: !!p.querySelector('svg, .d-icon'),
                    cls: (p.className||'').toString().slice(0,45)}));
                }""")
            print("PAG_ITEMS =", json.dumps(det, ensure_ascii=True))
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("PAG_STATE_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
