# Wallet UI Integration Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable driver, selector cheatsheet, and isolated integration test suite for driving the Locksmith wallet UI through the `locksmith-ui-tester` socket.

**Architecture:** A layered driver under `tests/integration/driver/` — a self-contained socket `Client` (Layer 0), `selectors` page objects (Layer 1, the living cheatsheet), and `actions` verbs (Layer 2). Integration tests run against an ephemeral wallet launched with a throwaway `$HOME` seeded with symlinked plugin clones, torn down with `rm -rf`. Headless unit tests cover the driver logic; wallet-requiring tests self-skip when the app is absent. A `scripts/wallet.py` CLI exposes the same actions against the developer's running wallet.

**Tech Stack:** Python 3.13, pytest, `socket` (AF_UNIX), `subprocess`, the installed `locksmith-ui-tester` plugin clone. No new third-party deps.

**Design spec:** `docs/superpowers/specs/2026-06-11-wallet-ui-integration-harness-design.md`

---

## File Structure

```
tests/integration/
  __init__.py                    # (empty) — marks the dir importable
  driver/
    __init__.py                  # (empty)
    client.py                    # Layer 0 — socket Client + default_socket_path + ControlError
    selectors.py                 # Layer 1 — page objects (objectName constants). The cheatsheet.
    actions.py                   # Layer 2 — create_vault / open_vault / open_designer
    instance.py                  # seed_plugin_home + EphemeralWallet context manager
  conftest.py                    # running_wallet + ephemeral_wallet fixtures (skip logic)
  test_client.py                 # headless unit tests (Layer 0)
  test_actions.py                # headless unit tests (Layer 2, FakeClient)
  test_instance.py               # headless unit tests (seeding)
  test_instance_boots.py         # INTEGRATION spike — ephemeral wallet pings (de-risks seeding)
  test_vault_lifecycle.py        # INTEGRATION — create + reopen
  test_designer_smoke.py         # INTEGRATION — open designer plugin
  README.md                      # op reference + "how to add a page object"
scripts/
  wallet.py                      # interactive CLI over the running wallet
pyproject.toml                   # MODIFY: add tests/integration to pythonpath
src/locksmith_micro_app_designer/plugin.py  # MODIFY: stable objectNames on designer nav buttons
```

**Verified facts baked into this plan (do not re-derive):**
- Tester wire protocol: connect AF_UNIX, send `json.dumps({"op": op, **kwargs}) + b"\n"`, read until `\n`, parse JSON. Error replies are `{"error": "..."}`.
- Socket path: `$LOCKSMITH_CONTROL_SOCKET` else `~/.locksmith-control.sock`.
- Wallet binary: `/Applications/Locksmith.app/Contents/MacOS/Locksmith`. Must be exec'd directly with env (macOS `open` won't pass `$HOME`).
- Plugin loading: host reads `~/.locksmith/plugins/index.json` = `{"format":1,"plugins":[{"plugin_id","source","manifest_snapshot":{"entry_point":"mod:Class"}}, ...]}`, loads each by clone-dir name `~/.locksmith/plugins/<plugin_id>`. Missing per-wallet enable list = all enabled.
- Verified selectors: `toolbar.vaultsButton`; `Initialize New Vault` (a QListWidget item → `click_list_item`); `createVaultDialog.{nameField,passcodeField,createButton,cancelButton}`; `vaultDrawer.open.<name>`; `openVaultDialog.{passcodeField,openButton,cancelButton}`.
- Designer nav buttons have NO objectName upstream (Task 6 adds them in this repo).

---

## Task 1: Make `tests/integration` importable + package skeleton

**Files:**
- Create: `tests/integration/__init__.py` (empty)
- Create: `tests/integration/driver/__init__.py` (empty)
- Modify: `pyproject.toml` (`[tool.pytest.ini_options]`)

- [ ] **Step 1: Create the empty package markers**

Create `tests/integration/__init__.py` with no content, and `tests/integration/driver/__init__.py` with no content.

- [ ] **Step 2: Add the driver path to pytest's pythonpath**

In `pyproject.toml`, change:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

to:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "tests/integration"]
```

(`[tool.setuptools.packages.find] where = ["src"]` is unchanged, so nothing under `tests/` ships in the wheel.)

- [ ] **Step 3: Verify the existing suite still collects**

Run: `pytest --collect-only -q`
Expected: collection succeeds, the existing 68 tests are listed, no import errors.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/__init__.py tests/integration/driver/__init__.py pyproject.toml
git commit -m "test(integration): add tests/integration package + pythonpath"
```

---

## Task 2: Layer 0 — socket `Client`

**Files:**
- Create: `tests/integration/driver/client.py`
- Test: `tests/integration/test_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_client.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.client'`

- [ ] **Step 3: Write the implementation**

Create `tests/integration/driver/client.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_client.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tests/integration/driver/client.py tests/integration/test_client.py
git commit -m "feat(integration): add Layer 0 socket Client"
```

---

## Task 3: Seeding logic — `seed_plugin_home`

**Files:**
- Create: `tests/integration/driver/instance.py` (seeding portion)
- Test: `tests/integration/test_instance.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_instance.py`:

```python
import json

from driver.instance import seed_plugin_home


def test_seed_copies_index_and_symlinks_each_plugin(tmp_path):
    real = tmp_path / "real-plugins"
    (real / "ui_tester").mkdir(parents=True)
    (real / "designer").mkdir(parents=True)
    (real / "index.json").write_text(json.dumps({
        "format": 1,
        "plugins": [{"plugin_id": "ui_tester"}, {"plugin_id": "designer"}],
    }), encoding="utf-8")

    home = tmp_path / "home"
    seed_plugin_home(home, plugins_root=real)

    dest = home / ".locksmith" / "plugins"
    assert (dest / "index.json").exists()
    assert json.loads((dest / "index.json").read_text())["plugins"][0]["plugin_id"] == "ui_tester"
    assert (dest / "ui_tester").is_symlink()
    assert (dest / "designer").is_symlink()
    assert (dest / "ui_tester").resolve() == (real / "ui_tester").resolve()


def test_seed_skips_missing_plugin_dirs(tmp_path):
    real = tmp_path / "real-plugins"
    (real / "ui_tester").mkdir(parents=True)
    (real / "index.json").write_text(json.dumps({
        "format": 1,
        "plugins": [{"plugin_id": "ui_tester"}, {"plugin_id": "ghost"}],
    }), encoding="utf-8")

    home = tmp_path / "home"
    seed_plugin_home(home, plugins_root=real)

    dest = home / ".locksmith" / "plugins"
    assert (dest / "ui_tester").is_symlink()
    assert not (dest / "ghost").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_instance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.instance'`

- [ ] **Step 3: Write the implementation**

Create `tests/integration/driver/instance.py`:

```python
"""Ephemeral, isolated wallet instances for integration tests.

A fresh ``$HOME`` gives a pristine wallet (zero vaults) but has no plugins
installed. ``seed_plugin_home`` populates ``<home>/.locksmith/plugins`` by
copying the developer's real index.json and symlinking each plugin clone it
names, so the throwaway wallet loads the same ui_tester + designer plugins.
``EphemeralWallet`` launches the DMG binary against that HOME, waits for its
control socket, and tears everything down with the temp dir on exit.
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
            (dest / pid).symlink_to(src, target_is_directory=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_instance.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add tests/integration/driver/instance.py tests/integration/test_instance.py
git commit -m "feat(integration): add plugin-home seeding"
```

---

## Task 4: `EphemeralWallet` context manager

**Files:**
- Modify: `tests/integration/driver/instance.py` (append the class)

No headless unit test: launching needs the real DMG binary. This class is validated by the integration spike in Task 6. Implement it now so the spike has something to call.

- [ ] **Step 1: Append the class to `instance.py`**

Add to the end of `tests/integration/driver/instance.py`:

```python
class EphemeralWallet:
    """Context manager: a throwaway-HOME Locksmith instance with a live socket.

    Usage:
        with EphemeralWallet() as wallet:
            wallet.client.ping()
    """

    def __init__(self, binary: str = LOCKSMITH_BINARY,
                 plugins_root: Path = REAL_PLUGINS_ROOT, boot_timeout: float = 30.0):
        self.binary = binary
        self.plugins_root = plugins_root
        self.boot_timeout = boot_timeout
        self._tmp: tempfile.TemporaryDirectory | None = None
        self._proc: subprocess.Popen | None = None
        self.home: Path | None = None
        self.socket_path: str | None = None
        self.client: Client | None = None

    def __enter__(self) -> "EphemeralWallet":
        self._tmp = tempfile.TemporaryDirectory(prefix="ls-it-")
        self.home = Path(self._tmp.name)
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
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None
```

- [ ] **Step 2: Verify the module still imports and seeding tests still pass**

Run: `pytest tests/integration/test_instance.py -v`
Expected: 2 passed (the class import doesn't break the seeding tests)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/driver/instance.py
git commit -m "feat(integration): add EphemeralWallet context manager"
```

---

## Task 5: pytest fixtures + skip logic

**Files:**
- Create: `tests/integration/conftest.py`

- [ ] **Step 1: Write `conftest.py`**

Create `tests/integration/conftest.py`:

```python
"""Fixtures for wallet integration tests.

- ``running_wallet``: a Client bound to the developer's already-open wallet.
  Skips when no control socket is present.
- ``ephemeral_wallet``: a throwaway isolated wallet instance (session-scoped).
  Skips when the Locksmith app is not installed.
"""
import os

import pytest

from driver.client import Client, default_socket_path
from driver.instance import EphemeralWallet, LOCKSMITH_BINARY


@pytest.fixture
def running_wallet():
    path = default_socket_path()
    if not os.path.exists(path):
        pytest.skip("no running wallet control socket; launch Locksmith first")
    return Client(socket_path=path)


@pytest.fixture(scope="session")
def ephemeral_wallet():
    if not os.path.exists(LOCKSMITH_BINARY):
        pytest.skip(f"Locksmith app not installed at {LOCKSMITH_BINARY}")
    with EphemeralWallet() as wallet:
        yield wallet
```

- [ ] **Step 2: Verify headless suite is unaffected and integration tests would skip**

Run: `pytest tests/integration -v`
Expected: the headless unit tests (client, instance) pass; no errors from importing conftest. (No integration test files exist yet — they arrive in Tasks 6, 9, 10.)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/conftest.py
git commit -m "test(integration): add running_wallet + ephemeral_wallet fixtures"
```

---

## Task 6: Integration spike — ephemeral wallet boots & pings

**Files:**
- Create: `tests/integration/test_instance_boots.py`

This is the de-risking task: it proves the seed → launch → socket → ping path end-to-end. Run it on a machine with Locksmith installed.

- [ ] **Step 1: Write the test**

Create `tests/integration/test_instance_boots.py`:

```python
"""Integration spike: a seeded throwaway-HOME wallet comes up and responds.

Validates the riskiest part of the harness — that copying the real index.json
and symlinking the plugin clones is enough for the host to load ui_tester and
open its control socket in a fresh HOME. Skips when Locksmith isn't installed.
"""


def test_ephemeral_wallet_pings(ephemeral_wallet):
    assert ephemeral_wallet.client is not None
    assert ephemeral_wallet.client.ping() is True


def test_ephemeral_wallet_starts_with_zero_vaults(ephemeral_wallet):
    # A pristine HOME has no vaults: the drawer's vault rows are absent.
    result = ephemeral_wallet.client.call("count", target="vaultDrawer.vaultList")
    assert result.get("ok") is True
```

- [ ] **Step 2: Run the spike**

Run: `pytest tests/integration/test_instance_boots.py -v -s`
Expected (Locksmith installed): 2 passed. A throwaway window launches and closes.
Expected (no app): both skipped.

- [ ] **Step 3: If the socket does NOT come up, debug the seed**

If `test_ephemeral_wallet_pings` raises `TimeoutError`, temporarily set `stdout`/`stderr` in `EphemeralWallet.__enter__` to a log file instead of `DEVNULL`, re-run, and inspect:
- `<home>/.locksmith/plugins/index.json` was copied and lists `ui_tester`.
- The host log shows `plugin.loaded plugin_id=ui_tester` (not `files_missing` / `failed` / `incompatible`).
- If `files_missing`: the symlink target is wrong — confirm `~/.locksmith/plugins/ui_tester` exists.
- If `incompatible`: the host requires a host-version field in `manifest_snapshot`; copy that plugin's `locksmith-plugin.toml`-derived snapshot as-is (it already is, via the copied index). Capture the fix in `seed_plugin_home` and re-run the seeding unit tests.

Revert the stdout/stderr change once green.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_instance_boots.py
git commit -m "test(integration): spike — ephemeral wallet boots and pings"
```

---

## Task 7: Layer 1 — selectors (the cheatsheet)

**Files:**
- Create: `tests/integration/driver/selectors.py`
- Test: `tests/integration/test_selectors.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_selectors.py`:

```python
from driver import selectors as S


def test_static_selectors_present():
    assert S.Toolbar.VAULTS_BUTTON == "toolbar.vaultsButton"
    assert S.VaultDrawer.NEW_VAULT_ITEM == "Initialize New Vault"
    assert S.CreateVaultDialog.PASSCODE == "createVaultDialog.passcodeField"
    assert S.OpenVaultDialog.OPEN == "openVaultDialog.openButton"
    assert S.Designer.NAV_BUTTON == "designer.navButton"


def test_per_vault_selectors_interpolate_name():
    assert S.VaultDrawer.open_button("automation") == "vaultDrawer.open.automation"
    assert S.VaultDrawer.row("automation") == "vaultDrawer.row.automation"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_selectors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.selectors'`

- [ ] **Step 3: Write the implementation**

Create `tests/integration/driver/selectors.py`:

```python
"""Layer 1: page objects — the living selector cheatsheet.

Each class groups the objectNames (or list-item text) for one screen, plus the
op each control needs in a comment. Curated from the host source once per
screen. Actions and tests import from here so selectors never drift.
"""
from __future__ import annotations


class Toolbar:
    VAULTS_BUTTON = "toolbar.vaultsButton"   # click — opens the Vaults drawer


class VaultDrawer:
    NEW_VAULT_ITEM = "Initialize New Vault"  # QListWidget item → click_list_item
    VAULT_LIST = "vaultDrawer.vaultList"     # count / get_list_items

    @staticmethod
    def open_button(name: str) -> str:
        return f"vaultDrawer.open.{name}"    # click — opens the unlock dialog

    @staticmethod
    def row(name: str) -> str:
        return f"vaultDrawer.row.{name}"


class CreateVaultDialog:
    NAME = "createVaultDialog.nameField"         # type
    PASSCODE = "createVaultDialog.passcodeField" # type
    CREATE = "createVaultDialog.createButton"    # click
    CANCEL = "createVaultDialog.cancelButton"    # click


class OpenVaultDialog:
    PASSCODE = "openVaultDialog.passcodeField"   # type
    OPEN = "openVaultDialog.openButton"          # click
    CANCEL = "openVaultDialog.cancelButton"      # click


class Designer:
    NAV_BUTTON = "designer.navButton"            # click — enters the plugin (set in plugin.py)
    PAGE_OVERVIEW = "designer.overview"          # current_page value
    PAGE_TEMPLATES = "designer.templates"        # current_page value
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_selectors.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add tests/integration/driver/selectors.py tests/integration/test_selectors.py
git commit -m "feat(integration): add Layer 1 selectors cheatsheet"
```

---

## Task 8: Stable objectNames on designer nav buttons

**Files:**
- Modify: `src/locksmith_micro_app_designer/plugin.py` (`get_menu_entry`, `get_menu_section`)

The designer's `MenuButton`s carry no objectName, so they can't be targeted deterministically. Add objectNames in the repo we own. No headless test (plugin.py imports the host `locksmith` package, unavailable in this venv); verified by Task 10's smoke test.

- [ ] **Step 1: Set objectName on the main menu entry**

In `src/locksmith_micro_app_designer/plugin.py`, change `get_menu_entry`:

```python
    def get_menu_entry(self) -> MenuButton:
        return MenuButton(
            icon=QIcon(_ICON_PATH),
            label="Micro App Designer",
        )
```

to:

```python
    def get_menu_entry(self) -> MenuButton:
        button = MenuButton(
            icon=QIcon(_ICON_PATH),
            label="Micro App Designer",
        )
        button.setObjectName("designer.navButton")
        return button
```

- [ ] **Step 2: Set objectName on the in-plugin templates nav button**

In the same file, in `get_menu_section`, change:

```python
        self._templates_nav_button = MenuButton(
            icon=QIcon(_ICON_PATH),
            label="Micro-App Designer",
        )
        self._templates_nav_button.clicked.connect(self._show_templates_browser)
```

to:

```python
        self._templates_nav_button = MenuButton(
            icon=QIcon(_ICON_PATH),
            label="Micro-App Designer",
        )
        self._templates_nav_button.setObjectName("designer.templatesNavButton")
        self._templates_nav_button.clicked.connect(self._show_templates_browser)
```

- [ ] **Step 3: Verify the existing library suite is unaffected**

Run: `pytest -q`
Expected: existing tests pass (plugin.py is not imported by the headless suite; this is a no-op for them). The change compiles — confirm with `python -c "import ast; ast.parse(open('src/locksmith_micro_app_designer/plugin.py').read())"` → no output.

- [ ] **Step 4: Reinstall the designer clone so the running wallet picks up the objectName**

Since the wallet loads the clone at `~/.locksmith/plugins/designer`, the change must reach that clone. If it's a symlink to this repo it's automatic; otherwise note in `tests/integration/README.md` that the designer plugin must be reinstalled/upgraded in the wallet for the smoke test to see `designer.navButton`. (The ephemeral wallet symlinks the clone, so rebuild/reinstall there as your setup requires.)

Run: `ls -l ~/.locksmith/plugins/designer`
Expected: confirm whether it's a symlink (auto-updates) or a copy (needs reinstall).

- [ ] **Step 5: Commit**

```bash
git add src/locksmith_micro_app_designer/plugin.py
git commit -m "feat(plugin): add stable objectNames to designer nav buttons"
```

---

## Task 9: Layer 2 — actions

**Files:**
- Create: `tests/integration/driver/actions.py`
- Test: `tests/integration/test_actions.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_actions.py`:

```python
from driver import actions


class FakeClient:
    """Records calls and returns canned replies — no socket, no wallet."""

    def __init__(self, responses=None):
        self.calls: list = []
        self._responses = responses or {}

    def call(self, op, **kwargs):
        self.calls.append((op, kwargs))
        return self._responses.get(op, {"ok": True})

    def wait_for(self, target, condition="visible", timeout_ms=5000, occurrence=0):
        self.calls.append(("wait_for", {"target": target, "condition": condition}))
        return {"ok": True}


def test_create_vault_issues_expected_sequence():
    fake = FakeClient(responses={"current_page": {"ok": True, "vault_page": "identifiers"}})

    result = actions.create_vault(fake, "automation", "noble")

    ops = [c[0] for c in fake.calls]
    assert ops == [
        "click", "click_list_item", "wait_for", "type", "type",
        "click", "wait_for", "current_page",
    ]
    assert ("type", {"target": "createVaultDialog.nameField", "text": "automation"}) in fake.calls
    assert ("type", {"target": "createVaultDialog.passcodeField", "text": "noble"}) in fake.calls
    assert result == {"ok": True, "vault_page": "identifiers"}


def test_open_vault_targets_named_vault_then_types_passcode():
    fake = FakeClient(responses={"current_page": {"ok": True, "vault_page": "identifiers"}})

    actions.open_vault(fake, "automation", "noble")

    assert ("click", {"target": "vaultDrawer.open.automation"}) in fake.calls
    assert ("type", {"target": "openVaultDialog.passcodeField", "text": "noble"}) in fake.calls
    assert ("click", {"target": "openVaultDialog.openButton"}) in fake.calls


def test_open_designer_clicks_nav_and_returns_page():
    fake = FakeClient(responses={"current_page": {"ok": True, "vault_page": "designer.overview"}})

    result = actions.open_designer(fake)

    assert ("click", {"target": "designer.navButton"}) in fake.calls
    assert result == {"ok": True, "vault_page": "designer.overview"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_actions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'driver.actions'`

- [ ] **Step 3: Write the implementation**

Create `tests/integration/driver/actions.py`:

```python
"""Layer 2: reusable wallet actions composing Layer 0 (client) + Layer 1
(selectors). Each verb ends in a wait_for so the UI is settled on return, and
returns the resulting current_page for assertions. Works against any client
exposing call()/wait_for() — the live Client or a test fake.
"""
from __future__ import annotations

from driver import selectors as S


def create_vault(client, name: str, passcode: str) -> dict:
    """Open the drawer, fill the create dialog, submit; return current_page."""
    client.call("click", target=S.Toolbar.VAULTS_BUTTON)
    client.call("click_list_item", text=S.VaultDrawer.NEW_VAULT_ITEM)
    client.wait_for(S.CreateVaultDialog.NAME)
    client.call("type", target=S.CreateVaultDialog.NAME, text=name)
    client.call("type", target=S.CreateVaultDialog.PASSCODE, text=passcode)
    client.call("click", target=S.CreateVaultDialog.CREATE)
    client.wait_for(S.CreateVaultDialog.NAME, condition="hidden")
    return client.call("current_page")


def open_vault(client, name: str, passcode: str) -> dict:
    """Open the drawer, click the named vault's Open, unlock; return current_page."""
    client.call("click", target=S.Toolbar.VAULTS_BUTTON)
    client.call("click", target=S.VaultDrawer.open_button(name))
    client.wait_for(S.OpenVaultDialog.PASSCODE)
    client.call("type", target=S.OpenVaultDialog.PASSCODE, text=passcode)
    client.call("click", target=S.OpenVaultDialog.OPEN)
    client.wait_for(S.OpenVaultDialog.PASSCODE, condition="hidden")
    return client.call("current_page")


def open_designer(client) -> dict:
    """Click the designer plugin's nav entry; return the resulting current_page."""
    client.call("click", target=S.Designer.NAV_BUTTON)
    return client.call("current_page")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_actions.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tests/integration/driver/actions.py tests/integration/test_actions.py
git commit -m "feat(integration): add Layer 2 actions (create/open vault, open designer)"
```

---

## Task 10: Integration tests — vault lifecycle & designer smoke

**Files:**
- Create: `tests/integration/test_vault_lifecycle.py`
- Create: `tests/integration/test_designer_smoke.py`

These use the `ephemeral_wallet` fixture — isolated, pristine, auto-skipped when the app is absent.

- [ ] **Step 1: Write the vault lifecycle test**

Create `tests/integration/test_vault_lifecycle.py`:

```python
"""End-to-end vault lifecycle against an isolated ephemeral wallet."""
from driver import actions


def test_create_then_reopen_vault(ephemeral_wallet):
    client = ephemeral_wallet.client

    # Create a vault — it auto-opens into the identifiers page.
    page = actions.create_vault(client, "itvault", "secretpass")
    assert page.get("ok") is True
    assert page.get("vault_page")  # a vault sub-page is now active

    # The vault appears in the drawer's list.
    items = client.call("get_list_items", target="vaultDrawer.vaultList")
    assert any("itvault" in str(t) for t in items.get("items", []))
```

- [ ] **Step 2: Run it**

Run: `pytest tests/integration/test_vault_lifecycle.py -v -s`
Expected (app installed): 1 passed. (No app: skipped.)
If `get_list_items` returns an unexpected shape, inspect with `client.call("tree")` during the run and adjust the assertion to the actual key (`items` vs `texts`).

- [ ] **Step 3: Write the designer smoke test**

Create `tests/integration/test_designer_smoke.py`:

```python
"""Smoke test: the designer plugin loads and navigates in an isolated wallet."""
from driver import actions


def test_designer_nav_button_present_after_vault_open(ephemeral_wallet):
    client = ephemeral_wallet.client
    actions.create_vault(client, "dgnrvault", "secretpass")

    # The designer's main nav entry loaded (objectName set in plugin.py).
    count = client.call("count", target="designer.navButton")
    assert count.get("ok") is True
    assert count.get("count", 0) >= 1


def test_open_designer_navigates_to_a_designer_page(ephemeral_wallet):
    client = ephemeral_wallet.client
    actions.create_vault(client, "dgnrvault2", "secretpass")

    page = actions.open_designer(client)
    assert page.get("ok") is True
    assert str(page.get("vault_page", "")).startswith("designer.")
```

- [ ] **Step 4: Run it**

Run: `pytest tests/integration/test_designer_smoke.py -v -s`
Expected (app installed, designer clone carries the Task 8 objectName): 2 passed.
If `count` is 0, the running designer clone predates the objectName change — reinstall/upgrade it (see Task 8 Step 4). If `current_page` doesn't start with `designer.`, dump `client.call("current_page")` and `client.call("tree")` to see which page the nav entry lands on, and adjust.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_vault_lifecycle.py tests/integration/test_designer_smoke.py
git commit -m "test(integration): vault lifecycle + designer smoke tests"
```

---

## Task 11: Interactive CLI + README

**Files:**
- Create: `scripts/wallet.py`
- Create: `tests/integration/README.md`

- [ ] **Step 1: Write the interactive CLI**

Create `scripts/wallet.py`:

```python
#!/usr/bin/env python3
"""Drive the *running* Locksmith wallet from the shell, using the same driver
the integration tests use. Targets the default control socket.

Examples:
    python scripts/wallet.py create-vault automation noble
    python scripts/wallet.py open-vault automation noble
    python scripts/wallet.py open-designer
    python scripts/wallet.py screenshot /tmp/wallet.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the driver importable without installing anything.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "integration"))

from driver.client import Client  # noqa: E402
from driver import actions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Drive the running Locksmith wallet")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create-vault")
    p_create.add_argument("name")
    p_create.add_argument("passcode")

    p_open = sub.add_parser("open-vault")
    p_open.add_argument("name")
    p_open.add_argument("passcode")

    sub.add_parser("open-designer")

    p_shot = sub.add_parser("screenshot")
    p_shot.add_argument("path")

    args = parser.parse_args()
    client = Client()

    if args.cmd == "create-vault":
        result = actions.create_vault(client, args.name, args.passcode)
    elif args.cmd == "open-vault":
        result = actions.open_vault(client, args.name, args.passcode)
    elif args.cmd == "open-designer":
        result = actions.open_designer(client)
    elif args.cmd == "screenshot":
        result = client.call("screenshot", path=args.path)
    else:  # pragma: no cover
        parser.error(f"unknown command {args.cmd!r}")

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-test the CLI against the running wallet**

Run (with your wallet open): `python scripts/wallet.py screenshot /tmp/wallet-cli.png`
Expected: prints `{"ok": true, "path": "/tmp/wallet-cli.png", ...}`.
(If no wallet is running, it errors on connect — that's expected.)

- [ ] **Step 3: Write the README**

Create `tests/integration/README.md`:

````markdown
# Wallet UI integration harness

Drives the Locksmith wallet through the `locksmith-ui-tester` control socket.

## Layers (`driver/`)

- `client.py` — `Client(socket_path)`; `.call(op, **kwargs)`, `.wait_for(...)`, `.ping()`.
- `selectors.py` — page objects (objectName constants). **The selector cheatsheet.**
- `actions.py` — `create_vault`, `open_vault`, `open_designer`.
- `instance.py` — `EphemeralWallet` (throwaway-HOME instance) + `seed_plugin_home`.

## Running

```bash
pytest tests/integration            # integration tests (need /Applications/Locksmith.app)
pytest tests/integration/test_client.py tests/integration/test_actions.py  # headless unit tests
```

Integration tests auto-skip when the app (or a running wallet, for `running_wallet`)
is absent, so headless CI stays green.

## Interactive use

```bash
python scripts/wallet.py create-vault automation noble   # drives your already-open wallet
python scripts/wallet.py open-designer
```

## Available control ops

`ping`, `screenshot`, `tree`, `current_page`, `click`, `click_list_item`,
`click_table_row`, `click_row_action`, `type`, `select`, `get_text`, `is_checked`,
`is_visible`, `wait_for`, `count`, `get_list_items`, `get_table_rows`.

## Adding a page object

1. Open the wallet, navigate to the screen, run `client.call("tree")` (or
   `python scripts/wallet.py` + a one-off) to find `objectName`s. Cross-check the
   host source under `~/code/locksmith/src/locksmith/ui/`.
2. Add a class/constants to `driver/selectors.py` with the op each control needs.
3. Add a verb to `driver/actions.py` composing them, ending in a `wait_for`.
4. If a control has no `objectName`, add one in the owning source (as done for the
   designer nav buttons in `plugin.py`).
````

- [ ] **Step 4: Commit**

```bash
git add scripts/wallet.py tests/integration/README.md
git commit -m "feat(integration): interactive wallet CLI + harness README"
```

---

## Task 12: Final verification

- [ ] **Step 1: Full headless suite stays green**

Run: `pytest -q`
Expected: all prior 68 tests + the new headless unit tests pass; integration tests skip (unless an app/socket is present).

- [ ] **Step 2: Integration suite (on a machine with Locksmith)**

Run: `pytest tests/integration -v`
Expected: spike + lifecycle + designer smoke pass; throwaway wallet windows open and close; nothing left under `/tmp/ls-it-*`; your real `~/.keri` vaults untouched.

- [ ] **Step 3: Commit any fixups discovered during verification**

```bash
git add -A && git commit -m "test(integration): verification fixups"
```

---

## Self-Review

**Spec coverage:**
- Reusable driver over the socket → Tasks 2 (client), 7 (selectors), 9 (actions). ✓
- Living cheatsheet that can't go stale → `selectors.py` imported by actions + tests (Task 7). ✓
- Isolated, repeatable integration tests via ephemeral alt-HOME instance → Tasks 3–6, 10. ✓
- Seed plugins by symlink → `seed_plugin_home` (Task 3). ✓
- Headless CI/68 tests stay green; integration opt-in/self-skip → Task 5 fixtures, Task 12. ✓
- Interactive "make me a vault" path → `scripts/wallet.py` (Task 11). ✓
- `wait_for` not `sleep` in actions → Task 9. ✓
- `screenshot`-target fallback noted → README + spec; harness reads state via `tree`/`get_text`. ✓
- No-delete / LMDB-lock avoidance via `rm -rf` teardown → `EphemeralWallet.__exit__` (Task 4). ✓
- Growth path (add page object once) → README "Adding a page object" (Task 11). ✓
- Open items resolved: fixture scope = session (`ephemeral_wallet`, Task 5); driver placement = `tests/integration/driver/` (Task 1). ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. The two integration tests include explicit fallbacks (inspect `tree`/`current_page`) for shape mismatches rather than leaving behavior unspecified. ✓

**Type/name consistency:** `Client.call`/`wait_for`/`ping` used identically across actions, instance, conftest, CLI. Selector names (`Toolbar.VAULTS_BUTTON`, `CreateVaultDialog.PASSCODE`, `OpenVaultDialog.OPEN`, `Designer.NAV_BUTTON`, `VaultDrawer.open_button`) match between `selectors.py` (Task 7), `actions.py` (Task 9), and the tests. `seed_plugin_home`/`EphemeralWallet`/`LOCKSMITH_BINARY` consistent across Tasks 3–6. `designer.navButton` objectName set in Task 8 matches `Designer.NAV_BUTTON` and the smoke test. ✓

**Risk note:** The single real unknown is whether the copied `index.json` + symlinks suffice for the host to load the plugins in a fresh HOME (Task 6 spike). Task 6 Step 3 gives the debug path. Everything downstream depends only on a working socket, already proven for the running wallet.
