# -*- coding: utf-8 -*-
"""V0.3.2 — 测试自定义日期范围：填 2026-04-01 ~ 2026-04-30 → 确认 → 报表更新。"""
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
            # 打开日期选择器
            try:
                tab.locator(".d-daterangepicker-content, .report-date-range-picker").first.click(timeout=8000, force=True)
                time.sleep(2.5)
                print("PICKER_OPENED")
            except Exception as e:
                print("open fail", str(e)[:80])
            # 直接填两个日期输入框（start/end）
            try:
                filled = tab.evaluate(
                    """(d) => {
                      const ins = Array.from(document.querySelectorAll('.d-daterangepicker input.d-text, .d-daterangepicker-input-filter input'));
                      if (ins.length >= 2) {
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        setter.call(ins[0], d.start); ins[0].dispatchEvent(new Event('input', {bubbles:true}));
                        setter.call(ins[1], d.end); ins[1].dispatchEvent(new Event('input', {bubbles:true}));
                        return true;
                      }
                      return false;
                    }""", {"start": "2026-04-01", "end": "2026-04-30"})
                print("FILL_DATES =", filled)
                time.sleep(2)
            except Exception as e:
                print("fill fail", str(e)[:80])
            # 点确定
            try:
                ok = tab.evaluate(
                    """() => {
                      const els = Array.from(document.querySelectorAll('button,[class*=confirm],[class*=ok],[class*=submit]'));
                      const b = els.find(e => /确定|完成|查询/.test((e.textContent||'').trim()) && e.getBoundingClientRect().width > 0);
                      if (b) { b.click(); return true; }
                      return false;
                    }""")
                print("CLICK_CONFIRM =", ok)
                time.sleep(6)
            except Exception as e:
                print("confirm fail", str(e)[:80])
            # 验证输入框当前值 + 报表条数
            try:
                inputs = tab.evaluate(
                    """() => {
                      const ins = Array.from(document.querySelectorAll('input.d-text, .d-daterangepicker input'));
                      return ins.map(i => i.value).filter(v => /^\\d{4}-/.test(v));
                    }""")
                print("DATE_INPUTS =", inputs)
            except Exception:
                pass
            try:
                pag = tab.evaluate("() => { const p=document.querySelector('.d-pagination'); return p ? (p.textContent||'').trim().slice(0,60) : 'none'; }")
                print("PAG_TEXT =", pag)
            except Exception:
                pass
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("CUSTOM_DATE_TEST_DONE")


if __name__ == "__main__":
    sys.exit(main())
