# -*- coding: utf-8 -*-
"""V0.3 — 捕获 Spotlight 账户端点（user/info, get_account, balance）→ 账户实体。"""
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

CAMP_PAGE = "https://ad.xiaohongshu.com/"
WANT = ("user/info", "get_account", "rtb/account/balance", "finance/credit", "user/trade/info")

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
        inbox = Path(runtime.workspace.workspace_dir) / "treecut_inbox" / "creator" / "raw" / "creator"
        out_dir = inbox / "spotlight_account" / time.strftime("%Y%m%d_%H%M%S")
        out_dir.mkdir(parents=True, exist_ok=True)

        def run():
            tab = runtime.ensure_tabs().get("SPOTLIGHT")
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
                s = _safe(u)
                if any(w in s for w in WANT):
                    bodies.setdefault(s, body)

            tab.on("response", on_response)
            tab.goto(CAMP_PAGE, timeout=60000)
            time.sleep(8)
            tab.reload(timeout=60000)
            time.sleep(8)
            tab.remove_listener("response", on_response)
            for ep, body in bodies.items():
                name = re.sub(r"[^a-z0-9]+", "_", ep.replace("ad.xiaohongshu.com/api/", "")) + ".json"
                f = out_dir / name
                f.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
                (out_dir / (name + ".sha256")).write_text(
                    hashlib.sha256(f.read_bytes()).hexdigest(), encoding="utf-8")
                print(f"SAVED {name}")
            return sorted(bodies.keys())
        eps = runtime._in_browser(run, timeout=400)
        print(f"OUT_DIR = {out_dir}")
        print("EPS =", eps)
        return 0
    finally:
        runtime.close()
        print("ACCOUNT_CAPTURE_DONE")


def _safe(url):
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


if __name__ == "__main__":
    sys.exit(main())
