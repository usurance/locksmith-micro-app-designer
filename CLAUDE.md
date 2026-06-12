# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Two artifacts that produce/consume the **same** JSON contract — a `micro-app-template.json`
describing one role's slice of one use case in a KERI-native ecosystem:

1. **Locksmith wallet plugin** (`src/locksmith_micro_app_designer/`) — a PySide6
   direct-manipulation editor that runs *inside* the Locksmith wallet.
2. **Claude Code marketplace plugin** (`skills/micro-app-template-gen/`) — a conversational
   10-step authoring skill distributed via `.claude-plugin/`.

The normative artifact contract is
`docs/superpowers/specs/2026-05-09-micro-app-template-authoring-and-data-model.md`, validated against
the meta-schemas in `docs/superpowers/specs/schemas/`. Read it before changing the template shape,
primitives, or vocabulary — both artifacts must stay conformant. The same `docs/superpowers/specs/`
dir also holds the designer-plugin spec (`2026-05-12`) and runtime-design spec (`2026-05-15`);
`docs/superpowers/plans/` holds the historical v1 build plans.

## Commands

```bash
pip install -e .                       # install the package (Python >=3.13)
pytest                                 # run all tests (testpaths/pythonpath set in pyproject.toml)
pytest tests/micro_app_template/test_saidify.py            # one file
pytest tests/.../test_validate.py::test_aggregate_validates  # one test

# CLI wrappers (the skill drives these; invoked as plain scripts, not console entry points):
python scripts/micro_app_saidify.py --input path/to/micro-app-template.json --in-place
python scripts/micro_app_validate.py --input path/to/micro-app-template.json [--schema <meta-schema>]
```

There is no lint/format config checked in. `keri` and `jsonschema` are runtime deps but are
**not declared** in `pyproject.toml` (`dependencies = []`) — they come from the Locksmith venv
you install into.

## Architecture

The codebase splits cleanly into a **pure library** and a **Qt plugin layer**. Keep new
template-semantics logic in the library so it stays testable without a Qt/Locksmith runtime.

### Pure library — `src/.../template/` + `crossref.py`
No Qt, no Locksmith imports. This is the testable core:
- `canonical_json.py` — deterministic sorted-keys, 2-space, UTF-8, trailing-newline serialization.
  This exact form is used both on disk **and** as SAID input; the two must never diverge.
- `saidify.py` — wraps keripy `Saider.saidify` (Blake3-256). Sets `d` to a 44-char `#` placeholder,
  hashes the sorted-keys canonical form, injects the resulting SAID. `compute_said` / `saidify_document` / `verify_said`.
- `validate.py` + `xref.py` — validation has two independent halves: **JSON-Schema** structural
  validation against a meta-schema file, and **cross-reference** validation (`rule_refs`, credential
  ids, workflow ids resolve). xref works with no schema file; meta-schema validation needs the file.
- `crossref.py` — the *reverse* of `xref.py`: builds an inverted index (`"<kind>:<id>"` → consumers)
  feeding the "Used by" chips in every editor.

### Qt plugin layer — `plugin.py`, `editors/`, `widgets/`, `model.py`, `store.py`, `db.py`
- `DesignerPlugin` (`plugin.py`) subclasses **`locksmith.plugins.base.VaultPlugin`** — the host
  `locksmith` package is *not* in this repo, so the GUI cannot run standalone here; only the
  library + scripts are exercisable in isolation.
- **Page lifecycle is the non-obvious part.** `VaultPage.register_page` requires the full page-key
  set (defined in `keys.py`) up front, but real pages can't be built until a vault is open and a
  template is loaded. So `initialize()` registers **placeholder `QWidget`s** for every key; then
  `on_vault_opened` and `_open_template` build the real pages and **re-register** them with
  `vault_page.register_page(key, page)` to swap them into the host's `content_stack`. If you add a
  page, add its key to `keys.py` (`ALL_PAGE_KEYS`, and `PRIMITIVE_PAGE_KEY` if it's a primitive).
- `model.py` — `TemplateModel(QObject)` owns a deepcopy of the template dict and emits
  `changed(json_pointer)` / `dirty_changed(bool)`. Mutate via its named methods, **not**
  `model.doc[...] = ...` (direct mutation doesn't emit signals).
- `store.py` — file-on-disk source of truth under `keri/dgnr/templates/`:
  `registered/<SAID>/` (finalized) vs `drafts/<local-id>/` (WIP). A `TemplateRef` carries exactly
  one of `said`/`local_id`. Tests/callers redirect the root via
  `vault.plugin_state["designer.root_override"]`.
- `db.py` — `DesignerBaser(LMDBer)`, per-vault LMDB index (tail dir `keri/dgnr`) for fast browser
  rendering + last-opened resume. **Rebuildable from disk** — losing it loses no user data.
- Each per-primitive editor wraps a `PrimitiveEditorShell` (left kind-rail + identity strip +
  swappable right pane); cross-cutting surfaces are `widgets/validation_panel.py` and
  `widgets/json_source_view.py` (two-way bound to the model).

## Testing in the running wallet (locksmith-ui-tester)

The GUI can't run standalone here, but it **can** be driven live in the installed wallet
(`/Applications/Locksmith.app`, installed via DMG) using the `locksmith-ui-tester` plugin
(`seriouscoderone/locksmith-ui-tester`). When the wallet is open, that plugin serves a
JSON-over-unix-socket control surface at `~/.locksmith-control.sock` (appears ~1s after launch,
vanishes when the wallet quits).

The plugin framework clones every installed plugin to `~/.locksmith/plugins/<id>/` —
`ui_tester` (the tester) and `designer` (this repo) — plus `<id>.previous/` rollback copies and
`index.json`. **Prefer driving the tester from that installed clone**, not a dev checkout, so the
client always matches the server code the wallet loaded:

```bash
open /Applications/Locksmith.app   # then wait for ~/.locksmith-control.sock
PYTHONPATH=~/.locksmith/plugins/ui_tester/src python3 -m locksmith_ui_tester.cli ping
PYTHONPATH=~/.locksmith/plugins/ui_tester/src python3 -m locksmith_ui_tester.cli screenshot '{"path": "/tmp/wallet.png"}'
```

Ops: `ping`, `screenshot` (`target` selects a dialog), `tree`, `current_page`, `click`,
`click_list_item`, `type`, `select`. The `devctl` console script only exists if the tester package
is pip-installed somewhere; the `python -m locksmith_ui_tester.cli` form above is equivalent and
needs no install. `current_page` reports `vault_page: null` until a vault is opened.

## Gotchas

- **`test_cli.py` (4 tests) requires the package to be importable as a subprocess** — i.e.
  `pip install -e .` into your venv. Those tests shell out to `python scripts/micro_app_*.py`, which
  `import locksmith_micro_app_designer`; the subprocess doesn't inherit pytest's `pythonpath=["src"]`,
  so without the editable install they fail with `ModuleNotFoundError`. The other 64 tests pass
  in-process. (The meta-schemas these scripts validate against live at
  `docs/superpowers/specs/schemas/` — recovered from the `feat/designer-plugin-spec` branch of the
  parent `locksmith` repo, which the initial 2026-05-26 extraction had left behind.)
- keripy is on the **2.0** line: `koming.Komer` takes `klas=` (not `schema=`) for the record class
  (see git history). Match that when touching `db.py`.
- SAID stability depends on the sorted-keys recursion in `saidify.py` matching `canonical_json.py`.
  Change one, change both.
