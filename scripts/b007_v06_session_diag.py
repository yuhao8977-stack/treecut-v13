# -*- coding: utf-8 -*-
"""V0.6 — 前台会话 + 主页加载 API 诊断。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

PROFILE = "https://www.xiaohongshu.com/user/profile/63083262719"


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
        roles = runtime.check_roles()
        print("FRONTEND_ROLE =", json.dumps(roles.get("FRONTEND"), ensure_ascii=True))

        def probe():
            tab = runtime.ensure_tabs().get("FRONTEND")
            eps = []
            bodies = {}

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = response.headers.get("content-type") or ""
                    if "json" not in ctype:
                        return
                    body = response.json()
                except Exception:
                    return
                from urllib.parse import urlsplit
                s = urlsplit(u).netloc + urlsplit(u).path
                if s not in eps:
                    eps.append(s)
                if "user" in s or "note" in s or "feed" in s or "profile" in s:
                    bodies.setdefault(s, body)

            tab.on("response", on_response)
            tab.goto(PROFILE, timeout=60000)
            time.sleep(12)
            tab.remove_listener("response", on_response)
            print("URL =", tab.url[:140])
            print("EPS =", json.dumps(eps[:25], ensure_ascii=True))
            for ep, body in list(bodies.items())[:6]:
                d = body.get("data") if isinstance(body, dict) else None
                if isinstance(d, dict):
                    print(f"  {ep}: keys={list(d.keys())[:8]} | has notes={('notes' in d) or ('note_list' in d)}")
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("SESSION_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
