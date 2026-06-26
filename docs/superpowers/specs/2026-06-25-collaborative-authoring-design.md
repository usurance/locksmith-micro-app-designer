# Collaborative Multi-Party Authoring over KERI — Design Spec

| | |
|---|---|
| Status | Draft for review |
| Date | 2026-06-25 |
| Builds on | `keri_serviceaid` (in `~/code/keripy/keri_serviceaid/`) + `concierge-api` (`2026-06-23-concierge-api-local-runtime-design.md`) |
| Lineage | `micro-app-runtime` (2026-05-15, spec-only/abandoned) → `keri_serviceaid` → **concierge** (current) |

## 1. Goal & organizing principle

Let multiple parties **collaboratively author one composed artifact** over KERI, with each party's contribution cryptographically attributed and the whole assembled into a single verifiable, versioned **manifest** — driven from a CLI, verified by an integration test. The insurance product (the `ipd` data-model files) is the **first scenario**, not the system.

**Organizing principle (load-bearing):**

> **One micro-app = one role = one AID = one Service-AID** — one gated function, one signed result. **Cross-AID composition is the *ecosystem* layer** (what the ecosystem viewer surfaces), not something inside a single micro-app.

Therefore: each **contributor** is its own Service-AID; the **coordinator** is another Service-AID; their collaboration is **cross-AID IPEX**; the **manifest** is the ecosystem-level composition.

## 2. Scope

**In scope (the slice):**
- **Fragment issuance** — a contributor Service-AID issues a *fragment ACDC* (content SAID-referenced) for the files it authored ("I issue / I hold").
- **IPEX collaboration** — contributors grant fragments to the coordinator; the coordinator admits them ("I respond to").
- **Manifest assembly + validate** — the coordinator composes admitted fragments into a *manifest ACDC* via edges, and a structural `validate` step checks the whole ("Lineage").
- **Publish/Sandbox TEL lifecycle** on the manifest.
- **Two CLIs** — `said` (saidify) and `micro-app` (the authoring verbs) — thin over a Qt-free authoring library.
- **A bash multi-party integration test** as the acceptance criterion, against local demo witnesses.

**Out of scope (deferred, named):**
- Runtime execution of the other micro-app primitives (workflows, aggregates, projections, rules) — authorable in the designer; runtime later.
- The **designer→runtime bridge** (resolving a template's *symbolic* edges into live ACDC SAIDs) — real, unbuilt work; explicitly deferred.
- Deep cross-fragment / DAG attribute validation (the `ipd` normalization phase) — `validate` here is structural + authenticity only.
- Production HOA / serverless deployment; rewriting the designer plugin.
- `ipd` changes beyond *optionally* SAD-stamping its output via keripy's saidify.

## 3. Architecture & layering

```
┌ Domain CLIs (N, pluggable, KERI-unaware) ──────────────────────────┐
│  ipd (rating/product subdomain) · future subdomain CLIs            │
│  → produce FILES (optionally SAD-stamped via keripy Saider)        │
└────────────────────────────────────────────────────────────────────┘
        │ files
        ▼
┌ SAD / canon (the shared root = keripy) ─────────────────────────────┐
│  coring.Saider.saidify(...)  — used IDENTICALLY by designer,        │
│  runtime, and CLIs. No separate shared lib needed; keripy IS it.    │
└────────────────────────────────────────────────────────────────────┘
        │ SADs
        ▼
┌ Runtime substrate (BUILT) — keri_serviceaid ───────────────────────┐
│  ServiceAid · @svc.command · Request/Reply(.acdc edges,rules) ·     │
│  IpexGrantIssuer · LocalRuntime/TestRuntime · authz/credgate        │
│  ONE ServiceAid per role/AID.                                       │
└────────────────────────────────────────────────────────────────────┘
        │ reused by
        ▼
┌ concierge-api — the Qt-free shared layer (BUILT core) ─────────────┐
│  BindingController · RuntimePumpDoer  (Qt-free; pages/ = stub)      │
│  + NEW: authoring/  (fragment build, manifest assemble, validate)  │
│  + NEW: cli/  → `said`, `micro-app`  (thin; import authoring)       │
│  Consumed by BOTH the CLIs AND a future concierge plugin UI.        │
└────────────────────────────────────────────────────────────────────┘
        │ driven by
        ▼
┌ Integration test (bash, hermetic) ─────────────────────────────────┐
│  Multiple Service-AIDs (contributors + coordinator), local demo    │
│  witnesses (config-swappable to the federation), drives the CLIs.  │
│  INSURANCE scenario lives here only.                               │
└────────────────────────────────────────────────────────────────────┘
```

**Homes:** the new `authoring` module + the CLIs live in **`concierge-api`** (`src/concierge_api_local/authoring/` + `cli/`). Reuse `keri_serviceaid` (in keripy). The designer is **not** modified. This spec doc lives in the designer repo's `docs/superpowers/specs/` alongside the concierge spec (the curated home for runtime design), per existing convention.

## 4. Roles as Service-AIDs

Each role is one `ServiceAid` (one AID, one TEL), wired by a `LocalRuntime` (and one `BindingController` when hosted in the wallet). A party playing two roles runs **two** Service-AIDs — the principle, not a refactor.

| Role | Service-AID | `@svc.command`(s) | Gate (authz/credgate) |
|---|---|---|---|
| Contributor | one per contributor | `issue_fragment` → `Reply.acdc(...)` | optional "authorized-to-contribute" cred |
| Coordinator | one | `admit_fragment` (reaction to IPEX grant) · `assemble_manifest` → `Reply.acdc(edges=…)` · `publish_manifest` (TEL transition, §7) | optional "coordinator" cred |

The contributor's `issue_fragment` may invoke a **domain command** — e.g. it runs `ipd` (Excel→files) as the "I do" handler, then SAD-stamps and issues. `ipd` stays a leaf tool the command shells/calls.

## 5. Data model

All SAIDs via keripy `coring.Saider.saidify` (Blake3-256) — the shared root.

**Fragment ACDC** (issued by a contributor):
```
{ v, d:<SAID>, i:<contributor AID>, ri:<contributor TEL>,
  s:<fragment-TYPE schema SAID = the concept id>,
  a: { contentSaid:<SAID of the canonical NDJSON blob>, label, kind, role },
  e?: { prior:{ n:<prior fragment SAID>, s:<schema SAID> } },   // lineage
  r?: <rules> }
```
Content is **referenced, not inlined** (scales to 10⁶ rows; the blob travels with the IPEX grant / shared store).

**Manifest ACDC** (issued by the coordinator) — composes fragments via the `e` section. *Validated against the substrate:* `IpexGrantIssuer._issue_grant` builds the `e` block from `Reply.edges` where **each edge must be `{cred_said, schema_said}`** and saidifies it — so this shape is buildable **today, no `keri_serviceaid` change**:
```
Reply.acdc(
  recipient=<regulator or self>,
  attributes={ coordinate:<scenario id, e.g. lob/jurisdiction/version>, action },
  edges={ "coverages":{cred_said:<SAID>, schema_said:<SAID>},
          "rating_tables":{...}, … ,
          "supersedes":{cred_said:<prior manifest SAID>, schema_said:<manifest schema SAID>} },
  rules=<optional> )
```
The manifest **is** the whole product: content-addressed by its SAID; verifying it = every fragment edge resolves + each fragment ACDC verifies.

**Schema SAIDs are the concept identifiers** — a "rating-tables fragment" has one schema SAID everywhere (cross-system concept identity). Scenario supplies the schemas; the library is schema-agnostic.

**Designer-compatibility (cheap, no bridge built):** a fragment maps to a designer `credentials.exports[]` entry; the manifest to an export whose `envelope.edges` capture composition. We choose schema shapes that *fit* those primitives so a future bridge is natural — but the symbolic-edge→live-SAID **resolution layer is deferred** (it does not exist in either codebase today).

**Privacy:** fragments may carry the `u` salt to blind proprietary content until selective disclosure; default for the test = in-the-clear.

## 6. The shared authoring library (`concierge_api_local/authoring/`)

Qt-free, reused by the CLIs and a future concierge plugin UI. Pure functions over `keri_serviceaid` + keripy:
- `sad_of(path) -> (canonical_bytes, said)` — wrap keripy saidify (JSON: embed `d`; NDJSON: SAID over canonical bytes, recorded externally).
- `fragment_reply(content_said, schema_said, meta, prior?) -> Reply` — build the contributor's issuance `Reply`.
- `manifest_edges(fragments) -> dict` — build the `{name:{cred_said,schema_said}}` edge map (incl. `supersedes`).
- `manifest_reply(coordinate, action, edges) -> Reply`.
- `validate(manifest_said, store) -> Report` — structural + authenticity: every edge resolves, each fragment ACDC verifies, no duplicate fragment types (collision check). (Deep attribute/DAG validation deferred.)
- `lifecycle` helpers for §7.

No reusable logic lives in the CLIs — only argparse/click, stdout, exit codes.

## 7. Publish / Sandbox TEL lifecycle (the one real gap)

`keri_serviceaid`'s `Reply` does a single `Registry.issue`; it has no state-transition path. Design:
- The coordinator's `assemble_manifest` issues the manifest into a **Sandbox** registry (a normal issued credential; revocable/purgeable).
- A separate **`publish_manifest`** command transitions to **Published** by issuing the manifest into a **dedicated "published" registry whose entries are never revoked** (the v1 approach — simplest, and immutability is enforced by policy: the published registry has no revoke path). **Published = immutable + never revoked; Sandbox = revocable/purgeable.** *(Alternative — an immutable in-TEL state flag — is deferred; not v1.)*
- This requires one small `keri_serviceaid` extension: a reply path that can target a specific registry and, for Sandbox, call `Registry.revoke`. This is the **first substrate change** needed (the only one beyond what's built).

## 8. CLIs (thin)

- **`said`** — `said saidify <file> [--ndjson]` → prints/embeds the SAID (wraps keripy saidify). Handy for ad-hoc + the test.
- **`micro-app`** — verbs over the authoring lib + `keri_serviceaid`:
  `party init <name>` (incept a Service-AID + TEL, resolve witness OOBIs) · `fragment issue --content <file> --schema <said> --as <party>` · `grant --acdc <said> --to <coordinator>` · `admit --as <coordinator>` · `assemble --coordinate <id> --fragments <…> --as <coordinator>` · `validate --manifest <said>` · `publish --manifest <said>` · `list`/`verify`.

Witness/OOBI config is a **parameter**, default **local demo witnesses** (they carry mailboxes for IPEX), swappable to the **publisher's federated 5×5** with no flow change.

## 9. The collaboration flow (cross-AID IPEX)

1. `party init` for each contributor + the coordinator (demo witnesses).
2. Each contributor: run its domain command (e.g. `ipd` → files) → `said` → `fragment issue` (issues a fragment ACDC into its TEL) → `grant` to the coordinator.
3. Coordinator: `admit` each grant (its `MailboxDirector` + `Verifier` admit the presentations; polling handled here — the only async friction).
4. Coordinator: `assemble` → issues the manifest ACDC (`Reply.acdc(edges=…)`) referencing the admitted fragment SAIDs.
5. `validate` the manifest; on success `publish` (Sandbox→Published).
6. (Optional) coordinator `grant`s the published manifest to a regulator Service-AID, who admits — the "filing."

## 10. The integration test (acceptance criterion)

A **re-runnable bash script** (`tests/integration/collaborative_authoring.sh`) that:
- Spins up local demo witnesses; runs the §9 sequence via the three CLIs (`ipd`, `said`, `micro-app`) for an insurance scenario — e.g. **product-designer** issues `coverages` + `metadata` fragments, **actuary** issues `rating-tables`, **rules-author** issues `derivation-logic`; **carrier-coordinator** assembles + validates + publishes the manifest; **regulator** admits the filing.
- Asserts via exit codes / `grep`: each fragment ACDC issued + granted + admitted; the manifest's edges reference exactly those fragment SAIDs; `validate` passes; the published manifest verifies and the regulator admitted it.
- Hermetic (temp keystores per party; cleaned up). Insurance specifics live **only** here.

## 11. Testing strategy

- **Bash integration script (primary):** the §10 end-to-end multi-party flow — the "get out of the code, verify via CLI" oracle.
- **`pytest` + `keri_serviceaid.TestRuntime` (units):** each Service-AID's command function (`issue_fragment`, `assemble_manifest`, `validate`) in isolation, no witnesses; plus the authoring lib's pure functions (SAID determinism, edge-map construction, `validate` collision detection).
- I (Claude) also drive the CLIs live during dev for fast verification.

## 12. Risks & status

| Item | Status |
|---|---|
| Edge pass-through for the manifest | **Resolved** — supported today via `Reply.edges={name:{cred_said,schema_said}}` (`issue.py:108-116`). |
| Publish/Sandbox TEL lifecycle | **Design item (§7)** — needs a small `keri_serviceaid` state-transition extension; first substrate change. |
| Multi-role multiplicity | **Non-issue** — one Service-AID per role; a dual-role party runs two; "support N controllers" only. |
| Qt entanglement in concierge-api | **None** — core is Qt-free; `pages/` is an empty stub. |
| Designer↔runtime bridge | **Deferred** — symbolic-edge→live-SAID resolution is real, unbuilt work; we only keep schemas designer-representable. |
| Witness friction (async IPEX poll) | **Contained** — in the coordinator's admit step; demo witnesses by default. |

## 13. Out of scope (restated)

Other-primitive runtime, the designer→runtime bridge, deep DAG validation, production HOA/serverless, designer-plugin rewrite. These consume or extend this work later.
