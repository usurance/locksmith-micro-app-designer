# Shape & Disclosure Reference

Three decisions that fix a credential type's outer shape and what it reveals to a
verifier who doesn't hold it: targeted vs untargeted, public vs private, and which
disclosure mode the schema is built to support. Decide these before touching
attribute fields — they constrain how the Attribute section, `u` field, and schema
composition operators are shaped.

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

## Public vs private (`u`)

**When:** Does the credential's schema, once known alongside its SAID, let someone
correlate or reverse-engineer attribute values without ever holding a disclosed copy
(rainbow-table risk on a small/guessable value space)? Does a party need to commit to
the credential's SAID (e.g., anchor it, reference it in another ACDC) *before* the
holder is ready to disclose its contents?

**Default:** Public (no `u` field). Most attestations aren't confidential — treat
commitment to the SAID as a normal, non-leaking correlation point.

**Worked example:** A carrier operating-license credential is **public** — the
license number and jurisdiction are public record, and a regulator or reinsurer
routinely cites the SAID before ever seeing the full credential. A homeowner's
pre-bind personal-risk-attributes credential (prior-loss history, exact address,
credit-based insurance score) is **private** — the underwriter must be able to
commit to having received the SAID before the homeowner is willing to disclose the
underlying attributes, and the attribute value space (a handful of loss-history
categories, a small set of ZIP+4s) is narrow enough that schema + SAID alone would
otherwise leak which values are true.

**Mechanics:** ACDC Variants, top-level `u` (UUID) field, `keri:acdc`
references/sections.md; blinding/rainbow-table rationale in the same section.

## Disclosure-mode selection

**When:** Once shape and blinding are set, does the schema need to support a holder
revealing less than the full credential — one attribute among many, or a commitment
in advance of a later contractual reveal?

**Default:** Full disclosure. Build for selective or partial disclosure only when a
specific holder workflow requires revealing less than everything.

**Worked example:** A claims-adjuster authority credential is disclosed **fully** —
the verifying system needs the whole attribute block to authorize a claims action,
so there's no reason to withhold any part of it. A homeowner's underwriting-attribute
credential (address, prior losses, credit-based score, occupancy type) uses
**selective disclosure** via the Aggregate section — the holder reveals only
`occupancy type` to a marketing partner while withholding prior-loss history and
credit score. A pre-bind rate quote reveals only its SAID at the offer stage
(**partial/metadata disclosure**, "disclose enough to enable more disclosure") and
the full attribute block only once the applicant accepts and the chain-link
confidentiality window opens for contractual disclosure to the carrier's
underwriting system.

**Mechanics:** Graduated Disclosure family (Compact, Metadata, Partial, Nested
Partial, Full, Selective, Bulk-issued Instance), `keri:acdc`
references/sections.md; Selective Disclosure via the top-level Aggregate section
(`A` field); Compact Disclosure's `oneOf` schema-composition requirement; envelope
shape in `micro-app-template-gen` ten-step-process §Step 3.

## Choosing shape & disclosure

```
Is there a specific subject AID? ── yes ─→ targeted   ── no ─→ untargeted
Must you commit before revealing, or does schema+SAID leak values? ── yes ─→ private (`u`) ── no ─→ public
Will a holder reveal a subset of attributes independently? ── yes ─→ selective disclosure ── no ─→ full
```
