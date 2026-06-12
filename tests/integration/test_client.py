import json
import socket
import threading

import pytest

from driver.client import Client, ControlError, default_socket_path


def _start_server(path, reply: bytes, captured: list) -> threading.Thread:
    """Bind+listen in the calling thread (no connect race), accept in a worker."""
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    srv.listen(1)

    def handle():
        conn, _ = srv.accept()
        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
        captured.append(buf)
        conn.sendall(reply)
        conn.close()
        srv.close()

    t = threading.Thread(target=handle, daemon=True)
    t.start()
    return t


def test_call_frames_request_and_parses_reply(tmp_path):
    sock_path = str(tmp_path / "ctl.sock")
    captured: list = []
    reply = json.dumps({"ok": True, "pong": True}).encode() + b"\n"
    t = _start_server(sock_path, reply, captured)

    client = Client(socket_path=sock_path)
    result = client.call("ping")
    t.join(timeout=5)

    assert result == {"ok": True, "pong": True}
    assert json.loads(captured[0].decode().strip()) == {"op": "ping"}


def test_call_includes_kwargs_in_payload(tmp_path):
    sock_path = str(tmp_path / "ctl.sock")
    captured: list = []
    reply = json.dumps({"ok": True}).encode() + b"\n"
    t = _start_server(sock_path, reply, captured)

    client = Client(socket_path=sock_path)
    client.call("type", target="field", text="hi")
    t.join(timeout=5)

    assert json.loads(captured[0].decode().strip()) == {
        "op": "type", "target": "field", "text": "hi",
    }


def test_call_raises_control_error_on_error_reply(tmp_path):
    sock_path = str(tmp_path / "ctl.sock")
    captured: list = []
    reply = json.dumps({"error": "widget not found"}).encode() + b"\n"
    t = _start_server(sock_path, reply, captured)

    client = Client(socket_path=sock_path)
    with pytest.raises(ControlError):
        client.call("click", target="nope")
    t.join(timeout=5)


def test_default_socket_path_honors_env(monkeypatch):
    monkeypatch.setenv("LOCKSMITH_CONTROL_SOCKET", "/tmp/custom.sock")
    assert default_socket_path() == "/tmp/custom.sock"
