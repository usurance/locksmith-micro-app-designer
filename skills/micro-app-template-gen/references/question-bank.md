# Question Bank

Per-step questions to ask an SME. Pick the primary question first; ask follow-ups only when the primary answer leaves ambiguity. One question at a time. Plain language — push back on KERI jargon in user-facing answers.

## Step 0 — Identify the role

**Primary:**
- *"Which role does this micro-app embody?"* — get id, display name, description

**Follow-ups:**
- *"Is this an individual, an organization, a system, a device, an autonomous agent, or a government?"* — get `kind`
- *"Does this role typically operate its own witnesses? Watch others' KELs? Need an always-on mailbox to receive offline messages? Run credential registries?"* — get `keri_infrastructure` flags. Suggest defaults by kind; let the SME override.

## Step 1 — Name the use case

**Primary:**
- *"From this role's perspective, what's the outcome they want? State it as a past-tense fact in business language."*

**Follow-ups:**
- *"If two outcomes feel central, can you state each separately? They might be two micro-apps."*
- *"Does this template descend from another? If so, what's the parent's SAID and version, and what did you change?"*

## Step 1.5 — The KERI-shape pass

Ask these **before** Step 2's "what credentials," because Step 2 and Step 3 presuppose the set. Full
guidance and the counter-test: `references/keri-shape-pass.md`.

**Primary:**
- *"Walk me through the requirement one statement at a time. For each one: does this need to be
  provable later, to someone who wasn't there?"* — if no, it stays a template mechanic and the rest of
  these questions do not apply to it.

**Follow-ups per statement that does:**
- *"Who issues this, and is its existence the fact?"* — Q1, a credential. Listen for *issued, granted,
  approved, filed, certified, attested*; *immutable once …*; *superseded, never deleted*; *corrected
  forward*; *identified by a number that outlives us*; *who decided, when, on what basis*.
- *"Does this thing's standing change over time, and who changes it?"* — Q2, a lifecycle. Then: *"TEL
  state or a `supersedes` edge? Which does the rest of the corpus use?"* Record the answer.
- *"Does this say one thing must happen before another?"* — Q3, an edge. *"Which artifact commits to
  which?"*
- *"Only certain parties or scopes may do this — where does that list live?"* — Q4. If the answer is a
  list inside one credential, the chain cannot discriminate: *"could each scope be its own credential?"*
- *"For each identifier here: who mints this value, and who controls its lifecycle?"* — Q5. A
  hand-keyed, console-supplied, parsed, or concatenated value is provenance, not a key. Name the kind
  from authoring spec §5.7.
- *"Is this a fact you author, or one you observe someone else doing?"* — the truth-maker rule. Observed
  facts are recorded and evaluated as-of; you never refuse to record them.
- *"Who or what reads this, and when?"* — ask it of every derived value. No consumer means no field.

## Step 2 — Credential imports (the imports list)

**Primary:**
- *"What credentials must this role hold to take its actions?"*

**Follow-ups per imported credential:**
- *"What's this credential type called?"*
- *"What's the SAID of the schema?"* — if not known, note as TBD and continue
- *"Who issues it? (which role)"*
- *"Which lifecycle states make it usable? (default: active)"*
- *"Does the role start without an active instance of this credential type? If so, we still declare it here — the imports list captures types, not current holdings. Note the 'starts empty' status in the `narrative` field."*

## Step 3 — Credential exports (the exports list)

**Primary:**
- *"What credentials does this role produce?"*

**Follow-ups per exported credential:**
- *"What's the credential called and what does it convey?"*
- *"Who holds it? Who can verify it?"*
- *"Does it chain from another credential — like 'I can only issue this if I hold a parent credential'? If so, which?"*
  - *"Is the chain authorizing (holder becomes issuer), referencing (informational only), or via delegated AID?"*
- *"How sensitive is its data? Full disclosure, selective (per-field), or aggregate?"*
- *"What states does this credential go through?"* — list them
- *"For each state, how is it reached? Through which workflow? Mapping to KERI: is the transition an `issue` (initial creation), an `update` (mid-life change), or a `revoke` (terminal)?"*

## Step 4 — Commands

**Primary:**
- *"What actions does this role take?"*

**Follow-ups per command:**
- *"In imperative voice, what's this command called?"*
- *"What does the actor supply? (the payload)"*
- *"What must already be true for this command to be valid?"*
  - *"What credentials must the actor hold? (auth preconditions)"*
  - *"What facts must exist in the local state? (state preconditions)"*
  - *"Any deadlines, cooldowns, business hours? (temporal preconditions)"*
- *"If the actor retries, what stops a duplicate?"* — nothing to author here: `idempotency_key_expression` was removed from the template spec; the runtime dedups on the exn message's own SAID instead.
- *"What happens on success? Does it emit an IPEX message? Advance a credential's lifecycle? Append to a local aggregate? All of those?"*

## Step 5 — Aggregates

**Primary:**
- *"What state does this role track locally?"*

**Follow-ups per aggregate:**
- *"What history must I read to know if a command is valid?"* — that's the aggregate
- *"What's its identifier and how is it minted? (inception event)"* — the `boundary.inception_event_type`; also ask *"which field on the event picks out one instance from another?"* — the `boundary.instance_key`
- **What does each event in this aggregate's log record?** Name each event type in the past tense,
  and for each one: which properties does it carry, which are always present, and which are
  genuinely optional? Anything a fold handler reads must be always-present.
- **Does any event type have more than one producer?** If two triggers would write the same event
  type with a literal telling them apart, those are two event types. Name them separately.
- **Is any property of this event the *birth* of an identity** — the moment a credential SAID
  becomes the thing's name? Declare it with `from: credential_said` on that event type. If
  other events carry the same key from command input afterwards, that is the mint/carry
  pattern and the checker verifies both sides route one projection.
- *"Walk each event type this aggregate cares about — for each, what happens to the state? Is it a simple field set/append/remove (an op list), or does it need a full custom reducer (a raw CEL expression)?"* — this builds the `fold` handler map, one entry per event type
- *"What test vectors prove each fold handler does what you just said? Give me a couple of `(events in) → (state out)` examples per handler."* — `test_vectors`
- *"What invariants does it protect? (plain English; will become validation rules)"*
- *"Is this log private, witnessed, or shared with others?"*

## Step 6 — Reactions

**Primary:**
- *"What does this role do when something happens that they didn't initiate?"*

**Follow-ups per reaction:**
- *"What event are they reacting to? An incoming credential? An exn message? A local lifecycle transition? A scheduled timer?"*
- *"What do they do in response? (same emission shape as commands)"*
- *"What if the reaction fails? Log and continue? Spurn? Abort?"*

## Step 7 — Workflows

**Primary:**
- *"Are there multi-step external interactions this role participates in?"*

**Follow-ups per workflow:**
- *"Who's the counterparty?"*
- *"What kicks it off? A user action? A schedule? A received credential?"*
- *"Walk through the steps from this role's perspective only. For each: do they act, or are they waiting? If acting, which command or reaction? If waiting, what are they waiting for and what triggers the next step?"*
- *"Are there branches based on conditions? Time limits?"*

## Step 8 — Projections

**Primary:**
- *"What views does this role need to do their job?"*

**Follow-ups per projection:**
- *"What question does this answer?"*
- *"Which event streams does it fold over?"*
- *"Is this a list of rows, or one single summary document?"* — `shape`: `collection` (rows) or `object` (one folded document, no `primary_key`)
- *"For a `collection` shape: what field (or expression over the event) picks out which row an incoming event updates?"* — `primary_key`
- *"Do those event streams come from more than one log? If so, what ordering can you rely on — the single-source order, sort by timestamp, or does the fold have to work in any order?"* — `ordering` (`source_seq` | `datetime_said` | `commutative`)
- *"Walk each event type — for each, does it add/update a row, remove one, or replace the whole document?"* — builds the `fold` handler map, same op-list/raw-reducer duality as an aggregate
- *"What test vectors prove each handler does what you just said?"* — `test_vectors`
- *"What's the output shape? (Locksmith will render this as a table, list, cards, kanban, timeline, or summary)"*
- *"Who's allowed to see each row? (credential-gated row filter)"*

## Step 9 — Rules

**Primary:**
- *"Let's go through all the forward-referenced rules and author each. For each rule, what type fits best?"*

**Follow-ups per rule:**
- *Type-specific questions, see `rule-types-reference.md`*

## Step 10 — Metadata

**Primary:**
- *"Let's audit the naming conventions. Did we follow them, or do you have specific reasons for deviating?"*

**Follow-ups:**
- *"Which emergent ecosystems do you think this micro-app belongs to? (kebab-case tags)"*
- *"Does this template improve on, refine, or compete with any other template you know of?"*
- *"Any author notes you want surfaced when someone explores the emergent ecosystem view?"*
- *"Any templates you know are compatible or incompatible with this one?"*
