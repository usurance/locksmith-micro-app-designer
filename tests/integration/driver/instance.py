"""Ephemeral, isolated wallet instances for integration tests.

A fresh ``$HOME`` gives a pristine wallet (zero vaults) but has no plugins
installed. ``seed_plugin_home`` populates ``<home>/.locksmith/plugins`` by
copying the developer's real index.json and symlinking each plugin clone it
names, so the throwaway wallet loads the same ui_tester + designer plugins.
``EphemeralWallet`` (added in a later task) launches the DMG binary against
that HOME, waits for its control socket, and tears everything down on exit.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from driver.client import Client

LOCKSMITH_BINARY = "/Applications/Locksmith.app/Contents/MacOS/Locksmith"
REAL_PLUGINS_ROOT = Path.home() / ".locksmith" / "plugins"


def seed_plugin_home(home: Path, plugins_root: Path = REAL_PLUGINS_ROOT) -> None:
    """Copy the real plugin index and symlink each plugin clone it references
    into ``<home>/.locksmith/plugins`` so a fresh HOME loads the same plugins."""
    dest = home / ".locksmith" / "plugins"
    dest.mkdir(parents=True, exist_ok=True)
    index_src = plugins_root / "index.json"
    index = json.loads(index_src.read_text(encoding="utf-8"))
    shutil.copyfile(index_src, dest / "index.json")
    for record in index.get("plugins", []):
        pid = record.get("plugin_id")
        if not pid:
            continue
        src = plugins_root / pid
        if src.exists():
            link = dest / pid
            link.unlink(missing_ok=True)  # idempotent: replace stale/broken link on re-run
            link.symlink_to(src, target_is_directory=True)


class EphemeralWallet:
    """Context manager: a throwaway-HOME Locksmith instance with a live socket.

    Usage:
        with EphemeralWallet() as wallet:
            wallet.client.ping()

    The temp HOME is created under /tmp (NOT the default $TMPDIR) because macOS
    AF_UNIX socket paths must stay under 104 chars; $TMPDIR paths are too long.
    """

    def __init__(self, binary: str = LOCKSMITH_BINARY,
                 plugins_root: Path = REAL_PLUGINS_ROOT, boot_timeout: float = 30.0):
        self.binary = binary
        self.plugins_root = plugins_root
        self.boot_timeout = boot_timeout
        self._tmp: str | None = None
        self._proc: subprocess.Popen | None = None
        self.home: Path | None = None
        self.socket_path: str | None = None
        self.client: Client | None = None

    def __enter__(self) -> "EphemeralWallet":
        # /tmp keeps the socket path short enough for AF_UNIX on macOS.
        self._tmp = tempfile.mkdtemp(prefix="ls-it-", dir="/tmp")
        self.home = Path(self._tmp)
        self.socket_path = str(self.home / ".locksmith-control.sock")
        seed_plugin_home(self.home, self.plugins_root)

        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["LOCKSMITH_CONTROL_SOCKET"] = self.socket_path
        self._proc = subprocess.Popen(
            [self.binary], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        deadline = time.monotonic() + self.boot_timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                self._cleanup_tmp()
                raise RuntimeError(
                    f"Locksmith exited early (code {self._proc.returncode}) "
                    f"before its socket appeared"
                )
            if os.path.exists(self.socket_path):
                candidate = Client(socket_path=self.socket_path)
                try:
                    if candidate.ping():
                        self.client = candidate
                        return self
                except OSError:
                    pass
            time.sleep(0.25)
        self.__exit__(None, None, None)
        raise TimeoutError(
            f"wallet socket {self.socket_path} did not come up within {self.boot_timeout}s"
        )

    def __exit__(self, *exc) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
        self._cleanup_tmp()

    def _cleanup_tmp(self) -> None:
        if self._tmp is not None:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None
