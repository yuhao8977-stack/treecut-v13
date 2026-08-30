"""XHS Work Browser V0.1 — TreeCut Local Bridge（§17/18/46）。

Browser ↔ TreeCut Local Service 本地通信：localhost HTTP，必须支持 health check：
  GET /health → {"service": "treecut-local", "status": "ok", ...}

§18：TreeCut Local 断开 → TREECUT_DISCONNECTED，不得继续任何未来数据 Commit 任务
（浏览器本身可保持登录）。服务恢复后下一次 health() 自动恢复 CONNECTED（§46 Test D）。
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from treecut.browser.policies import utcnow_iso

CONNECTED = "CONNECTED"
DISCONNECTED = "DISCONNECTED"


@dataclass
class HealthResult:
    connected: bool
    status: str = DISCONNECTED
    service: str = ""
    version: str = ""
    detail: str = ""
    checked_at: str = field(default_factory=utcnow_iso)

    def __post_init__(self) -> None:
        self.status = CONNECTED if self.connected else DISCONNECTED


class LocalBridge:
    """TreeCut Local Service 客户端（V0.1 只做 health；不做任何业务写入）。"""

    def __init__(self, base_url: str, timeout_seconds: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def health(self) -> HealthResult:
        try:
            import urllib.request
            url = f"{self.base_url}/health"
            with urllib.request.urlopen(url, timeout=self.timeout_seconds) as resp:  # noqa: S310 localhost
                payload = json.loads(resp.read().decode("utf-8"))
                ok = resp.status == 200 and payload.get("status") == "ok"
                return HealthResult(
                    connected=ok,
                    service=str(payload.get("service", "")),
                    version=str(payload.get("version", "")),
                    detail=str(payload.get("detail", "")),
                )
        except Exception as error:  # 断开/超时/拒绝 → DISCONNECTED
            return HealthResult(connected=False, detail=f"{type(error).__name__}: {str(error)[:80]}")


class LocalServiceStub:
    """参考实现：V0.1 的 TreeCut Local Service 最小 stub（供 Test D 与人工演示）。

    真实 TreeCut Local Service 后续按此 /health 契约接入。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 28888,
                 service: str = "treecut-local", version: str = "V0.1"):
        self.host = host
        self.port = port
        self.service = service
        self.version = version
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        if self._httpd is not None:
            return f"{self.host}:{self.port}"
        service, version = self.service, self.version

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if urlsplit(self.path).path == "/health":
                    body = json.dumps({
                        "service": service, "status": "ok",
                        "version": version, "detail": "V0.1 health only",
                    }).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *_: object) -> None:  # 静默
                return

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = self._httpd.server_address[1]  # port=0 → 实际临时端口
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return f"{self.host}:{self.port}"

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    @property
    def running(self) -> bool:
        return self._httpd is not None
