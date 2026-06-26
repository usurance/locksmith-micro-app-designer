# Data-Driven Micro-App Build — Template → Service-AID Loader — Design Spec

| | |
|---|---|
| Status | Draft for review |
| Date | 2026-06-25 |
| Builds on | `keri_serviceaid` (`~/code/keripy/keri_serviceaid/`) + `concierge-api` (`2026-06-23-concierge-api-local-runtime-design.md`) |
| Lineage | `micro-app-runtime` (spec-only/abandoned) → `keri_serviceaid` → **concierge** (current) |

## 1. Goal & organizing principles

Make **app-building data-driven**: an AI (or a person) authors a declarative **micro-app template**; a **loader** turns that template + deploy-time data into a configured, running **Service-AID**. The author writes *configuration*, never KERI plumbing — the substrate is already built and working. That is the whole point of the micro-app paradigm.

Two principles that resolve prior confusion:

1. **Template ⊥ Runtime.** The **micro-app template** is the *data/DSL* (authored via `/micro-app-template-gen`). The **Service-AID/concierge** is the *runtime* that executes it. The **loader** is the bridge — and it is *central*, not deferrable.
2. **One micro-app = one role = one AID = one Service-AID** (one gated function, one signed result). **Cross-AID composition is the *ecosystem* layer** (the ecosystem viewer), not something inside one micro-app.

The Risk-Profiler / Premium-Calculation **is a micro-app**: it gets a template; the loader configures a Service-AID; the `ipd` product data is what that micro-app's compute consumes.

## 2. Scope

**In scope:**
- **The loader** — `load(template, deploy_data) -> ServiceAid`: a *template-aware* layer that instantiates a `keri_serviceaid` `ServiceAid` (commands + providers) from a template + deploy manifest. (This subsumes the earlier "designer→runtime bridge": resolving template symbolic refs → live SAIDs *is* the loader's job.)
- **Per-compute credential gate** — each command's optional `requires_credential` (the ACDC a requester must present), data-driven.
- **Two substrate items** (the only `keri_serviceaid` changes): the **Publish/Sandbox TEL lifecycle** (§6.1) and **completing the credential-presentation gate** (§6.2).
- **Data production (collaborative authoring)** — `ipd` → files → fragment ACDCs → IPEX → a coordinator-assembled **manifest ACDC** (§5). The manifest SAID is a deploy-data input the micro-app consumes.
- **CLIs** — `said` (saidify) and `micro-app` (drive the loader + the authoring flow) — thin over the Qt-free authoring/loader library.
- **A bash multi-party integration test** as the acceptance criterion (§8), against local demo witnesses (swappable to the federation).

**Out of scope (deferred, named):**
- Runtime execution of the *other* micro-app primitives (aggregates/projections/workflows beyond what a single command needs).
- Deep cross-fragment / DAG attribute validation (the `ipd` normalization phase).
- Production HOA / serverless beyond defining the deploy-manifest seam.
- **Rewriting the designer plugin** — we *consume* its template output; we don't change the Qt editor.

## 3. Architecture & layering

```
┌ Domain CLIs (N, pluggable, KERI-unaware) ─ ipd + future subdomain CLIs → FILES ┐
└────────────────────────────────────────────────────────────────────────────────┘
        │ files                                   ┌ Template (the DSL) ──────────────┐
        ▼                                         │ authored via /micro-app-template │
┌ Data production (collaborative authoring, §5) ─┐│ -gen; LIVES IN ~/code/ugard       │
│ fragment ACDCs (per contributor Service-AID)  ││ (built/deployed there)            │
│ → IPEX → coordinator assembles MANIFEST ACDC  │└───────────────────────────────────┘
└────────────────────────────────────────────────┘        │ template
        │ manifest SAID (a deploy-data input)               ▼
        └───────────────────────────────►┌ LOADER (concierge-api, §4) ───────────────┐
        ┌ Deploy manifest (live data) ──►│ load(template, deploy_data) -> ServiceAid  │
        │ AIDs · schema SAIDs · ARNs ·   │ template-AWARE layer; keri_serviceaid core │
        │ OOBIs · gating cred SAIDs ·    │ stays template-AGNOSTIC                     │
        │ the manifest SAID              └────────────────────────────────────────────┘
        └──────────────────────────────────────────│ instantiates
                                                    ▼
┌ keri_serviceaid (BUILT, agnostic core) ─ ServiceAid · @svc.command · Reply.acdc(edges) ┐
│ providers: authz/credgate/verify/issue/deliver/idempotency/resolve · LocalRuntime     │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                                    │ hosted by
                                                    ▼
   Local: concierge-api BindingController/RuntimePumpDoer (vault)   |   Cloud: CDK + Lambda
```

**Homes:** the **loader + authoring lib + CLIs** live in **`concierge-api`** (`src/concierge_api_local/{loader,authoring}/` + `cli/`); reuse `keri_serviceaid`; the **template** lives in **`~/code/ugard`**; this spec lives in the designer repo's `docs/superpowers/specs/` (curated home for runtime design). `keri_serviceaid` stays **template-agnostic** (its own design decision); the loader is the template-aware sugar on top.

## 4. The loader (the core)

**Contract:** `load(template: dict, deploy: DeployManifest) -> ServiceAid` — read a static template + a deploy manifest, resolve symbolic refs to live values, and build a configured `ServiceAid` (its `@svc.command`s + providers) with no handwritten plumbing.

**The mapping (data-driven app build):**

| Template field (DSL) | Drives in `keri_serviceaid` | Deploy manifest fills |
|---|---|---|
| `header.role` + identity | the ServiceAid's role/AID | the incepted **AID** |
| `commands[]` | a `@svc.command(route, payload_schema, issues, requires_credential, fn)` registration | — |
| `commands[].compute` (abstract capability ref) | the command's `fn` | an **ARN** (cloud Lambda) or a **Python entry-point** (local) |
| `commands[].requires_credential?` (the gate, §4.1) | `requires_credential` → `credgate`/`verify` | required **schema SAID** + issuer/attribute constraints |
| `credentials.exports[]` | `issues` + `Reply.acdc(edges, rules)` | issued **schema SAID** + edge **SAIDs** |
| `credentials.imports[]` | inputs the compute expects | their **schema SAIDs** |
| `rules[]` | reply `rules` / preconditions | — |
| witness/OOBI | `LocalRuntime` / witness config | demo or **federation OOBIs** |
| product-data ref (`ipd`/manifest) | data the compute `fn` reads | the **manifest SAID** / content SADs |

**Decisions:**
- **A — Resolution time:** **deploy/startup.** Template is static; the deploy manifest injects live data; the loader builds the `ServiceAid` (local: at vault startup via `BindingController`; cloud: at CDK deploy). The **role AID is bound just before this** (§4.2): cloud auto-incepts at deploy; local binds via the one-time first-open setup.
- **B — Compute reference:** the template names compute **abstractly** (capability id + payload/issue schemas); the deploy manifest **binds** it to an **ARN** (cloud) or a **Python entry-point** (local) — the same template runs in either runtime.
- **C — Loader home:** a **template-aware layer in `concierge-api`**; `keri_serviceaid` stays template-agnostic.
- **D — Deploy manifest:** a small declarative artifact (role AID, schema SAIDs, compute ARNs/entry-points, OOBIs, gating cred SAIDs, the product manifest SAID) merged with the template by the loader. CDK plugs in here for cloud.

### 4.1 Per-compute credential gate — who may *ask*

Each command may declare an optional `requires_credential` (about the **requester**; §4.2 is about the micro-app's *own* identity):
```
requires_credential: {
  schema_said:            <ACDC type the requester must present>,   # deploy-filled
  issuer?:                <acceptable issuer AID / role>,           # optional constraint
  attribute_constraints?: { <attr>: <required value/predicate> },  # e.g. status=active, amount>=X
}
```
Enforcement (via `credgate`/`verify`): the requester **presents** the ACDC via IPEX/exn alongside the request; the gate checks schema match, issuer constraint, attribute constraints, and **not-revoked** (TEL); on failure → `Reply(kind="reject")`. The compute `fn` runs only if the gate passes. See §6.2 for the substrate-completion caveat.

### 4.2 Identity binding — who the micro-app *is* (local vs cloud)

The micro-app's **own** AID (the role's signing identity) is resolved **differently per runtime** and is a configuration input the loader consumes (orthogonal to §4.1 — that is who may *ask*; this is who the micro-app *is*):

- **Cloud:** the role AID is **auto-incepted at deploy** — witnesses + keystore provisioned automatically via the existing per-stack **KMS-encrypted Secrets Manager keeper**. No human input.
- **Local:** the user binds the AID via a **one-time, first-open setup step** — the concierge plugin's **`AidSelectorPage`** (currently an unbuilt stub) or, for the CLI path, a `build`/`bind` flag — choosing one of:
  - **use an existing AID** they control (e.g. one already holding a credential authorizing it to *act as* the role),
  - **use their own AID** (if it is so authorized), or
  - **create a fresh AID** for the role.
  This setup is **transient and non-revisitable**; it runs *before* `load(template, deploy)`, and the bound AID then fills the deploy manifest's role-AID slot.

**Optional role-authorization credential:** the chosen AID may be required to hold a credential authorizing it to act in the role (an authz check on the micro-app's *own* identity — "this AID may *be* a Rating Engine"), verified at bind time. Distinct from §4.1's per-request gate.

## 5. Data production — collaborative authoring (the input, not the center)

How the product **data** the micro-app consumes gets produced and assembled, by multiple parties — each its own Service-AID (per the one-AID principle):

- **Contributors** (e.g. product-designer, actuary, rules-author): each runs its domain command (`ipd` → files), `said`-stamps the content, and issues a **fragment ACDC** — `{i:<contributor AID>, s:<fragment-type schema SAID>, a:{contentSaid, label, kind, role}, e?:{prior}}` — content **SAID-referenced, not inlined**.
- IPEX: each contributor **grants** its fragment to the **coordinator**, who **admits** it.
- **Coordinator** (a Service-AID): assembles a **manifest ACDC** via edges — `Reply.acdc(edges={ "<fragment>":{cred_said, schema_said}, …, "supersedes":{cred_said:<prior manifest>, schema_said} })`. *Validated against the substrate:* `IpexGrantIssuer` builds the `e` block from exactly this `{cred_said, schema_said}` edge shape today — **no `keri_serviceaid` change needed for assembly.**
- A `validate` step checks the assembled whole: every edge resolves, each fragment ACDC verifies, no duplicate fragment types. (Deep attribute/DAG validation deferred.)
- The **manifest SAID becomes a deploy-data input** (§4 table, last row) the micro-app's compute reads.

Schema SAIDs are the concept identifiers (one schema SAID per fragment type, everywhere). Fragments/manifest are shaped to be **representable as designer `credentials.exports` (+ envelope edges)** so the template-gen path is natural — but we don't modify the designer.

## 6. The two substrate items (only `keri_serviceaid` changes)

### 6.1 Publish/Sandbox TEL lifecycle
`assemble_manifest` issues the manifest into a **Sandbox** registry (revocable/purgeable). A separate **`publish_manifest`** command issues it into a **dedicated "published" registry whose entries are never revoked** (immutability by policy; v1 — an immutable in-TEL state flag is deferred). Needs one small extension: a reply path that targets a specific registry and, for Sandbox, can `Registry.revoke`.

### 6.2 Complete the credential-presentation gate
The slot exists (`Command.requires_credential`, `credgate`/`verify`, `CredentialReq`), but the full **present → verify-against-`required_schema` → admit-and-check** path is the partially-deferred Gated-Retrieval item (allowlist gating works; credential-presentation gating is incomplete). Completing it is the second (small) substrate change.

## 7. CLIs (thin, over the loader + authoring libs)

- **`said`** — `said saidify <file> [--ndjson]` (wraps keripy saidify).
- **`micro-app`** — verbs over the loader + authoring lib:
  - Data production: `party init`, `fragment issue`, `grant`, `admit`, `assemble`, `validate`, `publish`.
  - Identity binding (local, §4.2): `bind [--aid <existing> | --use-own | --create-aid] [--require-role-cred <said>]` → choose/create the micro-app's own AID (the CLI equivalent of the `AidSelectorPage`).
  - Loader/build: `build --template <t> --deploy <d>` → instantiate (and, locally, run) a Service-AID from the template + deploy manifest (using the bound AID); `call <route>` to exercise a command (presenting a gating credential if required).

Witness/OOBI config is a parameter (default local demo witnesses with mailboxes; swappable to the federation).

## 8. Integration test (acceptance criterion)

A re-runnable **bash script** that proves the *whole* paradigm end-to-end, for an insurance scenario:
1. Spin up local demo witnesses; `party init` each role's Service-AID.
2. **Data production:** product-designer issues `coverages`+`metadata` fragments, actuary issues `rating-tables`, rules-author issues `derivation-logic` (each via `ipd` → `said` → `fragment issue` → `grant`); coordinator `admit`s, `assemble`s the manifest, `validate`s, `publish`es.
3. **Build:** author a micro-app template + a deploy manifest (manifest SAID, AIDs, a compute entry-point, a `requires_credential` gate); `micro-app build` → the loader instantiates the **Risk-Profiler/Premium-Calc Service-AID**.
4. **Run gated compute:** an authorized requester presents the gating credential and `call`s "calculate premium"; assert the gate passes, the compute runs on the published product data, and the **result is signed by the micro-app's AID**. Assert an *unauthorized* call is **rejected**.

Assertions via exit codes / `grep`; hermetic (temp keystores; cleaned up). Insurance lives only here.

## 9. Testing strategy

- **Bash integration script (primary):** the §8 end-to-end flow — "verify via CLI, out of the code."
- **`keri_serviceaid.TestRuntime` + `pytest` (units):** the loader's template→ServiceAid mapping (incl. credential-gate wiring), each command function in isolation, the authoring pure functions (SAID determinism, edge-map build, `validate` collision detection).

## 10. Risks & status

| Item | Status |
|---|---|
| Manifest edge assembly | **Resolved** — `Reply.edges={name:{cred_said,schema_said}}` supported today. |
| Publish/Sandbox TEL lifecycle | **Substrate item §6.1** — small `keri_serviceaid` extension. |
| Credential-presentation gate | **Substrate item §6.2** — slot exists; presentation-verify path partially deferred (Gated-Retrieval). |
| Compute as ARN vs entry-point | **Decision B** — abstract in template; deploy binds; runtime-agnostic. |
| Multi-role party | **Non-issue** — one Service-AID per role; a dual-role party runs two. |
| Designer↔runtime | **The loader IS the bridge** (symbolic→live resolution); designer plugin **not** rewritten — we consume its template. |
| Qt entanglement in concierge-api | **None** — core Qt-free; `pages/` is a stub. |
| Micro-app's own AID binding (§4.2) | Cloud = auto-incept at deploy (Secrets Manager keeper, exists). Local = one-time first-open setup; `AidSelectorPage` is the **unbuilt** concierge stub — the CLI `bind` exposes the same choice. Optional role-authorization-cred check at bind time. |

## 11. Out of scope (restated)

Other-primitive runtime, deep DAG validation, production HOA/serverless, designer-plugin rewrite. Authoring the actual template (via `/micro-app-template-gen`, in `~/code/ugard`) is the **next step after this loader contract is approved** — authored *against* this contract.
