# -*- coding: utf-8 -*-
"""V0.3 — 单元列表页：rtb/unit/search + rtb/unit/extra/list 完整响应捕获。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

UNIT_PAGE = "https://ad.xiaohongshu.com/aurora/ad/manage/unit"
WANT = ("rtb/unit/search", "rtb/unit/extra/list", "rtb/unit/base/list", "unit/data")

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
            bodies = {}
            pages_seen = []

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
                if any(w in s for w in WANT):
                    key = s
                    n = 1
                    while key in bodies:
                        key = f"{s}#{n}"
                        n += 1
                    bodies[key] = body
                    m = re.search(r"pageNum=(\d+)", u)
                    if m:
                        pages_seen.append(int(m.group(1)))

            tab.on("response", on_response)
            try:
                tab.goto(UNIT_PAGE, timeout=60000)
                time.sleep(8)
            except Exception as e:
                print(f"NAV_FAIL {str(e)[:120]}")
            try:
                tab.reload(timeout=60000)
                time.sleep(8)
            except Exception as e:
                print(f"RELOAD_FAIL {str(e)[:120]}")
            # 滚动 + 翻页尝试
            for _ in range(3):
                try:
                    tab.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2.5)
                except Exception:
                    pass
            try:
                tab.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('[class*=page],[class*=next],[class*=pagin] button,[class*=pagin] a'));"
                    " const n = els.find(e => /下一页|next/.test((e.textContent||'').trim()) || /next/i.test(e.className||''));"
                    " if (n) { n.click(); return true; } return false; }")
                time.sleep(4)
            except Exception:
                pass
            tab.remove_listener("response", on_response)

            out_dir = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                           r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\spotlight_unit")
            out_dir.mkdir(parents=True, exist_ok=True)
            for ep, body in bodies.items():
                name = re.sub(r"[^a-z0-9]+", "_", ep.replace("ad.xiaohongshu.com/api/", "")) + ".json"
                (out_dir / name).write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
                data = (body.get('data') or {})
                lst = data.get('list') or data.get('dataList') or data.get('units') or []
                print(f"SAVED {name} | total={data.get('total') or data.get('totalCount')} len={len(lst)}")
            print(f"OUT_DIR = {out_dir}")
            print("pages_seen =", sorted(set(pages_seen)))
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("UNIT_CAPTURE_DONE")


def _safe(url):
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


if __name__ == "__main__":
    sys.exit(main())
