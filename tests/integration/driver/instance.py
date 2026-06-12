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
import shutil
from pathlib import Path

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
            (dest / pid).symlink_to(src, target_is_directory=True)
