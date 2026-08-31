# -*- coding: utf-8 -*-
"""V0.3 — Spotlight API 结构探测：user/info + campaign 列表端点真实字段。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

SPOTLIGHT_HOME = "https://ad.xiaohongshu.com/aurora/ad/manage/campaign"
KEY_ENDPOINTS = ("user/info", "advId", "byvsellerId", "byvsellerid", "rtb/account", "user/trade")
CAMP_ENDPOINTS = ("campaign", "adgroup", "creative", "note", "promot")


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
            key_bodies = {}
            camp_bodies = {}
            all_eps = []

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = response.headers.get("content-type") or ""
                    if "json" not in ctype:
                        return
                    body = response.json()
                except Exception:
                    return
                low = u.lower()
                if any(k in low for k in KEY_ENDPOINTS):
                    key_bodies.setdefault(_safe(u), body)
                if any(k in low for k in CAMP_ENDPOINTS) and "leona" in low:
                    camp_bodies.setdefault(_safe(u), body)
                s = _safe(u)
                if s and s not in all_eps:
                    all_eps.append(s)

            tab.on("response", on_response)
            try:
                tab.goto(SPOTLIGHT_HOME, timeout=60000)
                time.sleep(8)
            except Exception as e:
                print(f"NAV_FAIL {str(e)[:120]}")
            try:
                tab.reload(timeout=60000)
                time.sleep(10)
            except Exception as e:
                print(f"RELOAD_FAIL {str(e)[:120]}")
            tab.remove_listener("response", on_response)

            # 落盘 key 端点体（账户证据）
            import hashlib as _h
            from pathlib import Path as _P
            base = _P(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                      r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\spotlight_account")
            out_dir = base / time.strftime("%Y%m%d_%H%M%S")
            out_dir.mkdir(parents=True, exist_ok=True)
            for ep, body in key_bodies.items():
                import re as _re
                name = _re.sub(r"[^a-z0-9]+", "_", ep.replace("ad.xiaohongshu.com/api/", "")) + ".json"
                f = out_dir / name
                f.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
                (out_dir / (name + ".sha256")).write_text(_h.sha256(f.read_bytes()).hexdigest(), encoding="utf-8")
            print("ACCOUNT_EVIDENCE_DIR =", out_dir)

            print("=== KEY ENDPOINT BODIES (structure) ===")
            for ep, body in key_bodies.items():
                print(f"--- {ep} ---")
                print(_shape(body, depth=0)[:1200])
            print()
            print("=== CAMP/CREATIVE ENDPOINTS ===")
            for ep in camp_bodies:
                print("  ", ep)
            print()
            print("=== ALL LEONA EPS ===")
            for ep in all_eps:
                print("  ", ep)
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("API_PROBE_DONE")


def _safe(url: str) -> str:
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


def _shape(node, depth=0, max_depth=3):
    if depth > max_depth:
        return "..."
    if isinstance(node, dict):
        parts = []
        for k, v in list(node.items())[:15]:
            if isinstance(v, (dict, list)):
                parts.append(f"{k}:{_shape(v, depth + 1, max_depth)}")
            else:
                s = str(v)
                parts.append(f"{k}={s[:40]}")
        return "{" + ", ".join(parts) + "}"
    if isinstance(node, list):
        if not node:
            return "[]"
        return f"[{len(node)}] {_shape(node[0], depth + 1, max_depth)[:200]}"
    return str(node)[:40]


if __name__ == "__main__":
    sys.exit(main())
