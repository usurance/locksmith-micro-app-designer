# Edges & Provenance Reference

Three decisions that fix how a credential type chains to what came before it:
which edge operator expresses the relationship, whether one parent or several
combine into a single authority verdict, and whether the edge is required,
optional, or absent. A load-bearing reconciliation sits between the first two
decisions: ugard narrows the spec's general-purpose edge mechanism to
authority/provenance only, and that narrowing is restated (not reargued) below.

## Chaining vs linking vs delegated

**When:** Does authority for this credential transfer from the parent
credential's holder (they become this credential's issuer), is the edge a
mere provenance pointer with no authority transfer, or is this credential
issued by a KEL-delegated AID of the parent's holder rather than the holder's
top-level AID?

**Default:** `authorizes` (I2I) when the parent's holder must be this
credential's issuer — the common delegation/appointment case.
`references` (NI2I) only for provenance pointers — never for carrying data.
`authorizes-via-delegate` (DI2I) when the issuer is a KEL-delegated AID of the
parent's holder, not the holder's own AID.

**Worked example:** The carrier-license design's edge justification: a
license **references** the DOI authority without descending from it (the
license's issuer is not the DOI's Issuee — NI2I). An agent appointment
**authorizes** off the carrier license (the license's holder — the carrier —
is the appointment's issuer — I2I). A regional underwriting office that the
carrier has KEL-delegated (its AID is a delegated AID of the carrier's, not
the carrier's own top-level AID) issues appointment credentials on the
carrier's behalf: those appointments **authorize-via-delegate** off the
license, because the appointment's issuer is a delegated AID of the license's
holder, not the holder's own AID (DI2I).

**Mechanics:** Edge Section, unary-operator table (`I2I`/`NI2I`/`DI2I`),
`keri:acdc` references/sections.md; template edge-name-to-operator mapping in
`micro-app-template-gen` ten-step-process §Step 3.

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

## Single edge vs multi-parent edge-group

**When:** Does authorization for this credential depend on exactly one prior
credential, or must two or more independent prior credentials combine into a
single authority verdict?

**Default:** A single edge. Reach for an edge-group with an m-ary operator
only when the verdict genuinely requires combining more than one parent —
don't reach for a combinator to express something that's really two separate
single-edge credentials.

**Worked example:** A reinsurance-treaty acceptance credential is bound only
if **both** the ceding carrier's cession authorization **and** the
reinsurer's binding-authority credential hold — an edge-group of two named
edges combined with `AND`. Contrast a jurisdiction-authorization credential
that's satisfied by **either** a direct state-DOI license **or** a
reciprocal-state license — an edge-group combined with `OR`.

**Mechanics:** Edge Section, m-ary operator table (`AND`/`OR`/`AVG`/`WAVG`/etc.),
`keri:acdc` references/sections.md.

## Cardinality

**When:** Is this edge present on every instance of the credential type, or
does its presence vary by which business path an instance took — and should
that variation still be the *same* schema (same SAID), or a different type?

**Default:** Required, when every instance of the type has something to chain
from. Optional (not listed in the schema's top-level `required` array) when
some instances legitimately have nothing to chain from and others do —
provided both cases are still faithfully described by one schema. A
credential type with no parent at all in its ecosystem model carries no edge
section.

**Worked example:** A carrier's founding operating license is a **root**
credential — no edge section, nothing precedes it. An agent appointment
carries a **required** single edge to an active carrier license — no
appointment is ever issued without one. A policy endorsement carries an
**optional** edge to the prior endorsement: the first endorsement on a policy
has none, the second and later ones do, and both validate against the same
endorsement schema SAID because the edge field isn't marked required.

**Mechanics:** Edge Section (top-level `e` field, `oneOf` compaction
requirement), `keri:acdc` references/sections.md.

## Choosing an edge

```markdown
Does the parent's holder issue this credential? ── yes ─→ authorizes (I2I)
  └─ via a delegated AID? ─→ authorizes-via-delegate (DI2I)
Is the edge only a provenance pointer (no authority, no data)? ─→ references (NI2I)
Are you using the edge to carry attribute values? ─→ STOP: model as import + aggregate fold, not an edge
Multiple parents combine into one authority verdict? ─→ edge-group with m-ary operator
```
