# -*- coding: utf-8 -*-
"""V0.3.1 — 窗口语义验证：近7天 vs 近30天，同笔记指标对比 + 请求时间参数。"""
from __future__ import annotations

import json
import re
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
            captures = []

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = response.headers.get("content-type") or ""
                    if "json" not in ctype or "rtb/common/data/report" not in u:
                        return
                    body = response.json()
                    data = body.get("data") or {}
                    dl = data.get("dataList") or []
                    captures.append({
                        "range": getattr(on_response, "cur", "?"),
                        "total": data.get("totalData"),
                        "n": len(dl),
                        "first": (dl[0] if dl else None),
                    })
                except Exception:
                    pass

            tab.on("response", on_response)
            tab.goto(NOTE_REPORT, timeout=60000)
            time.sleep(9)
            on_response.cur = "CURRENT"
            # 打开 picker 点 最近30天
            try:
                tab.locator(".d-daterangepicker-content, .report-date-range-picker").first.click(timeout=8000, force=True)
                time.sleep(2.5)
            except Exception as e:
                print("open fail", str(e)[:80])
            on_response.cur = "LAST_30D"
            try:
                loc = tab.locator("button").filter(has_text="最近30天").first
                if loc.count() > 0:
                    loc.click(timeout=8000, force=True)
                    time.sleep(8)
                    print("CLICK_30D_OK")
            except Exception as e:
                print("30d click fail", str(e)[:100])
            tab.remove_listener("response", on_response)

            # 输入框当前值
            try:
                inputs = tab.evaluate(
                    """() => {
                      const ins = Array.from(document.querySelectorAll('input.d-text'));
                      return ins.map(i => i.value).filter(v => /^\\d{4}-/.test(v));
                    }""")
                print("DATE_INPUTS =", inputs)
            except Exception as e:
                print("inputs fail", str(e)[:60])

            print("CAPTURES =", len(captures))
            for c in captures:
                f = c["first"]
                if f and f.get("dataValueJson"):
                    dvj = json.loads(f["dataValueJson"])
                    print(f"  range={c['range']} n={c['n']} note={f.get('noteId')} fee={dvj.get('fee')} imp={dvj.get('impression')} click={dvj.get('click')} msg={dvj.get('messageConsult')} leads={dvj.get('msgLeadsNum')}")
                else:
                    print(f"  range={c['range']} n={c['n']} (no data)")
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("WINDOW_TEST_DONE")


if __name__ == "__main__":
    sys.exit(main())
