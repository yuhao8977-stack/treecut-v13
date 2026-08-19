"""LAN hub discovery: host answers UDP probes, slave auto-finds it after network changes."""
from __future__ import annotations

import hashlib
import json
import socket
import threading
import time


PROBE_PORT = 8767
PROBE_PAYLOAD = json.dumps({"t": "treecut-probe"}).encode("utf-8")


def fingerprint(token: str) -> str:
    """Short public fingerprint of the shared token; never reveals the token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


def _reply_payload(token: str, port: int) -> bytes:
    return json.dumps({
        "t": "treecut-hub",
        "fp": fingerprint(token),
        "port": port,
    }).encode("utf-8")


class HubResponder:
    """Host side: answer broadcast probes so slaves can find the hub on a new LAN."""

    def __init__(self, token: str, port: int = 8766):
        self._token = token
        self._port = port
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind(("", PROBE_PORT))
        except OSError:
            return
        self._sock.settimeout(1.0)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        payload = _reply_payload(self._token, self._port)
        while not self._stop.is_set():
            try:
                data, address = self._sock.recvfrom(1024)
                if json.loads(data.decode("utf-8", errors="replace")).get("t") == "treecut-probe":
                    self._sock.sendto(payload, address)
            except (socket.timeout, OSError):
                pass
            except Exception:
                pass

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass


def discover_hubs(timeout: float = 3.0, expected_fp: str | None = None) -> list[tuple[str, int]]:
    """Slave side: broadcast a probe and collect fingerprint-matched hub replies."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.4)
    found: list[tuple[str, int]] = []
    try:
        sock.sendto(PROBE_PAYLOAD, ("255.255.255.255", PROBE_PORT))
    except OSError:
        pass
    deadline = time.time() + max(0.5, timeout)
    while time.time() < deadline:
        try:
            data, address = sock.recvfrom(1024)
        except socket.timeout:
            continue
        except OSError:
            break
        try:
            payload = json.loads(data.decode("utf-8", errors="replace"))
            if payload.get("t") != "treecut-hub":
                continue
            if expected_fp and payload.get("fp") != expected_fp:
                continue
            candidate = (address[0], int(payload.get("port") or 8766))
            if candidate not in found:
                found.append(candidate)
        except Exception:
            continue
    sock.close()
    return found
