# ACDC Design Grounding-Facts Brief

**Purpose:** a working companion to `docs/superpowers/plans/2026-07-16-acdc-design-skill.md`
(the implementation plan for the `acdc-design` skill). It is not itself the skill content — it is
the traceability layer: for each of the nine credential-type design decisions the skill covers,
this brief records (a) the hard spec constraint(s) with a verifiable citation anchor into the
normative ACDC spec, (b) the settled-canon reference where `ugard/docs/canon/` already decided the
question, and (c) any practice-level note, explicitly flagged as practice rather than spec-normative.

**Ground truth:** the normative ACDC specification (~8,891 lines; hereafter "the spec") — accessed
via the `keri:acdc` / `keri:spec` skills, the canonical source being the IETF/ToIP ACDC
specification (local copy at `~/KERI/specs/acdc-specification.md` on the author's machine, if
available). Line numbers below are from that file as read on 2026-07-16 and may drift if the spec
file changes — the quoted anchor phrase is the durable reference; re-run the Step 3 check below if
a citation ever looks stale.

**Source hierarchy (per the skill design, `docs/superpowers/specs/2026-07-16-acdc-design-skill-design.md`):**
1. Normative spec — ground truth for every protocol claim.
2. `keri:acdc` / `keri:spec` skills — distilled mechanics; spec overrides on discrepancy.
3. `keri:chat` — ecosystem-*practice* cross-check only, never sole authority for a normative claim.
4. `ugard` canon + carrier worked example — for ugard's own decisions.

Tasks 3–6 (the four `references/*.md` files) cite this brief; reviewers verify authored claims
trace to it and that it in turn traces to the spec.

---

## 1. Targeted vs untargeted

- **Spec:** An ACDC variant is **Targeted** if the Attribute (or Attribute-aggregate) section
  has a top-level Issuee, `i`, field; **Untargeted** if that field is absent: "Two variants,
  namely, Targeted (Untargeted), are defined respectively by the presence (absence) of an
  Issuee, `i` field at the top-level of the Attribute section" (spec — "Targeted Attribute
  Section"). Targeted ACDCs let the Issuee provably control and disclose the credential by
  virtue of controlling the Issuee AID; the field is nested inside the Attribute section
  specifically so the Issuee AID itself remains partially disclosable. (spec §"Targeted
  Attribute Section", ~line 1357-1394; glossary terms "Targeted ACDC" / "Untargeted ACDC".)
- **Canon:** none specific.
- **Practice note:** —

## 2. Public vs private (`u` field)

- **Spec:** ACDC variants are determined by the top-level `u` (UUID) field. No `u` → **public**:
  the SAID does not blind contents; with schema + SAID known, field values may be discoverable
  via rainbow-table attack, so a commitment to the SAID is a correlation point → treat as
  non-confidential. `u` with sufficient entropy → **private**: SAID blinds contents; commitment
  leaks no correlation until disclosure. Empty `u` (`""`) → **metadata** variant. (spec —
  "ACDC Variants" / top-level `u` field.)
- **Canon:** none specific.
- **Practice note:** —

## 3. Disclosure-mode selection

- **Spec:** The spec defines a family of **Graduated Disclosure** mechanisms — "disclose enough
  to enable more disclosure" applied recursively — enumerated as: Compact Disclosure, Metadata
  Disclosure, Partial Disclosure, Nested Partial Disclosure, Full Disclosure, Selective
  Disclosure, and Bulk-issued Instance Disclosure (spec §"Graduated Disclosure"). Compact
  Disclosure specifically requires the block's schema to carry a `oneOf` composition operator
  that validates against both the compact (SAID-only) and full form of the block: "Compact
  Disclosure of a block (field map) of data relies on the inclusion in that block of a
  cryptographic digest of the content (SAID) ... The Schema for the block MUST include a
  `oneOf` composition Operator that validates against both the compact and full versions of the
  block" (spec, same section — anchor phrase "Compact Disclosure of a block"). Selective
  Disclosure specifically is implemented via the top-level Aggregate section, `A` field (spec
  §"Aggregate Section", ~line 1890).
- **Canon:** none specific — `keri-trust-and-verification.md` (ugard canon) restates the
  mechanics descriptively but does not add a design decision beyond the spec.
- **Practice note:** —

## 4. Edge topology & operators

- **Spec:** The Edge Section (`e` field) forms a sub-graph of Edge blocks and Edge-groups; the
  section itself "MUST have a 'oneOf' composition with only its SAID so that the Edge Section
  MUST be expressable in the most compact form" (spec §"Edge Section", ~line 2478-2541). Each
  Edge block carries an Operator, `o`, field that is either a **unary operator on the Edge
  itself** or an **m-ary operator on an Edge-group**: `I2I` (Issuer-To-Issuee — "The Issuer AID
  of this ACDC MUST be the Issuee AID of the node this Edge points to"), `NI2I`
  (Not-Issuer-To-Issuee — "MAY or MAY not be"), and `DI2I` (Delegated-Issuer-To-Issuee — "MUST
  be either the Issuee AID or a delegated AID of the Issuee AID") (spec, unary-operator table,
  ~line 2877-2929). Default-operator rule: if an Edge's Operator field does not include `I2I`,
  `NI2I`, or `DI2I`, the spec supplies a default based on whether the pointed-to node's Attribute
  section has an Issuee (~line 2895-2928). M-ary operators (`AND`/`OR`/`AVG`/`WAVG`/etc.) combine
  Edge-group members (spec, m-ary operator table, ~line 2625-2673).
- **Canon:** `ugard/docs/canon/credential-authority-model.md` §5 decides **edges are
  authz-only** — a data-facet predicate never edge-walks; the authz layer verifies the chain
  (via `I2I`/`DI2I`) and hands evaluation a verdict. This is an ugard-specific narrowing of the
  spec's general-purpose edge mechanism, not a spec requirement: the spec itself permits edges to
  carry arbitrary linked context (e.g. `NI2I` used to attach data, not just authority).
- **Practice note:** the wider ecosystem pattern of using `NI2I` edges to *link in extra
  data/context* (not just prove authority/provenance) is common practice elsewhere but is **not**
  the ugard way per the canon decision above — flagged so authors coming from generic ACDC
  material don't reach for data-carrying edges in this framework.

## 5. Registry/TEL pattern

- **Spec:** The optional top-level Registry SAID, `rd`, field "value is the SAID of an Issuer's
  Transaction Event Log (TEL) registry that maintains a dynamic state for the ACDC, such as
  issuance and/or revocation state" (spec §"Registry SAID Field", ~line 546-562). Registry state
  is maintained by a **TEL Registrar** (a component operating under the Issuer's auspices that
  publishes Registry state via a TEL) and cached by a **TEL Observer** (an independent component
  Validators query instead of the Registrar directly) — "A TEL Registrar is a computing component
  that operates under the auspices of the ACDC Issuer to maintain and publish a Registry of the
  ACDC state via a TEL. A TEL Observer, on the other hand, is a[n independent component allowing]
  Validators to cache the Registry" (spec §"TEL Registrars and TEL Observers", ~line 3666-3690).
  A Registry inception event (`rip`) and update events are anchored into the Issuer's KEL,
  cryptographically binding ACDC/registry state to Issuer key state (~line 3605-3618).
  A registry SAID MAY also be omitted entirely — "No issuance/revocation Registry is used" is a
  valid, spec-recognized configuration (~line 3605) — or nested inside the Attribute/Aggregate
  section instead of at the top level, for an application- or Issuer-specific registry
  distinct from the top-level one (~line 558-562).
- **Canon:** `ugard/docs/canon/credential-authority-model.md` treats TEL/Observer non-revocation
  as one of the two ambient authz gates (no-phone-home revocation check) — a usage decision built
  on top of this spec mechanism, not a redefinition of it.
- **Practice note:** —

## 6. Versioning & migration

- **Spec:** Every schema MUST carry a top-level `version` field as a semver dotted-decimal string
  ("major.minor.patch"); this field is **informative only** and is *not* used in JSON Schema
  validation (spec §"Schema Versioning", ~line 1120-1130). The **normative** version determinant
  is the Schema's `$id` field, a SAID: "the Schema ID, `$id` field value as a SAID provides a
  cryptographically verifiable version indicator independent of the version field value... the
  `$id` field value is the normative determiner of the Schema's true, verifiable version" (same
  section, ~line 1147-1155). Any change to the schema — including changing only the `version`
  field — produces a new SAID, i.e. a new type (type-is-schema). Backward-compatibility rule: a
  new schema version is **backward incompatible** if some ACDC instance that validated against
  the old schema is not guaranteed to validate against the new one; a **backward incompatible**
  schema MUST bump the semver *major* number relative to any version it is incompatible with
  (~line 1159-1170, anchor "backward incompatible"). Edge/node schema-version interplay: an
  Edge's `s` (schema) field may differ in version from the schema of the node it points to; if
  both validate, the Edge's schema MAY carry a higher *minor* version; if the Edge's schema does
  not validate against the pointed-to node, the Edge's schema is backward incompatible and MUST
  carry a higher *major* version (~line 1172-1185).
- **Canon:** the skill design's already-settled position ("Extension is by new SAID / chaining,
  never in-place schema mutation" — `docs/superpowers/specs/2026-07-16-acdc-design-skill-design.md`
  §"Two decisions already settled by canon") restates this spec rule as a design default rather
  than adding new constraint.
- **Practice note:** —

## 7. EGF adoption (of schema SAIDs)

- **Spec:** Because a Schema's SAID is a unique content-addressable identifier, an ecosystem can
  enforce compliance for an ACDC type "by comparison to the allowed schema SAID in a well-known
  publication or registry of ACDC types for a EGF. The EGF may be specified solely by the Issuer
  for the ACDCs it generates or be specified by some mutually agreed upon ecosystem governance
  mechanism" (spec, ~line 1243-1249). More broadly, the spec's "Extensibility" section frames
  this as **permission-less by design**: "there is no shared governance over these [KEL/TEL] data
  structures... the function of an extensible Registry of ACDC types now becomes merely Schema
  discovery or schema blessing for a given context or ecosystem. The reach of such a Registry of
  ACDC types can be tailored by ecosystem participants to their desired level of
  interoperability" (spec §"Extensibility", ~line 6633-6664, anchor "permission-less ACDC type
  Registries"). I.e. the spec does not mandate a specific EGF registry mechanism or timing — it
  only requires that whatever mechanism an ecosystem picks be anchored to schema SAIDs.
- **Canon:** none specific yet — ugard's `egf-publisher-registry` backlog item (referenced in
  `docs/superpowers/specs/2026-07-16-acdc-design-skill-design.md` Non-goals) will own the
  publication/discovery *service*; this skill covers only the authoring-side decision of whether
  and how a credential type declares/expects EGF registration.
- **Practice note (flagged — source: owner `keri:chat` session, 2026-07-16, mixes fact with
  practice):** the practice pattern of shipping a credential type before its "real" governing
  authority (e.g. a state DOI) has joined KERI — i.e. adopting the schema SAID into ecosystem use
  under a provisional/interim EGF, then formally registering it once the real authority is
  onboard — is an ecosystem *practice*, not a spec requirement. Useful practice-level patterns
  worth carrying (still practice, not spec-normative): governance-framework SADs that embed an
  explicit transition plan, and verifier dual-acceptance windows (accepting both the provisional
  and the eventual EGF-blessed SAID for a bounded period). See also Decision 9 below for the
  corrected fact this same source got wrong about authority AIDs.

## 8. Schema-encoded vs external governance

- **Spec:** The spec provides two distinct mechanisms for attaching governance/legal terms to a
  credential type, and they are not mutually exclusive: (1) **schema-encoded** — the top-level
  Rule Section, `r` field, carries "both human and machine readable legal language that MAY be
  associated with the ACDC" (spec §"Partially Disclosable Rule Section field", ~line 670-673),
  built from Rule blocks whose `l` field is literally "Legal Language ... Text of a Ricardian
  contract clause" (spec, top-level field table, ~line 437; §"Rule Section", ~line 2997-3166,
  anchors "Rule Section" / "Ricardian contract" / "Legal Language") — the terms travel inside the
  ACDC itself, SAID-committed and optionally selectively disclosable; (2) **external** — EGF-level
  governance, where "ACDC-specific Schema compliance requirements usually are specified in the
  EGF for a given ACDC type" (spec, ~line 1243-1244) and enforcement happens by comparing the
  ACDC's schema SAID against an ecosystem's registry/publication of allowed SAIDs, i.e. the terms
  live outside the ACDC, in ecosystem-level governance documents/registries the schema SAID is
  checked against.
- **Canon:** none specific — this is the same schema-SAID-as-compliance-key mechanism referenced
  in Decision 7 (EGF adoption); the two decisions are two facets of the same underlying spec
  mechanism (Rule section vs EGF registry) rather than independent spec rules.
- **Practice note (flagged — source: owner `keri:chat` session, 2026-07-16):** the practice
  pattern of using schema-level `enum`/`const` constraints on the Issuer AID field to restrict
  which AIDs may legitimately issue a given credential type (an authoring-time governance
  shortcut, layered on top of whichever of the two mechanisms above is chosen) is a practice-level
  technique, not a spec requirement.

## 9. Authority bootstrapping

- **Spec:** The Issuer, `i`, field "value MUST be the AID of the Issuer" (spec §"Issuer, `i`
  field", ~line 4462-4473); the Issuer AID's control authority is established via KERI-verifiable
  Key State (spec, top-level field table, ~line 402: "Autonomic Identifier whose control
  authority is established via KERI verifiable Key State"). Authority for a credential type is
  therefore bound to an AID, not to a name, org, or any other app-layer identifier. The KERI
  protocol spec establishes that this binding survives key compromise/weakening: "With key
  pre-rotation, control over the identifier can be re-established by rotating to a one-time use
  set of unexposed but pre-committed rotation keypairs... Authoritative control over the
  identifier persists in spite of the evolution of the Key state" (`keri-specification.md`
  §"Key rotation/pre-rotation", ~line 820-837, anchor "persists in spite of the evolution of the
  Key state").
- **Canon:** none specific — `ugard/docs/canon/credential-authority-model.md` covers *runtime*
  authority verification (ambient tiers, edges-authz-only) but not the authoring-time question of
  how a credential type bootstraps its issuing authority before the "real" authority is fully
  onboarded to KERI.
- **Practice note — CORRECTED FACT (source: owner `keri:chat` session, 2026-07-16, which mixed
  fact with invention on this specific point):** the session claimed that baking an authority AID
  into a credential type's schema/governance is risky because it "breaks on key rotation to a new
  AID." **This is wrong and must not be repeated as fact.** KERI AIDs are stable across key
  rotation — pre-rotation is precisely the mechanism that lets an AID's controlling keys change
  while the AID itself (and its accumulated KEL-anchored authority) persists unchanged (see the
  spec citation above). Baked-in authority AIDs do **not** break on ordinary key rotation. The
  real risk the practice patterns below are actually mitigating is authority *replacement* —
  a successor organization takes over the role, or an unrecoverable key compromise forces
  abandoning the AID entirely — which is a materially different (and rarer) event than routine
  rotation. With that correction applied, these ecosystem-practice patterns (still practice, not
  spec-normative) remain useful for the *replacement* scenario: issuer `enum`/`const` schema
  constraints (narrow which AIDs may issue, make swapping the allowed set an explicit schema
  change); governance-framework SADs that carry an explicit transition/succession plan; verifier
  dual-acceptance windows (accept both the outgoing and incoming authority AID for a bounded
  period during a handoff); and equivalence/supersession credentials (an ACDC issued by the new
  authority AID that formally attests succession from the old one).

---

## Step 3 verification — citation-resolution check

Every quoted anchor phrase above was checked against the spec file with
`grep -c -i '<phrase>' <spec>` and confirmed to resolve (count ≥ 1) before this brief was
finalized. Anchors and counts:

| Anchor phrase | File | Count |
|---|---|---|
| `ACDC Variants` | acdc-specification.md | 2 |
| `Targeted Attribute Section` | acdc-specification.md | 4 |
| `Untargeted ACDC` | acdc-specification.md | 13 |
| `Graduated Disclosure` | acdc-specification.md | 26 |
| `Compact Disclosure of a block` | acdc-specification.md | 1 |
| `Edge Section` | acdc-specification.md | 54 |
| `Issuer-To-Issuee` | acdc-specification.md | 4 |
| `Not-Issuer-To-Issuee` | acdc-specification.md | 1 |
| `Delegated-Issuer-To-Issuee` | acdc-specification.md | 1 |
| `TEL Registrars and TEL Observers` | acdc-specification.md | 1 |
| `Registry SAID Field` | acdc-specification.md | 1 |
| `Schema Versioning` | acdc-specification.md | 2 |
| `backward incompatible` | acdc-specification.md | 2 |
| `Extensibility` | acdc-specification.md | 7 |
| `permission-less ACDC type Registries` | acdc-specification.md | 1 |
| `Rule Section` | acdc-specification.md | 61 |
| `Ricardian contract` | acdc-specification.md | 5 |
| `Legal Language` | acdc-specification.md | 18 |
| `` Issuer, `i` field `` | acdc-specification.md | 5 |
| `persists in spite of the evolution of the Key state` | keri-specification.md | 1 |
| `Key rotation/pre-rotation` | keri-specification.md | 1 |

No dangling citations.
