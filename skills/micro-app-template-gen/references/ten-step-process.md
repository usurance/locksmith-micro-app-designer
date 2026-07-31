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

## Step 1.5 — The KERI-shape pass

**Goal:** convert the requirement's verbs into KERI primitives *before* any mechanics are chosen.

**Why here:** Step 2 asks "what credentials must this role hold" and Step 3 asks "what credentials
does this role produce" — both **presuppose the set**. Nothing before them asks whether a given
requirement is describing a credential, a lifecycle, an edge, or an identity at all. Three templates
in this corpus, authored at different times through these ten steps, converged on the same class of
mistake for that reason: a requirement's sentence became a boolean, a status column, or a domain
event, when ACDC and KERI already gave the fact unforgeably.

**Walk `references/keri-shape-pass.md`.** Five questions, each with an observable tell:

| | Question | The tell, in one line |
|---|---|---|
| Q1 | **Which tier** — nothing, anchor, or ACDC? | nobody outside checks it → **workbench**; someone must verify **later** that it happened → **anchor** (`ixn` seal; `log_scope: witnessed`); someone must **act on its current standing** → **ACDC** |
| Q1 | Is this a credential? | an authority verb; *immutable once …*; *superseded, never deleted*; a row carrying both a decision and a status |
| Q1b | Targeted or untargeted? | conferring something on a **named party** → a targeted **credential** (and only a Targeted far node can bear an `I2I` edge); publishing an **observation** → an untargeted **attestation**, `NI2I` only |
| Q2 | Is this a lifecycle? | a `status` field set by a **fold literal**; a `*_superseded`/`*_revoked` event type; two emissions from one trigger writing one projection |
| Q3 | Is this an ordering fact? | a **boolean** named `*_before_*`, `already_*`, `pre_*`; or derived `size(state.x) > 0` |
| Q4 | Is this discrimination against an array element? | a membership test (`exists`, `contains`, `in`) over an **array attribute**, gating admissibility |
| Q5 | Is this identity? | a hand-keyed, console-supplied, parsed, or concatenated value used as a key — cross-reference authoring spec §5.7's six identifier kinds and **name the kind** |

It is **diagnostic, not prescriptive.** The reference's counter-test lists what legitimately stays a
template mechanic (local workspace state, derived projections, pure gates, observed counterparty
facts), and its truth-maker rule marks where structural impossibility stops: *you may refuse to
construct only what you are the truth-maker for.*

**Save:** the five answers, one line each, into `metadata.json` — `convention_compliance` (an open
string→string map) or `author_intent_notes`. The lifecycle spelling in particular must be recorded,
because a corpus can otherwise end up spelling supersession three ways, as this one does.

**This step is re-entered.** See §The back-edge in the reference, and the note at Step 4.

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
>
> **And check the set itself.** Step 1.5 decides *whether* a fact is a credential; `acdc-design`
> decides *what the credential looks like*. If you arrived here without running the shape pass, the
> exports list is whatever the requirement's nouns happened to be. Run it. Reach **`keri:acdc`** for
> edge operators, `validate_edge` semantics, and TEL registry patterns — this is where the
> existence-vs-value distinction and the lifecycle spelling get settled.

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

The state machine layered on top can have any names; transitions map each to one of these three TEL
primitives. A TEL's `ts` **MUST be a string from a finite set of state values** (ACDC, `upd` field
constraints), which is exactly what your `states` list is — `issued`/`revoked` are the spec's *common*
CESR encodings, not the whole permitted set.

### One spelling per concept — decide it here, record it in `metadata.json`

**A credential's own lifecycle has two legitimate spellings and one wrong one.** Choose, and write the
choice down; otherwise a corpus ends up with all three, as this one has:

| Spelling | Use when | Corpus |
|---|---|---|
| **TEL state** (`issued → superseded`, `tel_primitive: update`) | the issuer's act changes the thing's standing | `rating_attestation` ✅ |
| **A `supersedes` edge** (self-referential, `operator: references` / NI2I) | the *lineage link* itself must be verifiable, not just the standing | `product_definition_version` ✅ |
| **A domain event** (`rate_program_superseded`) | **never, for a credential's own lifecycle** | rate program ❌ |

Only the third produced a blocking finding — because a domain event needs a second emission and a TEL
does not, so two emissions from one command context competed for one projection's routing key and the
supersession stamped `status: 'superseded'` over the row it had just sealed. Record it as e.g.
`"lifecycle_spelling": "TEL state — supersession is an update on the credential's own registry; no
domain event."` See `references/keri-shape-pass.md` Q2.

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

**The envelope carries the SAID of the credential this emission issues. You do not name it,
and you cannot rename it.**

An emission cannot name the credential its command is issuing — that SAID does not exist
until the issuance runs. So it is not a payload property at all: the runtime stamps it on
the event envelope as `credential_said`, and your fold handler reads it directly:

```json
"fold": { "version_registered": [
  { "op": "set", "target": "said", "value": "event.credential_said" }
] }
```

- Do **not** declare `credential_said` (or any other envelope name) as a property of your
  event's `payload_schema`. It is reserved — the fold engine stamps the envelope *over* the
  payload, so a payload property with that name is silently discarded.
- The value is meaningful only when the emission list contains a `kind: credential` exchange
  emission at or before this one. Put the issuing exchange first.
- Every *attribute* value is already in `command.*`, because your command supplied them. The
  SAID is the one value issuance *creates* rather than *consumes* — which is exactly why it
  lives on the envelope and not in your contract.
- Inbound is the same shape: a reaction triggered by `credential_received` reads the
  triggering credential's SAID as `event.credential_said`, its issuer as
  `event.credential_issuer`, and its resolved edges as `event.credential_edges.<name>`.

### Your event's property names ARE the binding

There is no mapping slot. An `aggregate_event` emission is `{kind, aggregate_id, event_type}`
and nothing else — the meta-schema *rejects* any other key. **Every property you declare in
that event type's `payload_schema` (Step 5) binds to the same-named field of the trigger
context.** With no slot there is nowhere to rename, which is the point.

The three trigger surfaces — which one applies depends on what fires the emission:

| Trigger | A declared property `foo` binds to |
|---|---|
| Command | `command.foo` — a field of the command's `payload_schema` |
| Reaction on an inbound exn | `event.foo` — a field of the inbound note's payload |
| Reaction on `credential_received` | `event.credential.attributes.foo` — an ACDC attribute |

A `required` property with no same-named field on its trigger is an `unsupplied_property`
error. The fix is to make the names agree — rename the *command* field where the event's
name is the better one — not to reach for a transform, because there isn't one.

**There are exactly three legal moves, and the third is the one authors miss.**

1. **Make the names agree** — the default, above.
2. **Declare a mint** (`from`, below) — only for the mint/carry split of a stable business key.
3. **Go back to Step 1.5, then Step 3** — the credential is the wrong shape or the wrong granularity.

Move 3 is the resolution whenever the value is **derived from state** rather than named anywhere. Moves
1 and 2 cannot reach a `state.*` derivation by construction: there is no name to agree with, and `from`
names envelope slots only. An author who does not know move 3 exists has no legal option left and
invents a payload field — which is, mechanically, how this corpus's two derived booleans were authored
(`in_mandate` from `state.mandate_states.exists(…)`, `governance_sealed_before_freeze` from
`size(state.sealed_governance) > 0`). Both were **modelling errors that a correct object graph makes
unconstructable**: the ordering fact is an edge, the authorization fact is a credential the inbound
artifact must chain to. The missing-value error was not a hole in the model — it was a detector.

See `references/keri-shape-pass.md` §The back-edge, Q3 and Q4.

**The eight reserved envelope names.** The fold engine stamps these over the payload, so a
`payload_schema` MUST NOT declare any of them:

`type`, `said`, `seq`, `source_aid`, `datetime`, `credential_said`, `credential_issuer`,
`credential_edges`

A fold handler reads them directly and they need no producer: `event.datetime` rather than a
`granted_at` property, `event.credential_said` rather than a copied `license_said`.

#### The declared mint

One exception lets a *differently*-named property pull its value from one of the eight
instead of from the trigger: `"from": "<envelope slot>"` on that property, in its event
type's `payload_schema` — the same closed eight-name enum above and nothing else. No CEL
expressions, no renames. The property name **is** the domain name (`application_id`, never
`credential_said`); `from` only says which envelope slot mints it. The declaration sits on
the event **type**, once — every producer of that event type mints the same property the
same way (owner ruling 2026-07-28, register finding 37; authoring spec §6.5).

**Reach for it in exactly one situation:** a stable business key (identifier kind 3) whose
value is *born* as a credential SAID at one event type, and from then on is carried by
ordinary command fields at every other event type that needs it — the mint/carry split
behind a collection projection's `primary_key`.

Worked pair from the corpus: `application_received` declares
`"application_id": { "type": "string", "from": "credential_said" }` — the mint, the moment
the credential this event's own emission just admitted becomes the application's domain
identity. `license_granted`, a later event feeding the same projection, carries
`application_id` conform-by-name from `command.application_id` instead — the carry.
`micro-app check` verifies both sides route into one projection.

**Do NOT reach for it when:**

- The value is reachable conform-by-name from the trigger — that's the default, and it
  needs no declaration at all.
- It's a timestamp. A fold reads `event.datetime` directly; nothing mints it into a payload
  property.
- It's provenance a fold can already read off the envelope. `event.credential_said`,
  `event.credential_issuer`, `event.credential_edges.<name>` are available to any handler
  without a producer; `from` exists only to carry one of those values INTO a
  differently-named domain property that outlives the event that minted it, not to
  duplicate what a handler can already reach directly.

**Two things that used to be mapping tricks, and where they go now:**

- **A discriminator literal** — one producer writing `kind: 'compliance'` so a shared event
  type can be told apart — becomes **two named event types**, with the literal moved into
  each type's fold handler. See Step 5.
- **A rename at a wire boundary** — your local vocabulary differs from the counterparty's —
  moves to the **fold**, which is legal and visible: declare the property under the wire's
  name and have the handler write your local name from it. Renaming at the emission is not
  legal, because there is no emission-side expression to do it in.

### Fold coverage — the check that will reject your template

Every `event.<field>` any fold handler reads must be a `required` property of that event
type's declared `payload_schema`, or one of the eight envelope names. This is mechanically
checked; a template that violates it will not compile:

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
4. **Events** — the declared contract for each event type this log carries (below)
5. **Invariants** — forward-ref validation rules
6. **Log scope** — `private` | `witnessed` | `shared`

### Declare your events BEFORE the fold and before the emissions

The event is the durable log record. Roughly two independent consumers read each one — an aggregate
fold *and* one or two projections — so its shape is a shared contract, not a private input. Declare it
once, on the aggregate, keyed by event type (authoring spec §6.5):

```json
"events": {
  "license_received": {
    "description": "A license credential was granted to us and admitted.",
    "payload_schema": {
      "type": "object",
      "properties": {
        "license_said": { "type": "string" },
        "jurisdiction": { "type": "string" },
        "effective":    { "type": "string", "format": "date" }
      },
      "required": ["license_said", "jurisdiction", "effective"],
      "additionalProperties": false
    }
  }
}
```

**Author the contract first, then the mappings that satisfy it.** The old order — write the mappings
and let the contract be whatever they happened to produce — is why the event shape used to be
declared once per producer with nothing requiring the producers to agree, and why fields went quietly
missing: nobody proofreads a restatement.

Four rules the meta-schema enforces, so getting them wrong fails `micro_app_validate.py`:

- **`additionalProperties: false` is required.** A contract that isn't closed isn't a contract.
- **Never declare `type`, `said`, `seq`, `source_aid` or `datetime`** as payload properties. They come
  from the event envelope, and the fold engine stamps them *over* the payload — so a payload property
  with one of those names is silently discarded at fold time. Name yours `license_said`,
  `attestation_said`, `version_said`, as the corpus does. A handler reading `event.said` gets the
  envelope's value and needs no producer.
- **Mark a property `required`** if any fold handler reads it, or if it is named by this aggregate's
  `boundary.instance_key` or a projection's `primary_key` (routing precedes the handler). Leave
  genuinely optional fields un-`required` — that is what they are for, instead of an `''` sentinel.
- **A shared event-type name creates no contract.** If a counterparty's template uses the same event
  type name, that is a coincidence: the regulator's `license_granted` carries nine properties and the
  carrier's carries four, and both are correct. Events never cross a template boundary; exchanges do.
  Cross-role shape agreement belongs on the wire, never on an event name.

**`events` is REQUIRED.** It is the only description of an event's contract — there is no mapping
left to infer one from — so an aggregate without it does not validate.

**Fold-op gotcha (applies to projection folds too, Step 8):** every fold-op field is a **CEL expression string** — including `increment`'s `by`, which must be written `"by": "1"` / `"by": "-1"`, never a bare JSON number. The meta-schema rejects numeric `by` with an opaque "not valid under any of the given schemas" error on the whole handler.

### `instance_key` is a routing selector, not an identifier

It must name a field **every source event supplies** (routing precedes the handler). If
one emission of one event type in this aggregate's `fold` map omits that field, that event
is not mis-folded, it is **un-appendable**: it never lands at all, silently.

```json
"boundary": { "instance_key": "event.product_id", "inception_event_type": "workspace_created" }
```

Then **every** event type in this aggregate's fold must declare `product_id` as a
`required` property. A constant (`"'license_registry'"`) always routes and is always safe.

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

**A reaction observes a counterparty's fact, so the truth-maker rule applies here** — reach
**`keri:acdc`** for what a fold may and may not assume about an inbound credential, and **`keri:spec`**
where KEL anchoring or ordering is being relied on. You may refuse to construct only what you are the
truth-maker for: an artifact *you* author can be made structurally impossible, but an artifact you
merely *witness* must be recorded and then **evaluated as-of at read time, never frozen at ingest**.
A derived judgment written once on upsert and never recomputed is a bug — and if nothing reads it, it
is decoration. See `references/keri-shape-pass.md` §The truth-maker rule.

## Step 7 — Workflows

**Goal:** Name the multi-step external interactions from this role's perspective.

Each workflow is a sequence of self-actions and counterparty-awaits. From this role's POV only — the counterparty's half lives in their own micro-app.

For each:

1. **Counterparty role**
2. **Trigger** — manual (with initiator_role), scheduled, lifecycle_event, exn_received, credential_received
3. **Steps** — ordered list. Each step has: `actor` (self or counterparty), `command_id` or `reaction_id` (for self steps), `expected_inbound` (for counterparty steps), `branches` (rule-conditioned next_step pointers), `next_steps` (unconditional), `time_bound` (duration + on_expiry).

The exchange palette across steps:

- IPEX credential exchange — kind: credential, verb: one of six (apply/offer/agree/grant/admit/spurn).
  **Three of the six are initiating** — `apply` (disclosee-driven), `offer` and `grant`
  (discloser-driven) — and `spurn` rejects at **any** stage, so every awaiting step needs a refusal
  path (adversarial check 5). `grant → admit` is a legal two-message exchange; the full
  `apply → offer → agree → grant → admit` is the negotiated path. Note also that **IPEX carries an
  already-issued ACDC** — issuance is the anchor in the issuer's KEL/TEL and happens before the first
  message — so an exchange step is transmission, never the act of issuing
- exn message — kind: message, pattern: command|query|notification, route
- Internal step — exchange: null

## Step 8 — Projections

**Goal:** Define what this role looks at.

Projections fold events into views. Locksmith renders them.

**Before you author the columns, run two shape checks on the row** (`references/keri-shape-pass.md`
Q1 and Q2):

- **A row carrying both a decision and a status is a credential wearing a table.** Decision fields —
  `decided_by`, `decided_at`, `rationale`, `*_reference`, `approval*` — beside a `status` column mean
  the thing this row describes is an issued artifact, and the row should be a projection *of* that
  credential's TEL rather than the place its standing is decided.
- **A `status` a fold handler sets from a literal is a lifecycle spelled as a column.** `{"op":
  "set", "target": "status", "value": "'superseded'"}` makes the status a function of *which event
  arrived*. If the underlying thing is a credential, its standing is its TEL state and "current" is a
  **dated query** over effective dates and the read date — derived, never stamped. A projection that
  answers "which one is live" while holding neither the approval nor the effective date is making a
  claim it cannot support.

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
events, compared for exact equality.

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

**Fold vector, `collection`-shape projection** — same shape, but `expected` is wrapped as
`{"rows": …}` and **`rows` is an object keyed by `primary_key`, not a list**. The engine's fold returns
`dict[key, row]` for a collection, so a list never compares equal and you get a diff that is hard to
read. Note that `primary_key` is a bare field name (`"license_said"`), not a CEL expression.

```json
{
  "name": "each granted license becomes one row, keyed by license_said",
  "events": [
    { "type": "license_granted",
      "payload": { "license_said": "ELic1...", "jurisdiction": "US-CA", "granted_at": "2026-08-10T00:00:00Z" } },
    { "type": "license_granted",
      "payload": { "license_said": "ELic2...", "jurisdiction": "US-UT", "granted_at": "2026-08-11T00:00:00Z" } }
  ],
  "expected": {
    "rows": {
      "ELic1...": { "license_said": "ELic1...", "jurisdiction": "US-CA", "granted_at": "2026-08-10T00:00:00Z" },
      "ELic2...": { "license_said": "ELic2...", "jurisdiction": "US-UT", "granted_at": "2026-08-11T00:00:00Z" }
    }
  }
}
```

A `delete` op removes that key outright, so the vector covering it lists the remaining keys only — and
you need one, because the floor counts `license_revoked` as its own handler.

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
