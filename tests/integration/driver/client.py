"""Layer 0: a self-contained client for the locksmith-ui-tester control socket.

Reimplements the tester's tiny newline-delimited-JSON wire protocol directly,
so the harness has no import-path dependency on the (un-installed) plugin clone
under ~/.locksmith. The protocol is: connect AF_UNIX, send
``json.dumps({"op": op, **kwargs}) + b"\\n"``, read until a newline, parse JSON.
Error replies carry an ``"error"`` key.
"""
from __future__ import annotations

import json
import os
import socket
from pathlib import Path


def default_socket_path() -> str:
    override = os.environ.get("LOCKSMITH_CONTROL_SOCKET")
    if override:
        return override
    return str(Path.home() / ".locksmith-control.sock")


class ControlError(RuntimeError):
    """Raised when the wallet returns an {"error": ...} response."""


class Client:
    """Drives the wallet over the control socket. One call == one connection."""

    def __init__(self, socket_path: str | None = None, timeout: float = 10.0):
        self.socket_path = socket_path or default_socket_path()
        self.timeout = timeout

    def call(self, op: str, **kwargs) -> dict:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.socket_path)
        try:
            payload = {"op": op, **kwargs}
            sock.sendall(json.dumps(payload).encode("utf-8") + b"\n")
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
        finally:
            sock.close()
        line = buf.split(b"\n", 1)[0].decode("utf-8")
        result = json.loads(line)
        if isinstance(result, dict) and "error" in result:
            raise ControlError(f"{op}: {result['error']}")
        return result

    def wait_for(self, target: str, condition: str = "visible",
                 timeout_ms: int = 5000, occurrence: int = 0) -> dict:
        return self.call("wait_for", target=target, condition=condition,
                         timeout_ms=timeout_ms, occurrence=occurrence)

    def ping(self) -> bool:
        return bool(self.call("ping").get("pong"))
