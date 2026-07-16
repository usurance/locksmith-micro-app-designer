# ACDC-Schema Compliance Linter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A SAD/SAID + ACDC-schema compliance linter for micro-app template directories, wired into `micro_app_validate.py --lint` and documented in the micro-app-template-gen SKILL.md.

**Architecture:** Two new pure-library modules — `template/schema_said.py` (keripy-backed `$id` SAID compute/verify with `kli saidify` insertion-order parity) and `template/lint.py` (check catalog S01–S09 per schema file, T01–T07 cross-file, F01/F02 file-level) — orchestrated by `lint_template_dir(Path) -> LintResult`. The existing `validate.py`/editor path stays untouched and keripy-free.

**Tech Stack:** Python ≥3.13, keripy 2.0.0-dev6 (`keri.core.coring.Saider`), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-07-16-acdc-schema-compliance-linter-design.md` (read it first — the check catalog and severity table there are normative for this plan).

## Global Constraints

- Run everything with the Locksmith venv: `~/code/locksmith/.venv/bin/python` (the designer repo has no venv; `keri`/`jsonschema` live there; pytest `pythonpath=["src"]` is set in pyproject.toml). Repo root: `~/code/locksmith-micro-app-designer`.
- `test_cli.py` subprocess tests need the editable install in that venv (`~/code/locksmith/.venv/bin/pip install -e .`) — check with `pip show locksmith-micro-app-designer` before assuming breakage.
- **Schema `$id` SAIDs hash the document in file insertion order — never sort keys.** Template `d` SAIDs sort keys recursively (existing `saidify.py`). Do not mix the two.
- New logic goes in the pure library (`src/locksmith_micro_app_designer/template/`), no Qt imports, no shelling out to `kli`.
- The bundled worked-example schemas lack `version` — S05 **must** fire on them; tests pin this as expected (do NOT "fix" the example schemas; re-SAIDing them is an owner-scheduled migration).
- Severity: `error` = ACDC-spec MUST violation / integrity failure; `warning` = locally-unresolvable external SAID or hygiene. Exit 1 only on errors.
- One pre-existing dirty file (`tests/integration/microapp_in_vault_witnessed.sh`) is NOT ours — never `git add` it.

---

### Task 1: `schema_said.py` — ACDC-schema SAID compute/verify (kli parity)

**Files:**
- Create: `src/locksmith_micro_app_designer/template/schema_said.py`
- Test: `tests/micro_app_template/test_schema_said.py`

**Interfaces:**
- Consumes: `keri.core.coring.Saider` (from the Locksmith venv).
- Produces (used by Tasks 2–3 and test fixtures):
  - `SAID_LABEL: str = "$id"`
  - `compute_schema_said(block: dict) -> str`
  - `verify_schema_said(block: dict) -> bool`
  - `saidify_schema_block(block: dict) -> dict` (returns stamped copy)
  - `iter_said_blocks(doc: dict) -> Iterator[tuple[str, dict]]` — `(path, block)` for every dict at any depth carrying `"$id"`, root first (root path `"<root>"`), depth-first
  - `is_bare_said(value: object) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for ACDC-schema SAID computation (kli-saidify parity)."""
from __future__ import annotations

import json
from pathlib import Path

from locksmith_micro_app_designer.template.schema_said import (
    SAID_LABEL,
    compute_schema_said,
    is_bare_said,
    iter_said_blocks,
    saidify_schema_block,
    verify_schema_said,
)

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLE_SCHEMA = (
    REPO_ROOT
    / "skills/micro-app-template-gen/references/examples"
    / "regulator-grants-carrier-license/schemas/carrier_license.json"
)


def _minimal_block() -> dict:
    return {
        "$id": "",
        "description": "test block",
        "type": "object",
        "properties": {"d": {"type": "string"}},
    }


def test_saidify_then_verify_roundtrip():
    stamped = saidify_schema_block(_minimal_block())
    assert stamped["$id"].startswith("E")
    assert len(stamped["$id"]) == 44
    assert verify_schema_said(stamped) is True


def test_verify_fails_on_tamper():
    stamped = saidify_schema_block(_minimal_block())
    stamped["description"] = "tampered"
    assert verify_schema_said(stamped) is False


def test_verify_fails_on_missing_or_empty_id():
    assert verify_schema_said({"type": "object"}) is False
    assert verify_schema_said({"$id": "", "type": "object"}) is False


def test_saidify_does_not_mutate_input():
    block = _minimal_block()
    saidify_schema_block(block)
    assert block["$id"] == ""


def test_worked_example_saids_verify_top_and_nested():
    """Pins kli-saidify parity against a real artifact stamped by kli."""
    doc = json.loads(EXAMPLE_SCHEMA.read_text())
    for path, block in iter_said_blocks(doc):
        assert verify_schema_said(block), f"SAID at {path} does not verify"


def test_insertion_order_sensitivity():
    """Schema SAIDs bind to file key order — a sorted rehash MISMATCHES.

    This is the load-bearing difference from template-d saidify (which
    sorts recursively). If this test ever fails, kli parity broke.
    """
    doc = json.loads(EXAMPLE_SCHEMA.read_text())

    def sort_rec(o):
        if isinstance(o, dict):
            return {k: sort_rec(o[k]) for k in sorted(o)}
        if isinstance(o, list):
            return [sort_rec(x) for x in o]
        return o

    assert compute_schema_said(doc) == doc["$id"]
    assert compute_schema_said(sort_rec(doc)) != doc["$id"]


def test_iter_said_blocks_yields_root_first_with_paths():
    doc = {
        "$id": "root-said",
        "properties": {
            "a": {
                "oneOf": [
                    {"type": "string"},
                    {"$id": "nested-said", "type": "object"},
                ]
            }
        },
    }
    got = list(iter_said_blocks(doc))
    assert got[0][0] == "<root>"
    assert got[0][1]["$id"] == "root-said"
    assert got[1][0] == "properties.a.oneOf[1]"
    assert got[1][1]["$id"] == "nested-said"


def test_is_bare_said():
    doc = json.loads(EXAMPLE_SCHEMA.read_text())
    good = doc["$id"]
    assert is_bare_said(good) is True
    assert is_bare_said(f"did:keri:{good}") is False
    assert is_bare_said(f"sad:{good}") is False
    assert is_bare_said(f"https://example.com/{good}") is False
    assert is_bare_said("not-a-said") is False
    assert is_bare_said("E" + "x" * 20) is False
    assert is_bare_said("") is False
    assert is_bare_said(None) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/code/locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template/test_schema_said.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'locksmith_micro_app_designer.template.schema_said'`

- [ ] **Step 3: Write the implementation**

```python
"""SAID computation for ACDC schema documents.

ACDC schemas carry their SAID in the `$id` field — at the top level and
in every bundled sub-schema block (e.g. the expanded attribute-block
variant inside `a.oneOf`). Unlike micro-app templates, whose `d` SAID is
computed over the recursively key-sorted canonical form (see saidify.py),
schema `$id` SAIDs are computed over the document's **insertion order**,
matching `kli saidify --label '$id'` (which hashes the mapping exactly as
loaded from disk). Schema files are therefore order-sensitive artifacts:
re-serializing one with sorted keys breaks its SAID.
"""
from __future__ import annotations

from typing import Any, Iterator

from keri.core.coring import Saider

SAID_LABEL = "$id"
"""Label field carrying the SAID in ACDC schema documents."""


def compute_schema_said(block: dict[str, Any]) -> str:
    """Compute the SAID of an ACDC schema block over its insertion order."""
    if SAID_LABEL not in block:
        raise KeyError(f"block missing label field: {SAID_LABEL!r}")
    saider, _ = Saider.saidify(sad=dict(block), label=SAID_LABEL)
    return saider.qb64


def saidify_schema_block(block: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of block with its SAID stamped into `$id`."""
    if SAID_LABEL not in block:
        raise KeyError(f"block missing label field: {SAID_LABEL!r}")
    _, stamped = Saider.saidify(sad=dict(block), label=SAID_LABEL)
    return stamped


def verify_schema_said(block: dict[str, Any]) -> bool:
    """True iff block[$id] is the SAID of the block's stored content."""
    claimed = block.get(SAID_LABEL)
    if not isinstance(claimed, str) or not claimed:
        return False
    return compute_schema_said(block) == claimed


def is_bare_said(value: object) -> bool:
    """True iff value is a bare CESR digest primitive (no URI prefix).

    Bare means no scheme/prefix of any kind (rejects `did:`, `sad:`,
    `https://`, ...); the value must parse as a CESR digest (Saider
    rejects non-digest derivation codes and wrong lengths).
    """
    if not isinstance(value, str) or not value:
        return False
    if ":" in value or "/" in value:
        return False
    try:
        Saider(qb64=value)
    except Exception:
        return False
    return True


def iter_said_blocks(doc: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (path, block) for every dict in doc carrying a `$id`.

    Root first (path "<root>"), then depth-first in insertion order with
    dotted/bracketed paths matching the repo's xref path style
    (e.g. "properties.a.oneOf[1]").
    """
    def walk(node: Any, path: str) -> Iterator[tuple[str, dict[str, Any]]]:
        if isinstance(node, dict):
            if SAID_LABEL in node:
                yield (path or "<root>", node)
            for key, value in node.items():
                child = f"{path}.{key}" if path else key
                yield from walk(value, child)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                yield from walk(item, f"{path}[{i}]")

    yield from walk(doc, "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/code/locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template/test_schema_said.py -v`
Expected: all PASS. If `Saider(qb64=...)` raises an unexpected error type for the `is_bare_said` reject cases, the broad `except Exception` already covers it; if `Saider.saidify` mutates the input despite the `dict()` shallow copy (it should not — the label is a top-level key on the copy), fix by deep-copying in `saidify_schema_block` only.

- [ ] **Step 5: Commit**

```bash
cd ~/code/locksmith-micro-app-designer
git add src/locksmith_micro_app_designer/template/schema_said.py tests/micro_app_template/test_schema_said.py
git commit -m "feat(template): ACDC-schema \$id SAID compute/verify with kli-saidify insertion-order parity"
```

---

### Task 2: `lint.py` — per-schema-file checks S01–S09

**Files:**
- Create: `src/locksmith_micro_app_designer/template/lint.py`
- Test: `tests/micro_app_template/test_lint.py`
- Modify: `tests/micro_app_template/conftest.py` (add compliant-dir fixture used here and in Task 4)

**Interfaces:**
- Consumes: Task 1's `SAID_LABEL`, `is_bare_said`, `iter_said_blocks`, `verify_schema_said`, `saidify_schema_block`; existing `saidify.saidify_document`/`verify_said`; existing `canonical_json.canonicalize`.
- Produces (used by Tasks 3–4):
  - `LintFinding(file: str, path: str, code: str, message: str, severity: str = "error")`
  - `LintResult(findings: list[LintFinding])` with `.errors`, `.warnings`, `.is_compliant`
  - `lint_schema_doc(doc: dict, file: str) -> list[LintFinding]` (S01–S09)
  - `collect_edge_schema_pins(doc: dict) -> list[tuple[str, str]]` — `(path, said)` of `s` const pins in the expanded `e` section (S09 validates them; Task 3's T06 resolves them)

- [ ] **Step 1: Add the compliant-dir fixture to conftest.py**

Append to `tests/micro_app_template/conftest.py` (keep the existing content; add `import copy`, `import json` alongside the existing imports):

```python
import copy
import json

from locksmith_micro_app_designer.template.canonical_json import canonicalize
from locksmith_micro_app_designer.template.saidify import saidify_document
from locksmith_micro_app_designer.template.schema_said import saidify_schema_block


def make_compliant_schema() -> dict:
    """A minimal fully-lint-compliant ACDC schema (envelope + attribute block)."""
    schema = {
        "$id": "",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Test Credential",
        "description": "Minimal compliant ACDC schema for lint tests.",
        "type": "object",
        "credentialType": "TestCredential",
        "version": "1.0.0",
        "properties": {
            "v": {"description": "ACDC version string.", "type": "string"},
            "d": {"description": "Credential SAID.", "type": "string"},
            "i": {"description": "Issuer AID.", "type": "string"},
            "ri": {"description": "Registry identifier.", "type": "string"},
            "s": {"description": "Schema SAID.", "type": "string"},
            "a": {
                "oneOf": [
                    {"description": "Attributes block SAID, compact form.", "type": "string"},
                    {
                        "$id": "",
                        "description": "Attributes block.",
                        "type": "object",
                        "properties": {
                            "d": {"description": "Attributes block SAID.", "type": "string"},
                            "i": {"description": "Issuee AID.", "type": "string"},
                            "dt": {
                                "description": "Issuance date-time.",
                                "type": "string",
                                "format": "date-time",
                            },
                            "claim": {"description": "A test claim.", "type": "string"},
                        },
                        "additionalProperties": False,
                        "required": ["d", "i", "dt", "claim"],
                    },
                ]
            },
        },
        "additionalProperties": False,
        "required": ["v", "d", "i", "ri", "s", "a"],
    }
    schema["properties"]["a"]["oneOf"][1] = saidify_schema_block(
        schema["properties"]["a"]["oneOf"][1]
    )
    return saidify_schema_block(schema)


def write_template_dir(root, template: dict, metadata: dict, schemas: dict) -> None:
    """Write a template dir. `schemas` maps filename -> doc. Schemas are
    written in insertion order (json.dumps, NOT canonicalize) because their
    SAIDs bind to key order; template/metadata use the canonical form."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "micro-app-template.json").write_text(canonicalize(template))
    (root / "metadata.json").write_text(canonicalize(metadata))
    schemas_dir = root / "schemas"
    schemas_dir.mkdir(exist_ok=True)
    for name, doc in schemas.items():
        (schemas_dir / name).write_text(json.dumps(doc, indent=2) + "\n")


@pytest.fixture
def compliant_template_dir(tmp_path, minimal_valid_template):
    """A fully lint-compliant template dir; lint must return zero findings."""
    schema = make_compliant_schema()
    template = copy.deepcopy(minimal_valid_template)
    template["credentials"]["exports"] = [
        {
            "id": "test_credential",
            "name": "Test Credential",
            "schema": {
                "schema_path": "schemas/test_credential.json",
                "schema_said": schema["$id"],
            },
        }
    ]
    template = saidify_document(template)
    metadata = {"for_micro_app_said": template["d"]}
    root = tmp_path / "tester-minimal"
    write_template_dir(root, template, metadata, {"test_credential.json": schema})
    return root
```

- [ ] **Step 2: Write the failing tests for S01–S09**

Create `tests/micro_app_template/test_lint.py`:

```python
"""Tests for the SAD/SAID + ACDC-schema compliance linter (S/T/F checks)."""
from __future__ import annotations

import copy
import json

from locksmith_micro_app_designer.template.lint import (
    LintFinding,
    LintResult,
    collect_edge_schema_pins,
    lint_schema_doc,
)
from locksmith_micro_app_designer.template.schema_said import saidify_schema_block

from .conftest import make_compliant_schema


def _codes(findings) -> set[str]:
    return {f.code for f in findings}


def _resaidify(schema: dict) -> dict:
    """Re-stamp nested attribute block then the envelope (bottom-up)."""
    schema = copy.deepcopy(schema)
    a_oneof = schema.get("properties", {}).get("a", {}).get("oneOf")
    if a_oneof and isinstance(a_oneof[-1], dict) and "$id" in a_oneof[-1]:
        a_oneof[-1] = saidify_schema_block(a_oneof[-1])
    return saidify_schema_block(schema)


def make_edge_section(pin_said: str, operator: str = "NI2I") -> dict:
    """An expanded-e-section oneOf like the carrier_license worked example."""
    return {
        "oneOf": [
            {"description": "Edge block SAID, compact form.", "type": "string"},
            {
                "$id": "",
                "description": "Edges.",
                "type": "object",
                "properties": {
                    "d": {"description": "Edge block SAID.", "type": "string"},
                    "application": {
                        "description": "Edge to the adjudicated application.",
                        "type": "object",
                        "properties": {
                            "n": {"description": "Node SAID.", "type": "string"},
                            "s": {
                                "description": "Node schema SAID.",
                                "type": "string",
                                "const": pin_said,
                            },
                            "o": {
                                "description": "Edge operator.",
                                "type": "string",
                                "const": operator,
                            },
                        },
                        "additionalProperties": False,
                        "required": ["n", "s", "o"],
                    },
                },
                "additionalProperties": False,
                "required": ["d", "application"],
            },
        ]
    }


def make_schema_with_edges(pin_said: str, operator: str = "NI2I") -> dict:
    schema = make_compliant_schema()
    schema = {k: v for k, v in schema.items()}  # preserve order, drop stamp
    schema["properties"]["e"] = make_edge_section(pin_said, operator)
    schema["properties"]["e"]["oneOf"][1] = saidify_schema_block(
        schema["properties"]["e"]["oneOf"][1]
    )
    schema["required"] = schema["required"] + ["e"]
    return saidify_schema_block(schema)


VALID_EXTERNAL_SAID = "ENbhxLlFINUDp1EU4mV5RVVL-CS6Ub72zXY89EcM7Ccb"


def test_compliant_schema_has_no_findings():
    assert lint_schema_doc(make_compliant_schema(), "schemas/x.json") == []


def test_compliant_schema_with_edges_has_no_findings():
    doc = make_schema_with_edges(VALID_EXTERNAL_SAID)
    assert lint_schema_doc(doc, "schemas/x.json") == []


def test_s01_missing_top_level_id():
    doc = make_compliant_schema()
    del doc["$id"]
    assert "S01" in _codes(lint_schema_doc(doc, "f"))


def test_s02_uri_prefixed_id():
    doc = make_compliant_schema()
    doc["$id"] = f"did:keri:{doc['$id']}"
    assert "S02" in _codes(lint_schema_doc(doc, "f"))


def test_s02_expanded_variant_missing_id():
    doc = make_compliant_schema()
    del doc["properties"]["a"]["oneOf"][1]["$id"]
    doc = saidify_schema_block(doc)
    assert "S02" in _codes(lint_schema_doc(doc, "f"))


def test_s03_top_level_tamper():
    doc = make_compliant_schema()
    doc["title"] = "Tampered"
    findings = lint_schema_doc(doc, "f")
    assert any(f.code == "S03" and f.path.startswith("<root>") for f in findings)


def test_s03_nested_tamper():
    doc = make_compliant_schema()
    doc["properties"]["a"]["oneOf"][1]["description"] = "tampered"
    doc = saidify_schema_block(doc)  # top-level re-stamped; nested left stale
    findings = lint_schema_doc(doc, "f")
    assert any(f.code == "S03" and "oneOf[1]" in f.path for f in findings)


def test_s04_wrong_or_missing_dialect():
    doc = make_compliant_schema()
    doc["$schema"] = "http://json-schema.org/draft-07/schema#"
    assert "S04" in _codes(lint_schema_doc(_resaidify(doc), "f"))
    doc2 = make_compliant_schema()
    del doc2["$schema"]
    assert "S04" in _codes(lint_schema_doc(_resaidify(doc2), "f"))


def test_s05_missing_or_malformed_version():
    doc = make_compliant_schema()
    del doc["version"]
    assert "S05" in _codes(lint_schema_doc(_resaidify(doc), "f"))
    doc2 = make_compliant_schema()
    doc2["version"] = "1.0"
    assert "S05" in _codes(lint_schema_doc(_resaidify(doc2), "f"))


def test_s06_nonlocal_and_dynamic_refs():
    doc = make_compliant_schema()
    doc["properties"]["extra"] = {"$ref": "https://example.com/x.json"}
    assert "S06" in _codes(lint_schema_doc(_resaidify(doc), "f"))
    doc2 = make_compliant_schema()
    doc2["properties"]["extra"] = {"$dynamicRef": "#thing"}
    assert "S06" in _codes(lint_schema_doc(_resaidify(doc2), "f"))


def test_s06_local_and_said_refs_allowed():
    doc = make_compliant_schema()
    doc["properties"]["extra"] = {"$ref": "#/properties/d"}
    doc["properties"]["extra2"] = {"$ref": VALID_EXTERNAL_SAID}
    assert "S06" not in _codes(lint_schema_doc(_resaidify(doc), "f"))


def test_s07_compact_variant_not_first():
    doc = make_compliant_schema()
    oneof = doc["properties"]["a"]["oneOf"]
    doc["properties"]["a"]["oneOf"] = [oneof[1], oneof[0]]
    assert "S07" in _codes(lint_schema_doc(_resaidify_swapped(doc), "f"))


def _resaidify_swapped(schema: dict) -> dict:
    schema = copy.deepcopy(schema)
    oneof = schema["properties"]["a"]["oneOf"]
    for i, br in enumerate(oneof):
        if isinstance(br, dict) and "$id" in br:
            oneof[i] = saidify_schema_block(br)
    return saidify_schema_block(schema)


def test_s07_compactable_oneof_missing_compact_variant():
    doc = make_compliant_schema()
    doc["properties"]["a"]["oneOf"] = [doc["properties"]["a"]["oneOf"][1]]
    assert "S07" in _codes(lint_schema_doc(_resaidify(doc), "f"))


def test_s08_reserved_label_type_divergence():
    doc = make_compliant_schema()
    doc["properties"]["a"]["oneOf"][1]["properties"]["dt"] = {
        "description": "wrong",
        "type": "object",
    }
    assert "S08" in _codes(lint_schema_doc(_resaidify(doc), "f"))


def test_s08_w_accepts_string_or_number():
    doc = make_compliant_schema()
    doc["properties"]["a"]["oneOf"][1]["properties"]["w"] = {
        "description": "weight",
        "type": "number",
    }
    assert "S08" not in _codes(lint_schema_doc(_resaidify(doc), "f"))


def test_s09_edge_missing_required_n():
    doc = make_schema_with_edges(VALID_EXTERNAL_SAID)
    edge = doc["properties"]["e"]["oneOf"][1]["properties"]["application"]
    edge["required"] = ["s", "o"]
    doc["properties"]["e"]["oneOf"][1] = saidify_schema_block(
        doc["properties"]["e"]["oneOf"][1]
    )
    assert "S09" in _codes(lint_schema_doc(saidify_schema_block(doc), "f"))


def test_s09_bad_edge_operator():
    doc = make_schema_with_edges(VALID_EXTERNAL_SAID, operator="X2X")
    assert "S09" in _codes(lint_schema_doc(doc, "f"))


def test_s09_malformed_edge_schema_pin():
    doc = make_schema_with_edges("not-a-said")
    assert "S09" in _codes(lint_schema_doc(doc, "f"))


def test_collect_edge_schema_pins():
    doc = make_schema_with_edges(VALID_EXTERNAL_SAID)
    pins = collect_edge_schema_pins(doc)
    assert pins == [
        ("properties.e.oneOf[1].properties.application.properties.s.const",
         VALID_EXTERNAL_SAID)
    ]


def test_lint_result_severity_partitions():
    r = LintResult(findings=[
        LintFinding("f", "p", "S05", "m", "error"),
        LintFinding("f", "p", "T03", "m", "warning"),
    ])
    assert len(r.errors) == 1 and len(r.warnings) == 1
    assert r.is_compliant is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/code/locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template/test_lint.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'locksmith_micro_app_designer.template.lint'`

- [ ] **Step 4: Write the implementation (schema-file half)**

Create `src/locksmith_micro_app_designer/template/lint.py`:

```python
"""SAD/SAID + ACDC-schema compliance linter for micro-app template dirs.

Design (normative check catalog + severities):
docs/superpowers/specs/2026-07-16-acdc-schema-compliance-linter-design.md

Checks S01-S09 run per schemas/*.json document; T01-T07 run across
micro-app-template.json + metadata.json + schemas/ (Task 3); F01/F02 are
file-level (missing / unparseable). Severity "error" = ACDC-spec MUST
violation or SAID/xref integrity failure; "warning" = well-formed but
locally unresolvable (assumed external) or hygiene.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from locksmith_micro_app_designer.template.schema_said import (
    SAID_LABEL,
    is_bare_said,
    iter_said_blocks,
    verify_schema_said,
)

ACDC_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
EDGE_OPERATORS = ("I2I", "NI2I", "DI2I")
DYNAMIC_REF_KEYWORDS = (
    "$dynamicRef", "$dynamicAnchor", "$recursiveRef", "$recursiveAnchor",
)

# ACDC reserved field labels -> JSON-Schema types they may declare.
# None = any type acceptable (cargo). Per keri:acdc references/acdc-structure.md.
RESERVED_LABEL_TYPES: dict[str, tuple[str, ...] | None] = {
    "d": ("string",),
    "u": ("string",),
    "i": ("string",),
    "rd": ("string",),
    "dt": ("string",),
    "n": ("string",),
    "o": ("string",),
    "w": ("string", "number", "integer"),
    "l": ("string",),
    "cargo": None,
}


@dataclass
class LintFinding:
    """A single compliance finding."""
    file: str
    path: str
    code: str
    message: str
    severity: str = "error"  # error | warning


@dataclass
class LintResult:
    """All findings for one template directory."""
    findings: list[LintFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def is_compliant(self) -> bool:
        return not self.errors


def _walk(node: Any, path: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (path, d) for every dict in node, depth-first, insertion order."""
    if isinstance(node, dict):
        yield (path or "<root>", node)
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from _walk(item, f"{path}[{i}]")


def _is_compact_variant(branch: Any) -> bool:
    return isinstance(branch, dict) and branch.get("type") == "string"


def _is_expanded_variant(branch: Any) -> bool:
    return isinstance(branch, dict) and branch.get("type") == "object"


def lint_schema_doc(doc: dict[str, Any], file: str) -> list[LintFinding]:
    """Run per-schema-file checks S01-S09; return findings (file tagged)."""
    findings: list[LintFinding] = []

    # S01 -- top-level $id present and non-empty
    top = doc.get(SAID_LABEL)
    if not isinstance(top, str) or not top:
        findings.append(LintFinding(
            file, SAID_LABEL, "S01", "top-level $id missing or empty",
        ))

    # S02/S03 -- every $id block: bare SAID that verifies
    for path, block in iter_said_blocks(doc):
        value = block.get(SAID_LABEL)
        if not isinstance(value, str) or not value:
            if path != "<root>":  # root covered by S01
                findings.append(LintFinding(
                    file, f"{path}.{SAID_LABEL}", "S02",
                    "bundled sub-schema $id missing or empty",
                ))
            continue
        if not is_bare_said(value):
            findings.append(LintFinding(
                file, f"{path}.{SAID_LABEL}", "S02",
                f"$id {value!r} is not a bare SAID (URI prefixes are "
                "forbidden; must parse as a CESR digest)",
            ))
            continue
        if not verify_schema_said(block):
            findings.append(LintFinding(
                file, f"{path}.{SAID_LABEL}", "S03",
                f"$id does not verify: SAID recomputed over the block's "
                f"content differs from claimed {value!r} (schema SAIDs "
                "hash the file's insertion order; see design spec)",
            ))

    # S04 -- $schema dialect
    if doc.get("$schema") != ACDC_DIALECT:
        findings.append(LintFinding(
            file, "$schema", "S04",
            f"$schema must be {ACDC_DIALECT!r} (ACDC 1.0), "
            f"got {doc.get('$schema')!r}",
        ))

    # S05 -- version present, major.minor.patch
    version = doc.get("version")
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        findings.append(LintFinding(
            file, "version", "S05",
            f"version field must be present in 'major.minor.patch' form "
            f"(ACDC Schema Versioning MUST), got {version!r}",
        ))

    # S06 -- static-schema rules: no dynamic refs; $ref local or SAIDified
    for path, node in _walk(doc):
        for kw in DYNAMIC_REF_KEYWORDS:
            if kw in node:
                findings.append(LintFinding(
                    file, f"{path}.{kw}", "S06",
                    f"dynamic schema reference {kw} is forbidden "
                    "(static-schema rule)",
                ))
        ref = node.get("$ref")
        if isinstance(ref, str):
            local = ref.startswith("#")
            saidified = (
                is_bare_said(ref)
                or ref.startswith("sad:")
                or ref.startswith("did:")
            )
            if not (local or saidified):
                findings.append(LintFinding(
                    file, f"{path}.$ref", "S06",
                    f"non-local $ref {ref!r} is forbidden (must be local "
                    "'#...' or a static SAIDified reference: bare SAID, "
                    "'sad:SAID', or 'did:...')",
                ))

    # S07 -- compact-form-first (ACDC most-compact-form constraint R35)
    for path, node in _walk(doc):
        oneof = node.get("oneOf")
        if not isinstance(oneof, list):
            continue
        has_saided_expanded = any(
            _is_expanded_variant(br) and SAID_LABEL in br for br in oneof
        )
        has_expanded = any(_is_expanded_variant(br) for br in oneof)
        compact_idx = [i for i, br in enumerate(oneof) if _is_compact_variant(br)]
        if not (has_saided_expanded or (has_expanded and compact_idx)):
            continue  # not a compactable-section oneOf
        if not compact_idx:
            findings.append(LintFinding(
                file, f"{path}.oneOf", "S07",
                "compactable section oneOf has no compact (string SAID) "
                "variant (R35)",
            ))
        elif compact_idx[0] != 0 or _is_expanded_variant(oneof[0]):
            findings.append(LintFinding(
                file, f"{path}.oneOf", "S07",
                "compact (string SAID) variant must be FIRST in a "
                "compactable section's oneOf (R35)",
            ))
        for i, br in enumerate(oneof):
            if _is_expanded_variant(br) and SAID_LABEL not in br:
                findings.append(LintFinding(
                    file, f"{path}.oneOf[{i}]", "S02",
                    "expanded variant of a compactable section must carry "
                    "its own verifiable $id (bundled sub-schema rule)",
                ))

    # S08 -- reserved field labels keep their spec types
    for path, node in _walk(doc):
        props = node.get("properties")
        if not isinstance(props, dict):
            continue
        for label, allowed in RESERVED_LABEL_TYPES.items():
            sub = props.get(label)
            if allowed is None or not isinstance(sub, dict):
                continue
            declared = sub.get("type")
            declared_types = (
                [declared] if isinstance(declared, str)
                else declared if isinstance(declared, list) else None
            )
            if declared_types is None:
                continue
            if not set(declared_types) <= set(allowed):
                findings.append(LintFinding(
                    file, f"{path}.properties.{label}.type", "S08",
                    f"reserved ACDC field label {label!r} redefined with "
                    f"divergent type {declared!r} (spec type: "
                    f"{'/'.join(allowed)})",
                ))

    # S09 -- edge blocks: n required; o const in I2I/NI2I/DI2I; s const a SAID
    for path, edge_name, edge in _iter_edge_blocks(doc):
        required = edge.get("required", [])
        if "n" not in required:
            findings.append(LintFinding(
                file, f"{path}.required", "S09",
                f"edge block {edge_name!r} must require 'n' (node SAID)",
            ))
        edge_props = edge.get("properties", {})
        o_const = edge_props.get("o", {}).get("const") if isinstance(
            edge_props.get("o"), dict) else None
        if o_const is not None and o_const not in EDGE_OPERATORS:
            findings.append(LintFinding(
                file, f"{path}.properties.o.const", "S09",
                f"edge operator const {o_const!r} must be one of "
                f"{'/'.join(EDGE_OPERATORS)}",
            ))
        s_const = edge_props.get("s", {}).get("const") if isinstance(
            edge_props.get("s"), dict) else None
        if s_const is not None and not is_bare_said(s_const):
            findings.append(LintFinding(
                file, f"{path}.properties.s.const", "S09",
                f"edge schema pin const {s_const!r} is not a well-formed "
                "bare SAID",
            ))

    return findings


def _iter_edge_blocks(
    doc: dict[str, Any],
) -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Yield (path, edge_name, edge_block) for every edge definition in the
    expanded variant(s) of the top-level `e` section.

    An edge definition is any object-typed property of the expanded e-block
    other than the reserved labels d/u/o.
    """
    e_section = doc.get("properties", {}).get("e")
    if not isinstance(e_section, dict):
        return
    for i, branch in enumerate(e_section.get("oneOf", [])):
        if not _is_expanded_variant(branch):
            continue
        for name, sub in branch.get("properties", {}).items():
            if name in ("d", "u", "o"):
                continue
            if isinstance(sub, dict) and sub.get("type") == "object":
                yield (
                    f"properties.e.oneOf[{i}].properties.{name}", name, sub,
                )


def collect_edge_schema_pins(doc: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (path, said) for every well-formed `s` const pin in the
    expanded e-section edge blocks. Task 3's T06 resolves these against the
    known-SAID set; S09 already reports malformed ones."""
    pins: list[tuple[str, str]] = []
    for path, _name, edge in _iter_edge_blocks(doc):
        s_sub = edge.get("properties", {}).get("s")
        if isinstance(s_sub, dict):
            s_const = s_sub.get("const")
            if isinstance(s_const, str) and is_bare_said(s_const):
                pins.append((f"{path}.properties.s.const", s_const))
    return pins
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/code/locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template/test_lint.py tests/micro_app_template/test_schema_said.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/code/locksmith-micro-app-designer
git add src/locksmith_micro_app_designer/template/lint.py tests/micro_app_template/test_lint.py tests/micro_app_template/conftest.py
git commit -m "feat(lint): per-schema ACDC compliance checks S01-S09"
```

---

### Task 3: `lint.py` — dir-level checks T01–T07 + F01/F02 + golden example tests

**Files:**
- Modify: `src/locksmith_micro_app_designer/template/lint.py` (append dir-level half)
- Modify: `tests/micro_app_template/test_lint.py` (append T/F tests + golden tests)
- Modify: `docs/superpowers/specs/2026-07-16-acdc-schema-compliance-linter-design.md` (name F01/F02 in the error-handling section)

**Interfaces:**
- Consumes: Task 2's `LintFinding`/`LintResult`/`lint_schema_doc`/`collect_edge_schema_pins`; Task 1's `is_bare_said`; existing `saidify.verify_said`.
- Produces (used by Task 4): `lint_template_dir(template_dir: Path) -> LintResult`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/micro_app_template/test_lint.py` (add `from pathlib import Path`, `import pytest`, and the new imports to the top of the file):

```python
from pathlib import Path

import pytest

from locksmith_micro_app_designer.template.lint import lint_template_dir
from locksmith_micro_app_designer.template.saidify import saidify_document

from .conftest import write_template_dir

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLES = REPO_ROOT / "skills/micro-app-template-gen/references/examples"


def _read_dir(root: Path) -> tuple[dict, dict, dict]:
    template = json.loads((root / "micro-app-template.json").read_text())
    metadata = json.loads((root / "metadata.json").read_text())
    schemas = {
        p.name: json.loads(p.read_text())
        for p in sorted((root / "schemas").glob("*.json"))
    }
    return template, metadata, schemas


def test_compliant_dir_zero_findings(compliant_template_dir):
    result = lint_template_dir(compliant_template_dir)
    assert result.findings == []
    assert result.is_compliant is True


def test_t01_template_said_tamper(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["header"]["description"] = "tampered"
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert "T01" in _codes(r.errors)


def test_t02_missing_schema_file(compliant_template_dir):
    (compliant_template_dir / "schemas/test_credential.json").unlink()
    r = lint_template_dir(compliant_template_dir)
    assert "T02" in _codes(r.errors)


def test_t02_schema_said_mismatch(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["credentials"]["exports"][0]["schema"]["schema_said"] = (
        VALID_EXTERNAL_SAID
    )
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert "T02" in _codes(r.errors)


def test_t03_malformed_import_said_is_error(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["credentials"]["imports"] = [
        {"id": "other_credential", "expected_schema_said": "not-a-said"}
    ]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "T03" and f.severity == "error" for f in r.findings)


def test_t03_unresolved_import_said_is_external_warning(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["credentials"]["imports"] = [
        {"id": "other_credential", "expected_schema_said": VALID_EXTERNAL_SAID}
    ]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "T03" and f.severity == "warning" for f in r.findings)
    assert r.is_compliant is True


def test_t04_emission_and_authz_saids(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["commands"] = [{
        "id": "do_thing",
        "emissions": [{
            "kind": "credential",
            "verb": "grant",
            "schema_said_referenced": VALID_EXTERNAL_SAID,
        }],
        "authz": {"method": "credential", "schema_said": "not-a-said"},
    }]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    t04 = [f for f in r.findings if f.code == "T04"]
    assert any(f.severity == "warning" for f in t04)  # external emission SAID
    assert any(f.severity == "error" for f in t04)    # malformed authz SAID


def test_t05_metadata_said_mismatch(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    metadata["for_micro_app_said"] = VALID_EXTERNAL_SAID
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert "T05" in _codes(r.errors)


def test_t06_unresolved_edge_pin_warns(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    schema = make_schema_with_edges(VALID_EXTERNAL_SAID)
    template["credentials"]["exports"][0]["schema"]["schema_said"] = schema["$id"]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(
        compliant_template_dir, template, metadata,
        {"test_credential.json": schema},
    )
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "T06" and f.severity == "warning" for f in r.findings)


def test_t06_edge_pin_resolved_by_template_reference(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    schema = make_schema_with_edges(VALID_EXTERNAL_SAID)
    template["credentials"]["exports"][0]["schema"]["schema_said"] = schema["$id"]
    template["credentials"]["imports"] = [
        {"id": "other_credential", "expected_schema_said": VALID_EXTERNAL_SAID}
    ]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(
        compliant_template_dir, template, metadata,
        {"test_credential.json": schema},
    )
    r = lint_template_dir(compliant_template_dir)
    assert "T06" not in _codes(r.findings)


def test_t07_orphan_schema_warns(compliant_template_dir):
    orphan = make_compliant_schema()
    (compliant_template_dir / "schemas/orphan.json").write_text(
        json.dumps(orphan, indent=2) + "\n"
    )
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "T07" and f.severity == "warning" for f in r.findings)


def test_f01_missing_metadata(compliant_template_dir):
    (compliant_template_dir / "metadata.json").unlink()
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "F01" and f.file == "metadata.json" for f in r.errors)


def test_f01_missing_template(tmp_path):
    (tmp_path / "schemas").mkdir()
    r = lint_template_dir(tmp_path)
    assert any(
        f.code == "F01" and f.file == "micro-app-template.json"
        for f in r.errors
    )


def test_f02_unparseable_schema(compliant_template_dir):
    (compliant_template_dir / "schemas/broken.json").write_text("not json")
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "F02" and f.file == "schemas/broken.json" for f in r.errors)


@pytest.mark.parametrize("name", [
    "regulator-grants-carrier-license",
    "carrier-license-application",
])
def test_worked_examples_pin_known_findings(name):
    """The bundled examples MUST fail S05 (missing schema version) and
    nothing else at error severity. Fixing them re-SAIDs the schemas and
    cascades into locksmith CarrierPlugin trust constants -- an owner-
    scheduled migration. If this test starts failing because S05 stops
    firing, the migration happened: update this test, not the linter."""
    result = lint_template_dir(EXAMPLES / name)
    assert _codes(result.errors) == {"S05"}
    schema_count = len(list((EXAMPLES / name / "schemas").glob("*.json")))
    assert len(result.errors) == schema_count
    assert _codes(result.warnings) <= {"T03", "T04", "T06", "T07"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/code/locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template/test_lint.py -v`
Expected: FAIL — `ImportError: cannot import name 'lint_template_dir'`

- [ ] **Step 3: Write the implementation (dir-level half)**

Append to `src/locksmith_micro_app_designer/template/lint.py` (add `import json` and `from pathlib import Path` to the module imports; also `from locksmith_micro_app_designer.template.saidify import verify_said`):

```python
TEMPLATE_FILE = "micro-app-template.json"
METADATA_FILE = "metadata.json"

# Template keys whose string values are schema-SAID references (T03/T04).
_SAID_REF_KEYS = ("expected_schema_said", "schema_said_referenced", "schema_said")


def _load_json(path: Path, rel: str, findings: list[LintFinding]) -> Any | None:
    """Load a JSON file; on absence/parse failure record F01/F02 and return None."""
    if not path.exists():
        findings.append(LintFinding(rel, "", "F01", f"{rel} not found"))
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        findings.append(LintFinding(rel, "", "F02", f"unparseable JSON: {e}"))
        return None


def _iter_template_said_refs(
    template: dict[str, Any],
) -> Iterator[tuple[str, str, Any]]:
    """Yield (path, key, value) for every schema-SAID reference field in the
    template. `schema_said` paired with a sibling `schema_path` is the export
    pin handled by T02 and is skipped here."""
    for path, node in _walk(template):
        for key in _SAID_REF_KEYS:
            if key not in node:
                continue
            if key == "schema_said" and "schema_path" in node:
                continue  # exports[].schema -- T02's job
            value = node[key]
            if value is None:
                continue
            yield (f"{path}.{key}" if path != "<root>" else key, key, value)


def lint_template_dir(template_dir: Path) -> LintResult:
    """Lint one micro-app template directory. Never raises on bad artifacts:
    missing/unparseable files become F01/F02 findings and remaining checks
    still run where their inputs exist."""
    findings: list[LintFinding] = []
    template_dir = Path(template_dir)

    template = _load_json(template_dir / TEMPLATE_FILE, TEMPLATE_FILE, findings)
    metadata = _load_json(template_dir / METADATA_FILE, METADATA_FILE, findings)

    # Schema files: S01-S09 each, plus collect $ids and edge pins.
    schema_docs: dict[str, dict[str, Any]] = {}
    schemas_dir = template_dir / "schemas"
    if schemas_dir.is_dir():
        for path in sorted(schemas_dir.glob("*.json")):
            rel = f"schemas/{path.name}"
            doc = _load_json(path, rel, findings)
            if doc is not None:
                schema_docs[rel] = doc
                findings.extend(lint_schema_doc(doc, rel))

    local_saids = {
        doc[SAID_LABEL]: rel for rel, doc in schema_docs.items()
        if isinstance(doc.get(SAID_LABEL), str) and doc[SAID_LABEL]
    }

    referenced_paths: set[str] = set()
    referenced_saids: set[str] = set()

    if template is not None:
        # T01 -- template's own SAID
        if not verify_said(template):
            findings.append(LintFinding(
                TEMPLATE_FILE, "d", "T01",
                "template d SAID does not verify against the canonical "
                "(sorted-keys) form",
            ))

        # T02 -- export schema pins
        exports = (template.get("credentials") or {}).get("exports") or []
        for i, export in enumerate(exports):
            schema_ref = export.get("schema")
            if not isinstance(schema_ref, dict):
                continue
            base = f"credentials.exports[{i}].schema"
            schema_path = schema_ref.get("schema_path")
            schema_said = schema_ref.get("schema_said")
            if schema_path:
                referenced_paths.add(schema_path)
                if schema_path not in schema_docs:
                    findings.append(LintFinding(
                        TEMPLATE_FILE, f"{base}.schema_path", "T02",
                        f"schema_path {schema_path!r} not found in template "
                        "directory",
                    ))
                elif schema_docs[schema_path].get(SAID_LABEL) != schema_said:
                    findings.append(LintFinding(
                        TEMPLATE_FILE, f"{base}.schema_said", "T02",
                        f"schema_said {schema_said!r} does not match "
                        f"{schema_path}'s $id "
                        f"{schema_docs[schema_path].get(SAID_LABEL)!r}",
                    ))
            if isinstance(schema_said, str):
                referenced_saids.add(schema_said)

        # T03/T04 -- every other schema-SAID reference in the template
        for path, key, value in _iter_template_said_refs(template):
            code = "T03" if key == "expected_schema_said" else "T04"
            if not is_bare_said(value):
                findings.append(LintFinding(
                    TEMPLATE_FILE, path, code,
                    f"{key} {value!r} is not a well-formed bare SAID",
                ))
                continue
            referenced_saids.add(value)
            if value not in local_saids:
                findings.append(LintFinding(
                    TEMPLATE_FILE, path, code,
                    f"{key} {value!r} does not match any local schemas/*.json "
                    "$id -- assumed external; verify against the ecosystem "
                    "schema registry (future EGF resolver)",
                    severity="warning",
                ))

        # T05 -- metadata binds to this template
        if metadata is not None:
            if metadata.get("for_micro_app_said") != template.get("d"):
                findings.append(LintFinding(
                    METADATA_FILE, "for_micro_app_said", "T05",
                    f"for_micro_app_said "
                    f"{metadata.get('for_micro_app_said')!r} does not match "
                    f"the template's d {template.get('d')!r}",
                ))

    # T06 -- edge `s` const pins resolve against known SAIDs
    known_saids = set(local_saids) | referenced_saids
    for rel, doc in schema_docs.items():
        for path, said in collect_edge_schema_pins(doc):
            if said not in known_saids:
                findings.append(LintFinding(
                    rel, path, "T06",
                    f"edge schema pin {said!r} does not resolve to a local "
                    "schema $id or any template-referenced SAID -- assumed "
                    "external",
                    severity="warning",
                ))

    # T07 -- orphan schema files
    for rel, doc in schema_docs.items():
        said = doc.get(SAID_LABEL)
        if rel not in referenced_paths and said not in referenced_saids:
            findings.append(LintFinding(
                rel, "", "T07",
                "schema file is not referenced by any export schema_path, "
                "import/emission SAID, or edge pin",
                severity="warning",
            ))

    return LintResult(findings=findings)
```

- [ ] **Step 4: Run tests; iterate on the golden expectations**

Run: `cd ~/code/locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template/test_lint.py -v`
Expected: all PASS. The golden tests are the likely wobble point: if the worked examples surface additional *legitimate* error findings (i.e., real spec violations the owner hasn't acknowledged), STOP and re-check by hand against the ACDC reference before touching either the linter or the test — the golden set may only be widened for verified, owner-acknowledged gaps, and the linter may only be fixed for genuine false positives.

- [ ] **Step 5: Amend the design spec's error-handling section with the F-codes**

In `docs/superpowers/specs/2026-07-16-acdc-schema-compliance-linter-design.md`, replace the line:

```
- All per-file checks are independent: one broken schema file doesn't mask findings in others.
```

with:

```
- File-level failures get their own codes: `F01` (expected file missing) and `F02` (unparseable
  JSON), both error severity. All per-file checks are independent: one broken schema file doesn't
  mask findings in others.
```

- [ ] **Step 6: Commit**

```bash
cd ~/code/locksmith-micro-app-designer
git add src/locksmith_micro_app_designer/template/lint.py tests/micro_app_template/test_lint.py docs/superpowers/specs/2026-07-16-acdc-schema-compliance-linter-design.md
git commit -m "feat(lint): dir-level checks T01-T07 + F01/F02; golden tests pin known S05 on worked examples"
```

---

### Task 4: CLI wiring — `micro_app_validate.py --lint`

**Files:**
- Modify: `scripts/micro_app_validate.py`
- Modify: `tests/micro_app_template/test_cli.py`

**Interfaces:**
- Consumes: Task 3's `lint_template_dir`; the `compliant_template_dir` fixture from Task 2.
- Produces: `--lint` flag; output lines `  SEVERITY CODE file:path: message`; exit 1 iff meta-schema/xref validation fails or any error-severity lint finding.

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/micro_app_template/test_cli.py`:

```python
EXAMPLES = REPO_ROOT / "skills/micro-app-template-gen/references/examples"


def test_validate_lint_compliant_dir_exits_zero(compliant_template_dir):
    result = _run(
        VALIDATE,
        "--input", str(compliant_template_dir / "micro-app-template.json"),
        "--lint",
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "LINT OK" in result.stdout


def test_validate_lint_flags_missing_version_on_worked_example():
    template = (
        EXAMPLES / "regulator-grants-carrier-license/micro-app-template.json"
    )
    result = _run(VALIDATE, "--input", str(template), "--lint")
    assert result.returncode == 1
    assert "S05" in result.stderr


def test_validate_without_lint_unchanged_on_worked_example():
    template = (
        EXAMPLES / "regulator-grants-carrier-license/micro-app-template.json"
    )
    result = _run(VALIDATE, "--input", str(template))
    assert result.returncode == 0
    assert "S05" not in result.stdout + result.stderr
```

Note: the compliant-dir fixture's template is built from `minimal_valid_template` and must pass the meta-schema half too — it already does (same seed the existing validate tests use). If the meta-schema rejects the added minimal export entry (`credentials.exports[0]` requires more fields), extend the fixture's export entry in `conftest.py` with the missing required fields reported by the failure rather than weakening the test.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/code/locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template/test_cli.py -v`
Expected: the three new tests FAIL (`--lint` unrecognized / missing fixture wiring); the four pre-existing tests still PASS.

- [ ] **Step 3: Implement the flag**

Replace the body of `main()` in `scripts/micro_app_validate.py` with:

```python
def main() -> int:
    p = argparse.ArgumentParser(description="Validate a micro-app template.")
    p.add_argument("--input", required=True, type=Path, help="Path to micro-app-template.json")
    p.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Path to meta-schema (default: project meta-schema)")
    p.add_argument(
        "--lint", action="store_true",
        help="Also run the SAD/SAID + ACDC-schema compliance lint over the "
             "template directory (requires keripy from the Locksmith venv)",
    )
    args = p.parse_args()

    if not args.input.exists():
        print(f"error: file not found: {args.input}", file=sys.stderr)
        return 2
    if not args.schema.exists():
        print(f"error: schema not found: {args.schema}", file=sys.stderr)
        return 2

    doc = json.loads(args.input.read_text())
    result = validate_template(doc, args.schema)

    if result.is_valid:
        print(f"OK: {args.input} validates against {args.schema.name}")
    else:
        print(f"FAIL: {args.input}", file=sys.stderr)
        for e in result.errors:
            print(f"  {e.path}: {e.message}", file=sys.stderr)

    ok = result.is_valid

    if args.lint:
        try:
            from locksmith_micro_app_designer.template.lint import lint_template_dir
        except ImportError as e:
            print(
                "error: --lint requires keripy (install into / run from the "
                f"Locksmith venv, e.g. ~/code/locksmith/.venv): {e}",
                file=sys.stderr,
            )
            return 2

        lint_result = lint_template_dir(args.input.parent)
        for f in lint_result.findings:
            loc = f"{f.file}:{f.path}" if f.path else f.file
            line = f"  {f.severity.upper()} {f.code} {loc}: {f.message}"
            print(line, file=sys.stderr if f.severity == "error" else sys.stdout)
        if lint_result.is_compliant:
            print(
                f"LINT OK: {args.input.parent} "
                f"({len(lint_result.warnings)} warning(s))"
            )
        else:
            print(f"LINT FAIL: {args.input.parent}", file=sys.stderr)
            ok = False

    return 0 if ok else 1
```

(The lint import stays inside the branch so no-flag invocations never import keripy.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/code/locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template/test_cli.py -v`
Expected: all PASS (7 tests). If the subprocess tests fail with `ModuleNotFoundError`, run `~/code/locksmith/.venv/bin/pip install -e ~/code/locksmith-micro-app-designer` (documented gotcha) and re-run.

- [ ] **Step 5: Commit**

```bash
cd ~/code/locksmith-micro-app-designer
git add scripts/micro_app_validate.py tests/micro_app_template/test_cli.py
git commit -m "feat(cli): micro_app_validate.py --lint runs the ACDC-schema compliance linter"
```

---

### Task 5: SKILL.md documentation + full-suite verification

**Files:**
- Modify: `skills/micro-app-template-gen/SKILL.md`

**Interfaces:**
- Consumes: Task 4's CLI contract (`--lint`, exit semantics).
- Produces: skill documentation; no code.

- [ ] **Step 1: Update the Validation section**

In `skills/micro-app-template-gen/SKILL.md`, replace:

```markdown
## Validation

Before declaring done:

```bash
source .venv/bin/activate
python scripts/micro_app_validate.py --input docs/micro-apps/{path}/micro-app-template.json
python scripts/micro_app_saidify.py --input docs/micro-apps/{path}/micro-app-template.json --verify
```

Both must exit 0.
```

with:

```markdown
## Validation

Before declaring done:

```bash
source .venv/bin/activate
python scripts/micro_app_validate.py --input docs/micro-apps/{path}/micro-app-template.json --lint
python scripts/micro_app_saidify.py --input docs/micro-apps/{path}/micro-app-template.json --verify
```

Both must exit 0.

`--lint` runs the SAD/SAID + ACDC-schema compliance linter over the whole template
directory (checks S01–S09 per `schemas/*.json`, T01–T07 cross-file; catalog in
`docs/superpowers/specs/2026-07-16-acdc-schema-compliance-linter-design.md`). It verifies
every `$id` SAID by recomputation, the `$schema` dialect, the mandatory `version` field,
static-schema `$ref` rules, compact-form-first `oneOf` ordering, reserved-label integrity,
edge-block operators/pins, and that every SAID pinned in the template resolves to a local
schema. Well-formed SAIDs that don't resolve locally (e.g. an imported credential's schema
living in the counterparty's template dir) are **warnings** ("assumed external"), not
failures. Requires keripy (Locksmith venv).
```

- [ ] **Step 2: Correct the canonical-JSON wording in the Output section**

Replace:

```markdown
All files canonical JSON (sorted keys, two-space indent). Template has `d` field set to the computed SAID. Metadata's `for_micro_app_said` matches the template's `d`. Each schema file is its own JSON-Schema document with its own SAID computed via `scripts/saidify_acdc_schema.py` (existing utility) or the same saidify recipe.
```

with:

```markdown
`micro-app-template.json` and `metadata.json` are canonical JSON (sorted keys, two-space
indent). Template has `d` field set to the computed SAID. Metadata's `for_micro_app_said`
matches the template's `d`. Each schema file is its own JSON-Schema document with its own
SAID computed via `scripts/saidify_acdc_schema.py` (existing utility). **Schema files are
insertion-order-sensitive**: their `$id` SAIDs hash the file's key order as written (kli
saidify semantics), so never re-serialize a saidified schema with sorted keys.
```

- [ ] **Step 3: Add the two anti-patterns**

In the `## Anti-patterns` list, after the line `- ❌ Inventing schema SAIDs — they must be content-addressed`, insert:

```markdown
- ❌ Re-serializing a saidified schema with sorted keys — the `$id` binds to the file's key order
- ❌ Shipping a schema without a `version` field ("major.minor.patch") — the linter rejects it (ACDC Schema Versioning MUST)
```

- [ ] **Step 4: Update the Workflow "Saidify and validate" row**

Replace:

```markdown
- **Saidify and validate** — run `scripts/micro_app_saidify.py --in-place` then `scripts/micro_app_validate.py`
```

with:

```markdown
- **Saidify and validate** — run `scripts/micro_app_saidify.py --in-place` then `scripts/micro_app_validate.py --lint` (meta-schema + xrefs + SAD/SAID + ACDC-schema compliance)
```

- [ ] **Step 5: Run the full suite**

Run: `cd ~/code/locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template -v`
Expected: all PASS (existing 60+ tests plus the new lint/schema_said/cli tests). Integration tests (`tests/integration`) need the wallet/vault harness — out of scope; do not run them.

- [ ] **Step 6: Smoke-run the CLI both ways**

```bash
cd ~/code/locksmith-micro-app-designer
~/code/locksmith/.venv/bin/python scripts/micro_app_validate.py \
  --input skills/micro-app-template-gen/references/examples/regulator-grants-carrier-license/micro-app-template.json
~/code/locksmith/.venv/bin/python scripts/micro_app_validate.py \
  --input skills/micro-app-template-gen/references/examples/regulator-grants-carrier-license/micro-app-template.json --lint; echo "exit=$?"
```

Expected: first exits 0 with `OK:`; second prints the S05 findings + `LINT FAIL` and `exit=1` (the known missing-`version` migration gap, by design).

- [ ] **Step 7: Commit**

```bash
cd ~/code/locksmith-micro-app-designer
git add skills/micro-app-template-gen/SKILL.md
git commit -m "docs(skill): document --lint compliance step; schema key-order + version-field rules"
```
