---
name: micro-app-template-gen
description: Use when authoring a single micro-app template — a JSON artifact describing one role's slice of a KERI-native ecosystem application. Walks a subject-matter expert (or AI agent) through producing micro-app-template.json + metadata.json + schemas/*.json conforming to the spec at docs/superpowers/specs/2026-05-09-micro-app-template-authoring-and-data-model.md.
user_invocable: true
---

# Micro-App Template Generator

## Overview

A **micro-app template** captures one role's perspective on one use case in some KERI-native ecosystem. The carrier's side of license-application is one template. The regulator's side is a different template. Multi-actor patterns decompose into multiple templates; bilateral conversations emerge at runtime from KERI-native protocols.

The artifact (`micro-app-template.json` + sibling `metadata.json` + `schemas/*.json`) is what Locksmith (the wallet) reads to render and run a deployed micro-app. This skill walks an SME through producing it.

**Read the spec first:** `docs/superpowers/specs/2026-05-09-micro-app-template-authoring-and-data-model.md` is normative. This skill is one (informative) authoring path. The artifact contract is fixed by the spec.

## When to use

- An SME wants to design a new micro-app from scratch.
- An SME wants to extend an existing template with a new credential, command, workflow, or rule.
- An AI agent is generating a candidate template for human review.
- A template is being forked from a parent and adapted.

## When NOT to use

- Reviewing or editing an existing template without re-walking the steps (use the Micro App: Designer plugin, when available).
- Authoring runtime behavior for a deployed micro-app (that's Locksmith's domain).
- Designing the ecosystem as a whole (no such artifact; ecosystem is emergent).

## Prerequisites

Before starting, confirm:

1. **Which role does this micro-app embody?** Get the role's id (kebab-case), display name, and intrinsic kind.
2. **One-sentence outcome statement?** Past tense, business language ("a license has been granted", "a claim has been adjusted").
3. **Where does the artifact get written?** Default: `docs/micro-apps/{role-id}-{use-case-id}/`.

## Workflow

The 10-step process is **rigid in order**. Step N's questions depend on Step N-1's answers. Within a step, the content is flexible. **Save after each step.**

| # | Step | Reference |
|---|---|---|
| 0 | Identify the role | `references/ten-step-process.md` §Step 0; `references/question-bank.md` §Step 0 |
| 1 | Name the use case (pivotal event) | §Step 1 |
| 2 | Credential imports (the imports list) | §Step 2 |
| 3 | Credential exports (the exports list) | §Step 3 — heaviest step; produces schemas/*.json files |
| 4 | Commands | §Step 4 |
| 5 | Aggregates | §Step 5 |
| 6 | Reactions | §Step 6 |
| 7 | Workflows | §Step 7 |
| 8 | Projections | §Step 8 |
| 9 | Rules | §Step 9 — resolve every forward-referenced rule_ref |
| 10 | Conventions, hints, lineage (metadata.json) | §Step 10 |

Plus:

- **Adversarial review** (between Step 10 and save) — walk `references/adversarial-prompts.md` checklist
- **Author the vectors** (after Step 9 — an `expect_rejected_by` names a rule id, so the rules must exist
  — and before saidify) — every aggregate and projection you added needs `test_vectors[]` at the coverage
  floor: one vector reaching each `fold` handler, and an `expect_rejected_by` vector naming each
  invariant. See `references/ten-step-process.md` §Vectors.
- **Saidify and validate** — run `scripts/micro_app_saidify.py --in-place` then `scripts/micro_app_validate.py --lint` (meta-schema + xrefs + SAD/SAID + ACDC-schema compliance)

## Reference files

| File | Purpose |
|---|---|
| `references/ten-step-process.md` | Detailed prose for each step — rationale, field mappings, anti-patterns |
| `references/question-bank.md` | Primary + follow-up questions to ask per step |
| `references/adversarial-prompts.md` | Pre-save adversarial review checklist |
| `references/rule-types-reference.md` | Per-type rule guidance with worked examples |
| `references/cel-1.0-cheat-sheet.md` | CEL/1.0 syntax: bound contexts per position, operators, idioms, format pipes, profile extension functions, gotchas |
| `references/naming-conventions.md` | Recommended naming for credentials, roles, workflows, routes |
| `references/skeleton.json` | Copyable starting template (minimal-valid with REPLACE-ME fields) |
| `references/examples/` | Worked examples (one per ecosystem domain, when available) |
| the `acdc-design` skill | Credential-type design decisions consumed at Step 3 (targeted/untargeted, `u`/blinding, disclosure, edges, registry, versioning, governance) |

## Discipline (rigid)

- **Walk steps in order.** No skipping. Step N's answers depend on Step N-1's.
- **One question at a time.** Don't batch.
- **Save after each step.** Never lose progress.
- **Plain language.** Push back on KERI jargon (AID, IPEX) in user-facing fields. Use spec vocabulary (Roles, Credentials, Workflows).
- **Resolve every forward reference.** Step 9 walks all rule_refs surfaced in Steps 3-8; nothing dangles.
- **Run validation before declaring done.** `scripts/micro_app_validate.py` must pass.
- **Saidify before committing.** `scripts/micro_app_saidify.py --in-place` stamps the `d` field.

## Anti-patterns

- ❌ Authoring two roles in one template — split into two
- ❌ Skipping Step 9 (rules) — most contractual and enforcement substance lives there
- ❌ Skipping the adversarial review — the highest-value step
- ❌ Inventing schema SAIDs — they must be content-addressed
- ❌ Re-serializing a saidified schema with sorted keys — the `$id` binds to the file's key order
- ❌ Shipping a schema without a `version` field ("major.minor.patch") — the linter rejects it (ACDC Schema Versioning MUST)
- ❌ Authoring an attribute-only export schema — an ACDC schema is the full *envelope* (`v/d/i/ri/s/a.oneOf`); the SME's attributes nest under `a.oneOf[1]` with `d/i/dt`. A top-level attribute schema fails ACDC issuance (`'<field>' is a required property`). See ten-step §Step 3.
- ❌ Authoring on `/ipex/*` routes — reserved for protocol
- ❌ Conflating imported credentials with exported credentials — different lists, different purposes
- ❌ Putting state or principal in `idempotency_key_expression` — must be deterministic from payload alone

## Recovery / resumption

If the user re-enters with a partial template:

1. Read the existing `micro-app-template.json`
2. Identify the first unfilled or incomplete primitive (often: empty arrays past a certain step)
3. Summarize what's filled in 3-5 lines
4. Resume at the first unfilled step

## Output

A directory at `docs/micro-apps/{role-id}-{use-case-id}/` containing:

```
{role-id}-{use-case-id}/
├── micro-app-template.json
├── metadata.json
└── schemas/
    ├── {credential_a}.json
    ├── {credential_b}.json
    └── ...
```

`micro-app-template.json` and `metadata.json` are canonical JSON (sorted keys, two-space
indent). Template has `d` field set to the computed SAID. Metadata's `for_micro_app_said`
matches the template's `d`. Each schema file is its own JSON-Schema document with its own
SAID computed via `scripts/saidify_acdc_schema.py` (existing utility). **Schema files are
insertion-order-sensitive**: their `$id` SAIDs hash the file's key order as written (kli
saidify semantics), so never re-serialize a saidified schema with sorted keys.

## Validation

Before declaring done:

```bash
source .venv/bin/activate
python scripts/micro_app_validate.py --input docs/micro-apps/{path}/micro-app-template.json --lint
python scripts/micro_app_saidify.py --input docs/micro-apps/{path}/micro-app-template.json --verify
```

Both must exit 0.

Then the two concierge-api gates. **Both must exit 0**, and they cover different things — neither
substitutes for the other.

`micro-app check` — the static gate. It is the **only** one that sees routing and emission-binding
defects (`boundary.instance_key` / `primary_key` coverage, every `event.<field>` a fold reads being
supplied by some emission's `payload_mapping`). A test vector structurally cannot catch these, because
it supplies its own event payloads. Needs no vault and no keri stack.

```bash
cd ~/code/concierge-api && PYTHONPATH=src ~/code/keripy/.venv/bin/python -m concierge_api_local.cli.microapp \
  check --template <abs path to docs/micro-apps/{path}/micro-app-template.json>
```

`micro-app vectors` — the behavioral coverage gate. It **executes** your `test_vectors[]`.

```bash
cd ~/code/concierge-api && PYTHONPATH=src ~/code/keripy/.venv/bin/python -m concierge_api_local.cli.microapp \
  vectors --template <abs path to docs/micro-apps/{path}/micro-app-template.json> \
  --baseline <abs path to docs/micro-apps/coverage-baseline.json>
```

Your new units are absent from the baseline, so they are held to 100% on both metrics (every `fold`
handler exercised, every invariant pinned by an `expect_rejected_by`). **Run the vectors — do not merely
write them**; the runner has twice turned an argument into a fact. This gate is deliberately not wired
into `micro-app build`, which stays hermetic.

`--lint` runs the SAD/SAID + ACDC-schema compliance linter over the whole template
directory (checks S01–S09 per `schemas/*.json`, T01–T07 cross-file; catalog in
`docs/superpowers/specs/2026-07-16-acdc-schema-compliance-linter-design.md`). It verifies
every `$id` SAID by recomputation, the `$schema` dialect, the mandatory `version` field,
static-schema `$ref` rules, compact-form-first `oneOf` ordering, reserved-label integrity,
edge-block operators/pins, and that every SAID pinned in the template resolves to a local
schema. Well-formed SAIDs that don't resolve locally (e.g. an imported credential's schema
living in the counterparty's template dir) are **warnings** ("assumed external"), not
failures. Requires keripy (Locksmith venv).
