# `acdc-design` Skill — Design

**Date:** 2026-07-16
**Status:** proposed (brainstorm approved, owner, 2026-07-16)
**Spec authority (ground truth):** ACDC specification —
`/Users/seriouscoderone/KERI/specs/acdc-specification.md` (normative, 8,891 lines). Distilled
mechanics via the `keri:acdc` and `keri:spec` skills; ecosystem practice cross-checked via
`keri:chat`. On any conflict the normative spec wins (`specs-trump-canon`).
**Originating backlog:** `../ugard/backlog/2026-07-16-acdc-design-guide.md`
**Repos touched:** `locksmith-micro-app-designer` (new skill + small `micro-app-template-gen` edit);
`ugard` (thin canon pointer, backlog status)

## Problem

There is no consolidated guidance — anywhere — for the *design decisions* behind an ACDC credential
type. Confirmed against the ecosystem (`keri:chat`, 2026-07-16): beyond the normative spec (which
documents every *option*), the GLEIF vLEI training notebooks (mechanics tutorial), and the
WebOfTrust production schemas (worked examples), no design guide, best-practices doc, or authoring
style guide exists.

Locally the guidance exists but is fragmented across `ugard/docs/canon/` (decisions), the
`keri:acdc` references (mechanics/options), and one worked instance (the carrier-license design).
A repo sweep (2026-07-16) found **nine decision areas with no "choose X when Y" guidance**:
targeted vs untargeted; public vs private (`u`/blinding); disclosure-mode selection; edge topology
and chaining-vs-linking; registry/TEL pattern choice; versioning & migration; EGF adoption of schema
SAIDs; schema-encoded vs external governance; and authority bootstrapping ("open now, closed
later"). The last is acute for ugard: the insurance reference ecosystem must ship credential types
now whose real issuing authorities (state DOIs) join KERI later, and every such type currently
improvises its own transition story.

The real consumer of this guidance is not only a human — it is the `micro-app-template-gen` skill,
whose Step 3 ("Credential exports") is the heaviest step and produces the `schemas/*.json` files,
yet carries no decision framework for these choices. So the deliverable must be *active* (guidance a
skill applies while authoring), not a passive document. It must also be usable standalone: anyone
designing an ACDC credential type should be able to reach for it without walking the full 10-step
template flow.

## Goals

- A standalone, user-invocable skill `acdc-design` that guides the nine credential-type design
  decisions, each as an explicit framework with a stated default, grounded in the normative spec.
- Reusable by `micro-app-template-gen` Step 3 (delegate the decisions, resume serialization) and
  invocable on its own ("design a carrier-license credential type").
- Single source of truth: kills the copy-drift already observed between `ugard/docs/canon/` and the
  skill's own references (canon's `ten-step-process.md` has diverged from the skill copy).

## Non-goals

- **Not schema authoring/serialization mechanics.** The ACDC envelope shape, the `oneOf` compact
  form, and the SAIDify recipe already live in `micro-app-template-gen/references/ten-step-process.md`
  Step 3 and the `keri:acdc` references. This skill *points* to those; it does not restate them.
- **Not the template workflow.** `micro-app-template-gen` still owns the 10-step
  template+metadata+schemas flow. This skill is the decision layer Step 3 leans on.
- **Not compliance linting.** SAID/schema integrity checking is the
  `2026-07-16-acdc-schema-compliance-linter-design.md` linter's job.
- **Not the EGF registry/publisher service.** This skill covers only the *authoring-side*
  governance decisions; publication/discovery is the ugard `egf-publisher-registry` backlog item.
- No runtime, no network resolution of external SAIDs.

## Home & boundaries

New skill at `locksmith-micro-app-designer/skills/acdc-design/`, sibling to
`skills/micro-app-template-gen/`. The skill family lives together; the skill is general-purpose
(anyone designing an ACDC), and `micro-app-template-gen` is one caller among potentially many.

Two invocation paths:
1. **Standalone** — "help me design the homeowner claim-attestation credential type."
2. **Delegated** — `micro-app-template-gen` Step 3 hands off the design decisions, then resumes the
   template/metadata/schema serialization it already owns.

## Structure (skill-creator progressive disclosure)

```
skills/acdc-design/
├── SKILL.md
└── references/
    ├── shape-and-disclosure.md
    ├── edges-and-provenance.md
    ├── lifecycle-and-registries.md
    └── governance-and-bootstrapping.md
```

**SKILL.md** (always loaded on trigger; well under 500 lines):
- **Mental-model preamble** — schemas are unsigned SADs; integrity comes from the SAID, authority
  from the issuer's signature committing to the schema SAID, trust from the EGF. (Pre-empts the
  recurring "should we sign/register the schema?" confusion, confirmed via `keri:chat`.)
- **Master decision checklist** — the nine decisions in the order they arise while designing a
  credential type, each routing to the reference that covers it.
- **Source-hierarchy note** (see below) so any agent extending the skill respects grounding.

**`references/` — nine areas clustered into four files (loaded on demand):**

| File | Decisions |
|---|---|
| `shape-and-disclosure.md` | targeted vs untargeted · public vs private (`u`/blinding) · disclosure-mode selection |
| `edges-and-provenance.md` | edge topology & cardinality · chaining (I2I) vs linking (NI2I) · restates canon's edges-are-authz-only decision |
| `lifecycle-and-registries.md` | registry/TEL pattern choice · versioning & migration |
| `governance-and-bootstrapping.md` | EGF adoption of schema SAIDs · schema-encoded vs external governance · authority bootstrapping ("open now, closed later") |

## Per-decision format

Mirrors the proven house style of `micro-app-template-gen/references/rule-types-reference.md`:

- **When to choose X vs Y** — the discriminating question(s).
- **Default** — the recommended choice absent a reason to deviate.
- **Worked example** — insurance-flavored, drawn from the carrier-license design where possible.
- **Mechanics pointer** — to the spec / `keri:acdc` reference / `ten-step-process.md`, not a restatement.

Each cluster file ends with a compact decision tree (à la rule-types-reference §"Choosing the right
type"); SKILL.md's master checklist routes across all nine.

## Content-sourcing & verification discipline

The skill's authoring notes and this spec bind content production to a four-tier source hierarchy:

1. **Normative spec** (`/Users/seriouscoderone/KERI/specs/acdc-specification.md`) — ground truth for
   every protocol claim. Cite the section/requirement where a decision rests on a hard constraint
   (static-schema rule; most-compact-form SAID algorithm; `a`/`A` mutual exclusivity; `u`-field
   public/private/metadata determination; schema versioning `$id`-is-normative).
2. **`keri:acdc` + `keri:spec` skills** — distilled references for structured mechanics; the spec
   file overrides them on any discrepancy.
3. **`keri:chat`** — only for ecosystem-*practice* questions (what vLEI actually does; adoption
   patterns) and as a cross-check. Never the sole authority for a normative claim.
4. **ugard canon + carrier worked example** — for ugard's *decisions* (edges-authz-only, two-facet)
   and reusable insurance patterns.

**Embedded rule:** anything harvested from a RAG conversation or from canon is verified against
tier 1 before it becomes guidance; practice-level patterns are *labeled as practice, not
spec-normative*. Worked cautionary example carried into `governance-and-bootstrapping.md`: a
`keri:chat` session (owner, 2026-07-16) claimed baked-in authority AIDs break "on key rotation to a
new AID" — **wrong**, since KERI AIDs are stable across key rotation (pre-rotation is the point);
the real risk is authority *replacement* (successor org / unrecoverable compromise). Its useful
patterns (issuer `enum`/`const` constraints, governance-framework SADs with transition plans,
verifier dual-acceptance windows, equivalence/supersession credentials) are practice-level, and the
skill labels them so.

## Two decisions already settled by canon (restated, not reopened)

- **Edges are authz-only.** `ugard/docs/canon/credential-authority-model.md` §5 decides that a
  data-facet predicate never edge-walks; the authz layer verifies the chain and hands evaluation a
  verdict. `edges-and-provenance.md` restates this: NI2I remains valid as an authority/provenance
  operator, but the ecosystem-common "link your ACDC to theirs via NI2I to *carry extra
  data/context*" pattern is **not** the ugard way (data is delivered on-demand and folded into
  state, never carried on an edge). The skill states this explicitly so authors coming from generic
  ACDC material don't reach for data-carrying edges.
- **Extension is by new SAID / chaining, never in-place schema mutation.** Type-is-schema: any
  change is a new type. `shape-and-disclosure.md` and `lifecycle-and-registries.md` anchor on this.

## Integration

- **`micro-app-template-gen` edit (small):** in `SKILL.md` and `references/ten-step-process.md`
  Step 3, add a pointer — "for the design decisions in this step (targeted/untargeted, blinding,
  disclosure, edges, registry, versioning, governance), consult the `acdc-design` skill." No
  restructuring of the 10-step flow.
- **`u`-field template fix:** the canonical Step-3 authoring template omits the `u` field entirely,
  so an author following it never faces the privacy decision. Add `u` (with guidance) to the
  template/skeleton so the blinding decision the skill teaches is actually expressible.
- **Canon relationship (drift-kill):** `ugard/docs/canon/` gets a **thin pointer** to the skill as
  the single source, not another copy. `credential-authority-model.md`, `rule-types-reference.md`,
  and `keri-trust-and-verification.md` stay as-is and are cross-linked.

## Testing / evaluation (Principle VII + skill-creator)

A skill's real output is behavioral, so evaluation uses the skill-creator harness rather than unit
tests over prose:

- **Behavioral evals** — a handful of realistic design prompts ("design the carrier-license
  credential type"; "design a homeowner claim attestation"; "I need to issue a license before the
  state DOI is on KERI") run with vs. without the skill, human-reviewed via the eval viewer, judged
  on whether the nine decisions are surfaced and defended with spec-grounded reasoning.
- **Trigger evals** — should-fire on "design an ACDC / credential type / schema for X"; should-not
  over-trigger on unrelated KERI work (running a witness, rotating keys) or on the
  serialization/linting tasks other skills own.
- **Spec-grounding spot check** — each cluster file's hard-constraint claims trace to a cited
  section of the normative spec.

## Open questions

None blocking. Cluster boundaries and the exact worked examples may shift during authoring; the
nine decisions and the four-file grouping are fixed by this design.
