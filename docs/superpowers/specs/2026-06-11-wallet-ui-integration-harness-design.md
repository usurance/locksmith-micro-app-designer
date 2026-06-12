# Wallet UI Integration Harness — Design

**Date:** 2026-06-11
**Status:** Approved design, pending implementation plan

## Purpose

Driving the running Locksmith wallet through the `locksmith-ui-tester` socket works, but
every new flow currently costs a slow round of *selector discovery* — dumping the widget
tree and grepping the host `locksmith` source for `objectName`s, plus trial-and-error over
which op a control needs (e.g. "Initialize New Vault" is a `QListWidget` item, so it needs
`click_list_item`, not `click`).

This harness removes that cost permanently. It gives the repo:

1. A reusable **driver** over the tester socket, so a flow like "create a vault" is one call
   instead of ten.
2. A **living selector cheatsheet** that cannot go stale, because the helpers and tests both
   import it.
3. A repeatable **integration test suite** that exercises the designer plugin end-to-end in a
   real wallet, isolated from the developer's working wallet.

These are three layers of one artifact, not three separate things. The expensive part is the
driver + selectors; tests then come nearly free.

## Goals & non-goals

**Goals**
- One-call reusable actions (`create_vault`, `open_vault`, `open_designer`, …) for both
  interactive dev use and assertion-based tests.
- Selectors curated once, in code, shared by everything.
- Integration tests that run against a pristine, isolated wallet and never touch the real
  `~/.keri` store.
- The existing 68 pure-library tests and headless CI stay green — the integration suite is
  opt-in and self-skips when the wallet app is absent.

**Non-goals (YAGNI)**
- No auto-generation of selectors from the host source. Selectors are curated by hand as we
  hit each screen.
- No cross-repo extraction yet. Everything starts in this repo; the generic parts are kept
  modular so a future lift into `locksmith-ui-tester` is a copy, not a refactor.
- No new tester ops. The current op set (`ping`, `screenshot`, `tree`, `current_page`,
  `click`, `click_list_item`, `click_table_row`, `click_row_action`, `type`, `select`,
  `get_text`, `is_checked`, `is_visible`, `wait_for`, `count`, `get_list_items`,
  `get_table_rows`) is sufficient.

## Constraints discovered

These shaped the design and are recorded so the implementer does not re-derive them:

- **`locksmith-ui-tester` ships a reusable client.** `cli.py` exposes
  `send(op, kwargs, socket_path, timeout) -> dict`; we import it rather than shelling out to
  the CLI.
- **`wait_for` is the non-flaky primitive.** It polls a selector for `visible`/`hidden`
  while pumping Qt events. All actions use it instead of `sleep`.
- **`screenshot` with a `target` silently falls back to the full window** for non-top-level
  widgets. To verify form field contents, read them back from `tree`/`get_text`, not a
  screenshot.
- **Alt-`HOME` isolation works with the DMG build.** Launching the embedded binary directly —
  `HOME=$TMP /Applications/Locksmith.app/Contents/MacOS/Locksmith` — yields a fully isolated
  instance with zero vaults (verified: `VaultDrawer … total=0`), writing only under `$TMP`.
  macOS `open` will *not* pass env to a GUI app, so the harness must exec the inner binary.
  Two instances with different `HOME` get independent control sockets and coexist (verified).
- **A fresh `HOME` has no plugins** (`plugins=0`, no socket). The harness must seed
  `$HOME/.locksmith/plugins/` before launch.
- **Plugin install paths** (host `locksmith/plugins/storage.py`): clones live at
  `~/.locksmith/plugins/<id>/`; the shared registry is `~/.locksmith/plugins/index.json`; the
  per-wallet enable list is `<keri_base>/locksmith/plugin-enable.json`.
- **Vault state persists under `~/.keri/`** across category dirs (`reg/ ks/ not/ rt/ mbx/
  db/ …`), one subdir per vault name. There is **no delete-vault UI action**, and open vaults
  hold LMDB locks — so deleting a vault's dirs from a running wallet is fragile. This is why
  test isolation uses a throwaway `HOME` (teardown = `rm -rf`) rather than vault deletion.
- **Temp vaults are gated by a global `config.temp` flag**, not a per-dialog option, so they
  cannot be requested on demand from a normal running wallet.

## Architecture

### Layout (in this repo)

```
tests/integration/
  driver/
    client.py       # Layer 0 — wrapper over tester send(): connect, call(op, **kw), wait_for
    selectors.py    # Layer 1 — page objects; objectName constants. The living cheatsheet.
    actions.py      # Layer 2 — create_vault, open_vault, open_designer, goto_primitive, …
    instance.py     # ephemeral alt-HOME wallet: seed plugins, launch, await socket, teardown
  conftest.py       # fixtures + skip-when-no-binary
  test_vault_lifecycle.py
  test_designer_smoke.py
  README.md         # op reference + "how to add a page object"
scripts/
  wallet.py         # interactive CLI shim → drives the *running* wallet
```

The driver lives under `tests/` so nothing leaks into the shipped plugin package
(`src/locksmith_micro_app_designer/`). `scripts/wallet.py` bootstraps `sys.path` to import
the driver for interactive use.

### Layer 0 — `client.py`

Thin object wrapping the tester's `send()`. Holds a socket path; exposes `call(op, **kwargs)`
returning the parsed dict (raising on `{"error": …}`), plus convenience `wait_for(target,
condition="visible", timeout_ms=...)`. Default socket path is the tester default
(`~/.locksmith-control.sock`); the ephemeral instance passes its own path.

### Layer 1 — `selectors.py`

One small class or constant group per screen, holding the `objectName`s (and the op each
control needs). Curated from the host source once per screen. Examples already known:

- `Toolbar.VAULTS_BUTTON = "toolbar.vaultsButton"`
- `VaultDrawer.NEW_VAULT_ITEM = "Initialize New Vault"` (a list item → `click_list_item`)
- `CreateVaultDialog.NAME = "createVaultDialog.nameField"`,
  `PASSCODE = "createVaultDialog.passcodeField"`,
  `CREATE = "createVaultDialog.createButton"`

This module is the cheatsheet. `README.md` is a human index that points into it.

### Layer 2 — `actions.py`

Verbs composing Layer 0 + Layer 1, each ending in a `wait_for` so callers get a settled UI:

```python
def create_vault(client, name, passcode):
    client.call("click", target=Toolbar.VAULTS_BUTTON)
    client.call("click_list_item", text=VaultDrawer.NEW_VAULT_ITEM)
    client.wait_for(CreateVaultDialog.NAME)
    client.call("type", target=CreateVaultDialog.NAME, text=name)
    client.call("type", target=CreateVaultDialog.PASSCODE, text=passcode)
    client.call("click", target=CreateVaultDialog.CREATE)
    client.wait_for(CreateVaultDialog.NAME, condition="hidden")
    return client.call("current_page")
```

Each action returns enough to assert on (resulting `current_page`, a `get_text`, etc.).

### Ephemeral instance — `instance.py`

A context manager providing an isolated wallet for the test suite:

1. `mkdtemp()` a temp HOME; create `$TMP/.locksmith/plugins/`.
2. **Symlink** `~/.locksmith/plugins/ui_tester` and `~/.locksmith/plugins/designer` into it.
3. Write the minimal `index.json` (and enable list, if required) so both plugins auto-load.
4. Launch `…/Contents/MacOS/Locksmith` with `HOME=$TMP` and
   `LOCKSMITH_CONTROL_SOCKET=$TMP/.locksmith-control.sock`.
5. `wait_for` the socket file, then yield a `client` bound to it.
6. On exit: terminate the process, then `rm -rf $TMP`.

**Primary technical risk:** the exact `index.json` / enable-list shape the host expects in
order to auto-load a symlinked plugin. The first implementation step is a spike that stands
the instance up and confirms `ping` succeeds; everything downstream is cheap once it does.
The alt-HOME launch and independent cross-instance sockets are already verified, so this is
the only remaining unknown.

### Interactive use — `scripts/wallet.py`

A small CLI over the same driver, pointed at the **already-running** wallet's default socket:

```bash
python scripts/wallet.py create-vault automation noble
python scripts/wallet.py open-designer
python scripts/wallet.py screenshot /tmp/x.png
```

This is the "make me a vault" ergonomics path for day-to-day dev. Same code as the tests,
different socket.

### Integration tests + skip behavior

- A `wallet` pytest fixture yields a fresh ephemeral instance (scope: **session**, with
  per-test cleanup of artifacts created inside the vault).
- `conftest.py` auto-skips the entire `tests/integration/` tree when
  `/Applications/Locksmith.app` is absent, so the 68 pure-library tests and headless CI stay
  green. Run the suite explicitly with `pytest tests/integration`.
- First two tests prove the harness:
  - **Vault lifecycle** — create a vault, assert it opens (title / `current_page`), reopen it.
  - **Designer smoke** — open the designer plugin nav entry, assert its landing page renders.

## Decisions & rationale

- **Everything in this repo, generic parts modular** ("start here, extract later"). No
  cross-repo tax until a second plugin needs the generic helpers.
- **Layered stack (helpers + tests), not either/or.** The driver is the expensive artifact;
  tests are a thin layer on top.
- **Isolation via ephemeral alt-HOME instance**, not a shared/dedicated vault. Pristine and
  repeatable, trivial `rm -rf` teardown, no LMDB-lock or delete-vault problems, never touches
  the real `~/.keri`. The integration suite spins up its own wallet; interactive helpers
  drive whatever wallet is already running.
- **Seed plugins by symlink**, not copy. Fast, always reflects the current clones during dev.
  A copy-based hermetic mode can be added for CI later if needed.

## Open items (to finalize in the plan)

- **Fixture scope:** leaning session-scoped instance + per-test artifact cleanup (fast); the
  alternative is per-module (cleaner isolation, slower).
- **Driver placement:** leaning `tests/integration/driver/` over a top-level package, to keep
  it out of the shipped plugin.

## Testing strategy

The driver and selectors are exercised by the integration tests themselves. `instance.py`
gets validated first by the spike (socket comes up). The pure-library suite is unaffected and
remains the headless baseline.
