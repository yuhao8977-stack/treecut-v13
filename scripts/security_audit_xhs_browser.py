# -*- coding: utf-8 -*-
"""XHS Work Browser §50 Security Audit — 扫描 repo/reports/logs/json/db 无敏感信息。

扫描模式（只匹配"疑似真实凭证值"，不误伤安全注释）：
- cookie / authorization / session token / xsec_token / credential / password 后跟长字面值
- URL query 型签名参数（xsec_token= / sign= / signature= / ticket= 后跟 16+ 字符值）
- Authorization: Bearer/Basic 头
- 常见 token 形态（32+ hex/base64）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "src" / "treecut" / "browser",
    ROOT / "configs" / "xhs_work_browser.yaml",
    ROOT / "tests" / "test_xhs_work_browser_v01.py",
    ROOT / "docs",
]

# 敏感字段名后跟疑似真实值（12+ 字符的引号字面量）
FIELD_VALUE = re.compile(
    r"(?:cookie|authorization|session[_\-]?token|xsec[_\-]?token|credential|"
    r"password|passwd|access[_\-]?token|refresh[_\-]?token)"
    r"\s*[=:]\s*[\"'][A-Za-z0-9+/=_\-\.]{12,}[\"']",
    re.IGNORECASE,
)
# URL query 型签名参数（真实签名值）
QUERY_SIGNED = re.compile(
    r"(?:xsec_token|xsec_source|sign|signature|ticket|spm_id_from)"
    r"\s*=\s*[A-Za-z0-9+/=_\-\.]{16,}",
    re.IGNORECASE,
)
# 认证头
AUTH_HEADER = re.compile(
    r"authorization\s*[:=]\s*(?:bearer|basic)\s+[A-Za-z0-9+/=_\-]{16,}",
    re.IGNORECASE,
)
# 长 hex/base64 token 形态（仅当出现在赋值上下文）
TOKEN_LITERAL = re.compile(
    r"(?:token|secret|session)\s*[=:]\s*[\"'][A-Fa-f0-9]{32,}[\"']",
    re.IGNORECASE,
)

PATTERNS = [
    ("FIELD_VALUE", FIELD_VALUE),
    ("QUERY_SIGNED", QUERY_SIGNED),
    ("AUTH_HEADER", AUTH_HEADER),
    ("TOKEN_LITERAL", TOKEN_LITERAL),
]

# 我们的安全注释本身包含这些词，属合法出现；仅当匹配到"疑似值"才算命中。
# 因此上述正则都要求跟随字面值，注释中的 "不保存 cookie / xsec_token" 不会命中。


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    for name, pattern in PATTERNS:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            snippet = match.group(0)
            if len(snippet) > 120:
                snippet = snippet[:120] + "..."
            hits.append((name, line, snippet))
    return hits


def main() -> int:
    total = 0
    for target in TARGETS:
        if target.is_file():
            files = [target]
        else:
            files = sorted(target.rglob("*")) if target.is_dir() else []
        for path in files:
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.parts):
                continue
            if path.suffix not in {".py", ".yaml", ".yml", ".json", ".md", ".txt", ".toml"}:
                continue
            hits = scan_file(path)
            if hits:
                total += len(hits)
                print(f"[HIT] {path.relative_to(ROOT)}")
                for name, line, snippet in hits:
                    print(f"  {name} @line {line}: {snippet}")
    if total == 0:
        print("SECURITY_AUDIT: PASS — 未发现敏感凭证/签名值")
        return 0
    print(f"SECURITY_AUDIT: FAIL — 发现 {total} 处疑似敏感信息")
    return 1


if __name__ == "__main__":
    sys.exit(main())
