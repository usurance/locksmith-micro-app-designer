# Data-Driven Micro-App Build — Template → Service-AID Loader — Design Spec


|           |                                                                                                                             |
| --------- | --------------------------------------------------------------------------------------------------------------------------- |
| Status    | Approved — authoring the Product-Designer template next (§11), then writing-plans                                                                                                            |
| Date      | 2026-06-25                                                                                                                  |
| Builds on | `keri_serviceaid` (`~/code/keripy/keri_serviceaid/`) + `concierge-api` (`2026-06-23-concierge-api-local-runtime-design.md`) |
| Lineage   | `micro-app-runtime` (spec-only/abandoned) → `keri_serviceaid` → **concierge** (current)                                     |


## 1. Goal & organizing principles

Make **app-building data-driven**: an AI (or a person) authors a declarative **micro-app template**; a **loader** turns that template + deploy-time data into a configured, running **Service-AID**. The author writes *configuration*, never KERI plumbing — the substrate is already built and working. That is the whole point of the micro-app paradigm.

Four principles that resolve prior confusion:

1. **Template ⊥ Runtime.** The **micro-app template** is the *data/DSL* (authored via `/micro-app-template-gen`). The **Service-AID/concierge** is the *runtime* that executes it. The **loader** is the bridge — and it is *central*, not deferrable.
2. **One micro-app = one Role × one Responsibility = one role *identity* (AID).** That identity is *realized* as **one or more Service-AID deployments** (a command handler now; aggregate / projection compute in Phase 2 — §4.3), which **normally share the one role AID** (optionally with a cloud-provisioned *delegated supporting* AID). So **Service-AID = the deployment unit; the AID = the identity anchor** that unifies them. A Role's *full* behavior takes **many** micro-apps; **cross-micro-app / cross-AID composition is the *ecosystem* layer** (the ecosystem viewer), not something inside one micro-app.
3. **ACDCs are the currency; most are authored or imported, not generated.** Of the template's **8 primitives**, ACDCs enter through **`credentials`** — `exports` declare the ACDC types this role *issues*, `imports` the types it must *hold* — while **`commands`/`reactions`/`workflows`** move them via **IPEX** (grant / admit) by *referencing* credential ids; `header`, `role`, `aggregates`, `projections`, and `rules` are **pure configuration**. The template concerns itself with *ACDCs* — their schema SAIDs and IPEX flow — not any one data format. ACDCs are sourced three ways: **authored** (by `/micro-app-template-gen`, the default), **imported** from other ecosystems (they are just SAIDs — the composability win: snap an existing concept onto your context), or **derived** from a deterministic pre-ACDC (SAD) source. *Only novel services invent new ACDCs; mature ecosystems are assembled from existing ones.*
4. **Immutable, disposable deployments over a federated system-of-record.** A deployment is never mutated or migrated in place — it is built **immutable** (content-addressed; §4.4), and when it changes a **new build is deployed *beside* the old** for clients to cut over to (old retired). This is viable because the **system-of-record is the federated KERI substrate** (counterparties' KELs/TELs, ACDCs by SAID) — *not* the app's own store — so there is **no app-level data to migrate**. Derived state (aggregates/projections) is **rebuildable** by replaying the federated log. The **durable** things are the *log + the role AID + its keystore + the federated ACDCs*; the **disposable** thing is the compute deployment. (Infra reconciliation, where wanted, is the deploy target's job — §4 Contract.)

*Example (insurance — the only domain we touch, and only as the §8 test scenario):* a **Product Designer** role's *Manage Insurance Product* responsibility is one micro-app whose **commands** include `sandbox` and `publish` (creating / releasing product versions); a **Rating Engine** role's *Calculate Premium* responsibility is another. Each gets a template; the loader configures its Service-AID. Those commands traffic in **ACDCs** — the Product is an ACDC, the sandbox *result* is an ACDC — and `ipd` is just *one* (insurance-specific, deterministic) **SAD source** feeding some of them. **`sandbox`/`publish` are domain commands of a template — never features of this generic spec.**

## 2. Scope

**In scope:**

- **The loader** — `load(template, deploy_data) -> ServiceAid`: a *template-aware* layer that instantiates a `keri_serviceaid` `ServiceAid` (commands + providers) from a template + deploy manifest. (This subsumes the earlier "designer→runtime bridge": resolving template symbolic refs → live SAIDs *is* the loader's job.)
- **Per-compute authorization gate** — each command's optional, **pluggable** authz *method* (`aid` / `allowlist` / `credential`), data-driven (§4.1).
- **Two substrate items** (the only `keri_serviceaid` changes — both **domain-agnostic**): **registry-targeting + revoke** (§6.1) and **completing the credential-presentation authz method** (§6.2).
- **ACDC sourcing & assembly (collaborative authoring)** — the ACDCs a micro-app traffics in, **authored / imported / derived**, IPEX-exchanged and (where co-produced) coordinator-assembled into a **manifest ACDC** (§5). `ipd` is the insurance test's deterministic SAD source — one source, not the model. The resulting SAIDs are deploy-data inputs.
- **Local schema availability on load** — register the micro-app's schemas into the local KERI store and make them resolvable to direct peers (KERI **direct mode**); global OOBI publishing is **deferred** (§5.2).
- **CLIs** — `said` (saidify) and `micro-app` (drive the loader + the authoring flow) — thin over the Qt-free authoring/loader library.
- **A bash multi-party integration test** as the acceptance criterion (§8), against local demo witnesses (swappable to the federation).

**Phasing:** Phase 1 (this build) = the **command** Service-AID, end-to-end. Phase 2 (designed in §4.3, built next) = the **aggregate / projection / workflow** Service-AIDs. The loader / deploy-manifest / identity seams are designed for *all* primitives now; only the command facet is *built* now.

**Out of scope (deferred, named):**

- **Building** the aggregate / projection / workflow Service-AIDs *now* — their runtime is **designed in §4.3** and is the committed **next phase**; this build is command-first.
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

**Homes:** the **loader + authoring lib + CLIs** live in `**concierge-api`** (`src/concierge_api_local/{loader,authoring}/` + `cli/`); reuse `keri_serviceaid`; the **template** lives in `**~/code/ugard`**; this spec lives in the designer repo's `docs/superpowers/specs/` (curated home for runtime design). `keri_serviceaid` stays **template-agnostic** (its own design decision); the loader is the template-aware sugar on top.

## 4. The loader (the core)

**Contract:** `load(template: dict, deploy: DeployManifest) -> ServiceAid` — read a static template + a deploy manifest, resolve symbolic refs to live values, and build a configured `ServiceAid` (its `@svc.command`s + providers) with no handwritten plumbing. It is a **pure function** — deterministic (same template + manifest → the same `ServiceAid` config), holding no state of its own. It **does not reconcile**: provisioning, convergence, and teardown belong to the **pluggable deploy target** (CloudFormation/CDK in the cloud; the wallet runtime locally). Re-running `load` recomputes the configuration; the *deployment* is immutable & disposable (Principle 4), not reconciled in place.

**The mapping (data-driven app build):**


| Template field (DSL)                           | Drives in `keri_serviceaid`                                                           | Deploy manifest fills                                                    |
| ---------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `header.role` + identity                       | the ServiceAid's role/AID                                                             | the incepted **AID**                                                     |
| `commands[]`                                   | a `@svc.command(route, payload_schema, issues, requires_credential, fn)` registration | —                                                                        |
| `commands[].compute` (abstract capability ref) | the **command** Service-AID's `fn` (Phase 1) — the *arbitrary* business compute (vs. the DSL-conformant aggregate/projection fns) | an **ARN** (cloud) / **entry-point** (local) + the signing **AID** |
| `commands[].requires?` (authz gate, §4.1)      | the chosen authz provider (`authz` / `credgate`)                                      | the method's live values (AID / AID-set / **schema SAID** + constraints) |
| `aggregates[]` *(Phase 2, §4.3)* | an **aggregate** Service-AID — one DSL-driven fold fn for all aggregates | aggregate compute **ARN / entry-point** + AID |
| `projections[]` *(Phase 2, §4.3)* | a **projection** Service-AID — one DSL-driven fold fn for all projections | projection compute **ARN / entry-point** + AID |
| `workflows[]` *(Phase 2, §4.3)* | orchestration across command/aggregate/projection + counterparties | — |
| `credentials.exports[]`                        | `issues` + `Reply.acdc(edges, rules)`                                                 | issued **schema SAID** + edge **SAIDs**                                  |
| `credentials.imports[]`                        | inputs the compute expects                                                            | their **schema SAIDs**                                                   |
| `rules[]`                                      | precondition / constraint clauses (`rule_ref`ed across the template) — **config, not ACDC content**                                                         | —                                                                        |
| witness/OOBI                                   | `LocalRuntime` / witness config                                                       | demo or **federation OOBIs**                                             |
| ACDC inputs/outputs (per element)              | the ACDCs each element consumes / produces                                                           | the live **ACDC / schema SAIDs** (authored, imported, or derived)                                     |


> **Two distinct `rules`.** The template's top-level `rules[]` (+ `rule_ref`s) are *authoring-time constraint clauses* (legal prose, predicates, validations, computations) — **configuration** referenced across the template, **not** ACDC content. An issued ACDC's `r` (Ricardian) block is populated **separately, at issuance**, via `Reply.acdc(rules=…)` (keripy `proving.credential` sets the `r` block). Whether an export's `rule_refs` → `legal_prose` serializes into that `r` block is **unspecified today** — a gap to settle during template authoring.

**Decisions:**

- **A — Resolution time:** **deploy/startup.** Template is static; the deploy manifest injects live data; the loader builds the `ServiceAid` (local: at vault startup via `BindingController`; cloud: at CDK deploy). The **role AID is bound just before this** (§4.2): cloud auto-incepts at deploy; local binds via the one-time first-open setup.
- **B — Compute reference:** the template names compute **abstractly** (capability id + payload/issue schemas); the deploy manifest **binds** it to an **ARN** (cloud) or a **Python entry-point** (local) — the same template runs in either runtime.
- **C — Loader home:** a **template-aware layer in `concierge-api`**; `keri_serviceaid` stays template-agnostic.
- **D — Deploy manifest:** a small declarative artifact (role AID, schema SAIDs, compute ARNs/entry-points + **code digests**, OOBIs, gating cred SAIDs, the **EGF acceptable-SAID set** (§5.1), the product manifest SAID) merged with the template by the loader; the loader emits the **SAID lockfile** (§4.4) identifying the build. CDK plugs in here for cloud.
- **E — Build lifecycle:** **immutable & disposable** (Principle 4). The loader is a **pure compiler**; builds are SAID-locked (§4.4); a changed build deploys **beside** the prior one (no in-place mutation, no data migration). Reconciliation/teardown is the **deploy target's** concern, never the loader's.

### 4.1 Per-compute authorization gate — who may *ask* (pluggable method)

Each command may declare an optional authorization gate (about the **requester**; §4.2 is about the micro-app's *own* identity). The **method is itself data-driven** — a loadable **authz class** (a `keri_serviceaid` provider Protocol: today `authz` for AID-based, `credgate` for credential-based). The template names the method + config; the deploy manifest fills live values; the loader binds the chosen authz provider into the command:


| `requires.method` | Caller must…                           | Template config                                                          | Deploy fills        |
| ----------------- | -------------------------------------- | ------------------------------------------------------------------------ | ------------------- |
| `aid`             | be a specific AID                      | —                                                                        | the **AID**         |
| `allowlist`       | be one of a set of AIDs                | —                                                                        | the **AID set**     |
| `credential`      | own/present an ACDC of a required type | `issuer?` / `attribute_constraints?` (e.g. `status=active`, `amount>=X`) | the **schema SAID** |


For `credential`: the requester **presents** the ACDC via IPEX/exn; the gate checks schema match + issuer + attribute constraints + **not-revoked** (TEL). On any method's failure → `Reply(kind="reject")`; the compute `fn` runs only if the gate passes.

The abstraction is the injected authz **provider Protocol**, so new methods (a multisig threshold, a delegation check, or a *composed* `allowlist`-AND-`credential`) are loadable without touching command code. **Status:** `aid`/`allowlist` map to the shipped `authz` provider; `credential` is the partially-deferred presentation gate (§6.2).

### 4.2 Identity binding — who the micro-app *is* (local vs cloud)

The micro-app's **own** AID (the role's signing identity) is resolved **differently per runtime** and is a configuration input the loader consumes (orthogonal to §4.1 — that is who may *ask*; this is who the micro-app *is*):

- **Cloud:** the role AID is **auto-incepted at deploy** — witnesses + keystore provisioned automatically via the existing per-stack **KMS-encrypted Secrets Manager keeper**. No human input.
- **Local:** the user binds the AID via a **one-time, first-open setup step** — the concierge plugin's `**AidSelectorPage`** (currently an unbuilt stub) or, for the CLI path, a `build`/`bind` flag — choosing one of:
  - **use an existing AID** they control (e.g. one already holding a credential authorizing it to *act as* the role),
  - **use their own AID** (if it is so authorized), or
  - **create a fresh AID** for the role.
  This setup is **transient and non-revisitable**; it runs *before* `load(template, deploy)`, and the bound AID then fills the deploy manifest's role-AID slot.

**Optional role-authorization credential:** the chosen AID may be required to hold a credential authorizing it to act in the role (an authz check on the micro-app's *own* identity — "this AID may *be* a Rating Engine"), verified at bind time. Distinct from §4.1's per-request gate.

### 4.3 Compute topology — one template, one-or-more Service-AIDs

A micro-app template (one Role × one Responsibility) compiles to **one or more Service-AID deployments**, each a *gated compute facet* of the same role identity:

- **Command Service-AID** *(Phase 1 — this build)* — handles exn commands, runs the per-command `fn`, issues ACDCs.
- **Aggregate Service-AID** *(Phase 2)* — folds the role's event stream into state. **Not arbitrary compute:** ONE function for *all* aggregates, **driven by the `aggregates` DSL**, with extension points where a specific aggregate needs them.
- **Projection Service-AID** *(Phase 2)* — folds streams into read-side views; likewise **one function for all projections**, driven by the `projections` DSL.
- **Workflows** *(Phase 2)* — orchestrate across the above (and counterparties).

These are like the concierge-api *arbitrary-compute* Service-AID, but **conform to their config** rather than running arbitrary code — the "AI just *configures* the app (business rules in the DSL)" thesis carried to every primitive.

**Identity:** the deployments **normally share the one role AID** (co-located facets of one identity); optionally the cloud provisions a **delegated supporting AID** for a given compute. Either way the **deploy manifest binds each primitive's compute** (ARN / entry-point) and its AID — the *same* loader seam as commands (Decision B). So *Service-AID* is the **deployment unit**, the **AID is the identity anchor**: this refines Principle 2 without violating it.

### 4.4 Build identity & lifecycle — the SAID lockfile (not semver)

A deployed micro-app is identified by a **SAID lockfile**: a `said`-stamped, KEL-anchored record of exactly *what was deployed* — the **template SAID + every imported/authored schema SAID + compute-binding digests** (pin **code digests, not ARN strings**) + witness/OOBI config + the EGF acceptable-SAID set (§5.1). Being content-addressed, the build is **immutable by construction**: any change yields a new lockfile SAID = a new build (Principle 4).

This **replaces semver as the *identity***. SAID and semver answer different questions, and the SAID-native answers are more honest:

| Need | Mechanism |
| --- | --- |
| *Which exact build?* (identity) | the **lockfile SAID** |
| *Which is newer?* (ordering) | the role AID's **KEL sequence number** (the anchoring `ixn`'s `sn`) |
| *Lineage* | a **`supersedes` edge** between build lockfiles |
| *Compatible?* | exact **schema-SAID match** (binary, unforgeable); cross-version interop is an explicit EGF/consumer acceptance decision (§5.1) — not a semver *promise* and not an automatic substrate bridge |

Human `version` strings survive **only** as non-normative domain labels where humans need them (e.g. a regulatory filing label) — never as the build's identity. **Anchor the lockfile SAID into issued ACDCs** (the ecosystem's `product_version_said` field is exactly this) so every signed result carries provenance — *which build computed it*.

## 5. ACDC sourcing & assembly (the input, not the center)

The ACDCs a micro-app's elements traffic in come from three sources:

- **Authored** — `/micro-app-template-gen` defines the schema and the issuing element produces the ACDC. **The common case.**
- **Imported** — an ACDC (or just its schema SAID) from another ecosystem, referenced as-is. They are *just SAIDs*; sharing a schema SAID = composing the same concept. **The composability win.**
- **Derived** — a deterministic process emits a **SAD**, then *augmented* into an ACDC (issuer `i`, schema `s`, edges `e`). `ipd` is the insurance example: it emits SADs (coverages, rating-tables, derivation-logic) that ride in an ACDC's `a` by content SAID, not inlined.

When several parties co-produce one Responsibility's inputs, assembly is generic and IPEX-native (each party its own Service-AID):

- Each contributor issues a **fragment ACDC** — `{i:<contributor AID>, s:<schema SAID>, a:{contentSaid, label, kind}, e?:{prior}}` — and **grants** it to a **coordinator**, who **admits** it.
- **Coordinator** (a Service-AID): assembles a **manifest ACDC** via edges — `Reply.acdc(edges={ "<fragment>":{cred_said, schema_said}, …, "supersedes":{cred_said:<prior manifest>, schema_said} })`. *Validated against the substrate:* `IpexGrantIssuer` builds the `e` block from exactly this `{cred_said, schema_said}` edge shape today — **no `keri_serviceaid` change needed for assembly.**
- A `validate` step checks the assembled whole: every edge resolves, each fragment ACDC verifies, no duplicate fragment types. (Deep attribute/DAG validation deferred.)
- The resulting **SAIDs are deploy-data inputs** (§4 table) the elements read.

Schema SAIDs are the concept identifiers (one per concept, everywhere — exactly what makes import & composition work). Fragments/manifest are shaped to be **representable as designer `credentials.exports` (+ envelope edges)** so the template-gen path is natural — but we don't modify the designer.

### 5.1 Schema evolution — explicit, governed acceptance (not an automatic substrate bridge)

Verified against the normative ACDC spec (`draft-ssmith-acdc`) + keripy. A few things are true; one tempting shortcut is **not**:

- **A schema SAID is an immutable cryptographic identity.** A revised schema is a *new* SAID = a *distinct type*. (The human `version` annotation in a schema is ecosystem convention, not normative; the ACDC `v` field *is* normative.)
- **The protocol does NOT auto-bridge versions.** There is no normative mechanism by which a new schema `oneOf`-accepts an older one, and an edge's `s` MUST equal the far node's schema SAID **exactly** (§9.1.4 — no version tolerance). `oneOf` in ACDC is for compact-vs-expanded *disclosure of the same schema* (§3.6), not cross-version compatibility; §3.3 mandates **static, SAID-immutable schemas**.
- **Compatibility is therefore an explicit, governed decision — not free.** A micro-app / ecosystem declares the **set of schema SAIDs it accepts** (an **EGF acceptable-SAID set** — an informational governance pattern, not a protocol requirement) and its consumer logic handles each accepted shape. So **a v2 micro-app reads v1-era credentials because it *explicitly accepts* v1's schema SAID** — config + a consumer branch, *not* an automatic substrate feature.
- **Trust by adoption.** Within that acceptable-set, trust accrues to a SAID through *abundant use* (a widely-adopted SAID becomes a de-facto standard); issuer provenance is at most a signal, never a gate.
- **Instance authenticity is always verified** via KERI (schema-SAID match + issuer KEL + TEL non-revocation) — separate and unconditional.

**So hole #1 is bounded, not eliminated:** cross-version interop is the *consumer's explicit responsibility* (accept the old SAID + handle its shape via the acceptable-set) — real work, but config + a branch, not a data migration. The throw-away / parallel-deploy model (Principle 4) still holds because *data* never migrates; only the consumer's accepted-SAID set grows.

> **Verification note:** an LLM-RAG initially suggested automatic `oneOf` cross-version composition, edge-`s` version tolerance, and auto minor-version tolerance. Checked against `draft-ssmith-acdc` (§3.3 static/immutable schemas; §9.1.4 exact edge-`s` match; §3.6 `oneOf` = disclosure forms) + keripy: those are **not** spec-supported. Only the EGF acceptable-SAID *pattern* survives, and it is informational, not a MUST.

### 5.2 Schema availability on load — local / direct mode (global publishing deferred)

For a micro-app's commands to validate the credentials it traffics in, its schemas must be **resolvable**. This build does that **locally**, in **KERI direct mode**:

- **On load (the local / Locksmith path), the loader registers the micro-app's schemas into the local KERI schema store** (`db.schema` via `Schemer` — the same SAID-verified pin keripy uses on OOBI resolution, `app/oobiing.py`). The Service-AID can then validate immediately.
- **Counterparties resolve them point-to-point** over Locksmith's already-shipped **peer-mode (direct TCP) transport** — no witnesses, no globally-reachable endpoint. Schema availability is scoped to the wallet's direct peers (and, for the §8 test, the local demo setup).

This is the **local counterpart** of a global *Micro-App EGF Publisher* — which would serve schemas at a world-reachable OOBI (e.g. `egf.keri.host/oobi/<said>`) so *any* EGF can pull them in. That **universal / indirect-mode publishing is deferred** to its own brainstorm (`backlog/2026-06-26-egf-publisher-and-schema-discovery.md`); Phase 1 ships only the local/direct path. Same load-time *step*, two reach scopes: **direct (local, now)** vs **published (global, later)**.

## 6. The two substrate items (only `keri_serviceaid` changes)

### 6.1 Registry targeting + revoke (generic)

Today a command reply single-issues into the ServiceAid's default registry. A command may need to (a) issue into a **named** registry and (b) **revoke** a prior credential — a small, **domain-agnostic** `keri_serviceaid` extension (a reply path that targets a chosen registry / can `Registry.revoke`). *Domain lifecycle commands rely on this* — e.g. an insurance **Product-Designer** micro-app's `sandbox`/`publish` commands (sandbox → a revocable registry; publish → an immutable-by-policy registry) — but those **lifecycle semantics live in that template's commands, not here.**

### 6.2 Complete the credential-presentation gate

The slot exists (`Command.requires_credential`, `credgate`/`verify`, `CredentialReq`), but the full **present → verify-against-`required_schema` → admit-and-check** path is the partially-deferred Gated-Retrieval item (allowlist gating works; credential-presentation gating is incomplete). Completing it is the second (small) substrate change.

## 7. CLIs (thin, over the loader + authoring libs)

- `**said`** — `said saidify <file> [--ndjson]` (wraps keripy saidify).
- `**micro-app**` — verbs over the loader + authoring lib:
  - Data production (generic composition): `party init`, `fragment issue`, `grant`, `admit`, `assemble`, `validate`. *(Domain lifecycle such as `sandbox`/`publish` are template **commands** run via `call`, not generic verbs.)*
  - Identity binding (local, §4.2): `bind [--aid <existing> | --use-own | --create-aid] [--require-role-cred <said>]` → choose/create the micro-app's own AID (the CLI equivalent of the `AidSelectorPage`).
  - Loader/build: `build --template <t> --deploy <d>` → instantiate (and, locally, run) a Service-AID from the template + deploy manifest (using the bound AID); `call <route>` to exercise a command (presenting a gating credential if required).

Witness/OOBI config is a parameter (default local demo witnesses with mailboxes; swappable to the federation).

## 8. Integration test (acceptance criterion)

A re-runnable **bash script** that proves the *whole* paradigm end-to-end, for an insurance scenario (the only place insurance appears):

1. Spin up local demo witnesses; `bind` / `party init` each role's Service-AID.
2. **Data production (generic):** product-designer issues `coverages`+`metadata` fragments, actuary issues `rating-tables`, rules-author issues `derivation-logic` (each via `ipd` → `said` → `fragment issue` → `grant`); coordinator `admit`s, `assemble`s the manifest, `validate`s.
3. **Build the Product-Designer micro-app:** author its template + deploy manifest; `micro-app build` → the loader instantiates its Service-AID. Invoke its **`publish` command** (a *template* command) to release a product **version** — exercising the §6.1 registry-targeting path end-to-end.
4. **Build the Rating-Engine micro-app + run gated compute:** load it; an authorized requester presents the gating credential and `call`s its *Calculate Premium* command; assert the gate passes, the compute runs on the **published** product version, and the **result is signed by the micro-app's AID**. Assert an *unauthorized* call is **rejected**.

Assertions via exit codes / `grep`; hermetic (temp keystores; cleaned up). `sandbox`/`publish`/`calculate` are the *templates'* commands — the machinery under test is domain-agnostic.

## 9. Testing strategy

- **Bash integration script (primary):** the §8 end-to-end flow — "verify via CLI, out of the code."
- `**keri_serviceaid.TestRuntime` + `pytest` (units):** the loader's template→ServiceAid mapping (incl. credential-gate wiring), each command function in isolation, the authoring pure functions (SAID determinism, edge-map build, `validate` collision detection).

## 10. Risks & status


| Item                               | Status                                                                                                                                                                                                                                                |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Manifest edge assembly             | **Resolved** — `Reply.edges={name:{cred_said,schema_said}}` supported today.                                                                                                                                                                          |
| Registry targeting + revoke      | **Substrate item §6.1** — small, domain-agnostic; insurance `sandbox`/`publish` are template commands that use it.                                                                                                                                                                                          |
| Credential-presentation gate       | **Substrate item §6.2** — slot exists; presentation-verify path partially deferred (Gated-Retrieval).                                                                                                                                                 |
| Compute as ARN vs entry-point      | **Decision B** — abstract in template; deploy binds; runtime-agnostic.                                                                                                                                                                                |
| Multi-role party                   | **Resolved (§4.3)** — one micro-app = one role *identity* realized as one-or-more Service-AID deployments (shared AID); a party in two roles runs two micro-apps.                                                                                                                                                                                 |
| Designer↔runtime                   | **The loader IS the bridge** (symbolic→live resolution); designer plugin **not** rewritten — we consume its template.                                                                                                                                 |
| Qt entanglement in concierge-api   | **None** — core Qt-free; `pages/` is a stub.                                                                                                                                                                                                          |
| Micro-app's own AID binding (§4.2) | Cloud = auto-incept at deploy (Secrets Manager keeper, exists). Local = one-time first-open setup; `AidSelectorPage` is the **unbuilt** concierge stub — the CLI `bind` exposes the same choice. Optional role-authorization-cred check at bind time. |


## 11. Out of scope (restated)

Building (not designing) the Phase-2 aggregate/projection/workflow Service-AIDs (designed in §4.3), **infrastructure reconciliation** (owned by the deploy target — CloudFormation/CDK / the wallet runtime; the loader is a pure compiler, §4), deep DAG validation, production HOA/serverless, designer-plugin rewrite. Authoring the actual template (via `/micro-app-template-gen`, in `~/code/ugard`) is the **next step after this loader contract is approved** — authored *against* this contract.