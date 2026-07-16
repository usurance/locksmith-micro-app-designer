# SAD/SAID + ACDC-Schema Compliance Linter — Design

**Date:** 2026-07-16
**Status:** approved (owner directive 2026-07-16, HOA-onboarding/EGF brainstorm in ugard: "the micro
app template gen skill should also have a linter to ensure compliance" with the SAD/SAID-everywhere
paradigm)
**Spec authority:** ACDC specification (keri:acdc skill, `references/acdc-structure.md`); template
contract at `../ugard/docs/superpowers/specs/2026-05-09-micro-app-template-authoring-and-data-model.md`

## Problem

`micro_app_validate.py` checks the template against the meta-schema and resolves internal
cross-references, and `micro_app_saidify.py --verify` checks the template's own `d`. Nothing checks
the **ACDC schemas** in `schemas/*.json` — the artifacts whose SAIDs are pinned into counterparty
templates, edge blocks, and locksmith trust constants. Today a schema can ship with a stale `$id`,
a missing `version` field, a dynamic `$ref`, or a compact-form-last `oneOf`, and no tool objects.
The SAD/SAID-everywhere paradigm demands that every content-addressed claim in a template directory
be *recomputed and compared*, not trusted.

## Goals

Lint a micro-app template directory (`micro-app-template.json` + `metadata.json` + `schemas/*.json`)
for ACDC-spec compliance and SAID integrity, wired into the existing validate entry point and
documented in the skill.

## Non-goals

- No rewriting/fixing of artifacts (lint reports; `saidify_acdc_schema.py` remains the write path).
- No network/registry resolution of external SAIDs — that is the future EGF resolver's job
  (ugard backlog: SAID-native EGF doc + resolver in keri_serviceaid). The linter leaves a clean seam.
- No re-SAIDing of the existing carrier schemas. Adding their missing `version` field changes their
  SAIDs, which are baked into locksmith `CarrierPlugin` trust constants — that migration is
  scheduled deliberately by the owner. The linter **is expected to fire** on them until then.

## Approaches considered

- **A. Pure-library `template/lint.py` + `--lint` flag on `micro_app_validate.py` (chosen).**
  Follows the repo's library/Qt split ("keep new template-semantics logic in the library");
  testable without Qt; `validate.py` stays keripy-free for the plugin's in-editor validation panel.
- **B. Extend `validate_template()` in place, always-on.** Rejected: `validate_template` is a pure
  `dict -> result` function used by the editor on unsaved documents; the linter is inherently
  multi-file I/O + keripy. Also flips existing green invocations red without an opt-in.
- **C. Standalone `micro_app_lint.py` script only.** Rejected: owner directive says wire into the
  existing validate entry point; a parallel script invites drift and gets skipped.

## Design

### Module layout (pure library, no Qt)

```
src/locksmith_micro_app_designer/template/
├── schema_said.py   # NEW — ACDC-schema SAID compute/verify ($id label), kli-parity
└── lint.py          # NEW — check catalog + lint_template_dir orchestration
scripts/micro_app_validate.py   # gains --lint
```

### SAID recompute semantics (load-bearing)

Two different canonical forms coexist in a template dir, and the linter must honor both:

| Artifact | Label | Key order hashed | Existing tool |
|---|---|---|---|
| `micro-app-template.json` | `d` | recursively **sorted** (canonical_json form) | `saidify.py` (`Saider.saidify`, Blake3-256) |
| `schemas/*.json` (top level and every nested `$id` block) | `$id` | **file insertion order — no sorting** | `kli saidify --label '$id'` via `saidify_acdc_schema.py` |

`kli saidify` is `Saider.saidify(sad=json.load(f), label=label)` — it hashes the mapping in file
order. Verified empirically 2026-07-16: recomputing the bundled worked-example schemas with sorted
keys MISMATCHES every `$id`; recomputing in insertion order MATCHES every `$id` (top-level and
nested `a`/`e` blocks, both example templates). Consequences:

1. `schema_said.py` computes with `Saider.saidify(sad=dict(block), label="$id")` — **never** the
   sorted-keys recursion in `saidify.py`.
2. Schema files are **order-sensitive artifacts**. Re-serializing them with sorted keys breaks
   their SAIDs. The SKILL.md output-contract wording ("all files canonical JSON, sorted keys") is
   corrected as part of this work: template + metadata are canonical-sorted; schemas keep their
   authoring order once saidified.
3. Nested blocks verify independently over their stored content (bottom-up authorship means the
   top-level hash covers the nested `$id` values as stored; verification order is irrelevant).

`schema_said.py` API:

```python
def compute_schema_said(block: dict) -> str          # label "$id", insertion order preserved
def verify_schema_said(block: dict) -> bool          # recompute == claimed
def iter_said_blocks(doc: dict) -> Iterator[tuple[str, dict]]   # (json_path, block) for every
                                                     # dict at any depth carrying "$id", root first
def is_bare_said(value: str) -> bool                 # CESR digest parse (Saider(qb64=...)), no URI scheme
```

### Check catalog

Findings carry `(file, path, code, message, severity)`. Severity: `error` = ACDC-spec MUST
violation or SAID/xref integrity failure (exit 1); `warning` = unverifiable-locally or hygiene
(exit 0). Codes are stable identifiers for docs/tests.

**Per schema file — `schemas/*.json`:**

| Code | Check | Severity |
|---|---|---|
| S01 | Top-level `$id` present and non-empty | error |
| S02 | Every `$id` (top-level + nested) is a **bare SAID**: no URI scheme/prefix, parses as a CESR digest primitive | error |
| S03 | Every `$id` block **verifies**: recomputed SAID over the block's stored (insertion-order) content equals the claimed `$id` | error |
| S04 | `$schema` present and exactly `"https://json-schema.org/draft/2020-12/schema"` (ACDC 1.0) | error |
| S05 | `version` present and `major.minor.patch` (`^\d+\.\d+\.\d+$`) — ACDC Schema Versioning: "version field MUST be present" | error |
| S06 | Static-schema rules: no `$dynamicRef`/`$dynamicAnchor`/`$recursiveRef`/`$recursiveAnchor` anywhere; every `$ref` is local (`#...`) or a static SAIDified reference (bare SAID, `sad:SAID`, `did:...`); `http(s)://` refs forbidden | error |
| S07 | Compact-form-first (R35): in any `oneOf` that contains both a string-typed (compact SAID) variant and an object variant carrying `$id`, the compact variant is **first** | error |
| S08 | Reserved labels (`d`,`u`,`i`,`rd`,`dt`,`n`,`o`,`w`,`l`,`cargo`) declared in any `properties` map at any depth must be type-compatible with the ACDC reserved-field table (`d/u/i/rd/dt/n/o/l`: string; `w`: string or number; `cargo`: any). Divergent declared type = redefinition | error |
| S09 | Edge blocks (expanded `e`-section variant): every edge property object requires `n`; a `const`-pinned `o` must be one of `I2I`/`NI2I`/`DI2I`; a `const`-pinned `s` must be a well-formed bare SAID | error |

**Template/dir level — cross-file:**

| Code | Check | Severity |
|---|---|---|
| T01 | Template `d` verifies (existing `verify_said`, sorted-canonical form) | error |
| T02 | Every `credentials.exports[].schema`: `schema_path` exists in the dir; `schema_said` equals that file's top-level `$id` | error |
| T03 | Every `credentials.imports[].expected_schema_said`: well-formed bare SAID (error if malformed); resolves to a local `schemas/*.json` `$id`, else reported **external** | warning (external) |
| T04 | Every emission `schema_said_referenced` and `authz.schema_said`: well-formed (error if malformed); local match, else external | warning (external) |
| T05 | `metadata.json` `for_micro_app_said` equals the template's `d` | error |
| T06 | Edge `s` const pins inside schemas resolve against known SAIDs (local schema `$id`s ∪ SAIDs referenced by the template), else external | warning (external) |
| T07 | Orphan schema file: a `schemas/*.json` never referenced by any export `schema_path`, import SAID, emission SAID, or edge pin | warning |

**External-reference policy (T03/T04/T06):** a well-formed SAID that doesn't resolve inside the
template dir is *assumed external* (the normal case for imports — the counterparty's export schema
lives in the counterparty's template dir) and reported as a warning naming the SAID, so a human or
a future EGF resolver can verify it against the ecosystem registry. No new metadata fields are
invented to suppress these; when the EGF resolver lands, these warnings become resolvable checks.

### API and CLI wiring

```python
@dataclass
class LintFinding:
    file: str        # path relative to the template dir ("" for dir-level findings)
    path: str        # JSON-path-ish location within the file
    code: str        # "S03", "T02", ...
    message: str
    severity: str    # "error" | "warning"

@dataclass
class LintResult:
    findings: list[LintFinding]
    @property
    def errors(self) -> list[LintFinding]
    @property
    def warnings(self) -> list[LintFinding]
    @property
    def is_compliant(self) -> bool   # no error-severity findings

def lint_template_dir(template_dir: Path) -> LintResult
```

`lint_template_dir` degrades gracefully: missing `metadata.json` or `schemas/` yields findings,
not crashes; unparseable JSON yields a single error finding for that file.

`scripts/micro_app_validate.py` gains `--lint`: after the existing meta-schema + xref validation of
`--input`, it treats the input's parent directory as the template dir and runs
`lint_template_dir`, printing findings grouped by file as `severity CODE file:path: message`.
Exit code 1 if the meta-schema/xref validation fails **or** any lint finding is error-severity;
warnings alone exit 0. Without `--lint`, behavior is byte-identical to today (the editor plugin and
existing callers are untouched; keripy is only imported under `--lint`).

### Known-findings posture (bundled examples)

The worked-example/fixture schemas (`carrier_license.json`, `carrier_license_application.json` —
mirrored 1:1 in ugard `docs/micro-apps/`) lack `version`, so S05 fires on them **by design**. The
test suite pins this as a golden expectation: linting the bundled examples must report exactly the
known S05 errors (plus expected external-SAID warnings) and nothing else at error severity. Fixing
the schemas re-SAIDs them and cascades into locksmith `CarrierPlugin` trust constants — an owner-
scheduled migration, out of scope here.

## Error handling

- keripy import failure raises at `--lint` invocation with a message pointing at the Locksmith
  venv convention (`~/code/locksmith/.venv`); the no-flag path never imports keri via lint.
- All per-file checks are independent: one broken schema file doesn't mask findings in others.
- Malformed SAID strings in template reference fields are errors (T03/T04 "well-formed" half), not
  external warnings — external status is only granted to values that parse as SAIDs.

## Testing

pytest, in-process, under `tests/micro_app_template/`:

- `test_schema_said.py` — compute/verify round-trip on constructed schema blocks; tamper detection;
  insertion-order sensitivity (sorted rehash of a saidified block MISMATCHES — pins kli parity);
  `iter_said_blocks` depth coverage; `is_bare_said` accept/reject (URI-prefixed, wrong length,
  non-digest codes).
- `test_lint.py` — a programmatically built **fully-compliant** template dir fixture (minimal
  template + one export schema with `version`, saidified via the library; matching metadata) yields
  zero findings; then one test per check code, each breaking exactly one rule in a copy of the
  compliant fixture and asserting exactly that finding fires.
- Golden tests over `skills/micro-app-template-gen/references/examples/*`: expected S05 errors,
  expected external warnings, no other errors — pins the known-migration state.
- `test_cli.py` additions — `--lint` exits 1 on the bundled example (S05), exits 0 on the compliant
  tmp fixture, and no-flag invocations are unchanged. (Subprocess tests require the editable
  install, per the existing gotcha.)

## Documentation (SKILL.md)

- Validation section: add the `--lint` invocation as a required pre-done step alongside the two
  existing commands.
- Output contract: correct the canonical-JSON wording — schemas are insertion-order-sensitive once
  saidified; never re-sort them.
- Anti-patterns: add "❌ Re-serializing a saidified schema with sorted keys — the `$id` binds to the
  file's key order" and "❌ Shipping a schema without a `version` field".
- Note the check-code table (or point to this spec) and the external-warning semantics.

## Environment

Designer repo has no venv of its own; run with the Locksmith venv
(`~/code/locksmith/.venv/bin/python`, keripy 2.0.0-dev6, jsonschema 4.26; pytest `pythonpath`
covers `src`). `kli` remains the write-path tool; the linter never shells out.
