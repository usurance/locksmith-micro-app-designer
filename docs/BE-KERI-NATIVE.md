# BE KERI NATIVE — The Prime Law of the Authentic Web

> **Status: LAW.** Stronger than a guiding principle. This is the **measuring stick** every design and implementation decision in this framework is checked against. When this Law conflicts with convenience, precedent, or a clever shortcut, **the Law wins.** The goal is not "an app that uses KERI" — it is to usher in a **new application framework built on KERI, the internet's trust-spanning layer** (Sam Smith's *Authentic Web*). A framework that is KERI-native *by construction* is the whole point; one that merely sits *near* KERI is a different, lesser thing.

## The Law

1. **For any concern that is KERI-*core*** — identity, authentication, authorization, verifiable data, integrity, state/history, trust, discovery, revocation, disclosure, serialization, delegation — **the solution MUST be expressed in KERI's own primitives.** Reinventing a native primitive in non-KERI clothing (a username, an ACL, a boolean rules-engine for authz, a UUID, a CA, a CRL, a bespoke wire format) is a **defect**, not a design choice.
2. **For any concern that is KERI-*adjacent*** — compute, content shape, transport, storage, UI, orchestration, infrastructure — **the solution MUST be KERI-*faithful*:** it must preserve verifiability, never re-centralize, never break content-addressing, and never disguise a native concern as adjacent.
3. **When a concern looks adjacent but is secretly core, pull it native.** (Authz looked like "a rules engine"; it is actually credentials + key-state. Pulled native.)

## The measuring stick (apply to every decision)

Ask, in order:

1. **Is this concern about *who*, *whether-authentic*, *who-may*, *what-is-true*, or *whom-to-trust*?** → It is **KERI-core**. There is a KERI primitive for it. Use it. If you're inventing a mechanism here, **stop — you are reinventing KERI.**
2. **Is this concern *computing over*, *presenting*, *transporting*, or *storing* KERI data?** → It is **KERI-adjacent**. Build it, but stay faithful: reference natives by SAID/AID, verify cryptographically, keep derived state rebuildable from the logs, don't re-centralize.
3. **Could a stranger with their own KERI stack still verify and participate?** → If not, you've coupled to an implementation. Fix it.

If a decision can't answer these cleanly, it isn't ready.

## What is KERI-native (concern → the primitive you MUST use)

| Concern | KERI-native primitive | NOT this |
|---|---|---|
| **Identity** | AID (self-certifying, KEL key-state) | username, account row, wallet-address, registry-DID |
| **Authentication** | signature + KEL verification | password, API key, OAuth token, session |
| **Authorization** (who-may-act) | credential possession (ACDC), **credential chains (edges + `I2I`/`NI2I`/`DI2I` operators)**, key-state, delegation (`dip`/`drt`), multisig threshold | ACL, role-in-a-DB, boolean rules engine, scopes |
| **Verifiable data / claims** | ACDC (issuer `i`, schema `s` SAID, attributes `a`, edges `e`, rules `r`) exchanged via IPEX | bare JSON, JWT, a REST payload |
| **Integrity / addressing** | SAID (self-addressing identifier) | UUID, separately-stored hash, DB primary key |
| **State / history / ordering** | KEL, TEL — append-only, witnessed | mutable DB rows, a blockchain, event-store sans KERI |
| **Trust / discovery** | OOBI, witnesses, watchers, mailboxes, percolated discovery | central registry, DNS-as-trust, CA/PKI |
| **Revocation / status** | TEL events | CRL, a `revoked` DB flag as the *source of truth* |
| **Confidentiality / disclosure** | graduated / selective disclosure, chain-link confidentiality | ad-hoc field redaction |
| **Serialization / wire** | CESR | bespoke binary, protobuf-for-KERI-data |
| **Delegation / cooperative control** | delegated AIDs, multisig groups | "admin" flags, shared secrets |

**The credential corollary (load-bearing):** *authorization is represented by credentials, not computed by expressions.* If a decision is complex, run it once and **issue an authorization credential**; thereafter every gate is just "present that credential." You never need an expression language for authz.

## What is KERI-adjacent (build it — but faithfully)

| Adjacent concern | Faithfulness rule |
|---|---|
| **App logic / compute** (premium calc, validation predicates, projection folds) | computes *over* native data; its *result* gets signed/issued (native). The compute is "just code" — keep it DSL-conformant where possible, sandboxed, deterministic. |
| **ACDC content shape** (attribute schemas, the flexible `r`/Ricardian block) | the *envelope* is native; design the *payload* freely, but content-address it (SAID) and reference schemas by SAID. UEL-in-`r` is *one* candidate for free-form contract logic — never for a concern KERI already expresses (authz, identity). |
| **CESR tooling** (parsers, pretty-printers) | CESR *is* native; tooling around it is adjacent but must round-trip faithfully. |
| **Transport / hosting** (HTTP vs TCP, schema servers, witness infra) | KERI is transport-agnostic; serve it however — trust is restored by SAID/signature, not by the host. |
| **Storage / caching** (the DynamoDBer, `db.schema`) | the *truth* is the log/credential; the store is a **cache**, always rebuildable. No protocol meaning leaks into the data layer. |
| **Orchestration / workflow** (sagas, process managers) | orchestrate *native exchanges*; the steps are exn/IPEX moves. |
| **Deployment / infra** (CDK, Lambda, the loader) | configures native runtimes; reconciliation is the infra's job; builds are SAID-locked. |
| **UI / rendering** | presentation of native state; never the source of truth. |

## The disguise trap

The dangerous failures are **core concerns wearing adjacent clothing**. Symptoms:
- A boolean expression / rules engine deciding *who may act* → that's **authz** → credentials/key-state.
- A computed key (`hash(payload…)`) deduplicating requests → KERI already gives every message a **SAID** → dedup on that.
- A "version string" identifying a build → use the **SAID** (+ KEL sequence + `supersedes` edge).
- A hosted "registry service" for discovery → that's **OOBI + percolation**, not a new server tier.
- A doc/format that "assumes our wallet" for *wire* behavior → wire behavior is **protocol**; keep it implementation-agnostic so any KERI stack participates.

When you catch one, **pull it native.** It almost always *simplifies* the system (you delete the reinvented mechanism and lean on the substrate).

## Living scorecard (audited 2026-06-28)

| Area | Verdict | Note |
|---|---|---|
| Identity / AID, signing | ✅ native | AIDs throughout; `open` ≠ anonymous (requester AID always recorded) |
| **Authorization** | ✅ **pulled native** | was drifting toward UEL predicates; corrected to structured KERI-native methods (`open`/`aid`/`allowlist`/`credential`, → chains) bound to `authz`/`credgate`/`verify` |
| Build identity / versioning | ✅ native | SAID lockfile + KEL-sn + `supersedes` edges; semver dropped |
| Schema hosting / discovery | ✅ faithful | data OOBI, SAID-verified; host untrusted; EGF = governance, not re-centralization |
| Registry / revoke (§6.1) | ✅ native | registries = TELs; revoke = TEL event |
| Storage / caching | ✅ faithful | `db.schema`/DynamoDBer are caches; logs are truth ([[feedback_no_concept_leak_into_storage]]) |
| **Idempotency** | ⚠️ **drifting** | template's `idempotency_key_expression: hash(payload…)` is a *computed* key; the native move is dedup on the **request/exn SAID**. Prefer message-SAID; treat hashed keys as a fallback. |
| **Template "assumes Locksmith"** (data-model spec l.59-61) | ⚠️ **partial** | fine for *rendering*; but the *wire* behavior it describes is protocol — keep the format implementation-agnostic so any KERI stack participates (Principle 5). |
| **`r` / Ricardian content** | ⏳ open | UEL is *one* candidate; ensure nothing that is actually authz/identity/obligation-KERI-can-express gets buried in free-form `r` logic. |
| App-logic predicates / state guards | ✅ faithful (watch) | UEL over derived `state` is fine **iff** state is always rebuildable from witnessed KEL/TEL — never a source of truth. |

**Re-run this scorecard whenever a new mechanism is introduced.** A ⚠️ is a debt to pull native; an entry that can't be made native or faithful is a design smell to escalate.
