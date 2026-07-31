# Question Bank

Per-step questions to ask an SME. Pick the primary question first; ask follow-ups only when the primary answer leaves ambiguity. One question at a time.

**Ask in business language; think in KERI.** The SME owns the domain, not the protocol — so a question
that says "targeted", "untargeted", "aggregate", "AID" or "op list" cannot be answered by the person
you are asking, and an unanswerable question gets a guess. Every KERI decision has a business question
that reveals it; the table below pairs them. **You** hold the protocol vocabulary and route to the
protocol skills. The SME never has to.

## The question the whole frame turns on

Ask this before anything else, and ask it again of every fact that comes up:

> ***"Does this need to be provable later, to someone who wasn't there?"***
>
> And if yes: ***"Who is that someone, and what will they already know when they check?"***

Almost everything else follows from the answer. A "no" means it stays local — a workspace note, a view,
a gate — and none of the KERI questions apply to it. A "yes" names a **verifier**, and the verifier is
what decides whether the fact is a credential, whether it needs an issuee, what may be withheld, and
what has to be an edge. Most authoring drift starts here: the ten steps otherwise run entirely from the
*actor's* side — what they hold, what they do, what they see — and never ask who relies on the result.

## KERI decision → what to actually ask

| The decision you are making | Ask the SME | You route to |
|---|---|---|
| Is this a credential at all? | *"Does this need to be provable later, to someone who wasn't there?"* | `keri-shape-pass.md` Q1 |
| Targeted or untargeted | *"When this goes out, is it addressed to one named party who's going to rely on it — or are you publishing a statement anyone might read?"* | `acdc-design`, shape-and-disclosure |
| Public or private (`u` blinding) | *"If someone learned only that this document exists — not what's in it — would that alone tell them something you'd rather not say?"* | same |
| Disclosure mode | *"When they show this, do they show the whole thing, or does the other side usually only need one part of it?"* | same |
| Edge operator | *"Does holding the parent give you the **right to issue** this — or does it just record **where the information came from**?"* | `acdc-design`, edges-and-provenance |
| Lifecycle spelling (TEL state vs edge) | *"When a new one replaces an old one: does the old one's **standing** change, or do you need to **prove the link** between them? Or both?"* | `keri-shape-pass.md` Q2; ten-step §Step 3 |
| Registry blinding | *"Should outsiders be able to see when you suspend or revoke one of these — or should even that be invisible to anyone but the holder?"* | `acdc-design`, lifecycle-and-registries |
| Bulk issuance | *"Will you issue the same thing over and over, where someone seeing the same identifier twice could connect two uses that shouldn't be connected?"* | same |
| Per-scope granularity | *"If someone has authority in three states, should they be able to prove just the one that's relevant — without revealing the other two?"* | `keri-shape-pass.md` Q4 |
| Identifier kind | *"Who assigns this number or code — you, or somebody else? And what happens to you if they change how they assign it?"* | `keri-shape-pass.md` Q5; spec §5.7 |
| Ordering as an edge | *"Is there something that must already have happened before this one is allowed to exist?"* | `keri-shape-pass.md` Q3 |
| Truth-maker | *"Is this something **you** decide, or something you're **recording that someone else** decided?"* | `keri-shape-pass.md` § truth-maker |

**Notation in this file:** *italic quoted* lines are things to say out loud to the SME. Unquoted bold
lines are notes to **you**, the author — do not read them aloud; they name the slot the answer lands in.

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
- *"Is this a variation on something that already exists? What did you change about it, and why?"* —
  **you** resolve the parent's SAID and version from the repo; ask only for the intent

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
- **Find the ACDC schema SAID yourself** — look it up in the counterparty's template or the shared
  schema pack. Do not ask an SME for a SAID; they have no way to know one. If it does not exist yet, note
  it as TBD and continue
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
  - *"Does holding that parent give you the right to issue this one — or does it just record where the information came from?"* → **authorizing** vs **referencing**
  - *"Could someone act on your behalf here — a deputy or a system you stand behind — using their own signature rather than yours?"* → **via delegate**. Never say "delegated AID" to an SME
- *"When they show this to someone, do they show all of it — or does the other side usually only need one part of it?"* → full vs selective vs partial disclosure. **Do not offer "aggregate" as a choice**; it is the mechanism for one of these answers, not something an SME can pick. Route the decision to `acdc-design`
- *"Is it addressed to one named party who'll rely on it, or is it a statement anyone might read?"* → targeted (**credential**) vs untargeted (**attestation**). Ask it this way; the two protocol words are yours, not theirs
- *"What states does this credential go through?"* — list them
- *"For each state, how is it reached? Through which workflow? Mapping to KERI: is the transition an `issue` (initial creation), an `update` (mid-life change), or a `revoke` (terminal)?"*

## Step 4 — Commands

**Primary:**
- *"What actions does this role take?"*

**Follow-ups per command:**
- *"In imperative voice, what's this command called?"*
- *"What does the actor supply? (the payload)"*
- *"By what authority is this person allowed to do it — what would they have to be holding for you to
  accept it?"* — **this answer goes to `authz` (`credential` + `schema_said`, or `aid`/`allowlist`, or
  `open`), NOT to `auth_preconditions`.** Authority is credential-gated, and expressing it as a CEL
  predicate is a defect (ten-step §Step 4). Asking "what must be true for this to be valid" invites a
  permission check, which is the Web-2.0 shape; ask what they **hold**
- *"What must already be true in your own records for this to make sense?"* → `state_preconditions`
- *"Any deadlines, cooldowns, business hours?"* → `temporal_preconditions`
- *"If the actor retries, what stops a duplicate?"* — **nothing to author:** the runtime dedups on the
  exn message's own SAID.
- *"When this succeeds, what actually happens? Does something go out to the other party? Does something
  they hold change status? Does it just get written down on your side? Any combination?"* → the three
  emission kinds. **Do not say "IPEX" or "aggregate" out loud** — the discipline rule scopes that
  vocabulary to your own modeling, not to the interview

## Step 5 — Aggregates

**Primary:**
- *"What has to have happened, and been written down, for this role to know whether the next action is
  allowed?"* — **the log is the record; state is a fold of it.** Do not open with "what state do you
  track" — that invites a database table, and a table is where a status column comes from (see the two
  row checks at ten-step §Step 8)

**Follow-ups per aggregate:**
- *"What history must I read to know if a command is valid?"* — that's the aggregate
- *"What's its identifier and how is it minted? (inception event)"* — the `boundary.inception_event_type`; also ask *"which field on the event picks out one instance from another?"* — the `boundary.instance_key`
- **What does each event in this aggregate's log record?** Name each event type in the past tense,
  and for each one: which properties does it carry, which are always present, and which are
  genuinely optional? Anything a fold handler reads must be always-present.
- **Does any event type have more than one producer?** If two triggers would write the same event
  type with a literal telling them apart, those are two event types. Name them separately.
- Ask: *"Is this the moment the thing gets the name it will be known by from now on?"* — **if yes, that
  property is the birth of an identity: declare it with `from: credential_said` on that event type.**
  When later events carry the same key from command input, that is the mint/carry pattern and the
  checker verifies both sides route one projection.
- *"Walk each event type — when this happens, what changes in the record you just described?"* — this
  builds the `fold` handler map, one entry per event type. **Whether that becomes an op list or a raw
  CEL reducer is yours to decide from their answer, not a question to ask** — an SME cannot choose
  between an op list and a reducer, and asking makes them guess
- *"What test vectors prove each fold handler does what you just said? Give me a couple of `(events in) → (state out)` examples per handler."* — `test_vectors`
- *"What invariants does it protect? (plain English; will become validation rules)"*
- *"Is this log private, witnessed, or shared with others?"*

## Step 6 — Reactions

**Primary:**
- *"What does this role do when something happens that they didn't initiate?"*

**Follow-ups per reaction:**
- *"What event are they reacting to? Something arriving from someone else, a status change on something they hold, or a timer?"*
- *"Who is allowed to send you this — anyone, specific parties, or only someone holding a particular credential?"* → `authz`, same as a command. **A reaction is externally invocable, so it needs one too** — and the bank used to skip this entirely
- *"What do they do in response? (same emission shape as commands)"*
- *"Is what arrives something you decide, or something you're recording that someone else decided?"* →
  the truth-maker rule. **You never refuse to record a counterparty's fact**; you record it and evaluate
  it as-of at read time
- *"What if the reaction fails? Log and continue? Refuse it? Stop?"* → `log_and_continue` / `log_and_spurn` / `abort`

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
- *"Walk each event type — when this happens, does a new line appear on this view, does an existing one change, or does one drop off?"* — builds the `fold` handler map; **the op-list vs raw-reducer choice is yours**, as with an aggregate
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
