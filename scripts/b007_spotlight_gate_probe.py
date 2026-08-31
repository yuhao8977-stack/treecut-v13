# -*- coding: utf-8 -*-
"""V0.3 — B007 Spotlight 账号门 + ad_account_id 校准探针。

流程：SPOTLIGHT tab → ad.xiaohongshu.com → 会话检测 → 账户名/ad_id 页面检测
→ 观察页面自有响应中真实 account 字段（ad_account_id/advertiser_id/...）
→ 与 Binding 比对 → 校准建议（升级 binding 或 NAME_CONFIRMED_BINDING）。
不模拟 signed API；不保存凭证。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime
from treecut.browser.account_detector import SpotlightIdentityDetector

SPOTLIGHT_HOME = "https://ad.xiaohongshu.com/"
NAME_RE = re.compile(r"T-?KUBON[^\s<]{0,30}")

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
            binding = runtime.workspace.load_binding()
            print("binding =", json.dumps({
                "spotlight_ad_account_id": binding.spotlight_ad_account_id,
                "spotlight_ad_account_name": binding.spotlight_ad_account_name,
            }, ensure_ascii=False))
            hits = []
            galaxy_eps = []

            def on_response(response):
                try:
                    u = response.url or ""
                except Exception:
                    return
                if "ad.xiaohongshu" in u and "json" in (response.headers.get("content-type") or ""):
                    s = _safe(u)
                    if s and s not in galaxy_eps:
                        galaxy_eps.append(s)
                try:
                    body = response.json()
                except Exception:
                    return
                # 找 account/advertiser 字段
                found = _find_account_fields(body, response.url or "")
                if found:
                    hits.append(found)

            tab.on("response", on_response)
            try:
                tab.goto(SPOTLIGHT_HOME, timeout=60000)
                time.sleep(8)
            except Exception as e:
                print(f"NAV_FAIL {str(e)[:120]}")
            # reload 触发页面自有请求
            try:
                tab.reload(timeout=60000)
                time.sleep(8)
            except Exception as e:
                print(f"RELOAD_FAIL {str(e)[:120]}")
            tab.remove_listener("response", on_response)

            print("URL_AFTER =", _safe(tab.url or ""))
            # 页面文本：找广告账户名 + ID
            try:
                body_txt = tab.evaluate("() => document.body ? document.body.innerText : ''")
                m_name = NAME_RE.search(body_txt or "")
                m_id = re.search(r"广告账户[ID号]{0,2}[:：\s]*([0-9a-zA-Z]{6,})", body_txt or "")
                m_id2 = re.search(r"(?:account|advertiser)[_\-]?id[:：\s]*([0-9a-zA-Z]{6,})", body_txt or "", re.I)
                print("PAGE_NAME_MATCH =", m_name.group(0)[:40] if m_name else None)
                print("PAGE_ID_MATCH =", m_id.group(1) if m_id else (m_id2.group(1) if m_id2 else None))
            except Exception as e:
                print("body scan fail", str(e)[:80])
            # 检测器结果
            det = SpotlightIdentityDetector(runtime.workspace).detect(tab)
            print("DETECTOR =", json.dumps({
                "primary_id": det.primary_id if det else None,
                "display_name": det.display_name if det else None,
            }, ensure_ascii=False))
            print("ACCOUNT_FIELD_HITS =", json.dumps(hits[:15], ensure_ascii=False, indent=1))
            print("GALAXY_EPS =", json.dumps(galaxy_eps[:30], ensure_ascii=True))
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("SPOT_GATE_PROBE_DONE")


def _safe(url: str) -> str:
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


def _find_account_fields(node, url: str):
    out = []
    def walk(n):
        if isinstance(n, dict):
            for k, v in n.items():
                if re.search(r"(ad_account|advertiser|account)[_\-]?id$", k, re.I) and isinstance(v, (str, int)) and str(v):
                    out.append({"field": k, "value": str(v)[:60], "url": _safe(url)[:100]})
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(n, list):
            for x in n:
                walk(x)
    walk(node)
    return out


if __name__ == "__main__":
    sys.exit(main())
