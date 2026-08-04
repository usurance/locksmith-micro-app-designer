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
| **1.5** | **KERI-shape pass** — convert requirement verbs into KERI primitives *before* choosing mechanics | **`references/keri-shape-pass.md`** — mandatory; re-entered by the back-edge |
| 2 | Credential imports (the imports list) | §Step 2 |
| 3 | Credential exports (the exports list) | §Step 3 — heaviest step; produces schemas/*.json files |
| 4 | Commands | §Step 4 |
| 5 | Aggregates | §Step 5 |
| 6 | Reactions | §Step 6 |
| 7 | Workflows | §Step 7 |
| 8 | Projections | §Step 8 |
| 9 | Rules | §Step 9 — resolve every forward-referenced rule_ref |
| 10 | Conventions, hints, lineage (metadata.json) | §Step 10 |

### The affordance grammar

A template's behavior decomposes into eleven affordances — a small, human-facing vocabulary for
what a Role does, grouped by position in the canonical abstract loop ("request compute based on my
credentials; the compute returns credentials attesting that the compute was done"). A reader holds
seven groups; the eleven leaves are the precision:

| | Affordance | Template surface |
|---|---|---|
| **authorization in** | *I hold* | `imports[]` naming me as Issuee (targeted ACDC — authority I can prove I possess) |
| | *I rely on* | `imports[]` untargeted, or targeted at another (evidence I verify but am not the subject of) |
| **the act** | *I respond to* | `commands[]` — authority exercised in the moment, then signed |
| | *I answer unattended* | `reactions[]`, `trigger: "automatic"`, `time_bound` — my AID signs on a standing precommitment declared in advance |
| **ACDC out** | *I issue* | `exports[]` **with** `holder_role` — targeted, I confer on a named party |
| | *I attest* | `exports[]` **without** `holder_role` — untargeted, "to whom it may concern" |
| **provable** | *I anchor* | TEL events (derived) + `log_scope`, kind-2 artifacts (declared) — commitment with **no ACDC at all** |
| conversations | *I follow* | `workflows[]` |
| state | *I track* | `aggregates[]` |
| | *I see* | `projections[]` — read-side view, never a protocol act |
| constraints | *I am bound by* | `rules[]` |

Only *I issue*, *I attest* and *I anchor* leave a trace in the Role's own **KEL** — three, not four.
*I answer unattended* and *I respond to* leave a **signed** trace: an `exn` is a KERI "Other Message",
which the spec puts in the class of messages *"not part of a KEL"* (KERI spec § *Message type field*),
so a reaction leaves a KEL trace only when it also mints (*I issue* / *I attest*) or anchors
(*I anchor*). The three that do get theirs from the anchoring requirement: *"The SAID of this event
MUST be anchored in the Issuer's KEL as the Registry proof seal. Update events in the Registry's TEL
MUST also be anchored"* (ACDC spec § *Issuance and Revocation*). *(Corrected 2026-08-02, fix round 2:
this line read "four … and *I answer unattended*", copied from the vision document, and contradicted
canon §5's audit table in the same paragraph that sends you to canon §5. The vision document was the
defect; canon and both specs agree on three.)* The full reasoning for each row — why the grammar reads
eleven rather than the original seven, why each addition earns its place, and the audit table that
splits KEL trace from signed trace — is in `docs/canon/keri-conceptual-contours.md` §5 (ugard repo).

Two of the eleven have their own dedicated per-step diagnostic below, because the targeted/untargeted
line is the one modelling mistake this grammar exists to make visible, and it cuts both ways
(imports as well as exports).

### The import diagnostic (run per import, at Step 2)

**Ask, for every import: is this an "I hold" or an "I rely on"?**

- *I hold* — targeted at me: an ACDC naming me as Issuee, authority I can prove I possess.
- *I rely on* — untargeted, or targeted at another party: evidence I verify but am not the
  subject of.

Conflating the two is precisely the conflation behind the 82%-of-commands authorization finding in
`docs/canon/keri-conceptual-contours.md` §4.3 (ugard repo) — see §5 for how the grammar makes it
visible in the model rather than only in a linter.

### The export diagnostic (run per export, at Step 3)

**Ask, for every export: is this an "I issue" or an "I attest"?**

- *I issue* — targeted: it confers something on a named party, who can prove they hold it.
  Declare `holder_role`; the schema declares `i`.
- *I attest* — untargeted: it asserts something, to whom it may concern. **Omit `holder_role`**;
  the schema omits `i`.

If you cannot answer, the export is mis-modelled. This one question catches four of the five
bundles in the corpus that this model change exists to replace.

The measurement and the full reasoning — why `holder_role` used to be required, what that forced
every export to become, and why the fix is three distinguishable shapes rather than one optional
field — are in `docs/canon/keri-conceptual-contours.md` §4.3 (ugard repo).

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
| `references/keri-shape-pass.md` | **Step 1.5.** The five diagnostic questions (credential? lifecycle? ordering fact? array-element discrimination? identity?), the existence-vs-value rule with `validate_edge` quoted, the truth-maker rule, the counter-test for what stays a mechanic, the back-edge, and the `keri:*` routing table |
| `references/ten-step-process.md` | Detailed prose for each step — rationale, field mappings, anti-patterns |
| `references/question-bank.md` | Primary + follow-up questions to ask per step |
| `references/adversarial-prompts.md` | Pre-save adversarial review checklist |
| `references/rule-types-reference.md` | Per-type rule guidance with worked examples |
| `references/cel-1.0-cheat-sheet.md` | CEL/1.0 syntax: bound contexts per position, operators, idioms, format pipes, profile extension functions, gotchas |
| `references/naming-conventions.md` | Recommended naming for credentials, roles, workflows, routes |
| `references/skeleton.json` | Copyable starting template (minimal-valid with REPLACE-ME fields) |
| `references/examples/` | Worked examples (one per ecosystem domain, when available) |
| the `acdc-design` skill | Credential-type design decisions consumed at Step 3 (targeted/untargeted, `u`/blinding, disclosure, edges, registry, versioning, governance). Step 1.5 decides *whether* there is a credential; this decides *what it looks like* |
| the `keri:acdc` skill | Edge operators and `validate_edge`, TEL registry patterns and `ts` state sets, disclosure — reached at Steps 1.5, 2–3 and 5–6 |
| the `keri:spec` skill | KEL anchoring, ordering, key state — reached at Steps 5–6 where a fold or workflow relies on them |
| the `keri:chat` skill | Adjudicates a protocol claim the template's prose makes; reached at adversarial review. Hosted, so it can be unavailable — fall back to the two reference skills above, which carry the same normative text locally |

## Discipline (rigid)

- **Walk steps in order.** No skipping. Step N's answers depend on Step N-1's.
- **One question at a time.** Don't batch.
- **Save after each step.** Never lose progress.
- **Run the KERI-shape pass before Step 2, and record its five answers.** `references/keri-shape-pass.md`.
- **Existence over values.** ACDC enforces constraints over existence and identity; it cannot enforce
  constraints over values inside a thing. When a requirement states a constraint, convert it into an
  existence constraint wherever the domain allows — usually by changing an object's granularity, not
  by adding a field. `validate_edge` never compares a near-node attribute against a far-node one.
- **The back-edge.** If a command, reaction, or projection needs a value the trigger cannot supply,
  **do not add a field — return to the shape pass, then to Step 3.** The default resolution is that
  the credential is the wrong shape or the wrong granularity. Making the names agree and declaring a
  mint (§6.5 `from`) are the only other legal moves, and neither can supply a value derived from
  state.
- **Plain language in user-facing fields** — names, descriptions, display strings: push back on KERI
  jargon (AID, IPEX) there, and use spec vocabulary (Roles, Credentials, Workflows). **KERI
  vocabulary is required when choosing the model** — see the KERI-shape pass. Keeping the jargon out
  of the UI is not a reason to keep the primitives out of the design.
- **Resolve every forward reference.** Step 9 walks all rule_refs surfaced in Steps 3-8; nothing dangles.
- **Run validation before declaring done.** `scripts/micro_app_validate.py` must pass.
- **Saidify before committing.** `scripts/micro_app_saidify.py --in-place` stamps the `d` field.

## Anti-patterns

- ❌ Authoring two roles in one template — split into two
- ❌ Skipping Step 9 (rules) — most contractual and enforcement substance lives there
- ❌ Skipping the adversarial review — the highest-value step
- ❌ Skipping the KERI-shape pass — the step that decides whether the other ten are modeling the right objects
- ❌ Saying "ACDC" when you mean the **ACDC schema** (the type) or vice versa — and calling an *untargeted* ACDC a credential. Four words, authoring spec §4: **ACDC** = the instance; **ACDC schema** = the type (`s` *is* the type field); **credential** = targeted (has an issuee); **attestation** = untargeted. "One credential per scope" means many instances of ONE schema, never a schema per scope
- ❌ Writing bare "schema" for an ACDC schema — `payload_schema`, `row_schema` and `state_schema` are ordinary JSON-Schema for local slots and are the *majority* of schema-bearing keys in this model
- ❌ Modeling a credential's supersession as a **domain event** — it is a TEL state change (or a `supersedes` edge); pick one spelling and record it
- ❌ A **status column set by a fold literal** — which event arrived is not a lifecycle; the lifecycle is the credential's TEL state and "current" is a dated query
- ❌ A **parser- or human-minted string as the identity** of an issued artifact — a foreign coordinate (identifier kind 4) is provenance, never the key
- ❌ A **boolean asserting an ordering** an edge could enforce — `*_before_*`, `already_*`, `size(state.x) > 0`
- ❌ An **array attribute standing in for per-scope authorization** — an edge targets a credential, not an array element, so the chain has nothing to discriminate against
- ❌ A **derived flag frozen at ingest** — written once on upsert, never recomputed; if it is an observation it is a read-time as-of evaluation
- ❌ A **flag with no consumer** — no rule, precondition, invariant, filter or notification reads it. If prose says a human must see it, route it somewhere
- ❌ **Defending against a hazard the protocol already eliminates** — verify the claim against the spec (`keri:acdc` / `keri:spec`); when canon and spec disagree, the canon is the defect
- ❌ Inventing schema SAIDs — they must be content-addressed
- ❌ Re-serializing a saidified schema with sorted keys — the `$id` binds to the file's key order
- ❌ Shipping a schema without a `version` field ("major.minor.patch") — the linter rejects it (ACDC Schema Versioning MUST)
- ❌ Authoring an attribute-only export schema — an ACDC schema is the full *envelope* (`v/d/i/ri/s/a.oneOf`); the SME's attributes nest under `a.oneOf[1]` with `d/i/dt`. A top-level attribute schema fails ACDC issuance (`'<field>' is a required property`). See ten-step §Step 3.
- ❌ Authoring on `/ipex/*` routes — reserved for protocol
- ❌ Conflating imported credentials with exported credentials — different lists, different purposes

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
cd ~/code/locksmith-micro-app-designer && PYTHONPATH=src ~/code/keripy/.venv/bin/python \
  scripts/micro_app_validate.py --input <abs path to micro-app-template.json> --lint
```

```bash
cd ~/code/locksmith-micro-app-designer && PYTHONPATH=src ~/code/keripy/.venv/bin/python \
  scripts/micro_app_saidify.py --input <abs path to micro-app-template.json> --verify
```

Both must exit 0. `micro_app_validate.py` is the gate that reads the **meta-schema**, so it is the
one that sees a malformed `events` block (Step 5).

**`PYTHONPATH=src` and an explicit interpreter are required.** This repo has no `.venv` and the
package is not installed, so the previously-documented `source .venv/bin/activate` silently did
nothing and both scripts died with `ModuleNotFoundError: locksmith_micro_app_designer`. Same shape as
the concierge invocations below. (The 8 `test_cli.py` failures in this repo's suite have the same
single cause and are pre-existing; 161 pass without them.)

Then the two concierge-api gates. **Both must exit 0**, and they cover different things — neither
substitutes for the other.

`micro-app check` — the static gate. It is the **only** one that sees routing and emission-binding
defects (`boundary.instance_key` / `primary_key` coverage, every `event.<field>` a fold reads being a
`required` property of that event's declared `payload_schema`, one of the eight envelope names,
or a declared `from` mint of one of them).
A test vector structurally cannot catch these, because
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
