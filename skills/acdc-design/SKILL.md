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

Ground truth is the normative ACDC specification — accessed via the `keri:acdc` /
`keri:spec` skills (the canonical source is the IETF/ToIP ACDC specification).
`keri:acdc`/`keri:spec` are distilled convenience; `keri:chat` answers *practice*
questions only. Verify any claim against the spec before it becomes guidance; label
practice patterns as practice. On conflict, the spec wins.

## Serialization is elsewhere

Once decisions are made, author the schema file per
`micro-app-template-gen/references/ten-step-process.md` §Step 3 (envelope shape,
`oneOf` compact form) and SAIDify with `scripts/saidify_acdc_schema.py`. This skill
decides; that step serializes.
