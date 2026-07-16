# `acdc-design` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone, user-invocable `acdc-design` skill that guides the nine ACDC credential-type design decisions, grounded in the normative ACDC spec, reusable by `micro-app-template-gen` Step 3.

**Architecture:** A new sibling skill at `locksmith-micro-app-designer/skills/acdc-design/` — `SKILL.md` (mental-model preamble + master decision checklist that routes) plus four `references/` cluster files (progressive disclosure). Content is produced grounding-first: a spec-cited facts brief is built before any decision framework is authored, so no claim ships un-verified. Small integration edits wire `micro-app-template-gen` Step 3 to it and fix the `u`-field template gap; `ugard/docs/canon/` gets a thin pointer (single source, no copy).

**Tech Stack:** Markdown skill (skill-creator conventions), JSON Schema (ACDC envelope examples), Python eval harness (skill-creator `generate_review.py` + `run_loop.py`). No application code.

## Global Constraints

- **Spec is ground truth.** Every protocol claim traces to `/Users/seriouscoderone/KERI/specs/acdc-specification.md`. `keri:acdc`/`keri:spec` are distilled convenience; `keri:chat` is for ecosystem *practice* only; on any conflict the spec wins (`specs-trump-canon`).
- **Practice ≠ normative.** Patterns harvested from RAG/canon are labeled as practice, not spec-normative.
- **Point, don't restate.** Envelope shape, `oneOf` compact form, SAIDify recipe already live in `micro-app-template-gen/references/ten-step-process.md` Step 3 and the `keri:acdc` references — link them, never duplicate.
- **House style:** per-decision format = *When to choose X vs Y → Default → Worked example (insurance-flavored) → Mechanics pointer*, mirroring `references/rule-types-reference.md`; each cluster file ends with a compact decision tree.
- **Template-level edge names:** use `authorizes` / `references` / `authorizes-via-delegate` (the template vocabulary), mapping each to `I2I` / `NI2I` / `DI2I` — do not expose raw operators in author-facing copy.
- **SKILL.md < 500 lines.** Depth goes in `references/`.
- **Two settled decisions are restated, not reopened:** (1) edges are authz-only (`ugard/docs/canon/credential-authority-model.md` §5); (2) extension is by new SAID / chaining, never in-place schema mutation.
- **Two repos, isolated worktrees** (Task 1): `locksmith-micro-app-designer` (skill + integration) and `ugard` (canon pointer + backlog). Each repo gets its own branch `acdc-design-skill` and its own worktree.

---

### Task 1: Create isolated branches + worktrees in both repos

**Files:** none authored; environment setup only.

**Interfaces:**
- Produces: two worktrees with checked-out branch `acdc-design-skill`, one per repo. All later tasks operate inside these worktrees. Tasks 2–8, 10 run in the `locksmith-micro-app-designer` worktree; Task 9 runs in the `ugard` worktree.

- [ ] **Step 1: Create the locksmith-micro-app-designer worktree**

Invoke `superpowers:using-git-worktrees` for repo `/Users/seriouscoderone/code/locksmith-micro-app-designer`, branch `acdc-design-skill` (base `main`). Let the skill choose the mechanism (native or `git worktree` fallback).

Fallback command if the skill defers to raw git:
```bash
cd /Users/seriouscoderone/code/locksmith-micro-app-designer
git worktree add -b acdc-design-skill .worktrees/acdc-design-skill main
```

- [ ] **Step 2: Verify the worktree is on the new branch**

Run:
```bash
git -C /Users/seriouscoderone/code/locksmith-micro-app-designer/.worktrees/acdc-design-skill branch --show-current
```
Expected: `acdc-design-skill`

- [ ] **Step 3: Create the ugard worktree**

Invoke `superpowers:using-git-worktrees` for repo `/Users/seriouscoderone/code/ugard`, branch `acdc-design-skill` (base `main`).

Fallback:
```bash
cd /Users/seriouscoderone/code/ugard
git worktree add -b acdc-design-skill .worktrees/acdc-design-skill main
```

- [ ] **Step 4: Verify**

Run:
```bash
git -C /Users/seriouscoderone/code/ugard/.worktrees/acdc-design-skill branch --show-current
```
Expected: `acdc-design-skill`

- [ ] **Step 5: Copy the approved spec into the worktree if not already present**

The spec was committed to `main` (`fce47fd`); confirm it is visible in the worktree:
```bash
ls /Users/seriouscoderone/code/locksmith-micro-app-designer/.worktrees/acdc-design-skill/docs/superpowers/specs/2026-07-16-acdc-design-skill-design.md
```
Expected: path exists. No commit in this task.

---

### Task 2: Build the grounding-facts brief

**Files:**
- Create: `docs/superpowers/plans/2026-07-16-acdc-design-grounding-brief.md` (working companion to this plan, in the locksmith worktree)

**Interfaces:**
- Produces: for each of the nine decisions, a block containing (a) the hard spec constraint(s) with a citation anchor into `acdc-specification.md`, (b) the settled-canon reference if any, (c) any practice-level note flagged as practice. Tasks 3–6 cite this brief; reviewers verify authored claims trace to it and it traces to the spec.

- [ ] **Step 1: Extract spec anchors for the nine decisions**

For each decision, locate the governing text in `/Users/seriouscoderone/KERI/specs/acdc-specification.md` and record a short quote/section pointer. Use grep to find anchors, e.g.:
```bash
SPEC=/Users/seriouscoderone/KERI/specs/acdc-specification.md
grep -n -i 'targeted\|untargeted\|issuee'      "$SPEC" | head
grep -n -i 'private\|public\|blind\|uuid\|salt' "$SPEC" | head
grep -n -i 'compact\|selective\|partial\|graduated disclosure' "$SPEC" | head
grep -n -i 'oneOf\|composable\|most compact'    "$SPEC" | head
grep -n -i 'registry\|TEL\|blind'               "$SPEC" | head
grep -n -i 'version\|\$id\|backward'            "$SPEC" | head
grep -n -i 'governance\|EGF\|ecosystem'         "$SPEC" | head
```

- [ ] **Step 2: Write the brief**

Write one block per decision. Example (real, verified earlier this session):

```markdown
## Public vs private (`u` field)
- **Spec:** ACDC variants are determined by the top-level `u` (UUID) field. No `u` → **public**: the SAID does not blind contents; with schema + SAID known, field values may be discoverable via rainbow-table attack, so a commitment to the SAID is a correlation point → treat as non-confidential. `u` with sufficient entropy → **private**: SAID blinds contents; commitment leaks no correlation until disclosure. Empty `u` (`""`) → **metadata** variant. (acdc-specification.md — "ACDC Variants" / top-level `u` field.)
- **Canon:** none specific.
- **Practice note:** —
```

Repeat for: targeted vs untargeted; disclosure-mode; edge topology & operators; registry/TEL pattern; versioning/migration; EGF adoption; schema-encoded vs external governance; authority bootstrapping. For the last three, carry the practice-level patterns from the owner's `keri:chat` (2026-07-16) **flagged as practice**, and record the corrected fact: KERI AIDs are stable across key rotation (pre-rotation), so baked-in authority AIDs do **not** break on rotation — the real risk is authority *replacement*.

- [ ] **Step 3: Verify every citation resolves**

For each spec citation in the brief, confirm the referenced text exists:
```bash
grep -c -i 'ACDC Variants' /Users/seriouscoderone/KERI/specs/acdc-specification.md
```
Expected: ≥ 1 for each cited anchor. No dangling citations.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-07-16-acdc-design-grounding-brief.md
git commit -m "docs(acdc-design): grounding-facts brief (spec citations per decision)"
```

---

### Task 3: Author `references/shape-and-disclosure.md`

**Files:**
- Create: `skills/acdc-design/references/shape-and-disclosure.md`

**Interfaces:**
- Consumes: grounding brief blocks for targeted/untargeted, public/private (`u`), disclosure-mode.
- Produces: a reference the SKILL.md checklist routes to for "what shape is the credential and what does it reveal."

- [ ] **Step 1: Write the three decisions in house-style format**

Each decision uses *When to choose X vs Y → Default → Worked example → Mechanics pointer*. Worked exemplar to include verbatim as the model for the file (targeted vs untargeted):

```markdown
## Targeted vs untargeted

**When:** Is the credential *about* a specific holder (an Issuee AID belongs in the
`a` block), or is it a "to whom it may concern" attestation of authorship only?

**Default:** Targeted. Most role/authority/license credentials name their subject;
untargeted is the exception (e.g., a published price table attesting only the issuer).

**Worked example:** A carrier license is **targeted** — the licensed carrier's AID is
the `a.i` Issuee. A public rate-filing attestation with no specific counterparty is
**untargeted** — verifiable authorship, no Issuee.

**Mechanics:** ACDC Variants (Targeted/Untargeted), `keri:acdc` references/sections.md;
envelope shape in `micro-app-template-gen` ten-step-process §Step 3.
```

Then author **public vs private (`u`)** using the brief's verified block — including the actionable rule: *default public for non-confidential attestations; choose private (add a high-entropy `u`) when a commitment to the credential must be made before disclosure, or when the schema+SAID would otherwise leak field values.* And **disclosure-mode** (full vs selective vs partial): default full; selective when a holder must reveal one attribute of many without the rest; partial/metadata when a commitment precedes contractual disclosure (chain-link confidentiality).

- [ ] **Step 2: Add the closing decision tree**

```markdown
## Choosing shape & disclosure

Is there a specific subject AID? ── yes ─→ targeted   ── no ─→ untargeted
Must you commit before revealing, or does schema+SAID leak values? ── yes ─→ private (`u`) ── no ─→ public
Will a holder reveal a subset of attributes independently? ── yes ─→ selective disclosure ── no ─→ full
```

- [ ] **Step 3: Verify structure**

Run:
```bash
cd skills/acdc-design/references
grep -c '^## ' shape-and-disclosure.md          # expect ≥ 4 (3 decisions + decision tree)
grep -c '\*\*Default:\*\*' shape-and-disclosure.md   # expect 3
```
Expected: ≥ 4 and 3.

- [ ] **Step 4: Commit**

```bash
git add skills/acdc-design/references/shape-and-disclosure.md
git commit -m "feat(acdc-design): shape-and-disclosure reference (targeted, u-field, disclosure)"
```

---

### Task 4: Author `references/edges-and-provenance.md`

**Files:**
- Create: `skills/acdc-design/references/edges-and-provenance.md`

**Interfaces:**
- Consumes: grounding brief block for edge topology & operators; `ugard/docs/canon/credential-authority-model.md` §5.
- Produces: the reference the checklist routes to for edge decisions.

- [ ] **Step 1: Write the edge decisions**

Cover: (a) chaining (`authorizes` / I2I — issuer of this credential is the holder of the parent) vs linking (`references` / NI2I — informational pointer, no authority transfer) vs delegated (`authorizes-via-delegate` / DI2I); (b) single edge vs multi-parent edge-group with m-ary operators; (c) cardinality.

**The load-bearing reconciliation (restate canon, do not reopen), include verbatim:**

```markdown
## Edges are authz-only (ugard decision)

In generic ACDC material, an NI2I "reference" edge is often used to hang extra
*data/context* off a credential (transcript → accreditation → course catalog).
**That is not the ugard way.** Per `credential-authority-model.md` §5, edges carry
*authority/provenance only*; a data-facet predicate never edge-walks. Data is
delivered on-demand and folded into aggregate state — never carried ambiently on an
edge. NI2I remains valid as a provenance operator (this credential *references* an
authority it did not descend from), but if you find yourself adding an edge to move
attribute values, stop: model that as a separate credential import + aggregate fold,
not an edge.
```

**Default:** `authorizes` (I2I) when the parent's holder must be this credential's issuer (the common delegation case); `references` (NI2I) only for provenance pointers, never for data; `authorizes-via-delegate` (DI2I) when the issuer is a KEL-delegated AID of the parent's holder.

**Worked example:** carrier-license design's edge justification (a license *references* the DOI authority without descending from it → NI2I; an agent appointment *authorizes* → I2I).

- [ ] **Step 2: Add the decision tree**

```markdown
## Choosing an edge

Does the parent's holder issue this credential? ── yes ─→ authorizes (I2I)
  └─ via a delegated AID? ─→ authorizes-via-delegate (DI2I)
Is the edge only a provenance pointer (no authority, no data)? ─→ references (NI2I)
Are you using the edge to carry attribute values? ─→ STOP: model as import + aggregate fold, not an edge
Multiple parents combine into one authority verdict? ─→ edge-group with m-ary operator
```

- [ ] **Step 3: Verify structure**

```bash
grep -c '^## ' skills/acdc-design/references/edges-and-provenance.md   # expect ≥ 3
grep -i 'authz-only' skills/acdc-design/references/edges-and-provenance.md   # expect a hit
```
Expected: ≥ 3 and a match.

- [ ] **Step 4: Commit**

```bash
git add skills/acdc-design/references/edges-and-provenance.md
git commit -m "feat(acdc-design): edges-and-provenance reference (I2I/NI2I/DI2I, authz-only)"
```

---

### Task 5: Author `references/lifecycle-and-registries.md`

**Files:**
- Create: `skills/acdc-design/references/lifecycle-and-registries.md`

**Interfaces:**
- Consumes: grounding brief blocks for registry/TEL pattern and versioning/migration.
- Produces: the reference the checklist routes to for lifecycle/versioning decisions.

- [ ] **Step 1: Write the two decisions**

**Registry/TEL pattern:** when a credential needs a revocation/state registry at all (any lifecycle beyond issue-once); backed (witnessed TEL) vs backerless; registry-per-type vs per-issuer; blinded-state TEL when the registry event stream itself is a correlation risk. Default: one backed registry per issuer, un-blinded, unless a privacy requirement forces blinded state. Map lifecycle transitions to TEL primitives (`issue`/`update`/`revoke`) per ten-step-process §Step 3.

**Versioning & migration (include verbatim the core rule):**

```markdown
## Versioning & migration

A schema is immutable: the `$id` SAID *is* the version, `version` semver is
informative. Any change is a **new SAID = a new type** (type-is-schema). You never
edit a schema in place. Backward-compatible additions → bump minor, new SAID, verifiers
may accept both. Backward-incompatible change → bump **major**; holders migrate by
**re-issuance** under the new schema (issue new, revoke old — the carrier design's
`issued → superseded` pattern). Edges that point at a changed type either accept both
majors via `oneOf`, or the pointed-to credentials are revoked+reissued.
```

- [ ] **Step 2: Add the decision tree**

```markdown
## Choosing lifecycle & registry

Any state after issuance (revoke/suspend/expire)? ── no ─→ no registry needed
                                                  └─ yes ─→ backed TEL, one per issuer
Registry event stream itself a correlation risk? ─→ blinded-state TEL
Schema change: attributes added only? ─→ minor bump, new SAID, dual-accept
Schema change: breaks old instances? ─→ major bump + re-issue holders
```

- [ ] **Step 3: Verify structure**

```bash
grep -c '^## ' skills/acdc-design/references/lifecycle-and-registries.md   # expect ≥ 3
grep -i 'type-is-schema\|new SAID' skills/acdc-design/references/lifecycle-and-registries.md
```
Expected: ≥ 3 and a match.

- [ ] **Step 4: Commit**

```bash
git add skills/acdc-design/references/lifecycle-and-registries.md
git commit -m "feat(acdc-design): lifecycle-and-registries reference (TEL pattern, versioning)"
```

---

### Task 6: Author `references/governance-and-bootstrapping.md`

**Files:**
- Create: `skills/acdc-design/references/governance-and-bootstrapping.md`

**Interfaces:**
- Consumes: grounding brief blocks for EGF adoption, schema-encoded vs external governance, authority bootstrapping (all practice-flagged where appropriate).
- Produces: the reference the checklist routes to for governance/bootstrapping decisions.

- [ ] **Step 1: Write the three decisions**

**EGF adoption of schema SAIDs:** a schema becomes "the standard" by an EGF pinning its SAID in a well-known accepted-set; adoption is emergent (vote-by-usage) across ecosystems, governed within one. Authoring-side action: publish the SAID and record it where the EGF's accepted-set will reference it. (Publication/discovery *service* is out of scope — ugard `egf-publisher-registry`.)

**Schema-encoded vs external governance:** you *can* bake authority into a schema — `enum`/`const` on the issuer `i`, a required authorization edge pinning an authority-credential schema SAID + `authorizes`(I2I), or a required rules-section commitment to a governance-framework SAID. Trade-off: automated, immutable, machine-checkable enforcement **vs** rigidity (adding an authorized issuer = new schema SAID = new type) and lock-in. Default: **external governance** (open schema, authorization in the EGF) — matches vLEI practice; bake in only for closed, stable, single-authority types. *(Practice-level; flag as such.)*

**Authority bootstrapping ("open now, closed later")** — include verbatim:

```markdown
## Authority bootstrapping ("open now, closed later")

ugard's literal situation: state DOIs are not on KERI yet, but credential types must
ship now. Pattern:
1. v1 schema leaves the issuer field **unconstrained** (open).
2. Fill the authority *role* with an internal placeholder AID; the carrier
   self-issues as placeholder (see the carrier-license design).
3. Declare current-vs-target authorized issuers and a transition plan in a
   governance-framework SAD.
4. When the real authority joins KERI, transition by **re-issuance** under the real
   authority, with a verifier dual-acceptance window; if closing the schema, ship a
   major-version v2 with the issuer constrained.

**Correction (spec fact, not the RAG claim):** KERI AIDs are *stable across key
rotation* (pre-rotation is the mechanism), so a baked-in authority AID does **not**
break when the authority rotates keys. The real reason to prefer open-then-closed is
authority **replacement** (successor org, unrecoverable compromise) and the rigidity
of constraining issuers before the ecosystem exists.
```

Couple this explicitly to the EGF-resolver work: the EGF doc model should carry bootstrap-phase fields (current AID, target authority, expected transition).

- [ ] **Step 2: Add the decision tree**

```markdown
## Choosing governance

Is the authority set closed, stable, single? ── yes ─→ may bake in (enum/const/edge/rules)
                                              └─ no  ─→ external governance (open schema + EGF)
Do the real authorities exist on KERI yet? ── no ─→ bootstrap: open v1 + placeholder + transition plan
Standardizing a type across parties? ─→ publish SAID; EGF pins it in the accepted-set
```

- [ ] **Step 3: Verify structure + practice flags**

```bash
grep -c '^## ' skills/acdc-design/references/governance-and-bootstrapping.md   # expect ≥ 4
grep -i 'practice' skills/acdc-design/references/governance-and-bootstrapping.md   # expect ≥ 1 flag
grep -i 'stable across key rotation' skills/acdc-design/references/governance-and-bootstrapping.md
```
Expected: ≥ 4, ≥ 1, and a match.

- [ ] **Step 4: Commit**

```bash
git add skills/acdc-design/references/governance-and-bootstrapping.md
git commit -m "feat(acdc-design): governance-and-bootstrapping reference (EGF, bootstrap)"
```

---

### Task 7: Author `skills/acdc-design/SKILL.md` (router)

**Files:**
- Create: `skills/acdc-design/SKILL.md`

**Interfaces:**
- Consumes: the four reference files (Tasks 3–6) — the checklist routes to them by exact filename.
- Produces: the always-loaded entry point; its `description` is the trigger surface for evals (Task 10).

- [ ] **Step 1: Write frontmatter + body**

```markdown
---
name: acdc-design
description: Use when designing an ACDC credential type or its JSON-Schema — deciding structure and governance, not serializing bytes. Covers targeted vs untargeted, public vs private (u-field blinding), disclosure mode, edge topology (authorizes/references/delegate), registry/TEL pattern, versioning & migration, EGF adoption of schema SAIDs, schema-encoded vs external governance, and authority bootstrapping ("open now, closed later"). Reach for this whenever someone asks how to design/model/structure a credential, verifiable attestation, or ACDC schema — even if they don't say "ACDC" — including from micro-app-template-gen Step 3. NOT for serializing/SAIDifying a schema (ten-step-process) or linting one.
user_invocable: true
---

# ACDC Credential-Type Design

## Mental model (read first)

An ACDC schema is an unsigned **SAD** (self-addressing data). Its **integrity**
comes from the SAID (`$id`), its **authority** from the issuer's signature on
issued credentials committing to that schema SAID, and its **trust** from the EGF
that pins the SAID. So: you don't sign or "register" a schema to make it
authoritative — you publish it and let an ecosystem adopt its SAID. Extension is
never in-place mutation: any change is a new SAID = a new type; you extend by
chaining new credentials via edges.

## Decision checklist (route to the reference for the decision in front of you)

| Decision | Reference |
|---|---|
| Targeted vs untargeted · public vs private (`u`) · disclosure mode | `references/shape-and-disclosure.md` |
| Edge topology · authorizes/references/delegate · edges-are-authz-only | `references/edges-and-provenance.md` |
| Registry/TEL pattern · versioning & migration | `references/lifecycle-and-registries.md` |
| EGF adoption · schema-encoded vs external governance · bootstrapping | `references/governance-and-bootstrapping.md` |

Work top-to-bottom for a new type; jump to the row you need for a single decision.

## Grounding discipline (for anyone extending this skill)

Ground truth is `/Users/seriouscoderone/KERI/specs/acdc-specification.md`. `keri:acdc`
/`keri:spec` are distilled convenience; `keri:chat` answers *practice* questions only.
Verify any claim against the spec before it becomes guidance; label practice patterns
as practice. On conflict, the spec wins.

## Serialization is elsewhere

Once decisions are made, author the schema file per
`micro-app-template-gen/references/ten-step-process.md` §Step 3 (envelope shape,
`oneOf` compact form) and SAIDify with `scripts/saidify_acdc_schema.py`. This skill
decides; that step serializes.
```

- [ ] **Step 2: Verify line count + routing integrity**

```bash
wc -l skills/acdc-design/SKILL.md   # expect < 500
for f in shape-and-disclosure edges-and-provenance lifecycle-and-registries governance-and-bootstrapping; do
  test -f skills/acdc-design/references/$f.md && echo "OK $f" || echo "MISSING $f"
done
```
Expected: < 500 lines; four `OK` lines (every routed reference exists).

- [ ] **Step 3: Commit**

```bash
git add skills/acdc-design/SKILL.md
git commit -m "feat(acdc-design): SKILL.md router (mental model + decision checklist)"
```

---

### Task 8: Wire `micro-app-template-gen` Step 3 + fix the `u`-field template gap

**Files:**
- Modify: `skills/micro-app-template-gen/SKILL.md` (reference table / Step 3 row)
- Modify: `skills/micro-app-template-gen/references/ten-step-process.md:122-157` (Step 3 envelope example)

**Interfaces:**
- Consumes: the `acdc-design` skill name.
- Produces: a pointer from Step 3 to `acdc-design`; a `u`-field-capable envelope example.

- [ ] **Step 1: Add the pointer in ten-step-process.md Step 3**

After the Step 3 goal line (`ten-step-process.md:92`), insert:
```markdown
> **Design decisions first.** Before authoring the schema, settle the design
> decisions for this credential (targeted/untargeted, public/private `u`, disclosure
> mode, edges, registry, versioning, governance) using the **`acdc-design`** skill.
> This step then serializes those decisions into the envelope below.
```

- [ ] **Step 2: Add `u` to the canonical envelope example**

In the envelope example (`ten-step-process.md:130-157`), add `u` to the top-level `properties` and a one-line note. Change the `properties` block to include:
```json
    "v": {"type": "string"},
    "d": {"type": "string"},
    "u": {"type": "string"},
    "i": {"type": "string"},
```
And add below the code block:
```markdown
`u` (top-level UUID) is **optional** and controls the public/private variant: omit it
for a public attestation; include a high-entropy value for a private (blindable)
credential. See the `acdc-design` skill (`shape-and-disclosure.md`). `u` is not added
to `required`.
```

- [ ] **Step 3: Add the reference-table row in micro-app-template-gen SKILL.md**

In the "Reference files" table, add:
```markdown
| the `acdc-design` skill | Credential-type design decisions consumed at Step 3 (targeted/untargeted, `u`/blinding, disclosure, edges, registry, versioning, governance) |
```

- [ ] **Step 4: Verify the template example still validates**

The envelope example is illustrative Markdown, not a live `schemas/*.json`, so no saidify run is required. Confirm the JSON block is well-formed:
```bash
sed -n '/^```json/,/^```/p' skills/micro-app-template-gen/references/ten-step-process.md | sed '1d;$d' | python -c "import sys,json; [json.loads(b) for b in sys.stdin.read().split('\n\n\n') if b.strip()]" 2>/dev/null; echo "checked"
```
If the multi-block split is awkward, instead copy the single edited envelope block to a temp file and run `python -m json.tool` on it. Expected: parses without error.

- [ ] **Step 5: Commit**

```bash
git add skills/micro-app-template-gen/SKILL.md skills/micro-app-template-gen/references/ten-step-process.md
git commit -m "feat(micro-app-template-gen): wire Step 3 to acdc-design + add u-field to envelope example"
```

---

### Task 9: Add the ugard canon pointer + flip backlog status (ugard worktree)

**Files:**
- Create: `docs/canon/acdc-design.md` (thin pointer) — in the **ugard** worktree
- Modify: `backlog/2026-07-16-acdc-design-guide.md` (Status → active/done-tracking)

**Interfaces:**
- Consumes: the skill's location.
- Produces: canon single-source pointer (no copy), backlog status updated.

- [ ] **Step 1: Write the thin pointer**

```markdown
# ACDC Credential-Type Design

The design decisions for ACDC credential types (targeted/untargeted, public/private
`u`-field blinding, disclosure mode, edge topology, registry/TEL pattern, versioning &
migration, EGF adoption, schema-encoded vs external governance, authority
bootstrapping) live in the **`acdc-design` skill**, not in canon — one source, no copy.

- Skill: `locksmith-micro-app-designer/skills/acdc-design/`
- Design: `locksmith-micro-app-designer/docs/superpowers/specs/2026-07-16-acdc-design-skill-design.md`

Related canon: [credential-authority-model.md](credential-authority-model.md) (edges
are authz-only), [rule-types-reference.md](rule-types-reference.md),
[keri-trust-and-verification.md](keri-trust-and-verification.md).
```

- [ ] **Step 2: Flip backlog Status**

In `backlog/2026-07-16-acdc-design-guide.md`, change `**Status:** proposed` to `**Status:** active` and append a line under it: `**Delivered as:** acdc-design skill (locksmith-micro-app-designer).`

- [ ] **Step 3: Verify + commit**

```bash
git -C /Users/seriouscoderone/code/ugard/.worktrees/acdc-design-skill add docs/canon/acdc-design.md backlog/2026-07-16-acdc-design-guide.md
git -C /Users/seriouscoderone/code/ugard/.worktrees/acdc-design-skill commit -m "docs(canon): pointer to acdc-design skill; backlog active"
```

---

### Task 10: Evaluate the skill (skill-creator harness)

**Files:**
- Create: `skills/acdc-design/evals/evals.json`
- Create (workspace, untracked): `acdc-design-workspace/iteration-1/…`

**Interfaces:**
- Consumes: the finished skill (Tasks 3–7).
- Produces: behavioral + trigger eval results for the human review gate.

- [ ] **Step 1: Write behavioral eval prompts**

```json
{
  "skill_name": "acdc-design",
  "evals": [
    {"id": 1, "prompt": "Design the carrier-license credential type for our insurance ecosystem.", "expected_output": "Surfaces targeted, u-field, disclosure, edge, registry, versioning, governance decisions with spec-grounded defaults", "files": []},
    {"id": 2, "prompt": "I need to issue carrier licenses now, but the state DOI isn't on KERI yet. How do I model the credential?", "expected_output": "Bootstrapping pattern: open v1, placeholder authority, transition plan, re-issue later", "files": []},
    {"id": 3, "prompt": "Should I add a reference edge to hang the accreditation document off my transcript credential?", "expected_output": "Restates edges-are-authz-only; routes data to import+aggregate fold, not an edge", "files": []}
  ]
}
```

- [ ] **Step 2: Run with-skill vs baseline via skill-creator**

Invoke `skill-creator` and follow its run/grade/viewer loop against `evals.json` (with-skill and no-skill baseline). Present the eval viewer for the human review gate. This is the behavioral test — judged on whether the nine decisions are surfaced and defended with spec-grounded reasoning.

- [ ] **Step 3: Trigger evals + description optimization**

Build the 20-query trigger eval set (should-fire: "design a credential/attestation/ACDC schema for X" in varied phrasings; should-not: running a witness, rotating keys, serializing/linting a schema). Run `skill-creator`'s description optimizer; apply `best_description` to SKILL.md frontmatter.

- [ ] **Step 4: Commit**

```bash
git add skills/acdc-design/evals/evals.json skills/acdc-design/SKILL.md
git commit -m "test(acdc-design): behavioral + trigger evals; optimized description"
```

---

## Self-Review

**Spec coverage:** SKILL.md router (spec §Structure) → Task 7; four reference clusters covering all nine decisions (spec §Structure table) → Tasks 3–6; per-decision format (spec §Per-decision format) → Tasks 3–6; source-hierarchy discipline (spec §Content-sourcing) → Task 2 + SKILL.md grounding section (Task 7); two settled decisions restated (spec §"already settled by canon") → Tasks 4 (edges-authz-only) & 5 (new-SAID); integration + `u`-field fix (spec §Integration) → Task 8; canon drift-kill pointer (spec §Integration) → Task 9; behavioral + trigger evals (spec §Testing) → Task 10; two-repo isolated worktrees (user directive) → Task 1. No gaps.

**Placeholder scan:** no "TBD/TODO/handle edge cases." Cluster tasks specify exact headings, the grounding-brief entries to cite, one verbatim worked exemplar each, a verification grep, and a commit — the remaining decisions are fully constrained by (structure + brief + exemplar), not left vague.

**Type/name consistency:** skill name `acdc-design` and the four reference filenames (`shape-and-disclosure.md`, `edges-and-provenance.md`, `lifecycle-and-registries.md`, `governance-and-bootstrapping.md`) are identical across the SKILL.md checklist (Task 7), the authoring tasks (3–6), and the canon pointer (Task 9). Edge vocabulary (`authorizes`/`references`/`authorizes-via-delegate` → I2I/NI2I/DI2I) is consistent between Task 4 and Task 8.
