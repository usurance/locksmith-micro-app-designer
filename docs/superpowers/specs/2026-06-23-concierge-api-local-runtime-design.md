# Concierge API — Local Runtime Design Spec

| | |
|---|---|
| Status | Draft for review |
| Date | 2026-06-23 |
| Projects | `concierge-api` (new repo: library `concierge-api-local` + AI skill) · small additions to `keri_serviceaid` |
| Related | `2026-05-15-micro-app-runtime-design.md` (superseded cloud framing) · `KERI-COMMUNICATION-MODEL.md` |

## 1. Goal

Let a developer build an **in-wallet KERI Service AID** — a "local concierge" — as a lean Locksmith plugin, reusing the exact `keri_serviceaid` contract/pipeline/providers that already run in the cloud Lambda, by adding a `LocalRuntime` adapter plus a thin plugin-builder library (an AI skill follows in a later plan).

## 2. Context & motivation

`keri_serviceaid` is the declarative Service-AID framework: `ServiceAid` + `@command`, a `Request → Reply` pipeline (verify → authz → idempotency → compute → issue → deliver), and six swappable providers. Today it ships only a **cloud** runtime (`runtime.init()` + Lambda `handler`, over DynamoDB + Secrets Manager) and a `TestRuntime`. The **local** runtime — the same pipeline driven inside a Locksmith vault, issuing from a vault AID — does not exist. That is the gap this spec closes.

The framework is deliberately layered so the gap is small: `contract.py` and `pipeline.py` are substrate-agnostic (no keripy at module top; they touch only `state.svc` providers + `state.hby/hab/rgy`). A `LocalRuntime` is therefore an **adapter**, exactly parallel to how the Lambda runtime is the cloud adapter. The local skeleton already half-exists: Locksmith's turret runs a sender-gated `Exchanger` owned by one vault AID; this generalizes that into a full Service-AID host.

**Metaphor:** a *concierge* answers requests on your behalf, locally and personally. The bound AID **is** the concierge — recipient of requests, issuer of replies.

## 3. Scope & non-goals

**In scope (v1):**
- A `LocalRuntime` adapter + `LMDBLedger` idempotency store + a `CredentialGate` authorizer (with a small `@command` contract extension), added to `keri_serviceaid`.
- A new repo `concierge-api` containing the library `concierge-api-local` (the `ConciergePlugin` base + a UI-free `BindingController` + a reusable `AidSelectorPage` + scaffolding). The repo also *houses* the AI skill, but the skill is built in a follow-up plan (below).
- A worked **Rating Engine** example that doubles as the integration fixture (no real insurance-domain schema modeling).

**Non-goals (later phases):**
- The **AI skill** (build-a-concierge scaffolding) — a follow-up plan, after the library exists.
- Folding `keri_serviceaid` into `concierge-api` as the `concierge-api` core (planned; out of scope now).
- Witnessed TEL issuance (v1 uses a no-backer registry, see §10).
- Delegation-based outbound authority (v1 = issue-as-self ± credential edge).
- A direct-socket (turret-style) inbound transport (v1 = mailbox poll).
- A `micro-app-template.json` → `ServiceAid` skeleton generator (designer→runtime bridge).

## 4. Naming & repositories

- **`concierge-api`** — new repo, the family monorepo.
- **`concierge-api-local`** — the library in that repo (Locksmith plugin layer). Depends on `keri_serviceaid` + `locksmith`.
- **AI skill** — lives in the same repo; mirrors `micro-app-template-gen` one level down (runtime, not authoring). **Built in a follow-up plan** (see §3), once the library lands.
- **`ConciergePlugin`** — the base class a developer subclasses.
- The `LocalRuntime` adapter lands in `keri_serviceaid` now (it reuses that package's internals — `RuntimeState`-style state, `_CaptureHandler`, `_wire_default_providers`, `pipeline`). In the later fold-in, `keri_serviceaid` becomes `concierge-api` (core) and the adapter re-homes cleanly in-repo.

## 5. Architecture overview

Three layers, top to bottom. **The boundary rule: everything KERI-mechanical stays in `keri_serviceaid`; `concierge-api-local` is only wallet-coupling + ergonomics; the developer writes almost nothing but business logic.**

```
① Developer's plugin (own repo)
   - subclass of ConciergePlugin; sets svc = ServiceAid(...), @svc.command fns, ACDC schemas
   - pure Request → Reply logic (no KERI)
        │ subclasses / installs
        ▼
② concierge-api-local (NEW repo: library now; AI skill follows)
   - ConciergePlugin base (VaultPlugin + AccountProviderPlugin)
   - BindingController (UI-free)        - AidSelectorPage (Qt, reusable)
   - scaffolding + Rating Engine example    (AI skill = follow-up plan)
        │ depends on
        ▼
③ keri_serviceaid (existing pkg — small additions)
   - NEW: LocalRuntime adapter, LMDBLedger, CredentialGate (+ @command requires_credential)
   - REUSED unchanged: contract · pipeline · 6 providers · LambdaRuntime · TestRuntime
```

The implementation therefore touches **two repos**: small additions to `keri_serviceaid`, and the new `concierge-api` repo.

## 6. Components

### 6.1 Additions to `keri_serviceaid`

**`LocalRuntime`** — the in-wallet adapter. Given an already-resolved bound AID, it runs the pipeline:
```python
class LocalRuntime:
    def __init__(self, svc: ServiceAid, *, hby, hab, rgy,
                 idempotency=None, inbound=None):
        # wires default providers (local variants) for any the dev left None:
        #   authz=CredentialGate (per-command: enforces requires_credential when
        #       declared, else falls through to the base Allowlist/open),
        #   verifier=OracleVerifier, resolver=OracleResolver,
        #   issuer=IpexGrantIssuer, deliverer=PostmanDeliverer,
        #   idempotency=LMDBLedger(hby.db)
        ...
    def doer(self) -> "hio.base.doing.Doer":
        "Mountable on the vault's Doist via the plugin's get_doers()."
```
- **Inbound handling.** The runtime registers, on `hby.exc`: (a) one `_CaptureHandler` per `svc` command route (verified command exns are captured, then the runtime drives `pipeline.process` on each); and (b) keripy's standard **IPEX admit handling** so `/ipex/grant` *presentations* are verified and admitted into the concierge's holdings (the credential store CredentialGate reads). `/ipex/*` are reserved routes — never command routes.
- **Inbound transport (v1).** A `MailboxDirector`/`Poller` drains the bound AID's **witness mailbox** (SSE). Requests buffer in the mailbox while the wallet is closed and drain on open. (Direct socket is a later transport.)
- The runtime's doer is **inert until activated** by the `BindingController` (it idles when unbound).

**`LMDBLedger`** — `IdempotencyStore` over a keripy LMDB `Suber` (parallels `DynamoLedger`): `seen(said)`, `record(said, grant)`.

**`CredentialGate`** — an `Authorizer` provider implementing present-then-cache:
```python
class CredentialGate:
    def __init__(self, *, hby, reger, svc): ...
    def authorize(self, req) -> tuple[bool, str]:
        # 1. read the route's requirement: svc.lookup(req.route).requires_credential
        # 2. query held credentials for one matching (schema [, issuer]) presented by req.sender
        # 3. verify it (vdr.verifying.Verifier) and re-check TEL revocation
        # 4. allow iff a valid, non-revoked match exists; else (False, reason) → silent drop
```
Reads from the concierge's **holdings** (populated by the IPEX admit handling above), not from `req.credentials`. No held/valid credential ⇒ deny (the pipeline's silent-drop applies).

**`@command` contract extension** — add an optional `requires_credential` to the command declaration so authorization is a **declared per-command policy**:
```python
@svc.command(route="/rate", issues=QUOTE_SCHEMA,
             requires_credential=CredentialReq(
                 schema=BROKER_SCHEMA, issuer=None,        # who/what must be presented
                 presentation="cache",                     # cache | embed | thread
                 cadence="revocation-recheck"))            # per-request revocation re-check
def rate(req: Request) -> Reply: ...
```
`CredentialReq` and the extra `Command` field are the only contract additions. When `requires_credential` is absent, the command is gated only by the `ServiceAid`'s base authz (Allowlist/open).

**Why declared on `@command`, not configured into the provider.** This mirrors the existing `issues` field exactly: per-command metadata is declared on `@command` and *consumed* by a provider — `cmd.issues` → the Issuer (`pipeline.py:68` `reply.schema_said = cmd.issues`), and now `cmd.requires_credential` → `CredentialGate`. `CredentialGate` therefore takes **no** per-command configuration (it reads the declaration off the command); a route→requirement map passed into the provider is explicitly rejected, since it would be the only per-command policy not co-located with the command.

### 6.2 `concierge-api-local` library

**`ConciergePlugin(VaultPlugin, AccountProviderPlugin)`** — the base a developer subclasses:
```python
class ConciergePlugin(VaultPlugin, AccountProviderPlugin):
    svc: ServiceAid                  # subclass sets this
    role_name: str                   # e.g. "rating-engine" (dedicated-AID default name)
    aid_policy: AidPolicy = AidPolicy.DEDICATED_OR_EXISTING

    # VaultPlugin
    def get_pages(self) -> dict[str, QWidget]:      # {concierge page, SETUP_PAGE_KEY: AidSelectorPage}
    def get_doers(self) -> list[Doer]:              # [self._controller.runtime_doer]  (idle until bound)
    def on_vault_opened(self, vault):               # controller.restore(); if controller.is_complete(): controller.start()
    def on_vault_closed(self, vault, clear=False):  # controller.stop(); if clear: controller.purge()

    # AccountProviderPlugin  (the non-in-your-face setup hook)
    def is_setup_complete(self, vault) -> bool:     # controller.is_complete()  (bound AND credentialed)
    def get_setup_page(self, vault) -> tuple[str, bool]:  # (SETUP_PAGE_KEY, should_push_menu)
```
Binding is **not** forced in `on_vault_opened`. The host (`locksmith/ui/vault/page.py:202-208`) checks `is_setup_complete` when the plugin is shown and routes to `get_setup_page` while unbound — the same proven pattern `KeriFoundationPlugin` uses. `on_vault_opened` only *restores* a persisted binding and starts the runtime if already bound.

**`BindingController`** — UI-free, testable, no Qt. The "other code that does the rest":
```python
class BindingController:
    def __init__(self, vault, svc, *, role_name, aid_policy, requirements): ...
    def restore(self) -> None             # load persisted binding from plugin state
    def is_complete(self) -> bool         # bound AID present AND declared credential held
    def candidate_aids(self) -> list[AidRef]          # for the selector
    def bind(self, *, existing: AidRef | None = None,
                      create_dedicated: bool = False) -> None   # resolve or create the Service AID
    def credential_status(self) -> CredentialStatus   # present | missing | revoked
    def start(self) -> None               # build LocalRuntime(svc, hby, hab, rgy), activate runtime_doer
    def stop(self) -> None                # deactivate runtime_doer, stop poller
    def purge(self) -> None               # delete binding + LMDBLedger + presentation cache (clear=True)
    @property
    def runtime_doer(self) -> Doer: ...
```
- `bind` with `create_dedicated=True` incepts a witnessed AID named for `role_name` (default); or binds an `existing` vault AID (`AidPolicy.DEDICATED_OR_EXISTING`).
- The declared outbound `authorizing credential` (optional, §9) is checked here; if missing, `is_complete()` is False and the setup page surfaces a blocked/acquire state.

**`AidSelectorPage`** — a reusable Qt `QWidget` returned via `get_pages()`/`get_setup_page`. Lists `candidate_aids()` + a "create dedicated `<role_name>`" action, shows credential status, drives `controller.bind`/`credential_status`, and reflects `is_complete()`. A developer can use it as-is or supply their own page and reuse the controller.

**Scaffolding + Rating Engine example + AI skill** — see §6.3 and §12.

### 6.3 AI skill (follow-up plan — not v1)

> Built once the library lands; specified here only for context.

Teaches/scaffolds a `ConciergePlugin`: choose `role_name` + `aid_policy`; declare `@command`s + ACDC schemas; declare `requires_credential` + presentation policy; generate the plugin skeleton plus a `TestRuntime` test; and a setup checklist (witnessing, credential acquisition). Mirrors `micro-app-template-gen` one level down. (A `micro-app-template.json` → `ServiceAid` skeleton generator is a noted future bridge, not v1.)

## 7. AID-binding & authorization model

"Authority" splits into two **independent** directions; conflating them is the main source of confusion.

**① Binding (setup-time).** Via the `AccountProviderPlugin` setup page. The user creates a dedicated AID (default, named for the role) or binds an existing vault AID; then the declared credential (if any) is ensured. The bound AID is the concierge's identity.

**② OUT — the concierge's right to issue** (why a Quote is trusted):
- *Issue-as-self* (v1 default): the bound AID issues as itself.
- *+ authorizing-credential edge* (optional, declarative): the bound AID holds an "authorized to run" ACDC; every issued ACDC chains an **edge** to it (`Reply.acdc(edges=...)`). This is the "credentials to run." If declared and missing, the plugin is not setup-complete.
- *Delegation* — later phase.

**③ IN — who may call it** (the authz provider, per command):
- *Allowlist / open* (base default).
- *`CredentialGate`* (built in v1): the caller must present an ACDC of the declared schema; verified + cached present-then-cache (§8).

## 8. Credential presentation — present-then-cache (v1 default)

Because IPEX is **non-normative** (a baseline for ecosystem-specific protocols), the presentation ceremony is a **declared per-command policy**, not a hardcoded flow. The exn carries: `r` (route), `a` (payload), `e` (embeds — where an ACDC rides), `q` (query-string-like modifiers), `p`/`xid` (exchange-thread linkage). v1 default = **present-then-cache**:

1. Caller presents the gating credential once via `/ipex/grant` (ACDC in `e`); the concierge's IPEX admit handling verifies + stores it, keyed by sender.
2. Caller sends the command (e.g. `/rate`) with the payload in `a`.
3. On each command, `CredentialGate` checks the **cached** verified credential and **re-checks TEL revocation** (no re-presentation unless absent/revoked).

`presentation` is overridable per command: `cache` (default), `embed` (ACDC in the command's `e`, stateless, re-sent each call), or `thread` (explicit `xip` exchange thread). `cadence` controls re-check/re-present frequency.

## 9. Data flow — Rating Engine (worked example)

`requester` → `mailbox` → `concierge runtime`:

1. **requester** presents its "licensed broker" credential — IPEX `grant` of the gating ACDC, addressed to the Rating Engine AID → its witness mailbox.
2. **requester** sends the `/rate` command exn — Risk Profile in `a`, addressed to the Rating Engine AID → mailbox.
3. **wallet opens** → `Poller` drains both; capture handler stashes the verified command; IPEX admit stores the verified credential; runtime drives `pipeline.process`.
4. **verify → CredentialGate → idempotency**: sig/tier check; CredentialGate confirms a valid, non-revoked broker ACDC from this sender is held; replay check on the command SAID.
5. **compute** — the `@command` fn reads the Risk Profile from `Request.payload`, computes premiums, returns `Reply.acdc(recipient=requester, attributes=quote, edges=…)`.
6. **issue** — `Credentialer.create` → `Registry.issue` (TEL) → `hab.interact` (KEL anchor); if declared, chain the authorizing-credential edge; frame as an IPEX grant.
7. **deliver** — `Poster` sends the grant to the requester's mailbox; idempotency records `(command SAID → grant)` *before* send (exactly-once: re-send re-delivers, never re-issues).
8. **requester** picks up the official Quote — verifiable by anyone (issuer = Rating Engine AID, anchored in its KEL/TEL).

## 10. Lifecycle & error handling

- **Setup/teardown.** Binding lives in the `AccountProviderPlugin` setup flow (§6.2), not `on_vault_opened`. `on_vault_opened` restores a persisted binding and starts the runtime only if already complete. `on_vault_closed` stops the runtime/poller; `clear=True` purges plugin-local durable state (binding, `LMDBLedger`, presentation cache) for that vault.
- **Inbound (v1).** Mailbox poll only; the concierge is *eventual*, not 24/7 — requests buffer in the witness mailbox and drain on open.
- **Error policy (inherited from the pipeline).** GRANT-on-success, **SILENCE on every other outcome** (bad sig / unauthorized / compute-raise / unknown route → log, no reply). Exactly-once issuance via record-before-deliver.
- **Revocation.** The cached presentation is TEL-revocation-rechecked per request (Observer / no-phone-home).
- **TEL issuance (v1).** **No-backer registry** — parity with the cloud runtime; the Quote is still fully verifiable because the issuing AID's KEL is witnessed and the TEL is anchored in it. Witnessed TEL is a later enhancement (local is better-positioned for it than cloud, having a real Doist + `Receiptor`).

## 11. Receiving/witnessing correctness (KERI comms constraints)

Per `KERI-COMMUNICATION-MODEL.md`: a reply is a **new signed message routed to the requester's reachable endpoint** (mailbox/direct), never an HTTP response. Inbound for the concierge is the bound AID's **witness mailbox** drained via `MailboxDirector`/`Poller` (SSE). When the runtime incepts/anchors for a witnessed AID, it must collect receipts via `agenting.Receiptor` (the `/receipts` path), **never `WitnessReceiptor`** (which assumes direct-mode push and hangs over HTTP — keripy#1422, locksmith#77).

## 12. Testing strategy

- **`TestRuntime`** (exists) — unit-test `@command` functions (`Request → Reply`) with zero keripy.
- **Unit (`keri_serviceaid`):** `LMDBLedger` idempotency; `CredentialGate` (present → verify → cache → revoke); `LocalRuntime` wiring against a temp `Habery`.
- **Unit (`concierge-api-local`):** `BindingController` (resolve/create AID, ensure credential, persist, start/stop, purge) — UI-free, no Qt.
- **Integration:** reuse the existing `locksmith-ui-tester` harness — an ephemeral wallet runs the Rating Engine `ConciergePlugin`; a second ephemeral wallet (or a scripted keripy requester) presents the broker credential and sends `/rate`; assert a signed Quote ACDC returns. The Rating Engine example *is* the integration fixture.
- **First deliverable / de-risking spike:** a **mock `AidSelectorPage`** wired to `BindingController` — pick/create an AID, watch the controller ensure the credential and flip the runtime on — before any rating logic.

## 13. Open questions & later phases

- Build the **AI skill** (build-a-concierge scaffolding), once the library lands.
- Fold `keri_serviceaid` into `concierge-api` as the core (renames; dependency re-homing).
- Witnessed TEL issuance for local concierges.
- Delegation-based outbound authority (Pattern A).
- Direct-socket (turret-style) inbound transport alongside mailbox poll.
- `micro-app-template.json` → `ServiceAid` skeleton generator (designer→runtime bridge).
- Credential **acquisition** flows (IPEX request / designer-assisted) when the declared authorizing credential is missing — v1 only detects-and-blocks.
```
