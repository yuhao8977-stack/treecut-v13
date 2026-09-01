# -*- coding: utf-8 -*-
"""V0.3.2 debug — 页大小+自定义日期序列的请求/响应/报表状态。"""
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
            reqs = []
            resps = []

            def on_req(r):
                try:
                    if "rtb/common/data/report" in (r.url or ""):
                        reqs.append(r.post_data or "")
                except Exception:
                    pass

            def on_resp(r):
                try:
                    if "rtb/common/data/report" in (r.url or ""):
                        b = r.json()
                        d = b.get("data") or {}
                        resps.append({"page": d.get("page"), "n": len(d.get("dataList") or []),
                                      "totalData": d.get("totalData")})
                except Exception:
                    pass

            tab.on("request", on_req)
            tab.on("response", on_resp)
            tab.goto(NOTE_REPORT, timeout=60000)
            time.sleep(9)
            print("STEP1 after load: reqs=%d resps=%d" % (len(reqs), len(resps)))
            print("  pag:", tab.evaluate("() => { const p=document.querySelector('.d-pagination'); return p ? p.textContent.trim().slice(0,60) : 'none'; }"))
            # 页大小 100
            try:
                tab.locator(".d-select-wrapper").first.click(timeout=8000, force=True)
                time.sleep(2)
                tab.evaluate("""() => { const els = Array.from(document.querySelectorAll('[class*=select-option], [class*=dropdown] li, [class*=dropdown] div'));
                  const t = els.find(e => (e.textContent||'').trim() === '100 条/页'); if (t) { t.click(); return true; } return false; }""")
                time.sleep(6)
                print("STEP2 after size100: reqs=%d resps=%d" % (len(reqs), len(resps)))
                print("  pag:", tab.evaluate("() => { const p=document.querySelector('.d-pagination'); return p ? p.textContent.trim().slice(0,60) : 'none'; }"))
            except Exception as e:
                print("size fail", str(e)[:80])
            # 自定义日期 April
            try:
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
                time.sleep(8)
                print("STEP3 after april fill: reqs=%d resps=%d" % (len(reqs), len(resps)))
                print("  pag:", tab.evaluate("() => { const p=document.querySelector('.d-pagination'); return p ? p.textContent.trim().slice(0,60) : 'none'; }"))
                print("  inputs:", tab.evaluate("() => Array.from(document.querySelectorAll('input.d-text, .d-daterangepicker input')).map(i => i.value).filter(v => /^\\d{4}-/.test(v))"))
            except Exception as e:
                print("date fail", str(e)[:80])
            # 按 Enter / 点别处关闭 picker
            try:
                tab.evaluate("() => { const el=document.activeElement; if (el) el.blur(); document.body.click(); }")
                time.sleep(6)
                print("STEP4 after blur: reqs=%d resps=%d" % (len(reqs), len(resps)))
                print("  pag:", tab.evaluate("() => { const p=document.querySelector('.d-pagination'); return p ? p.textContent.trim().slice(0,60) : 'none'; }"))
            except Exception as e:
                print("blur fail", str(e)[:60])
            print("RESPS:", json.dumps(resps[:6], ensure_ascii=False)[:1200])
            print("REQS sample:", json.dumps(reqs[:3], ensure_ascii=False)[:600])
            tab.remove_listener("request", on_req)
            tab.remove_listener("response", on_resp)
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("DEBUG_DONE")


if __name__ == "__main__":
    sys.exit(main())
