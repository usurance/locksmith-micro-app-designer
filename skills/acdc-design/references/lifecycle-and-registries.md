# Lifecycle & Registries Reference

Two decisions that fix how a credential type behaves *after* issuance: whether
it needs a revocation/state registry at all, and how the type itself evolves
over time without ever mutating an issued schema. Decide these once the
credential's shape (targeted/public/disclosure) and edges are settled — they
govern what happens next, not what the credential looks like on day one.

## Registry/TEL pattern

**When:** Does this credential ever change state after issuance — suspended,
revoked, expired — or is it issue-once with nothing tracked afterward? Any
lifecycle beyond issue-once needs a registry. If it needs one: backed
(witnessed TEL, published by a registrar operating under the issuer's KEL) or
backerless? One registry per credential type, or one per issuer shared across
everything that issuer issues? And is the registry's own event stream — who
issued or revoked what, and when — itself a correlation risk that argues for
blinded state?

**Default:** One backed registry per issuer, un-blinded, shared across every
credential type that issuer issues — unless a privacy requirement forces
blinded state. Map each lifecycle transition to one of the three TEL
primitives (`issue`/`update`/`revoke`) per
`micro-app-template-gen` ten-step-process §Step 3; the state-machine names
layered on top (`pending`, `active`, `suspended`, `revoked`, `superseded`, …)
are free-form, but every transition must ground out in one of those three.

**Worked example:** A carrier's operating license and its agent-appointment
credentials both revoke through the same backed TEL registry maintained by
the carrier — one registrar per issuer, not a separate registry per
credential type, because both types share the same issuer and neither needs
independent witnessing. A homeowner's private underwriting-attribute
credential (prior-loss history, credit-based score) is different: even the
plain fact that *a* revocation or update event occurred on a given date, tied
to a given holder, could let a correlator infer that the homeowner's risk
profile changed — so that registry runs blinded-state, trading queryable
transparency for the privacy the attributes themselves already demanded.

**Mechanics:** Registry SAID field (`rd`), TEL Registrars and TEL Observers,
`keri:acdc` references/sections.md; lifecycle-transition-to-TEL-primitive
mapping in `micro-app-template-gen` ten-step-process §Step 3.

## Versioning & migration

A schema is immutable: the `$id` SAID *is* the version, `version` semver is
informative. Any change is a **new SAID = a new type** (type-is-schema). You never
edit a schema in place. Backward-compatible additions → bump minor, new SAID, verifiers
may accept both. Backward-incompatible change → bump **major**; holders migrate by
**re-issuance** under the new schema (issue new, revoke old — the carrier design's
`issued → superseded` pattern). Edges that point at a changed type either accept both
majors via `oneOf`, or the pointed-to credentials are revoked+reissued.

**Worked example:** A carrier-license schema adds an optional
`multi_state_endorsement` attribute — backward-compatible, so it ships as a
minor bump under a new SAID, and verifiers written against the prior SAID
keep working unmodified while newer verifiers accept both. Later, the same
schema drops a required `license_number` format constraint in favor of a
structured `{state, number}` object — no old instance can satisfy the new
shape, so it's a major bump: every carrier holding the old license gets
re-issued under the new schema SAID, and the old credential is revoked
(`issued → superseded`). Any agent-appointment credential whose edge points at
the carrier license either widens its edge schema to accept both license
majors via `oneOf`, or those appointments are themselves revoked and
reissued against the new license SAID.

**Mechanics:** Schema `$id`/SAID as normative version determinant, `version`
semver field as informative-only, backward-(in)compatibility rule, and
Edge/node schema-version interplay — spec §"Schema Versioning"; `keri:acdc`
for SAID mechanics; `naming-conventions.md` `superseded` lifecycle state.

## Choosing lifecycle & registry

```markdown
Any state after issuance (revoke/suspend/expire)? ── no ─→ no registry needed
                                                  └─ yes ─→ backed TEL, one per issuer
Registry event stream itself a correlation risk? ─→ blinded-state TEL
Schema change: attributes added only? ─→ minor bump, new SAID, dual-accept
Schema change: breaks old instances? ─→ major bump + re-issue holders
```
