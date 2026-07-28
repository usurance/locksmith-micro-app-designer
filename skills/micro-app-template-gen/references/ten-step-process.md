# The Ten-Step Process (Detailed)

Detailed prose for each step of the micro-app template authoring path. The SKILL.md gives a one-line summary per step; this file gives the full context, rationale, and instructions.

## Step 0 — Identify the role

**Goal:** Select the single role this micro-app embodies. Every subsequent step is from this role's perspective.

**Why this is Step 0:** A micro-app captures *one role's slice* of a use case. Multi-actor patterns decompose into multiple templates. Naming the role first prevents scope creep into multi-role territory.

**What to capture:**

| Field | Notes |
|---|---|
| `role.id` | kebab-case stable identifier (e.g., `carrier`, `homeowner`, `state-doi`) |
| `role.display_name` | Title case label for UI ("Insurance Carrier", "Homeowner") |
| `role.description` | One paragraph explaining what this role *is* in the ecosystem |
| `role.kind` | One of: individual, organization, system, device, agent, government |
| `role.keri_infrastructure` | Four boolean flags (witness_pool, watcher_network, mailbox, acdc_registry) |

**Suggesting defaults for `keri_infrastructure`:**

- `individual` → mailbox usually true; witness_pool/watcher_network/acdc_registry usually false
- `organization`, `government` → all four typically true
- `system`, `agent` → mailbox true; others depend on operational scope
- `device` → usually only mailbox

Let the SME override defaults. The flags are deployment-readiness *expectations* — not enforcement.

**Anti-patterns:**

- ❌ Declaring two roles ("carrier and broker") — split into two templates
- ❌ Picking the wrong kind ("carrier is a person") — explain what kinds mean
- ❌ Skipping keri_infrastructure ("I don't know what these mean") — default by kind

**Save:** Write `role` field to the output template. The header (Step 1) hasn't been authored yet; defer the file write until the canonical JSON has at least `header + role`.

## Step 1 — Name the use case

**Goal:** Capture the use case's identity (header) and articulate the pivotal event from this role's perspective.

**Why this matters:** The "pivotal event" is the past-tense fact that defines success. Naming it sharpens the scope and reveals when you're actually trying to model two use cases.

**Questions to ask:**

1. *Outcome statement?* — One sentence in past tense, in the role's voice. "A claim has been filed." "A license has been granted."
2. *Multiple events surfacing?* — If two pivotal events compete, you have two micro-apps. Stop and split.
3. *Version?* — Start at `"1.0"` unless this is explicitly a fork of an existing template (Step 0 already captured the role; the header version is independent).
4. *Forked from?* — If derived from another template, capture the parent's SAID + version + intent.

**Field mapping:**

| Field | Source |
|---|---|
| `header.id` | kebab-case use case identifier (often `<role>-<verb>-<noun>`) |
| `header.display_name` | Title case label |
| `header.description` | The pivotal event statement + 1-2 sentences of context |
| `header.version` | Semver |
| `header.expression_language` | `"CEL/1.0"` (default for now) |
| `header.forked_from` | Optional |

**Save:** Write `header` and `role` fields. The template is now structurally minimal-valid (other primitives are empty arrays).

## Step 2 — Credential imports (the imports list)

**Goal:** Identify the credentials this role must hold for its commands to be authorized.

**Why this comes before exported credentials:** What you import constrains what you can DO. Imported credentials determine the universe of commands available.

**For each imported credential, capture:**

| Field | Notes |
|---|---|
| `id` | Local identifier (used by commands' auth_preconditions) |
| `expected_schema_said` | SAID of the schema; lookup in known templates or note as TBD |
| `expected_issuer_role` | Optional narrowing constraint |
| `expected_attribute_constraints` | Optional type hints |
| `lifecycle_acceptance` | Which lifecycle states make it usable (default `["active"]`) |
| `narrative` | SME tooltip explanation |

**Imports describe types, not instances.** Even if the role has NO active credential of a given type at the moment the micro-app is instantiated, declare the type here. Locksmith determines runtime holdings by observing the wallet's TEL state. The `narrative` field is the conventional place to note "no active instance at start; obtained via [workflow_id]."

**When the SAID isn't yet known:** Note it explicitly. The Ecosystem Viewer will surface dangling imports as candidates for alignment.

**Anti-patterns:**

- ❌ Inventing schema SAIDs — they must be content-addressed
- ❌ Conflating "credentials this role *imports*" with "credentials this role *exports*" — different lists

## Step 3 — Credential exports (the exports list)

**Goal:** Define the credentials this role produces — their envelope, schema, lifecycle, rules, value flow.

> **Design decisions first.** Before authoring the schema, settle the design
> decisions for this credential (targeted/untargeted, public/private `u`, disclosure
> mode, edges, registry, versioning, governance) using the **`acdc-design`** skill.
> This step then serializes those decisions into the envelope below.

**The most substantial step.** Each exported credential has six layers (per spec §6.3).

For each exported credential, walk:

1. **Envelope contract** — who holds it, who verifies it, what it chains from
2. **Schema** — author a JSON-Schema file in `schemas/` and capture its SAID
3. **Lifecycle** — states, initial state, transitions (with `tel_primitive` mapping each transition to issue/update/revoke)
4. **Ricardian rules** — forward-reference rule ids; will be authored in Step 9
5. **Value flow** — references to other credentials implied by this one

**Edge operators:**

| Operator | Meaning |
|---|---|
| `authorizes` | Holder of parent becomes issuer of this credential |
| `references` | Informational pointer; no authority transfer |
| `authorizes-via-delegate` | Issuer is a KEL-delegated AID of parent's holder |

**Lifecycle transitions ground out in TEL primitives:**

- `issue` — TEL issuance event (state becomes active or whatever the initial-active state is)
- `update` — TEL update event (intermediate state change, e.g., active → suspended)
- `revoke` — TEL revocation event

The state machine layered on top can have any names; transitions map each to one of these three TEL primitives.

**Schema authoring side-step:** When you reach the schema for a credential, write a separate JSON-Schema file at `schemas/{credential_id}.json`.

**The file MUST be a full ACDC *envelope* schema — not just the attribute fields.** A credential is issued as `{v, d, i, ri, s, a:{…}}` and KERI validates the schema against that **whole** object, so a schema that lists `license_number`, `effective_date`, … at the top level is **not** a valid ACDC schema: issuance fails with `ConfigurationError: '<field>' is a required property`. The SME describes the *attributes*; the schema file wraps them in the envelope. Canonical shape:

```json
{
  "$id": "",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Carrier License",
  "type": "object",
  "properties": {
    "v": {"type": "string"},
    "d": {"type": "string"},
    "u": {"type": "string"},
    "i": {"type": "string"},
    "ri": {"type": "string"},
    "s": {"type": "string"},
    "a": {
      "oneOf": [
        {"type": "string"},
        {
          "$id": "",
          "type": "object",
          "properties": {
            "d":  {"type": "string"},
            "i":  {"type": "string"},
            "dt": {"type": "string", "format": "date-time"},
            "license_number": {"type": "string"}
            /* …the SME's attribute fields go here… */
          },
          "additionalProperties": false,
          "required": ["d", "i", "dt", "license_number"]
        }
      ]
    }
  },
  "additionalProperties": false,
  "required": ["v", "d", "i", "ri", "s", "a"]
}
```

`u` (top-level UUID) is **optional** and controls the public/private variant: omit it
for a public attestation; include a high-entropy value for a private (blindable)
credential. See the `acdc-design` skill (`shape-and-disclosure.md`). `u` is not added
to `required`.

The SME's attributes live in the **second `a.oneOf` branch**, alongside the mandatory `d`/`i`/`dt`. (`e` and `r` sections follow the same `oneOf` pattern when the credential has edges or Ricardian rules.)

Stamp the SAIDs with `python scripts/saidify_acdc_schema.py schemas/{credential_id}.json` — it sets the **envelope** `$id` (the canonical *schema SAID*, used in the template's `schema_said` and in the issued credential's `s` field) **and** the inner `a.oneOf[1].$id` (the *attributes SAID*). Reference the envelope `schema_said` and `schema_path` in the template's `credentials.exports[]` and in any `emissions[].exchange.schema_said_referenced`. Confirm the result issues: a quick `IpexGrantIssuer` round-trip (or the loader's e2e) is the only thing that proves a schema is issuance-valid — `micro_app_saidify.py --verify` only checks the *template* SAID and treats `schema_said` as opaque.

## Step 4 — Commands

**Goal:** Define the actions this role takes. Each command becomes a button in Locksmith.

**For each command:**

1. **Route** — exn route following naming conventions (see `naming-conventions.md`). Must not start with `/ipex/`.
2. **Counterparty role** — who receives this command, if any
3. **Payload schema** — JSON-Schema for the actor's input (Locksmith renders as a form)
4. **Authorization (KERI-native)** — every externally-invocable command declares `authz`: `open` (any authenticated AID), `aid`/`allowlist` (specific AID(s)), or `credential` (`schema_said` [+ optional `issuer`]). Never express authorization as a CEL predicate — that is a defect (see the BE-KERI-NATIVE doc). `auth_preconditions` are for *non-authz* validation only (payload completeness, state guards).
5. **Preconditions** — state (forward-ref rules), temporal (forward-ref rules)
6. **Emissions** — what fires on success: exchange (IPEX or exn out), lifecycle_advance (advance a credential's state), aggregate_event (append to a local aggregate)

**Anti-patterns:**

- ❌ Using `/ipex/*` for app-defined commands — reserved for protocol
- ❌ Expressing authorization as a CEL predicate in `auth_preconditions` — use the `authz` field instead

### The just-issued credential's SAID

A `payload_mapping` sees `{command, state}` — and **neither can name the credential this
command is issuing**. Its SAID does not exist until the issuance runs. Use the binding
the authoring spec pins for exactly this (§6.4):

```json
"payload_mapping": "{ \"version_said\": credential.said, \"product_id\": command.product_id }"
```

- `credential.said` is available only **at or after** the `kind: credential` exchange
  emission that issues the export, in the same `emissions[]` list. Put the issuing
  exchange first.
- It is the **only** thing you need this binding for. Every attribute value is already in
  `command.*`, because your command supplied them — the SAID is the one value issuance
  *creates* rather than *consumes*.
- Do **not** confuse it with `event.credential` (Step 6, reactions): that is the
  **inbound** credential that triggered a reaction. Bare `credential` is **outbound**.

### Mapping coverage — the check that will reject your template

Every `event.<field>` any fold handler reads must be supplied by some emission's
`payload_mapping`. This is mechanically checked; a template that violates it will not
compile:

```bash
cd ~/code/concierge-api && PYTHONPATH=src ~/code/keripy/.venv/bin/python -m concierge_api_local.cli.microapp \
  check --template <abs path to micro-app-template.json>
```

Run it before you commit. It needs no vault and no keri stack.

## Step 5 — Aggregates

**Goal:** Define the local state this role tracks.

Aggregates are typically TEL-backed (when tracking credential lifecycle) or KEL-anchored local logs. For each:

1. **Inception event type** — the event that mints the aggregate's identifier
2. **State schema** — JSON-Schema for the folded state
3. **Initial state** — starting value
4. **Invariants** — forward-ref validation rules
5. **Log scope** — `private` | `witnessed` | `shared`

**Fold-op gotcha (applies to projection folds too, Step 8):** every fold-op field is a **CEL expression string** — including `increment`'s `by`, which must be written `"by": "1"` / `"by": "-1"`, never a bare JSON number. The meta-schema rejects numeric `by` with an opaque "not valid under any of the given schemas" error on the whole handler.

### `instance_key` is a routing selector, not an identifier

It must name a field **every source event supplies** (routing precedes the handler). If
one emission of one event type in this aggregate's `fold` map omits that field, that event
is not mis-folded, it is **un-appendable**: it never lands at all, silently.

```json
"boundary": { "instance_key": "event.product_id", "inception_event_type": "workspace_created" }
```

Then **every** emission targeting **every** event type in this aggregate's fold must
include `product_id` in its `payload_mapping`. A constant (`"'license_registry'"`) always
routes and is always safe.

This is the corpus's most-repeated blocker class — one anchor template shipped with 13
un-appendable emissions and passed every other gate. A fold *test vector cannot catch it*,
because the vector supplies its own event payload; only the static check can.

## Step 6 — Reactions

**Goal:** Define what this role does when it observes external events.

For each reaction:

1. **Trigger** — credential_received (with imported_credential_id + optional ipex_verb), exn_received (with route), lifecycle_event (with credential and state), or scheduled (with cadence)
2. **Authorization (KERI-native)** — every externally-invocable reaction declares `authz`: `open` (any authenticated AID), `aid`/`allowlist` (specific AID(s)), or `credential` (`schema_said` [+ optional `issuer`]). Never express authorization as a CEL predicate — that is a defect (see the BE-KERI-NATIVE doc). `auth_preconditions` are for *non-authz* validation only (payload completeness, state guards).
3. **Emissions** — same shape as command emissions
4. **Failure policy** — `log_and_continue` | `log_and_spurn` | `abort`; optional timeout_seconds

**The subscriber pattern:** Reactions observe events; they don't push to others. The decentralized property.

## Step 7 — Workflows

**Goal:** Name the multi-step external interactions from this role's perspective.

Each workflow is a sequence of self-actions and counterparty-awaits. From this role's POV only — the counterparty's half lives in their own micro-app.

For each:

1. **Counterparty role**
2. **Trigger** — manual (with initiator_role), scheduled, lifecycle_event, exn_received, credential_received
3. **Steps** — ordered list. Each step has: `actor` (self or counterparty), `command_id` or `reaction_id` (for self steps), `expected_inbound` (for counterparty steps), `branches` (rule-conditioned next_step pointers), `next_steps` (unconditional), `time_bound` (duration + on_expiry).

The exchange palette across steps:

- IPEX credential exchange — kind: credential, verb: one of six (apply/offer/agree/grant/admit/spurn)
- exn message — kind: message, pattern: command|query|notification, route
- Internal step — exchange: null

## Step 8 — Projections

**Goal:** Define what this role looks at.

Projections fold events into views. Locksmith renders them.

For each:

1. **Source events** — names of event types to fold
2. **Output schema** — JSON-Schema for the resulting state
3. **Fold** — CEL handler map (op list or raw reducer) over `{ row, event }` (or `{ state, event }` for `object`-shape projections) producing the row/state
4. **Access** — row_filter_rule_ref, lens_rule_ref
5. **Display** — view_type (table | list | cards | kanban | timeline | summary), columns, default_sort, empty_state

### `primary_key` has the identical rule

It must name a field **every source event supplies** (routing precedes the handler). Check
every entry in `source_events`, not just the obvious one — a projection sourcing four event
types needs the key in all four emissions, or those rows are never created.

## Step 9 — Rules

**Goal:** Author every rule forward-referenced in Steps 3–8.

**Resolve every forward reference.** Walking the template after Step 9, no rule_ref should point to an undefined id.

For each rule, choose its `type`:

| Type | Body or Expression? | Notes |
|---|---|---|
| `legal_prose` | `body` (markdown) | Ricardian contractual prose |
| `behavioral_expectation` | `body` (markdown) | Prose-only obligation |
| `business_policy` | both `body` and `expression` allowed | Hybrid prose + formal |
| `predicate` | `expression` + `language` + `purpose` | Executable boolean |
| `computational` | `expression` + `language` + `result_attribute` | Derived value |
| `validation` | `expression` + `language` | Constraint check |
| `binding_link` | `links[]` | Connects prose to executable |

See `rule-types-reference.md` for detailed guidance per type.

## Step 10 — Conventions, hints, lineage (metadata.json)

**Goal:** Produce the optional sibling `metadata.json` with non-canonical viewer color.

1. **Convention compliance audit** — for each category (credential_naming, role_naming, workflow_naming, etc.), record whether the template complies with conventions or where it deviates with rationale
2. **Ecosystem affinity** — kebab-case tags suggesting which emergent ecosystems this template belongs to
3. **Semantic lineage** — optional refines/improves/inspired_by/competes_with/obsoletes relations to other templates
4. **Author intent notes** — free text the viewer can surface
5. **Compatibility hints** — compatible_with and incompatible_with lists

**Save:** Write `metadata.json` alongside `micro-app-template.json`. Set `for_micro_app_said` to the template's SAID (computed in the saidify step below).

## Adversarial review (informal)

Walk the adversarial checklist (see `adversarial-prompts.md`). Document concerns in `metadata.author_intent_notes` or as out-of-band notes.

## Vectors

**Goal:** Every aggregate (Step 5) and projection (Step 8) you added ships `test_vectors[]` that a
runtime can *execute*. Author them after Step 9 — an `expect_rejected_by` names a rule id, so the rules
have to exist first — and before saidify.

### The floor (this is required, not recommended)

A new aggregate or projection MUST ship vectors such that:

1. **every event type in its `fold` map appears** in some vector's `events[]` or `append`; and
2. **every `invariants[]` entry is named by some vector's `expect_rejected_by`** — a vector that drives
   the guard to actually fire.

An invariant that is merely *evaluated* during an append that succeeds is **not** pinned. Only a
rejection pins it, and the vector must name the *specific* rule id: rejection by a different invariant
is a failure, not a pass.

Landed units are held instead by a ratchet against `docs/micro-apps/coverage-baseline.json`. A unit the
baseline **lists** fails if *either* its coverage ratio drops *or* its uncovered count
(`handlers - exercised`, `invariants - pinned`) grows — both rules, either one tripping, because a ratio
cannot see growth at a zero numerator (`0/7 -> 0/8` compares equal). A unit **absent** from the baseline
is new work and is held to the floor above, 100% on both metrics. See spec §6.5.

### The two shapes

**A vector nests its fields under `payload`, but a fold expression reads them unnested as
`event.<field>`** — `_flatten_event` spreads `payload` up to the top level. Two consequences: write
`event.jurisdiction`, never `event.payload.jurisdiction`; and a payload field must not collide with an
**envelope** field, because the envelope wins. `type`, `said`, `seq`, `source_aid` and `datetime` are
envelope names (cheat-sheet §2) — a payload named `said` is silently overwritten by the envelope's,
which is `""` when the event doesn't carry one. That is why the corpus writes `license_said`,
`application_said`, `index_said` and never a bare `said`.

**Fold vector** — `{ name, events[], expected }`. `expected` is the *entire* folded state after the
events, compared for exact equality. For a `collection`-shape projection, wrap it as `{"rows": [...]}`.

```json
{
  "name": "receiving a license adds it to active_licenses",
  "events": [
    { "type": "license_received",
      "payload": { "license_said": "EAbc...", "jurisdiction": "CA", "effective": "2026-08-01" } }
  ],
  "expected": {
    "active_licenses": [
      { "license_said": "EAbc...", "jurisdiction": "CA", "effective": "2026-08-01" }
    ],
    "expired_licenses": []
  }
}
```

**Invariant vector** — `{ name, events[], append, expect_rejected_by | expect_accepted }`. `events[]`
folds the *prior* state; `append` is the one proposed event that the invariants are then evaluated
against. Presence of `append` is what makes it an invariant vector.

```json
{
  "name": "a second active license in the same jurisdiction is rejected",
  "events": [
    { "type": "license_received",
      "payload": { "license_said": "EAbc...", "jurisdiction": "CA", "effective": "2026-08-01" } }
  ],
  "append": {
    "type": "license_received",
    "payload": { "license_said": "EDef...", "jurisdiction": "CA", "effective": "2026-09-01" }
  },
  "expect_rejected_by": "no_duplicate_active_license"
}
```

Shape rules the runner enforces:

- `append` and `expected` on the same vector is an error — the two shapes are mutually exclusive.
- Only `expect_rejected_by` and `expect_accepted` are recognized; any other `expect_*` key is rejected
  as a likely typo rather than silently defaulting to "expect accepted".
- A vector with no `expect_*` key at all means *expect accepted*.
- A fold vector whose `events[]` match **no** handler in the unit's `fold` map is an error, not a pass —
  it would otherwise pass vacuously against `initial_state`. Usually a misspelled event `type`.

### Run them

```bash
cd ~/code/concierge-api && PYTHONPATH=src ~/code/keripy/.venv/bin/python -m concierge_api_local.cli.microapp \
  vectors --template <abs path to micro-app-template.json> \
  --baseline <abs path to docs/micro-apps/coverage-baseline.json>
```

Must exit 0. The gate **executes** the vectors; writing one is not the same as running it.

### Two warnings

**A vector cannot catch a routing defect.** It supplies its own event payloads, so it passes while the
real emission omits the routing field. That is why `boundary.instance_key` / `primary_key` are checked
statically by `micro-app check`, and why writing a vector is not a substitute for running it.

**Write the rejection vector, not just the happy path.** The corpus went four bundles with *zero*
`expect_rejected_by` vectors, and two confirmed blockers hid in exactly that gap.

And know what a green run does **not** prove: handler coverage measures *reach*, not *strength* — a
vector whose `expected` asserts little still marks its handlers covered — and pinning an invariant proves
the guard *can* fire, not that it fires on every path that should trip it.

## Save and saidify

1. Run `scripts/micro_app_validate.py --input <path>` — must pass.
2. Run `scripts/micro_app_saidify.py --input <path> --in-place` — stamps the `d` field.
3. Re-run validate to confirm SAID is now correct.
4. Update `metadata.json` `for_micro_app_said` to the new SAID.
5. Commit the entire directory.
