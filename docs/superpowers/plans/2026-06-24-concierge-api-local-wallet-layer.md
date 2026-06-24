# Concierge API — wallet layer (Plan 2 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the new `~/code/concierge-api` repo and its `concierge_api_local` library — a `ConciergePlugin` base (Locksmith `VaultPlugin` + `AccountProviderPlugin`) that binds to a vault AID, builds a `keri_serviceaid.LocalRuntime` (Plan 1), drives it from the wallet's loop, and exposes an AID-selector setup page — plus a worked Rating Engine example.

**Architecture:** A plugin author subclasses `ConciergePlugin`, sets `svc = ServiceAid(...)` with `@svc.command`s, and ships a `locksmith-plugin.toml`. A UI-free `BindingController` owns the lifecycle: pick/create the bound Service AID, ensure the declared credential, build a `LocalRuntime`, register its capture handlers on `vault.hby.exc`, ensure the bound AID's mailbox is polled by the vault's existing `vault.mbx`, and mount a `RuntimePumpDoer` (on `vault.doers`) that calls `runtime.process_captured()` each tick. Binding is a user-driven setup step via `AccountProviderPlugin` (not forced on vault open). The UI-free core is unit-tested headlessly; the Qt plugin + live flow are verified in the running wallet via the existing `locksmith-ui-tester` harness.

**Tech Stack:** Python 3.13+, PySide6 (Qt), keripy 2.0, `keri_serviceaid` (Plan 1, now on `seriouscoderone/keripy@development`), the `locksmith` host package. New repo at `~/code/concierge-api`; package `src/concierge_api_local/`.

**Prerequisite:** Plan 1 is merged (`keri_serviceaid` exports `LocalRuntime`, `CredentialReq`, `ServiceAid`, `Reply`, etc.). Install it into the same venv the wallet uses.

**Conventions:**
- All code lives in `~/code/concierge-api`. Run tests from there: `python -m pytest tests/ -v`.
- Headless unit tests use a `FakeVault` (a stub exposing `hby`, `rgy`, `plugin_state`, `doers`, `mbx`, `receiptor`) + a temp `Habery` — NO Qt, NO running wallet.
- Qt-touching tests import PySide6 and use `pytest-qt`'s `qtbot` if available, else a `QApplication` fixture; they assert construction + signals, not pixels.
- Live verification reuses the `locksmith-ui-tester` harness documented in this repo's CLAUDE.md.

---

## File Structure (the new `~/code/concierge-api` repo)

```
concierge-api/
├── locksmith-plugin.toml            # manifest: plugin_id, entry_point="concierge_api_local.example_plugin:RatingEnginePlugin"
├── pyproject.toml                   # package concierge_api_local; deps: keri_serviceaid, PySide6
├── README.md
├── src/concierge_api_local/
│   ├── __init__.py                  # exports ConciergePlugin, BindingController, Binding, AidSelectorPage
│   ├── binding.py                   # Binding, BindingStore (durable JSON), BindingController  — UI-FREE
│   ├── pump.py                      # RuntimePumpDoer(doing.Doer)                              — UI-FREE
│   ├── keys.py                      # page-key constants
│   ├── plugin.py                    # ConciergePlugin(VaultPlugin, AccountProviderPlugin) base — Qt
│   ├── pages/
│   │   ├── __init__.py
│   │   └── aid_selector.py          # AidSelectorPage(QWidget)                                 — Qt
│   └── example_plugin.py            # RatingEnginePlugin(ConciergePlugin) + schemas            — worked example
└── tests/
    ├── conftest.py                  # FakeVault + temp Habery + schema fixtures
    ├── test_binding_store.py
    ├── test_binding_controller.py
    ├── test_pump.py
    ├── test_aid_selector.py         # Qt (skips if PySide6 import fails)
    ├── test_plugin.py               # ConciergePlugin lifecycle w/ FakeVault
    └── integration/README.md        # how to live-verify via locksmith-ui-tester
```

**Responsibilities:** `binding.py` is the testable heart (no Qt, no host). `pump.py` is a one-class doer. `plugin.py` is thin glue over `BindingController`. `pages/aid_selector.py` is a dumb view driving the controller. `example_plugin.py` is the only place a concrete `ServiceAid` + schemas live.

---

### Task 1: Scaffold the `concierge-api` repo

**Files:**
- Create: `~/code/concierge-api/{pyproject.toml, locksmith-plugin.toml, README.md, .gitignore}`
- Create: `~/code/concierge-api/src/concierge_api_local/__init__.py`
- Create: `~/code/concierge-api/tests/test_smoke.py`

- [ ] **Step 1: Create the repo + package skeleton.**

```bash
mkdir -p ~/code/concierge-api/src/concierge_api_local/pages ~/code/concierge-api/tests/integration
cd ~/code/concierge-api && git init -q
printf '__pycache__/\n*.py[cod]\n.pytest_cache/\n*.egg-info/\nbuild/\ndist/\n' > .gitignore
```

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "concierge-api-local"
version = "0.1.0"
description = "Run a keri_serviceaid Service AID locally as a Locksmith plugin"
requires-python = ">=3.13"
dependencies = []          # keri, keri_serviceaid, PySide6, locksmith come from the wallet venv

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

`locksmith-plugin.toml`:
```toml
plugin_id = "concierge_rating_engine"
entry_point = "concierge_api_local.example_plugin:RatingEnginePlugin"
manifest_version = 1
name = "Rating Engine (Concierge)"
version = "0.1.0"
description = "An in-wallet Insurance Rating Engine Service AID built on concierge-api-local"
requires_locksmith = ">=0.0.1"
capabilities = ["app.ui"]
```

`src/concierge_api_local/__init__.py`:
```python
"""concierge-api-local — build a local (in-wallet) KERI Service AID as a Locksmith plugin."""
from .binding import Binding, BindingStore, BindingController
from .pump import RuntimePumpDoer

__all__ = ["Binding", "BindingStore", "BindingController", "RuntimePumpDoer"]
```
(The Qt symbols `ConciergePlugin`/`AidSelectorPage` are added to `__all__` in Tasks 6/5 — keep `__init__` import-light until then so headless tests don't import PySide6.)

- [ ] **Step 2: Write a smoke test** — `tests/test_smoke.py`:
```python
def test_package_imports():
    import concierge_api_local
    assert hasattr(concierge_api_local, "BindingController")
```

- [ ] **Step 3: Run it.** `cd ~/code/concierge-api && python -m pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'concierge_api_local.binding'` (binding.py doesn't exist yet). That's fine; it confirms the path wiring. (Tasks 2-3 create `binding.py`; re-run then.)

- [ ] **Step 4: Commit.**
```bash
cd ~/code/concierge-api && git add -A && git commit -m "chore: scaffold concierge-api repo + concierge_api_local package"
```

---

### Task 2: `Binding` + `BindingStore` (durable per-vault persistence)

The binding (which AID this plugin runs as + whether setup is done) must survive vault close/reopen, so it's a small JSON file — not `vault.plugin_state` (in-memory only).

**Files:**
- Create: `~/code/concierge-api/src/concierge_api_local/binding.py` (this task adds `Binding` + `BindingStore` only; `BindingController` is Task 3)
- Test: `tests/test_binding_store.py`

- [ ] **Step 1: Write the failing test** — `tests/test_binding_store.py`:
```python
from concierge_api_local.binding import Binding, BindingStore


def test_load_missing_returns_empty_binding(tmp_path):
    store = BindingStore(str(tmp_path / "concierge" / "b.json"))
    b = store.load()
    assert b == Binding(alias=None, setup_complete=False)


def test_save_then_load_roundtrips(tmp_path):
    store = BindingStore(str(tmp_path / "concierge" / "b.json"))
    store.save(Binding(alias="rating-engine", setup_complete=True))
    assert store.load() == Binding(alias="rating-engine", setup_complete=True)


def test_clear_removes_file(tmp_path):
    path = tmp_path / "concierge" / "b.json"
    store = BindingStore(str(path))
    store.save(Binding(alias="x", setup_complete=True))
    store.clear()
    assert not path.exists()
    assert store.load() == Binding()
```

- [ ] **Step 2: Run to verify it fails.** `python -m pytest tests/test_binding_store.py -v` → ImportError.

- [ ] **Step 3: Implement** — create `src/concierge_api_local/binding.py`:
```python
"""Binding persistence + controller for a local Concierge (Service-AID plugin).

UI-free and host-light: imports keri_serviceaid (for LocalRuntime) and keripy, but
NO PySide6 and NO locksmith. The `vault` it's handed is duck-typed (see FakeVault in
tests): it needs `.hby`, `.rgy`, `.plugin_state`, `.doers`, and (at start) `.mbx`."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict


@dataclass
class Binding:
    alias: str | None = None        # bound Service-AID alias (None = unbound)
    setup_complete: bool = False


class BindingStore:
    """Durable per-vault binding as a JSON file (survives vault close/reopen)."""

    def __init__(self, path: str):
        self.path = path

    def load(self) -> Binding:
        if not os.path.exists(self.path):
            return Binding()
        with open(self.path, encoding="utf-8") as f:
            return Binding(**json.load(f))

    def save(self, binding: Binding) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(asdict(binding), f)

    def clear(self) -> None:
        if os.path.exists(self.path):
            os.remove(self.path)
```

- [ ] **Step 4: Run to verify it passes.** `python -m pytest tests/test_binding_store.py -v` → 3 passed.

- [ ] **Step 5: Commit.**
```bash
cd ~/code/concierge-api && git add -A && git commit -m "feat: Binding + BindingStore (durable per-vault binding persistence)"
```

---

### Task 3: `BindingController` (the UI-free lifecycle core)

Owns: list/bind the Service AID, check the declared credential, `is_complete`, build + start the `LocalRuntime`, stop, purge. Witnessed AID *creation* is deferred to Task 7 (needs the running vault); this task covers binding to an **existing** hab.

**Files:**
- Modify: `src/concierge_api_local/binding.py` (add `BindingController`)
- Test: `tests/conftest.py` (add fixtures), `tests/test_binding_controller.py`

- [ ] **Step 1: Add test fixtures** — `tests/conftest.py`:
```python
"""Headless fixtures: a temp Habery, a registered schema, and a FakeVault stub."""
import os
import sys
import tempfile

import pytest

os.environ.setdefault("HOME", tempfile.mkdtemp(prefix="concierge-test-"))

from keri.app.habbing import Habery
from keri.core.signing import Salter
from keri.core import scheming
from keri.kering import Kinds
from keri.vdr import credentialing


BROKER_SCHEMA_SAD = {
    "$id": "", "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "BrokerLicense", "type": "object",
    "properties": {"v": {"type": "string"}, "d": {"type": "string"},
                   "i": {"type": "string"}, "ri": {"type": "string"},
                   "s": {"type": "string"},
                   "a": {"oneOf": [{"type": "string"},
                         {"type": "object",
                          "properties": {"d": {"type": "string"}, "i": {"type": "string"},
                                         "dt": {"type": "string", "format": "date-time"},
                                         "license": {"type": "string"}},
                          "additionalProperties": False,
                          "required": ["d", "i", "dt", "license"]}]}},
    "additionalProperties": False, "required": ["v", "d", "i", "ri", "s", "a"]}


@pytest.fixture
def hby():
    h = Habery(name="wallet", temp=True, salt=Salter(raw=b'0123456789abcdef').qb64)
    yield h
    h.close()


@pytest.fixture
def rgy(hby):
    return credentialing.Regery(hby=hby, name="wallet", temp=True)


class FakeVault:
    """Duck-typed stand-in for locksmith.core.vaulting.Vault."""
    def __init__(self, hby, rgy):
        self.hby = hby
        self.rgy = rgy
        self.plugin_state = {}
        self.doers = []
        self.mbx = None          # set in tests that exercise start()
        self.receiptor = None


@pytest.fixture
def vault(hby, rgy):
    return FakeVault(hby, rgy)


@pytest.fixture
def broker_schema(hby):
    schemer = scheming.Schemer(sed=dict(BROKER_SCHEMA_SAD), kind=Kinds.json)
    hby.db.schema.pin(keys=(schemer.said,), val=schemer)
    return schemer.said
```

- [ ] **Step 2: Write the failing test** — `tests/test_binding_controller.py`:
```python
from keri_serviceaid import ServiceAid, Reply, CredentialReq, IpexGrantIssuer

from concierge_api_local.binding import BindingController


def _svc():
    svc = ServiceAid(alias="rating-engine")

    @svc.command(route="/ping")
    def ping(req):
        return Reply.none()
    return svc


def test_candidate_aids_lists_vault_habs(vault):
    vault.hby.makeHab(name="alice")
    vault.hby.makeHab(name="bob")
    ctl = BindingController(vault, _svc(), role_name="rating-engine",
                            store_path=vault.plugin_state.get("p", "/tmp/cc-test/b.json"))
    assert set(ctl.candidate_aids()) >= {"alice", "bob"}


def test_bind_existing_then_complete_when_no_credential_required(vault, tmp_path):
    vault.hby.makeHab(name="rating-engine")
    ctl = BindingController(vault, _svc(), role_name="rating-engine",
                            store_path=str(tmp_path / "b.json"))
    assert ctl.is_complete() is False           # nothing bound yet
    ctl.bind_existing("rating-engine")
    assert ctl.is_complete() is True            # bound + no credential required
    # persisted
    ctl2 = BindingController(vault, _svc(), role_name="rating-engine",
                             store_path=str(tmp_path / "b.json"))
    assert ctl2.bound_hab() is not None


def test_is_incomplete_until_required_credential_present(vault, tmp_path, broker_schema):
    hab = vault.hby.makeHab(name="rating-engine")
    svc = ServiceAid(alias="rating-engine")

    @svc.command(route="/rate", requires_credential=CredentialReq(schema=broker_schema))
    def rate(req):
        return Reply.none()

    ctl = BindingController(vault, svc, role_name="rating-engine",
                            requires_credential=CredentialReq(schema=broker_schema),
                            store_path=str(tmp_path / "b.json"))
    ctl.bind_existing("rating-engine")
    assert ctl.is_complete() is False           # bound but credential missing

    # admit a broker credential to the bound hab (issued into the vault's reger)
    IpexGrantIssuer()._issue_grant(
        vault.hby, hab, vault.rgy, schema_said=broker_schema, recipient=hab.pre,
        attributes={"license": "B-1"}, registry_name="wallet")
    assert ctl.is_complete() is True            # now the credential is held
```

- [ ] **Step 3: Run to verify it fails.** `python -m pytest tests/test_binding_controller.py -v` → ImportError / AttributeError.

- [ ] **Step 4: Implement** — append to `src/concierge_api_local/binding.py`:
```python
class BindingController:
    """UI-free lifecycle for a local Concierge: pick/bind the Service AID, ensure the
    declared credential, build + run a LocalRuntime, stop/purge. Witnessed AID CREATION
    is added in Task 7; this binds to an existing vault hab. `vault` is duck-typed."""

    def __init__(self, vault, svc, *, role_name, requires_credential=None,
                 store_path):
        self.vault = vault
        self.svc = svc
        self.role_name = role_name
        self.requires_credential = requires_credential
        self.store = BindingStore(store_path)
        self.binding = self.store.load()
        self.runtime = None
        self._doers: list = []

    # --- queries -------------------------------------------------------------
    def candidate_aids(self) -> list[str]:
        return [hab.name for hab in self.vault.hby.habs.values()]

    def bound_hab(self):
        if not self.binding.alias:
            return None
        return self.vault.hby.habByName(self.binding.alias)

    def credential_present(self) -> bool:
        if self.requires_credential is None:
            return True
        hab = self.bound_hab()
        if hab is None:
            return False
        reger = self.vault.rgy.reger
        schema_saids = {s.qb64 for s in reger.schms.get(
            keys=self.requires_credential.schema.encode("utf-8"))}
        for saider in reger.subjs.get(keys=hab.pre.encode("utf-8")):
            if saider.qb64 in schema_saids and reger.saved.get(keys=saider.qb64) is not None:
                return True
        return False

    def is_complete(self) -> bool:
        return self.bound_hab() is not None and self.credential_present()

    # --- mutations -----------------------------------------------------------
    def bind_existing(self, alias: str) -> None:
        self.binding.alias = alias
        self.binding.setup_complete = self.is_complete()
        self.store.save(self.binding)

    def start(self) -> None:
        """Build the LocalRuntime for the bound hab and mount it on the vault loop."""
        from keri_serviceaid import LocalRuntime  # local import keeps module light
        from .pump import RuntimePumpDoer

        hab = self.bound_hab()
        if hab is None or self.runtime is not None:
            return
        self.runtime = LocalRuntime(self.svc, hby=self.vault.hby, hab=hab,
                                    rgy=self.vault.rgy)
        # Inbound: ensure the bound hab's mailbox is polled by the vault's existing
        # MailboxDirector (do NOT spin up a second one). The capture handlers are
        # already registered on vault.hby.exc by LocalRuntime.__init__.
        self._ensure_mailbox_polled(hab)
        # Drive the pipeline each tick.
        pump = RuntimePumpDoer(self.runtime)
        self._doers = [pump]
        self.vault.doers.extend(self._doers)

    def _ensure_mailbox_polled(self, hab) -> None:
        """Add the bound hab to the vault's MailboxDirector if it exposes add_poller.
        Best-effort: the host may already poll all vault habs. (Exact add_poller
        signature / mailbox-eid resolution is verified against locksmith at execution.)"""
        mbx = getattr(self.vault, "mbx", None)
        if mbx is None or not hasattr(mbx, "add_poller"):
            return
        wits = getattr(hab.kever, "wits", []) or []
        for eid in wits:
            try:
                mbx.add_poller(hab, eid)
            except Exception:
                pass

    def stop(self) -> None:
        for d in self._doers:
            try:
                self.vault.doers.remove(d)
            except ValueError:
                pass
        self._doers = []
        if self.runtime is not None:
            led = getattr(self.runtime.svc, "idempotency", None)
            if led is not None and hasattr(led, "close"):
                led.close()
        self.runtime = None

    def purge(self) -> None:
        self.stop()
        self.store.clear()
        self.binding = Binding()
```

- [ ] **Step 5: Run to verify it passes.** `python -m pytest tests/test_binding_controller.py -v` → 3 passed. (If `_issue_grant` needs an escrow pump for the credential to land in `reger.saved`, add `vault.rgy.processEscrows()` after the call — same lesson as Plan 1 Task 8.)

- [ ] **Step 6: Commit.**
```bash
cd ~/code/concierge-api && git add -A && git commit -m "feat: BindingController — bind/credential-check/start/stop/purge (UI-free)"
```

---

### Task 4: `RuntimePumpDoer`

A periodic `doing.Doer` (matching Locksmith's `NotificationToastDoer` pattern) that calls `runtime.process_captured()` each tick.

**Files:**
- Create: `src/concierge_api_local/pump.py`
- Test: `tests/test_pump.py`

- [ ] **Step 1: Write the failing test** — `tests/test_pump.py`:
```python
from concierge_api_local.pump import RuntimePumpDoer


class FakeRuntime:
    def __init__(self):
        self.pumps = 0

    def process_captured(self):
        self.pumps += 1


def test_pump_calls_process_captured_on_recur():
    rt = FakeRuntime()
    doer = RuntimePumpDoer(rt)
    assert doer.tock == 1.0
    result = doer.recur(tyme=0.0)
    assert rt.pumps == 1
    assert result is False          # keep running
```

- [ ] **Step 2: Run to verify it fails.** `python -m pytest tests/test_pump.py -v` → ImportError.

- [ ] **Step 3: Implement** — create `src/concierge_api_local/pump.py`:
```python
"""RuntimePumpDoer — drives LocalRuntime.process_captured() on the vault's Doist.

The vault's MailboxDirector fills hby.exc; the LocalRuntime's capture handlers buffer
verified command exns; this doer drains+processes them each tick. Matches Locksmith's
periodic-Doer pattern (e.g. NotificationToastDoer)."""
from __future__ import annotations

from hio.base import doing


class RuntimePumpDoer(doing.Doer):
    def __init__(self, runtime, tock=1.0, **kwa):
        super().__init__(tock=tock, **kwa)
        self.runtime = runtime

    def recur(self, tyme):
        self.runtime.process_captured()
        return False        # False = keep running
```

- [ ] **Step 4: Run to verify it passes.** `python -m pytest tests/test_pump.py -v` → 1 passed.

- [ ] **Step 5: Commit.**
```bash
cd ~/code/concierge-api && git add -A && git commit -m "feat: RuntimePumpDoer drives process_captured on the vault loop"
```

---

### Task 5: `keys.py` + mock `AidSelectorPage`

The reusable setup page (mock first, per the spec's de-risking deliverable): lists candidate AIDs + a "create dedicated" action, shows credential status, and drives the controller. Dumb view — all logic is in `BindingController`.

**Files:**
- Create: `src/concierge_api_local/keys.py`, `src/concierge_api_local/pages/__init__.py`, `src/concierge_api_local/pages/aid_selector.py`
- Test: `tests/test_aid_selector.py`

- [ ] **Step 1: Page keys** — `src/concierge_api_local/keys.py`:
```python
"""Page-key constants registered with the host VaultPage."""
SETUP_PAGE = "concierge.setup"
CONCIERGE_PAGE = "concierge.main"
```

- [ ] **Step 2: Write the failing test** — `tests/test_aid_selector.py`:
```python
import pytest

pytest.importorskip("PySide6")     # skip headless CI without Qt

from PySide6.QtWidgets import QApplication
from concierge_api_local.pages.aid_selector import AidSelectorPage


class FakeController:
    def __init__(self):
        self.bound = None
        self._aids = ["alice", "rating-engine"]

    def candidate_aids(self):
        return self._aids

    def bind_existing(self, alias):
        self.bound = alias

    def is_complete(self):
        return self.bound is not None


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_lists_candidate_aids(app):
    ctl = FakeController()
    page = AidSelectorPage(controller=ctl)
    page.refresh()
    assert set(page.listed_aids()) == {"alice", "rating-engine"}


def test_selecting_an_aid_binds_via_controller(app):
    ctl = FakeController()
    page = AidSelectorPage(controller=ctl)
    page.refresh()
    page.select_aid("rating-engine")     # mock action (no real click needed)
    assert ctl.bound == "rating-engine"
```

- [ ] **Step 3: Run to verify it fails.** `python -m pytest tests/test_aid_selector.py -v` → ImportError.

- [ ] **Step 4: Implement** — `src/concierge_api_local/pages/__init__.py` (empty) and `src/concierge_api_local/pages/aid_selector.py`:
```python
"""AidSelectorPage — the Concierge setup page (mock).

A dumb QWidget view over a BindingController: lists candidate vault AIDs, lets the
user pick one (or, later, create a dedicated one), and shows credential status. All
decisions live in the controller; this page only renders + forwards intent."""
from __future__ import annotations

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QPushButton)


class AidSelectorPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("concierge.aidSelectorPage")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose the AID this Concierge runs as:"))
        self._list = QListWidget()
        self._list.setObjectName("concierge.aidList")
        self._list.itemClicked.connect(lambda item: self.select_aid(item.text()))
        layout.addWidget(self._list)
        self._status = QLabel("")
        self._status.setObjectName("concierge.setupStatus")
        layout.addWidget(self._status)

    # --- view API (also the test seam) --------------------------------------
    def refresh(self) -> None:
        self._list.clear()
        for alias in self.controller.candidate_aids():
            self._list.addItem(QListWidgetItem(alias))
        self._update_status()

    def listed_aids(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def select_aid(self, alias: str) -> None:
        self.controller.bind_existing(alias)
        self._update_status()

    def on_show(self) -> None:           # host convention (kerifoundation-style)
        self.refresh()

    def _update_status(self) -> None:
        self._status.setText("Ready" if self.controller.is_complete()
                             else "Setup incomplete — pick an AID")
```

- [ ] **Step 5: Run to verify it passes.** `python -m pytest tests/test_aid_selector.py -v` → 2 passed (or skipped if PySide6 unavailable).

- [ ] **Step 6: Commit.**
```bash
cd ~/code/concierge-api && git add -A && git commit -m "feat: mock AidSelectorPage (setup view over BindingController) + page keys"
```

---

### Task 6: `ConciergePlugin` base (VaultPlugin + AccountProviderPlugin)

Thin glue: owns a `BindingController`, registers pages, routes setup via `AccountProviderPlugin`, mounts doers when bound. Subclasses set `svc`, `role_name`, `plugin_id`, `requires_credential`.

**Files:**
- Create: `src/concierge_api_local/plugin.py`
- Modify: `src/concierge_api_local/__init__.py` (export `ConciergePlugin`, `AidSelectorPage`)
- Test: `tests/test_plugin.py`

- [ ] **Step 1: Write the failing test** — `tests/test_plugin.py`:
```python
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("locksmith")       # the host base classes

from keri_serviceaid import ServiceAid, Reply, CredentialReq
from concierge_api_local.plugin import ConciergePlugin
from concierge_api_local import keys


class _Rating(ConciergePlugin):
    plugin_id = "concierge_rating_engine"
    role_name = "rating-engine"

    def build_service(self):
        svc = ServiceAid(alias="rating-engine")

        @svc.command(route="/ping")
        def ping(req):
            return Reply.none()
        return svc


def test_is_setup_complete_false_before_binding(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    plugin = _Rating()
    plugin.on_vault_opened(vault)
    assert plugin.is_setup_complete(vault) is False


def test_get_setup_page_returns_setup_key(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    plugin = _Rating()
    plugin.on_vault_opened(vault)
    page_key, push_menu = plugin.get_setup_page(vault)
    assert page_key == keys.SETUP_PAGE
    assert push_menu is True


def test_binding_makes_setup_complete_and_starts_runtime(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    vault.hby.makeHab(name="rating-engine")
    plugin = _Rating()
    plugin.on_vault_opened(vault)
    plugin.controller.bind_existing("rating-engine")
    plugin.controller.start()
    assert plugin.is_setup_complete(vault) is True
    assert plugin.controller.runtime is not None
    assert len(vault.doers) >= 1            # pump doer mounted
```

- [ ] **Step 2: Run to verify it fails.** `python -m pytest tests/test_plugin.py -v` → ImportError (or skip if locksmith/PySide6 absent).

- [ ] **Step 3: Implement** — create `src/concierge_api_local/plugin.py`:
```python
"""ConciergePlugin — Locksmith plugin base for a local Service AID.

Subclass it: set `plugin_id`, `role_name`, optional `requires_credential`, and
implement `build_service()` returning a keri_serviceaid.ServiceAid. The base owns a
BindingController, registers the setup + main pages, routes setup via
AccountProviderPlugin, and starts the runtime once bound."""
from __future__ import annotations

import os

from PySide6.QtWidgets import QWidget, QLabel

from locksmith.plugins.base import VaultPlugin, AccountProviderPlugin

from .binding import BindingController
from .pages.aid_selector import AidSelectorPage
from . import keys


class ConciergePlugin(VaultPlugin, AccountProviderPlugin):
    # --- subclass contract ---------------------------------------------------
    plugin_id: str = "concierge"
    role_name: str = "concierge"
    requires_credential = None          # a keri_serviceaid.CredentialReq, or None

    def build_service(self):
        raise NotImplementedError("subclass must return a ServiceAid")

    # --- PluginCore ----------------------------------------------------------
    def initialize(self, app):
        self._app = app
        self._pages = {keys.SETUP_PAGE: QWidget(),       # placeholders until vault opens
                       keys.CONCIERGE_PAGE: QWidget()}
        self.controller = None

    # --- VaultPlugin ---------------------------------------------------------
    def on_vault_opened(self, vault):
        store_path = os.path.join(vault.hby.db.path, "..", "concierge",
                                  f"{self.plugin_id}.json")
        self.controller = BindingController(
            vault, self.build_service(), role_name=self.role_name,
            requires_credential=self.requires_credential, store_path=store_path)
        # Build real pages and re-register them (placeholder swap).
        setup = AidSelectorPage(controller=self.controller)
        main = QLabel(f"{self.role_name} concierge running")
        self._pages[keys.SETUP_PAGE] = setup
        self._pages[keys.CONCIERGE_PAGE] = main
        vault_page = getattr(self._app, "_vault_page", None)
        if vault_page is not None:
            vault_page.register_page(keys.SETUP_PAGE, setup)
            vault_page.register_page(keys.CONCIERGE_PAGE, main)
        if self.controller.is_complete():
            self.controller.start()

    def on_vault_closed(self, vault, *, clear=False):
        if self.controller is not None:
            self.controller.purge() if clear else self.controller.stop()
        self.controller = None

    def get_pages(self):
        return dict(self._pages)

    def get_doers(self):
        # Doers are mounted by controller.start() (it appends to vault.doers); nothing
        # extra to return here. (start() runs in on_vault_opened when already bound.)
        return []

    def get_menu_entry(self):
        from locksmith.ui.vault.menu import MenuButton
        button = MenuButton(label=self.role_name.title())
        button.setObjectName(f"{self.plugin_id}.navButton")
        return button

    def get_menu_section(self):
        return []

    # --- AccountProviderPlugin ----------------------------------------------
    def is_setup_complete(self, vault) -> bool:
        return self.controller is not None and self.controller.is_complete()

    def get_setup_page(self, vault):
        return keys.SETUP_PAGE, True
```

- [ ] **Step 4: Export** — update `src/concierge_api_local/__init__.py` to also export the Qt symbols, guarded so headless imports still work:
```python
from .binding import Binding, BindingStore, BindingController
from .pump import RuntimePumpDoer

__all__ = ["Binding", "BindingStore", "BindingController", "RuntimePumpDoer"]

try:                                  # Qt + host present (in the wallet)
    from .plugin import ConciergePlugin
    from .pages.aid_selector import AidSelectorPage
    __all__ += ["ConciergePlugin", "AidSelectorPage"]
except Exception:                     # headless/CI without PySide6 or locksmith
    pass
```

- [ ] **Step 5: Run to verify it passes.** `python -m pytest tests/test_plugin.py -v` → 3 passed (or skipped without PySide6/locksmith). NOTE: if `vault.hby.db.path` based `store_path` is awkward in tests, the test's `FakeVault.hby` is a temp Habery so `db.path` resolves; adjust the join if needed and report.

- [ ] **Step 6: Commit.**
```bash
cd ~/code/concierge-api && git add -A && git commit -m "feat: ConciergePlugin base (VaultPlugin + AccountProviderPlugin)"
```

---

### Task 7: Dedicated-AID creation (witnessed) in `BindingController`

Add `create_dedicated()` so setup can mint a fresh witnessed Service AID (named `role_name`) via Locksmith's `InceptDoer` + `vault.receiptor`, not just bind an existing one. Witnessed inception needs the running vault + witnesses, so this is verified in the wallet (Task 9), with a unit test for the unwitnessed/no-wits path.

**Files:**
- Modify: `src/concierge_api_local/binding.py`
- Test: `tests/test_binding_controller.py` (add an unwitnessed-create test)

- [ ] **Step 1: Write the failing test** — append to `tests/test_binding_controller.py`:
```python
def test_create_dedicated_unwitnessed_binds_new_hab(vault, tmp_path):
    ctl = BindingController(vault, _svc(), role_name="rating-engine",
                            store_path=str(tmp_path / "b.json"))
    assert vault.hby.habByName("rating-engine") is None
    ctl.create_dedicated(wits=[], toad=0)      # no witnesses -> synchronous, no receipting
    assert vault.hby.habByName("rating-engine") is not None
    assert ctl.bound_hab() is not None
    assert ctl.binding.alias == "rating-engine"
```

- [ ] **Step 2: Run to verify it fails.** `python -m pytest tests/test_binding_controller.py -v -k create_dedicated` → AttributeError.

- [ ] **Step 3: Implement** — add to `BindingController` in `binding.py`:
```python
    def create_dedicated(self, *, wits=None, toad=0, salt=None) -> None:
        """Create a fresh transferable Service AID named role_name and bind to it.

        With witnesses, real deployments route through Locksmith's InceptDoer +
        vault.receiptor for witness receipting (driven on the vault loop — see Task 9
        / the live harness). The unwitnessed path (wits=[]) completes synchronously
        via hby.makeHab and is what the unit test exercises."""
        wits = wits or []
        if not wits:
            self.vault.hby.makeHab(name=self.role_name, transferable=True,
                                   wits=[], toad=0,
                                   isith="1", icount=1, nsith="1", ncount=1)
            self.bind_existing(self.role_name)
            return
        # Witnessed path: hand off to the host's InceptDoer (it uses vault.receiptor,
        # NOT WitnessReceiptor). Imported lazily so headless tests don't need locksmith.
        from locksmith.core.habbing import InceptDoer
        incept = InceptDoer(app=self.vault.app, alias=self.role_name,
                            signal_bridge=getattr(self.vault, "signals", None),
                            algo="salty", transferable=True, wits=wits, toad=str(toad),
                            salt=salt, icount=1, isith=1, ncount=1, nsith=1)
        self.vault.doers.extend([incept])
        # Completion is asynchronous on the vault loop; bind once the hab appears.
        # The setup page polls is_complete()/bound_hab() after kicking this off.
```

> Execution note: the exact `InceptDoer` kwargs are taken from `locksmith/core/habbing.py:479-491` — verify them against the installed host and adjust (the unit test only covers the `wits=[]` branch, which doesn't import locksmith).

- [ ] **Step 4: Run to verify it passes.** `python -m pytest tests/test_binding_controller.py -v -k create_dedicated` → 1 passed.

- [ ] **Step 5: Commit.**
```bash
cd ~/code/concierge-api && git add -A && git commit -m "feat: BindingController.create_dedicated (witnessed via host InceptDoer; unwitnessed synchronous)"
```

---

### Task 8: Rating Engine example plugin

The worked example + the installable plugin's entry point. A `ConciergePlugin` subclass with a real `/rate` command gated by a broker credential, issuing a Quote.

**Files:**
- Create: `src/concierge_api_local/example_plugin.py`
- Test: `tests/test_example_plugin.py`

- [ ] **Step 1: Write the failing test** — `tests/test_example_plugin.py`:
```python
from keri_serviceaid import ServiceAid, CredentialReq
from concierge_api_local.example_plugin import (RatingEnginePlugin,
                                                 BROKER_SCHEMA_SAD, QUOTE_SCHEMA_SAD)


def test_plugin_id_matches_manifest():
    assert RatingEnginePlugin.plugin_id == "concierge_rating_engine"


def test_build_service_declares_gated_rate_command():
    svc = RatingEnginePlugin().build_service()
    assert isinstance(svc, ServiceAid)
    cmd = svc.lookup("/rate")
    assert cmd is not None
    assert isinstance(cmd.requires_credential, CredentialReq)
```

- [ ] **Step 2: Run to verify it fails.** `python -m pytest tests/test_example_plugin.py -v` → ImportError.

- [ ] **Step 3: Implement** — create `src/concierge_api_local/example_plugin.py`:
```python
"""RatingEnginePlugin — the worked Concierge example + the installable entry point.

Receives a Risk Profile on /rate (gated by a broker-license credential) and returns
a signed Quote ACDC. The schemas are illustrative, not a real insurance model."""
from __future__ import annotations

from keri.core import scheming
from keri.kering import Kinds

from keri_serviceaid import ServiceAid, Reply, CredentialReq

from .plugin import ConciergePlugin


BROKER_SCHEMA_SAD = {
    "$id": "", "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "BrokerLicense", "type": "object",
    "properties": {"v": {"type": "string"}, "d": {"type": "string"},
                   "i": {"type": "string"}, "ri": {"type": "string"},
                   "s": {"type": "string"},
                   "a": {"oneOf": [{"type": "string"},
                         {"type": "object",
                          "properties": {"d": {"type": "string"}, "i": {"type": "string"},
                                         "dt": {"type": "string", "format": "date-time"},
                                         "license": {"type": "string"}},
                          "additionalProperties": False,
                          "required": ["d", "i", "dt", "license"]}]}},
    "additionalProperties": False, "required": ["v", "d", "i", "ri", "s", "a"]}

QUOTE_SCHEMA_SAD = {
    "$id": "", "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "PremiumQuote", "type": "object",
    "properties": {"v": {"type": "string"}, "d": {"type": "string"},
                   "i": {"type": "string"}, "ri": {"type": "string"},
                   "s": {"type": "string"},
                   "a": {"oneOf": [{"type": "string"},
                         {"type": "object",
                          "properties": {"d": {"type": "string"}, "i": {"type": "string"},
                                         "dt": {"type": "string", "format": "date-time"},
                                         "premium": {"type": "number"}},
                          "additionalProperties": False,
                          "required": ["d", "i", "dt", "premium"]}]}},
    "additionalProperties": False, "required": ["v", "d", "i", "ri", "s", "a"]}


def _said(sad: dict) -> str:
    return scheming.Schemer(sed=dict(sad), kind=Kinds.json).said


BROKER_SCHEMA_SAID = _said(BROKER_SCHEMA_SAD)
QUOTE_SCHEMA_SAID = _said(QUOTE_SCHEMA_SAD)


class RatingEnginePlugin(ConciergePlugin):
    plugin_id = "concierge_rating_engine"
    role_name = "rating-engine"
    requires_credential = CredentialReq(schema=BROKER_SCHEMA_SAID)

    def build_service(self) -> ServiceAid:
        svc = ServiceAid(alias=self.role_name)

        @svc.command(route="/rate", issues=QUOTE_SCHEMA_SAID,
                     requires_credential=CredentialReq(schema=BROKER_SCHEMA_SAID))
        def rate(req):
            coverage = req.payload.get("coverage", "unknown")
            premium = 100.0 if coverage == "auto" else 250.0   # illustrative
            return Reply.acdc(recipient=req.sender,
                              attributes={"i": req.sender, "premium": premium})
        return svc
```

- [ ] **Step 4: Run to verify it passes.** `python -m pytest tests/test_example_plugin.py -v` → 2 passed.

- [ ] **Step 5: Commit.**
```bash
cd ~/code/concierge-api && git add -A && git commit -m "feat: RatingEnginePlugin worked example + installable entry point"
```

---

### Task 9: Live verification via the locksmith-ui-tester harness

The Qt plugin lifecycle, witnessed AID creation, and the full present-then-cache round-trip can't be unit-tested headlessly — they're verified in the running wallet using the harness in `~/code/locksmith-micro-app-designer/tests/integration/`.

**Files:**
- Create: `~/code/concierge-api/tests/integration/README.md`

- [ ] **Step 1: Install the example plugin into the dev wallet.** Document + run:
```bash
# Install concierge-api-local into the wallet venv, then register the plugin clone.
pip install -e ~/code/concierge-api
# Reinstall/upgrade the plugin from the wallet's Plugins page, or sync the clone:
cp -R ~/code/concierge-api ~/.locksmith/plugins/concierge_rating_engine
```

- [ ] **Step 2: Write the verification runbook** — `tests/integration/README.md` documenting these steps (each driven via the `python -m locksmith_ui_tester.cli` socket client per the designer repo's CLAUDE.md):
  1. Launch `/Applications/Locksmith.app`; wait for `~/.locksmith-control.sock`.
  2. Create/open a vault (`create_vault` / `open_vault`).
  3. Click the Rating Engine plugin nav entry → host routes to the **setup page** (`is_setup_complete` is False).
  4. On the setup page, pick an existing AID (or create dedicated) → `bind_existing`/`create_dedicated` runs; `is_setup_complete` flips True; the runtime starts (a `RuntimePumpDoer` appears in `vault.doers`).
  5. Re-click the plugin → now routes to the **concierge page** (not setup).
  6. (Full round-trip, manual) From a second wallet/AID: present a broker credential to the Rating Engine AID via IPEX grant, then send a `/rate` command exn; confirm a signed Quote ACDC arrives back in the requester's mailbox.

- [ ] **Step 3: Execute steps 1-5 against the running wallet** (step 6 is a documented manual check — note it as such; do not block on it). Capture a screenshot of the setup page and the post-bind concierge page via the tester's `screenshot` op.

- [ ] **Step 4: Commit the runbook.**
```bash
cd ~/code/concierge-api && git add -A && git commit -m "docs(integration): locksmith-ui-tester runbook for the Concierge plugin"
```

---

### Task 10: Full-suite regression + final review

- [ ] **Step 1: Run the whole headless suite.** `cd ~/code/concierge-api && python -m pytest tests/ -v`
Expected: all pass (Qt/host-dependent tests skip cleanly where PySide6/locksmith are absent; they run in the wallet venv).

- [ ] **Step 2: Confirm the public API imports** (headless): `python -c "from concierge_api_local import BindingController, Binding, RuntimePumpDoer; print('ok')"` → `ok`.

- [ ] **Step 3: Dispatch a final whole-implementation review** (per subagent-driven-development) over `git log --oneline` of the new repo, focusing on: the BindingController lifecycle (start/stop/purge correctness, the mailbox-polling seam, idempotency-ledger close on stop), the plugin's page-swap lifecycle, and whether the example + runbook actually prove the loop. Fix findings, then finish the branch.

---

## Self-Review

**Spec coverage (`2026-06-23-concierge-api-local-runtime-design.md`):**
- §3 "adapter + plugin base" library → the `concierge_api_local` package (Tasks 1-8). ✅
- §6.2 `ConciergePlugin` base (VaultPlugin + AccountProviderPlugin) → Task 6. ✅
- §6.2 UI-free `BindingController` → Tasks 3, 7. ✅
- §6.2 reusable `AidSelectorPage` (mock-first deliverable) → Task 5. ✅
- §6.2 Rating Engine worked example → Task 8. ✅
- §7/§8 AID-binding via the setup hook (not on_vault_opened); credential gate / present-then-cache → Task 3 `credential_present` + the LocalRuntime's `CredentialGate` from Plan 1; the live round-trip → Task 9. ✅
- §10 lifecycle (setup-page binding, restore-on-open, teardown, clear=purge, mailbox polling scoped to the bound hab) → Tasks 3 (`stop`/`purge`, `_ensure_mailbox_polled`), 6 (`on_vault_opened`/`on_vault_closed`). ✅ (Addresses Plan 1 final-review notes: scope polling to the bound hab; own LocalRuntime teardown — `stop()` closes the idempotency ledger and removes doers.)
- §12 testing: headless unit tests for the UI-free core + the ui-tester harness for the live flow → Tasks 2-8 + Task 9. ✅
- **Deferred (not this plan):** the AI skill (separate follow-up); the cloud→`concierge-api` fold-in.

**Placeholder scan:** No TBD/TODO. Two tasks (7, 9) carry explicit *execution-verification* notes (the `InceptDoer` kwargs and the `vault.mbx.add_poller` signature are taken from the host source and confirmed at run time; the witnessed-inception and full round-trip are live-wallet checks, not headless) — these are real, scoped instructions, consistent with how Plan 1's plan code was verified during execution.

**Type consistency:** `Binding(alias, setup_complete)`, `BindingStore(path).{load,save,clear}`, `BindingController(vault, svc, *, role_name, requires_credential=None, store_path)` with `.candidate_aids/.bound_hab/.credential_present/.is_complete/.bind_existing/.create_dedicated/.start/.stop/.purge/.runtime`, `RuntimePumpDoer(runtime, tock=1.0).recur`, `AidSelectorPage(controller).{refresh,listed_aids,select_aid,on_show}`, `ConciergePlugin` with `plugin_id/role_name/requires_credential/build_service` + the VaultPlugin/AccountProviderPlugin methods, and `keys.SETUP_PAGE`/`keys.CONCIERGE_PAGE` are used consistently across tasks. `LocalRuntime(svc, *, hby, hab, rgy)` matches the Plan 1 (now-landed) signature.
