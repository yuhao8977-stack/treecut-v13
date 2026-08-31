# -*- coding: utf-8 -*-
"""一次性诊断：B007 前台个人主页 note 列表的真实数据源。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime


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
        result = runtime._in_browser(lambda: run_diag(runtime))
        for line in result:
            print(line)
        return 0
    finally:
        runtime.close()


def run_diag(runtime):
    """在浏览器 owner 线程内执行。"""
    import time as _t
    front = runtime.ensure_tabs().get("FRONTEND")
    hits = []

    def on_resp(response):
        try:
            url = response.url or ""
        except Exception:
            return
        if "user_posted" in url or "user/selfinfo" in url:
            try:
                status = response.status
                ctype = response.headers.get("content-type", "")
                body = response.json() if "json" in ctype else None
                preview = str(body)[:500] if body is not None else "(non-json)"
            except Exception as error:
                status, ctype, preview = "?", "?", f"json()失败:{error}"
            hits.append({"url": url, "status": status, "ctype": ctype, "preview": preview})

    front.on("response", on_resp)
    front.goto("https://www.xiaohongshu.com/user/profile/63083262719", timeout=60000)
    for _ in range(6):
        try:
            front.evaluate("() => window.scrollBy(0, document.body.scrollHeight)")
        except Exception:
            pass
        _t.sleep(1.5)
    top = front.evaluate(
        "() => { const s = window.__INITIAL_STATE__ || window.__INITIAL_SSR_STATE__ || {};"
        "return Object.keys(s); }")
    lines = ["INITIAL_STATE_TOP_KEYS: " + str(top),
             "---- user_posted/selfinfo responses ----"]
    for h in hits:
        lines.append(f"URL: {h['url']} | status: {h['status']} | ctype: {h['ctype']}")
        lines.append("  body: " + str(h["preview"])[:400])
    return lines


if __name__ == "__main__":
    sys.exit(main())
