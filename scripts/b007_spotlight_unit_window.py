# -*- coding: utf-8 -*-
"""V0.3.1 — 单元页窗口捕获：为 7D/14D/30D 各抓 unit/search 全分页（window 作用域）。"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

UNIT_PAGE = "https://ad.xiaohongshu.com/aurora/ad/manage/unit"
WINDOWS = [("LAST_7D", "最近7天"), ("LAST_14D", "最近14天"), ("LAST_30D", "最近30天")]


def _safe(url):
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


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
        base = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                    r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\spotlight_unit_v031")
        results = {}

        def run_all():
            tab = runtime.ensure_tabs().get("SPOTLIGHT")
            for wkey, preset in WINDOWS:
                out_dir = base / time.strftime("%Y%m%d_%H%M%S") / wkey
                out_dir.mkdir(parents=True, exist_ok=True)
                print(f"=== WINDOW {wkey} ===")
                tab.goto(UNIT_PAGE, timeout=60000)
                time.sleep(7)
                # 设置窗口
                try:
                    tab.locator(".d-daterangepicker-content, .report-date-range-picker").first.click(timeout=8000, force=True)
                    time.sleep(2.5)
                    loc = tab.locator("button").filter(has_text=preset).first
                    if loc.count() > 0:
                        loc.click(timeout=8000, force=True)
                        time.sleep(6)
                except Exception as e:
                    print(f"  window set fail: {str(e)[:80]}")
                # 捕获 unit/search + extra 全分页
                bodies = {}
                max_page = {}

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
                    if not any(w in s for w in ("rtb/unit/search", "rtb/unit/extra/list")):
                        return
                    data = body.get("data")
                    pn = None
                    if isinstance(data, dict):
                        pn = data.get("pageNum")
                    key = s
                    if pn is not None:
                        if f"{s}#{pn}" in bodies:
                            return
                        key = f"{s}#p{pn}"
                        max_page[s] = max(max_page.get(s, 0), pn)
                    else:
                        n = 1
                        while key in bodies:
                            key = f"{s}#{n}"
                            n += 1
                    bodies[key] = body

                tab.on("response", on_response)
                no_new = 0
                for it in range(40):
                    before = len(bodies)
                    try:
                        tab.evaluate("() => { const els = Array.from(document.querySelectorAll('*'));"
                                     " const sc = els.filter(e => e.scrollHeight > e.clientHeight + 100"
                                     "   && getComputedStyle(e).overflowY !== 'visible');"
                                     " for (const e of sc) e.scrollTop = e.scrollHeight;"
                                     " window.scrollTo(0, document.body.scrollHeight); }")
                    except Exception:
                        pass
                    time.sleep(2.0)
                    if len(bodies) == before:
                        target = (max(max_page.values()) + 1) if max_page else 2
                        try:
                            loc2 = tab.locator(".d-pagination-page, [class*=pagination-page]").filter(has_text=str(target)).first
                            if loc2.count() > 0:
                                loc2.click(timeout=8000, force=True)
                                for _w in range(10):
                                    time.sleep(1.0)
                                    if len(bodies) > before:
                                        break
                        except Exception:
                            pass
                    if len(bodies) > before:
                        no_new = 0
                    else:
                        no_new += 1
                        if no_new >= 3:
                            print(f"  exhausted after {it + 1} rounds")
                            break
                tab.remove_listener("response", on_response)
                for key, body in bodies.items():
                    safe = re.sub(r"[^a-z0-9]+", "_", key.replace("ad.xiaohongshu.com/api/", "")) + ".json"
                    f = out_dir / safe
                    f.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
                    (out_dir / (safe + ".sha256")).write_text(hashlib.sha256(f.read_bytes()).hexdigest(), encoding="utf-8")
                results[wkey] = {"bodies": len(bodies), "max_pages": max_page, "dir": str(out_dir)}
                print(f"  {wkey}: {results[wkey]}")
            return results

        results = runtime._in_browser(run_all, timeout=1800)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    finally:
        runtime.close()
        print("UNIT_WINDOW_DONE")


if __name__ == "__main__":
    sys.exit(main())
