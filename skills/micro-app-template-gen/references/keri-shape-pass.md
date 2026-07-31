# The KERI-Shape Pass

Run this **before Step 2**, and again whenever a later step sends you back (see *The back-edge*).

The ten steps produce spec-conforming, lint-clean, SAID-correct JSON. They never ask whether the
thing you are modeling should be a **KERI primitive at all**. This pass is that question. It is
**diagnostic, not prescriptive**: most domain facts stay template mechanics, and §*The counter-test*
says which. Its job is to catch the requirement that is describing something ACDC and KERI already
give you *unforgeably*, before you translate the requirement's sentence into a boolean, a status
column, or a domain event.

**Its output is five recorded answers.** Write them into `metadata.json` — the five `Q`s below, one
line each, under `convention_compliance` (an open string→string map, so
`"lifecycle_spelling": "TEL state; …"` is legal today) or in `author_intent_notes`. A pass whose
answers are not written down did not happen: the next author, and the reviewer, both need to know
which shape you chose *and that you chose it*.

---

## Say which thing you mean (four words, and this page uses them strictly)

"ACDC" is used in the wild for both the type and the instance, and the confusion produces real
modeling errors — including one in an earlier draft of this page. Authoring spec §4 carries the
definitions; the short form:

| Term | Means |
|---|---|
| **ACDC** | the **instance** — one issued container. The spec's own bare usage |
| **ACDC schema** | the **type**. Under *type-is-schema* the `s` field **is** the type field, so the schema SAID is simultaneously the type identity and the immutable validation rules |
| **credential** | a **targeted** ACDC — one with an issuee (`i` in the attribute block): *"issued by Issuer and issued to Issuee"* |
| **attestation** | an **untargeted** ACDC — no issuee: *"to whom it may concern; verifiable authorship only."* **Not a credential** |

**The trap this page nearly walked into:** "one credential per scope" means **many instances of one
ACDC schema** — never one schema per scope. Fifty jurisdictions is fifty issued credentials from one
`state_authorization` schema, not fifty schemas. When you write about granularity, say *instances* or
say *schema*.

**And bare "schema" is overloaded in this model.** `payload_schema`, `row_schema`, `state_schema` are
ordinary JSON-Schema for local slots and are **not** ACDC schemas — measured across the landed corpus,
they are the *majority* of schema-bearing keys. Write "ACDC schema" whenever you mean the type.

**Four terms are not the whole variant space — they are the part that causes *naming* errors.** Three
more axes exist, each of which can make "the ACDC" mean something different, and every one is
`acdc-design`'s decision, not this page's:

| Axis | Why it is a naming hazard | Decided in |
|---|---|---|
| **Public / Private / Metadata** (the top-level `u` field) | A **metadata** ACDC (`u = ""`) has a SAID that *differs from the real private ACDC's*. "The ACDC's SAID" is two different values depending on which you meant | `acdc-design`, shape-and-disclosure |
| **Compact / non-compact** | The same instance, different bytes — sections replaced by their SAIDs. All variants form one hash tree, and the issuer's commitment is on the **most compact** variant's SAID. "The ACDC" may be any node on that tree | same |
| **Registry state: blinded (`bup`) or visible (`upd`)** | This is the hazard people hit most: *"a blinded credential"* almost always means **a credential whose registry state is blinded** — the blinding is on the TEL state, not on the ACDC | `acdc-design`, lifecycle-and-registries |

Two more that change what an *instance* is, same routing: **`a` vs `A`** (attribute section vs aggregate
section — mutually exclusive; the aggregate is what makes per-element selective disclosure possible), and
**bulk issuance**, where one logical grant is many pre-generated instances with distinct SAIDs, so "the
credential" is a set rather than a thing.

Say which axis you mean, then hand the decision to `acdc-design`. This page only decides whether the
thing should be an ACDC at all.

---

## The load-bearing rule

> **ACDC enforces constraints over existence and identity. It cannot enforce constraints over values
> inside a thing. So when a requirement states a constraint, the authoring move is to convert it into
> an existence constraint wherever the domain allows — usually by changing the granularity of an
> object, not by adding a field.**

The protocol basis, quoted rather than paraphrased (ACDC spec, Edge Validation — see the `keri:acdc`
skill, `references/sections.md` §3):

```
validate_edge(near, far, edge):
  1. SAID(far) == edge.n
  2. far satisfies its own schema
  3. If edge.s: validate far against edge.s schema (skip if same as step 2)
  4. Resolve effective unary operator (defaults above)
  5. Apply: I2I/DI2I check issuer-issuee; NOT inverts; NI2I = no constraint
  6. Return result
```

Three things follow, and they are the whole pass:

1. **No step compares an attribute value in the near node against one in the far node.** By
   enumeration — those six steps are the procedure. So stop trying to express
   `child.state ∈ parent.states[]` and start asking *what object the edge should point at*.
2. **Steps 1–3 hold independently of the operator.** The operator is not even resolved until step 4.
   `NI2I` means "no constraint" on the **issuer↔issuee relation** — it does **not** relax the
   requirement that the far node exist, hash to `edge.n`, and satisfy its schema. This is why the
   fixes below need no authority-bearing edge, and why they do not reopen
   `launch_edge_is_provenance_only` (correctly closed: edges are provenance; authority rides the role
   credential).
3. **The `r` section is not an escape hatch.** A terminal Rule block's fields are `d` (MAY), `u`
   (MAY), `l` (MUST — the legal language), and it **MUST NOT have any other fields**. There is
   nowhere to put an expression. Ricardian rules are contract text a human enforces, not a
   constraint language a validator runs.

**On the word "unconstructable."** Precisely: the bad state has **no valid representation**. You can
always emit bytes; a credential naming a far node that does not exist fails step 1, and *"broken
link = head invalid"* (ACDC, Provenance Validation), so every validator rejects it. That is
categorically different from a rule someone remembered to write. It does not stop anyone from
writing a row in their own local database — it stops them from ever getting a counterparty to accept
it.

---

## Q1 — Is this a credential?

**Ask:** does an authority *issue* this, such that its existence is the fact?

**The tells.** Any of these in the requirement text:

- an authority verb — *issued, granted, approved, filed, certified, attested, cleared, licensed*;
- *immutable once <verb>*; *superseded, never deleted*; *corrections are filed forward*;
- *identified by a number that outlives the parties*;
- *who decided, when, and on what basis*.

And in a draft: **a collection row carrying both a decision (`decided_by` / `decided_at` /
`rationale` / `approval_status` / `*_reference`) and a `status`** — that row is a credential wearing a
table.

**Not a tell:** a `*_said` field pointing at *someone else's* credential (`launch_approval_said`). That
is a reference to a decision, not a record of one — the decision already is a credential, and this row
correctly points at it.

**KERI-native shape.** An issued ACDC. The decision *is* the artifact; there is no separate audit
record to keep in sync with it. Its attributes are what the requirement enumerates.

### Then Q1b — is there a third option you are skipping?

**The shape the rest of this page was missing.** § *The truth-maker rule* says an artifact you merely
witness stays observational — and an author reads "observational" as *a local projection column*. There
is a middle option this page had no name for: if the observation must be **verifiable by someone else**,
its KERI-native form is an **untargeted attestation** — you author it, you sign it, and nobody can read
authority out of it. So the answer set is three, not two:

| If the fact… | Shape |
|---|---|
| confers something on a **named party** | a **credential** (targeted) |
| is an observation **others must be able to check** | an **attestation** (untargeted) |
| is an observation **nobody outside this role checks** | a local row — stay a mechanic |

**Ask the SME, not the protocol:** *"Is this addressed to one named party who's going to rely on it, or
is it a statement anyone might read? And does anyone outside your own team ever need to check it?"* The
words *targeted* and *untargeted* are yours, not theirs — see `question-bank.md` § "KERI decision →
what to actually ask".

One consequence worth knowing before you choose: only a **Targeted** far node may bear an `I2I` edge, so
an attestation is reachable by `NI2I` only — which is the point, but it constrains what can chain to it.

**The decision itself belongs to `acdc-design`** (`references/shape-and-disclosure.md`), which owns
targeted-vs-untargeted along with blinding and disclosure mode and carries the defaults and worked
examples. This page's job is to stop you skipping the question — not to answer it. Route.

Note the corpus has **zero** untargeted ACDCs — all six export schemas require `i` — so this branch is
unexercised here, and `rating_attestation` is *named* attestation while being targeted, i.e. it is a
credential. Read that as a gap to be careful about, not as precedent.

**Corpus, right:** `carrier_license` — the regulator's grant is the credential, with a four-state
lifecycle and all three TEL primitives.

**Corpus, wrong:** the **rate program**. R18 enumerates: issued by an authority, immutable once
approved, effective-dated, corrected by filing again forward, identified by a number outliving
everyone involved. *Every property R18 enumerates is a property of an issued credential.* It was
modeled as a mutable projection row with a `status` column, keyed by the filename of the spreadsheet
it was parsed out of. One consequence, measured: `effective_date` and `filing_reference` appear in
**zero predicates** across the template's rule expressions, `approval_status` — which R18's own Data
list names — appears **nowhere**, and the projection's own shipped test vector reports a program
effective `2027-01-01` as live on `2026-11-03` while the only chargeable program reads `superseded`.
Status was a literal chosen by which event arrived.

---

## Q2 — Is this a lifecycle?

**Ask:** is this `status` column the state of one thing over time?

**The tells.**

- A field named `status`, `state`, `*_status`, `*_state`, `phase`, `stage`, `disposition` on a row —
  **and a fold handler that assigns it a literal** (`{"op": "set", "target": "status", "value":
  "'superseded'"}`). A status set by *which event arrived* is a lifecycle spelled as a column.
- An event type named `*_superseded`, `*_revoked`, `*_suspended`, `*_expired`, `*_cancelled`,
  `*_reinstated`, `*_activated` — **whose subject has no credential to own the transition.** That
  qualifier is the whole tell, and it is what separates the corpus:

  | Event type | Subject | Verdict |
  |---|---|---|
  | `license_suspended` (regulator) | `carrier_license`, an **export** whose declared lifecycle has `suspended` | ✅ the TEL holds the standing; the event logs the act |
  | `clearance_revoked` (designer) | `filing_clearance`, an **import** | ✅ an observed counterparty transition — you record it, you never refuse it (truth-maker rule) |
  | `rate_program_superseded` (actuary) | `rate_program` — **neither an export nor an import; not a credential at all** | ❌ nothing owns the standing, so status must be stamped from whichever event arrived |

  Recording a transition is fine. Recording a transition that **no TEL owns** means the event *is* the
  mechanism, and that is the defect. *(Known false positive: a local alias for an imported credential —
  the actuary calls the designer's `product_definition_version` a "candidate", so `candidate_superseded`
  trips this tell and resolves benignly. Answer it by naming the credential the alias refers to.)*
- **Two emissions from one trigger context that write the same projection.** This is the mechanical
  tell that one of them is a lifecycle transition impersonating a domain event: conform-by-name binds
  both from the same context, so both take the same routing key and the second lands on the first's
  row.

**KERI-native shape.** A TEL state change on the credential's own registry. "Current" is then a dated
query, not a flag. A TEL's `ts` **MUST be a string from a finite set of state values**, which is
exactly what your `lifecycle.states` list is — `issued`/`revoked` are the spec's *common* encodings,
not the whole permitted set, so a richer declared state machine mapped onto the three
`tel_primitive`s (`issue` / `update` / `revoke`) is protocol-legal.

**Then pick ONE spelling and record it.** A credential's lifecycle has two legitimate spellings and
one wrong one:

| Spelling | Use when | Corpus |
|---|---|---|
| **TEL state** (`issued → superseded`, `tel_primitive: update`) | the issuer's act changes the thing's standing | `rating_attestation` ✅ |
| **A `supersedes` edge** (self-referential, `operator: references`/NI2I) | you need the *lineage link* to be verifiable, not just the standing | `product_definition_version` ✅ |
| **A domain event** (`rate_program_superseded`) | **never, for a credential's own lifecycle** | rate program ❌ |

This corpus currently carries **all three at once**, and only the third produced a blocking finding.
That is the tell. Write your choice into `metadata.json`:

```json
"convention_compliance": {
  "lifecycle_spelling": "TEL state — supersession is an update on the program's own registry; no domain event."
}
```

---

## Q3 — Is this an ordering fact?

**Ask:** does this boolean assert that one thing happened before another?

**The tells.**

- A **boolean** whose name contains `before`, `after`, `prior`, `already`, `pre_`, `post_`, `_first`,
  `_yet`.
- A requirement phrase: *"X must happen before Y"*, *"not until"*, *"only after"*.
- A presence derivation — `size(state.<x>) > 0`, `state.<x>.exists(...)` — whose result is **stored**
  as a field: an event property, a fold write target, a projection column.

**Stored, not gated.** The same expression inside a `state_precondition` or an invariant is a **pure
gate** and is exactly right — *"at least one seal exists before I let you seal"* is what a precondition
is for. Measured over this corpus, that one distinction is the difference between **2 hits and 25**:
all 23 presence checks sitting in `rules[].expression` are legitimate, and both **stored** ones were
blocking findings. Apply the tell to stored values only.

**KERI-native shape.** A **required edge** from Y to X. You cannot form Y without committing to X's
SAID, and a dangling commitment fails `validate_edge` step 1 — so "Y with no X in it" has no valid
representation. Two independent mechanisms carry it: the *required* part is your `e`-section schema
(an ACDC lacking the edge label fails step 2, its own schema); the *non-dangling* part is step 1.
The boolean then has nothing left to say and gets deleted, not repaired.

**And the ordering can't be gamed, for free.** `n` is a *hash* of the far node, so X must already exist
and be hashed before Y can commit to it. A cycle is unconstructable and the direction of the edge *is*
the direction of time — you get acyclicity from content-addressing, with no rule to write and nothing
to check. This is why "ordering is an edge" is safe rather than merely convenient.

**Corpus, wrong:** `governance_sealed_before_freeze`, computed `size(state.sealed_governance) > 0` at
observation time and carried in the event payload so a collection projection could read it. Note it
was also **lying about its own claim**: the expression asserts *"some seal exists on this desk right
now"*; the name promises *"this version's manifest commits to the governance I sealed."* Different
claims — and the bundle's own rule `governance_manifest_inclusion_is_content_plane` already conceded
the second was unproven. A required edge from the frozen version to the governance seal makes the
first claim structural and the boolean vacuous.

**Watch for this shape specifically:** a boolean that is written **once on upsert and never
recomputed**. See *The truth-maker rule*.

---

## Q4 — Is this discrimination against an array element?

**Ask:** am I checking membership in an array attribute to decide whether something is permitted?

**The tells.**

- An **array-typed attribute** on a credential — `states[]`, `lines[]`, `scopes[]`, `tiers[]`,
  `jurisdictions[]` — folded into an array field of local state; **and**
- an expression testing membership in it to gate admissibility:
  `state.<list>.exists(m, m == event.credential.attributes.<x>)`, `.contains(…)`, `in`.

**KERI-native shape.** **An edge targets an ACDC** — the spec's Edge block requires `n` to be the far
node's ACDC **SAID** — **not an array element.** So while the authorization lives in an array, the
chain has nothing to discriminate against and you are forced to check the value yourself, which is
precisely what `validate_edge` cannot do for you. Change the granularity: **one issued credential per
authorized scope — many instances of ONE ACDC schema.** Fifty jurisdictions is fifty issued
credentials from one `state_authorization` schema, *not* fifty schemas; if you find yourself minting a
schema per scope, you have read this the wrong way round. The inbound artifact then carries an `NI2I`
edge to *that scope's* credential, and an artifact for an unauthorized scope has no edge target —
step 1, plain `NI2I`, no authority in the edge.

**The objection to expect, and the spec's answer.** An SME will say *"that's a lot of credentials."*
It is, and the spec treats that as the **first** privacy mechanism rather than a cost: disclosure
tier 1 is **ACDC chaining** — *"decompose bundled credentials into a graph of separately disclosable
ACDCs."* Splitting `states[]` into per-scope credentials means the holder can disclose authority for
Utah without revealing that they also hold Nevada. The bundled array cannot do that at any price. So
the granularity change buys unforgeable discrimination **and** disclosure granularity; it is not a tax
paid for the former.

**Corpus, wrong:** `in_mandate`, computed
`state.mandate_states.exists(m, m == event.credential.attributes.state)`. The mandate's authorized
states were a `states[]` array attribute on one `launch_approval` credential. Model it as a
line-level thesis plus **per-`(line, state)` authorization credentials** and the clearance for an
unauthorized state is unconstructable. Two commands the current shape cannot express fall out of the
same fix: *adding* a state is issuing one credential, and *partial exit* is a TEL transition on one —
where today `record_exit_decision` has no `state` parameter at all and the whole mandate exits at
once.

**The honest limit, which you must write down rather than skip.** Chaining closes the **day-one case
only**. Scopes move: a mandate exits a state, an authorization expires, and a counterparty
legitimately pre-files months before your board decides. So a reconciliation read survives the
fix — **as an as-of evaluation with a named consumer**, never as a payload field frozen at ingest.
See *The truth-maker rule*.

---

## Q5 — Is this identity?

**Ask:** where does this identifier's value come from, and who controls its lifecycle?

**Cross-reference authoring spec §5.7 — the six identifier kinds — and name the kind.** Doing that
per identifier is the whole check. The failure mode is a kind-4 **foreign coordinate** promoted to
kind-3 **stable business key** or to a kind-5 **routing selector**.

**The tells.**

- The value is **hand-keyed by a human**, supplied as a console/CLI argument, or read off a parse run.
- The value is an **external system's coordinate** (a workbook reference, a filing tracking number, a
  legacy tool's path).
- The value is a **concatenation or format of other fields** — a composite string doing the work a
  SAID would do.
- It is `required`, `type: string`, and carries **no `pattern`**, while a sibling identifier in the
  same `payload_schema` is patterned. An unvalidated required string whose empty value is a silent
  no-op and whose typo'd value matches no row is a defect in field form.

**Apply that last tell to identifier-shaped names only** — `id`, `*_id`, `*_ref`, `*_key`,
`*_version`, `*_coordinate`, `*_number`, `*_reference`. Prose fields (`note`, `reason`, `rationale`,
`thesis`, `statement`) are *supposed* to be unpatterned, and `*_said` is verified by **resolving** the
content address, not by a regex. Unnarrowed, this tell fires 28 times on one bundle and buries the one
real hit; narrowed, it fires 6.

**KERI-native shape.** **A SAID over the content manifest.** If you already mint a SAID that commits
to the thing's content, *that* is the identity; a foreign coordinate keeps honest work as
**provenance** — where this content came from — filed next to the other provenance, never as the key.

**Corpus, wrong:** the rate program's `ipd_coordinate`, a caller-supplied
`<line>/US-XX/<major>.<minor>` string hand-keyed at the console during a spreadsheet parse, used as
the program's identity *and* as a projection's `primary_key` — in a template whose own rule
`rating_source_tracing` says a transcribed rate table is a defect waiting for a rate exam. The design
had already minted the right object (`program_manifest_said`, a SAID over the shard map) and had
already demoted the parse `index_said` to provenance **for exactly this reason**, then kept the parse
coordinate as the identity anyway. Getting a rule right one field over does not transfer.

---

## The truth-maker rule (where "make it impossible" stops)

Structural impossibility is the point of Q1–Q5, and applied everywhere it trades one systematic error
for another. The line:

> **You may refuse to construct only what you are the truth-maker for. Artifacts you author →
> structural. Artifacts you witness → observational, and the observation is evaluated as-of, never
> frozen at ingest.**

A filing clearance is a *regulator's* fact. Refusing to construct the record does not un-happen the
event; it deletes the only verifiable trace of it. Three cases break any construction-time model, and
each is a real requirement, not an edge case:

1. **A scope narrowed after an artifact was issued.** The artifact was valid when issued. It is not
   retroactively forgeable, and it is not currently in scope. Both are true.
2. **A counterparty acting outside your scope for their own valid reasons** — they pre-file, they
   file for a line you have not launched, they are right to.
3. **An inherited book** arriving with artifacts issued under someone else's authority.

Two corollaries, both observed in the corpus, both worth checking by name:

- **A derived observation frozen at ingest is a bug.** `in_mandate` was written once on upsert and
  never recomputed, so it could never reflect a scope that changed afterward. If the fact is an
  observation, it is a **read-time evaluation at a named as-of date**.
- **An observation with no consumer is decoration.** `in_mandate: false` had no invariant, no
  precondition, no filter, no alert, no notification — measured: each of the CUO bundle's two derived
  booleans occurred in exactly **one** expression, a copy-through in an unrelated fold handler. A
  human could read the column; nothing else did, and nothing refreshed it, so what the human read
  could be false by the time they read it. If the template's prose says a person must *see* something,
  the template must **route** it somewhere.

---

## The counter-test — what legitimately stays a template mechanic

Q1–Q5 are diagnostic. If you answer "yes" to all five on every fact, you have built a credential
registry, not a micro-app. These stay exactly where they are:

| Stays a mechanic | Why |
|---|---|
| **Local workspace state** — drafts, notes, sort order, a kanban lane, "seen" flags | No issuer, no counterparty, nothing to prove to anyone who was not there |
| **Derived projections** — counts, totals, filters, "days until", a sort | Recomputable from the log at read time. *Freezing* one is the bug; deriving it is the design |
| **Pure gates** — a `state_precondition` over this role's own state | `no_active_license_for_jurisdiction` reads your own aggregate. Nobody else needs to verify it |
| **Counterparty facts you observe** | Observational by the truth-maker rule — record, evaluate as-of, never refuse |
| **A finite declared state set** | The lifecycle *is* the states list. You do not need a credential per state — only per independently-authorized **scope** (Q4) |
| **Display columns and view types** | Presentation. A column is not a claim unless its name makes one (Q3's naming trap) |

The one question that separates the table above from Q1–Q5: **does this need to be provable later, to
someone who wasn't there?** If no, it is workbench or mechanic and this pass has nothing to say.

---

## The back-edge

**If a command, reaction, or projection needs a value the trigger cannot supply, do not add a field —
return to this pass, then to Step 3. The default resolution is that the credential is the wrong shape
or the wrong granularity.**

The ten steps run credentials (2, 3) → commands (4) → aggregates (5) → reactions (6) → projections
(8). Without a back-edge, a Step 6 or Step 8 dead end has only two legal moves — make the names agree,
or declare a mint (§6.5 `from`) — and **neither one can supply a value derived from state.** An author
with no third move invents a payload field. That is, mechanically, how the corpus's two derived
booleans got authored: both were computed at reaction time from `state.*`, and there was never a name
for them to agree with.

The third move is this pass. Run Q3 on `governance_sealed_before_freeze` and Q4 on `in_mandate` and
both properties stop existing rather than needing a slot.

---

## Reaching the protocol

Name these rather than reconstructing the protocol from memory:

| Where | Skill | For |
|---|---|---|
| Steps 2–3, credential design | **`acdc-design`** (already wired at Step 3) | targeted/untargeted, `u`/blinding, disclosure mode, edge topology, registry pattern, versioning, governance. This pass decides *whether* there is a credential; `acdc-design` decides *what it looks like*. Route to it — do not duplicate it |
| Steps 2–3, and Q1–Q5 here | **`keri:acdc`** | edge operators and `validate_edge`, TEL registry patterns and `ts` state sets, disclosure. Where existence-vs-value and the lifecycle spelling get settled |
| Steps 5–6, aggregates and reactions | **`keri:acdc`**, plus **`keri:spec`** | what a fold may assume about a credential; KEL anchoring and ordering |
| Adversarial review | **`keri:chat`** | adjudicating any protocol claim the template's prose makes |

**Specs are ground truth. When framework canon and the spec disagree, the canon is the defect** —
verify, do not assert. The framework has done this to itself: authoring spec §6.4 once forbade
conform-by-name from reaching an inbound ACDC's attributes, reasoning that implicit binding "would let
a counterparty's schema change silently re-bind this role's log." That hazard does not exist on this
protocol — ACDC requires a schema's `$id` to be a **bare SAID** and the schema to be **immutable**,
and every import pins `expected_schema_said`, so a counterparty schema that changes *is a different
SAID* and the import stops matching, loudly. A defensive mechanism against a threat the substrate had
already eliminated survived in the contract, with no requirement behind it. It was narrowed on
2026-07-31. The failure mode is not SME-specific: it is what happens whenever anyone authors in this
space without checking an assumption against the protocol.

**Reachability caveat:** `keri:chat` is a hosted service and is intermittent (it returned
`INTERNAL_ERROR` for a whole session, then answered some questions and not others in the next). The
fallback is the `keri:acdc` and `keri:spec` reference files, which carry the same normative text
locally.

**A second caveat about `keri:chat`, which matters more than availability: it does not distinguish
spec from tutorial.** Its corpus mixes `acdc-specification.html` and `keri-specification.html` with
training and glossary material, and it cites them interchangeably. Concretely, asked about issuance it
described *"a TEL issuance (`iss`) event"* three times — but the ACDC spec's registry ilks are **`rip`**
(registry inception), **`bup`** (blindable update) and **`upd`** (update). `iss`/`rev` are keripy/vLEI
implementation vocabulary. The answer was right; the vocabulary was one layer down from the spec. Use
chat to *find* the normative sentence, then read it.

**Two protocol facts worth knowing before you lean on IPEX.** First, **the ACDC spec's IPEX section is
explicitly non-normative** — a baseline for ecosystem-specific protocols, which is exactly why this
framework reserves `/ipex/*` and defines its own exchange semantics on top. Do not cite IPEX as
settled protocol. Second, **IPEX does not issue.** Issuance is the anchor — an issuance seal in the
issuer's KEL directly, or a TEL event anchored there — and it is a unilateral issuer-local act. The
ACDC's SAID exists at that moment, before any message goes out; a `grant` *transmits* an
already-issued ACDC and `admit` is the recipient's non-repudiable commitment back. Consequence for
modeling: a self-issued ACDC that is never disclosed to anyone needs **no IPEX at all**, and a
lifecycle transition is likewise an anchoring act rather than an exchange.

---

## Calibration

The tells above were run mechanically over all five landed bundles, after being written and before the
three migrated ones were read. What that measured:

| Bundle | Hits | What they were |
|---|---|---|
| `actuary-attests-product-rating` (redesign) | 14 | Q2b + Q2c both name **finding 38a**; Q5 names `ipd_coordinate`-as-key and `supersedes_program_version`; Q1 names the filed-instrument row |
| `chief-underwriting-officer-…` (redesign) | 15 | Q3 names **39b** three ways and **39a**'s expression; Q4 names 39a and its second consumer; Q2a names all five stamped status literals |
| `product-designer-publishes-product-version` | 4 | two genuine kind-4 foreign coordinates carried as data (correct), two kind-3 keys to name |
| `regulator-grants-carrier-license` | 1 | `application_id` — kind 3 with a declared mint; the question is real, the answer is good |
| `carrier-license-application` | 0 | — |

**Both blocking findings fire; the three migrated bundles produce 5 questions and 0 blockers.** That is
the intended shape: a diagnostic asks, you answer from the counter-test, you move on. A tell that fires
and resolves benignly has done its job — it is only broken when it fires on something you cannot answer,
or when it stays silent on something real.

## What this pass cannot see

Per the house rule that a gate must name what it is blind to:

- **It is single-template scoped** — exactly like `micro-app check`. An author can run Q2 perfectly,
  pick TEL state, record it, and still not know the corpus already spells supersession two other ways.
  **Corpus-wide spelling consistency is the compatibility checker's job**
  (`scripts/micro_app_compat.py`), not this pass's.
- **It cannot count consumers.** "An observation with no consumer" is a whole-template expression
  scan — is there any rule, precondition, invariant, or `row_filter` reading this field? A human
  walking Q3 will miss it; a corpus query will not.
- **It cannot see a declared-but-unread field.** `effective_date` and `filing_reference` appearing in
  zero predicates is a measurement, and it is the mechanical root of a shipped vector reporting a
  not-yet-effective program as current.
- **It says nothing about whether a requirement is executable at all.** A template can pass every
  question here and still, as the CUO bundle does, claim a requirement written entirely about adding a
  second state while carrying no command that can add one. That is traceability, not shape.
- **It does not check names against a wire.** A local alias for a counterparty's field name is a
  reconciliation problem (`option_ref` vs `pinned_to`), not a "should this be a KERI primitive"
  problem.

These are named here so the prose does not imply otherwise. Four of them are filed as corpus-scope
checks against `scripts/micro_app_compat.py`.
