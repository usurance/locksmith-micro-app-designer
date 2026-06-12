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

## Keeping the installed designer plugin in sync

The integration suite launches a throwaway wallet that loads plugins by
**symlinking the installed clones** under `~/.locksmith/plugins/`. The designer
clone (`~/.locksmith/plugins/designer/`) is a **copy**, not a symlink to this
repo — so after editing the designer plugin's source (e.g. `plugin.py`), the
clone is stale until you refresh it. Either reinstall/upgrade the plugin from
the wallet's Plugins page, or sync the source directly:

```bash
cp -R src/locksmith_micro_app_designer/ \
      ~/.locksmith/plugins/designer/src/locksmith_micro_app_designer/
```

Tests that assert on designer-specific objectNames (e.g. `designer.navButton`)
will only see your changes after this refresh.

## Adding a page object

1. Open the wallet, navigate to the screen, run `client.call("tree")` (or
   `python scripts/wallet.py` + a one-off) to find `objectName`s. Cross-check the
   host source under `~/code/locksmith/src/locksmith/ui/`.
2. Add a class/constants to `driver/selectors.py` with the op each control needs.
3. Add a verb to `driver/actions.py` composing them, ending in a `wait_for`.
4. If a control has no `objectName`, add one in the owning source (as done for the
   designer nav buttons in `plugin.py`).
