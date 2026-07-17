# Governance & Bootstrapping Reference

Three decisions that fix who is allowed to issue a credential type, how that
rule is enforced, and what to do when the "real" authority isn't on KERI yet.
Decide these after shape/disclosure and edges are settled, alongside
lifecycle — governance is a cross-cutting concern that touches the schema
(Issuer field, Rule section), the ecosystem (EGF registries), and, for a
greenfield ecosystem like ugard's, an explicit bootstrap plan. This file
carries the most **practice-level** (non-spec-normative) material in the
`acdc-design` reference set — every pattern below that isn't a direct spec
citation is flagged as practice, not protocol requirement.

## EGF adoption of schema SAIDs

**When:** Is this credential type meant to become a recognized standard
across multiple issuers or ecosystems — the thing everyone means when they
say "a carrier-license credential" — rather than a private, single-issuer
type?

**Default:** Adoption is emergent, not authored: a schema becomes "the
standard" when an Ecosystem Governance Framework (EGF) pins its SAID in a
well-known accepted-set, and multiple ecosystems voting-by-usage to converge
on the same SAID is how a de facto standard forms across ecosystems, while
one EGF governs acceptance within its own.

*(Practice-level: "adoption is emergent" / "vote-by-usage" is an
interpretive framing of how convergence tends to happen, not a spec
requirement — the spec-grounded part is narrower: EGF registries are
permission-less and ecosystem-tailored, per the Mechanics citation below.)*

The authoring-side action is
narrow: publish the SAID and record it where the EGF's accepted-set will
reference it. Building or operating the publication/discovery mechanism
itself is **out of scope** for credential-type design — that's ugard's
`egf-publisher-registry` backlog item, a separate service.

**Worked example:** A carrier-license schema, once designed and
SAID-derived, is published so that any state DOI's EGF (once DOIs are
KERI-native) or an interim ecosystem EGF can pin that SAID in its
accepted-issuer-types list. If two different regional ecosystems both
independently converge on referencing the same carrier-license SAID rather
than minting their own variants, that convergence — not any single
authoring act — is what makes the schema "the standard" carrier-license type.

**Mechanics:** spec §"Extensibility" (permission-less ACDC type registries —
schema SAID comparison against a well-known publication/registry is the
enforcement mechanism, and the spec deliberately does not mandate a specific
registry mechanism or timing); `keri:acdc` references/sections.md. The
publisher/registry *service* itself is out of scope here — see the
`egf-publisher-registry` backlog item.

## Schema-encoded vs external governance

**When:** Should "who may legitimately issue this credential type" be
enforced automatically and immutably by the schema itself, or left to an
EGF-level registry/authorization mechanism that can evolve without minting a
new schema SAID?

**Default:** **External governance** — an open schema (issuer field
unconstrained) with authorization decided in the EGF. This matches vLEI
practice and is the right default because it keeps authorization flexible:
adding an authorized issuer under external governance is an EGF update, not
a new type. Bake governance into the schema only for **closed, stable,
single-authority** types, where the authority set is not expected to change.

*(Practice-level: this is a design-posture recommendation built on top of
spec mechanisms, not a spec requirement — the spec permits either approach
and does not prefer one.)*

You *can* encode authority directly in the schema, three ways: an
`enum`/`const` constraint on the Issuer `i` field; a required authorization
edge that pins an authority-credential's schema SAID and uses the `I2I`
operator; or a required Rule-section (`r` field) commitment to a
governance-framework SAID (a Ricardian-contract-style legal-language
anchor). The trade-off is the same in all three: automated,
machine-checkable, immutable enforcement **versus** rigidity — adding an
authorized issuer means a new schema SAID, i.e. a new type — and lock-in to
whatever authority set existed at design time.

**Worked example:** A carrier's internal role credential (e.g.,
"licensed claims adjuster employed by Carrier X") is closed, stable, and
single-authority — Carrier X is the only issuer that will ever exist for
this exact type, so baking `enum: [carrier_X_AID]` onto the issuer field is
reasonable. A cross-carrier agent-appointment credential type, by contrast,
is expected to be issued by dozens of independent carriers, with new
carriers entering the market over time — external governance is the right
call there: the EGF's accepted-issuer list grows as carriers are
onboarded, with no new schema SAID required per carrier.

**Mechanics:** Rule Section (`r` field, Ricardian-contract "Legal Language")
for schema-encoded governance-framework commitments; Issuer `i` field for
`enum`/`const` constraints; Edge Section `I2I` operator for an authorization
edge pinning an authority-credential schema SAID — `keri:acdc`
references/sections.md; `credential-authority-model.md` (ugard canon) for
how an authorization edge is verified at runtime (edges are authz-only, per
`edges-and-provenance.md` in this reference set).

## Authority bootstrapping ("open now, closed later")

**When:** Does the credential type's "real," eventual issuing authority
(e.g., a state Department of Insurance) not yet exist on KERI, while the
credential type itself must ship now?

**Default:** Open the schema now, constrain later, per the pattern below —
verbatim from the design brief because the sequencing and the corrected
spec fact both matter and neither should be paraphrased loosely.

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

*(Practice-level: this whole bootstrap sequence — placeholder issuer,
governance-framework transition plan, dual-acceptance window, major-version
close — is an ecosystem practice pattern for ugard's specific situation, not
a spec requirement. The spec only requires that the Issuer AID's authority be
KERI-verifiable Key State; it says nothing about phased rollout.)*

**Worked example:** The carrier-license design is the concrete
instance of this pattern: v1 ships with the issuer field open, a carrier
self-issues its own license as an internal placeholder authority, and a
governance-framework SAD records that the target authority is the relevant
state DOI once that DOI is KERI-native — with a declared transition
(re-issuance under the DOI's AID, verifier dual-acceptance window) rather
than a promise to edit the existing schema in place.

**Couple to the EGF-resolver work:** the EGF doc model (the SAID-native EGF
document + resolver work tracked against `keri_serviceaid`) should carry
bootstrap-phase fields directly — current (placeholder) issuing AID, target
authority, and expected transition — so that a verifier resolving an EGF
document during the bootstrap window can see the phase explicitly rather
than inferring it from schema version alone. This is a data-model coupling
note, not a service design; the EGF publisher/registry *service* remains out
of scope for this skill.

**Mechanics:** Issuer `i` field (spec §"Issuer, `i` field") and KERI
Key-State/pre-rotation guarantees (`keri:spec`) for why AIDs are stable across key rotation
(the corrected fact above, restated: pre-rotation is the mechanism, not a
liability); `lifecycle-and-registries.md` (this reference set) for the
re-issuance / `issued → superseded` mechanics used at transition; the
carrier-license design for the concrete placeholder-issuer worked example;
the EGF-resolver backlog note for where bootstrap-phase fields belong in the
EGF doc model.

## Choosing governance

```markdown
Is the authority set closed, stable, single? ── yes ─→ may bake in (enum/const/edge/rules)
                                              └─ no  ─→ external governance (open schema + EGF)
Do the real authorities exist on KERI yet? ── no ─→ bootstrap: open v1 + placeholder + transition plan
Standardizing a type across parties? ─→ publish SAID; EGF pins it in the accepted-set
```
