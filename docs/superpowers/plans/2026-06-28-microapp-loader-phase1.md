# Micro-App Loader — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data-driven loader that compiles a micro-app **template + deploy manifest** into a configured, running `keri_serviceaid` **ServiceAid**, proving it end-to-end on the adopted DOI `regulator-grants-carrier-license` template (grant-license command facet).

**Architecture:** The loader is a **pure compiler** (`load(template, deploy) -> ServiceAid`) living in `concierge-api`; it maps template primitives onto the *already-built* `keri_serviceaid` runtime (ServiceAid + providers + LocalRuntime + BindingController). Phase-1 collapses the template's inbound **reaction** + the **command** it triggers into one `svc.command(route, issues, requires_credential)(fn)` registration. Authz is **KERI-native structured** (`open`/`aid`/`allowlist` → `Allowlist`; `credential` → `CredentialReq` + the existing `CredentialGate`) — **no UEL evaluator**. Two substrate items in the keripy fork: complete/verify the credential gate (§6.2 — mostly present) and add registry revoke (§6.1). CLIs (`said`, `micro-app`) wrap the loader + `BindingController`. A bash script is the acceptance gate.

**Tech Stack:** Python 3.13, `keri_serviceaid` (keripy fork), `keripy` (`coring.Saider`, `scheming.Schemer`, `credentialing`, `protocoling`), `concierge-api` (setuptools, pytest `pythonpath=["src"]`), the micro-app-template-gen skill scripts (`micro_app_validate.py`, `micro_app_saidify.py`), bash + `kli` demo witnesses.

## Global Constraints

- **BE KERI NATIVE is LAW** (`docs/BE-KERI-NATIVE.md`): every task is measured against it — authz/identity/integrity/state use KERI primitives; adjacent code stays faithful. Authz is **never** a UEL/expression evaluation.
- The loader is a **pure function**: `load(template, deploy)` is deterministic, holds no state, and **does not reconcile** — provisioning/teardown is the deploy target's job. A changed build is a new SAID-locked build, deployed beside the old (no in-place mutation/migration).
- **Builds are immutable & SAID-locked** (§4.4): every `build` emits a SAID lockfile.
- `keri_serviceaid` lives in the **keripy fork** (`~/code/keripy/keri_serviceaid/`); cross-package changes resolve against the MAIN checkout — **validate keri_serviceaid changes on `development`** before relying on them from `concierge-api`.
- **Tests:** keri_serviceaid + concierge-api tests run on `~/code/locksmith/.venv/bin/python`. For any run that touches the repo-root `tests/` of a tree containing a top-level `packaging/` dir, pass `--import-mode=importlib` (the packaging-shadow gotcha). `concierge-api` uses its own `pyproject` (`pythonpath=["src"]`, `testpaths=["tests"]`).
- **Template conformance:** the template stays valid against `micro-app-template/0.1` (`docs/superpowers/specs/schemas/micro-app-template.schema.json`); re-validate with the skill scripts after every format/template change.
- **Phase-1 scope only:** the grant-license command facet (react to application `open` → DOI authority → issue `carrier_license` → revoke). **Out of plan (Phase 2):** aggregates, projections, workflows, the UEL evaluator, named-registry targeting beyond a single registry, witnessed-TEL issuance hardening.

---

## Group dependencies

- **G0** (template format fix) and **G1** (keri_serviceaid substrate) are independent and lead.
- **G2** (loader) depends on G0 (reads the structured `authz`) and G1 (binds revoke + credential gate).
- **G3** (CLIs) wraps G2.
- **G4** (integration test) ties everything together and is the acceptance gate.

---

## Group 0 — Template format fix (BE-KERI-NATIVE correction)

Add a KERI-native structured `authz` field; remove the vestigial `idempotency_key_expression` (the runtime already dedups on the exn SAID — `pipeline.process` uses `serder.said`); keep the wire-facing format implementation-agnostic. Repos: `locksmith-micro-app-designer` (schema + skill + reference) and `ugard` (adopted template).

### Task G0.1: Add a structured `authz` field to the template schema

**Files:**
- Modify: `locksmith-micro-app-designer/docs/superpowers/specs/schemas/micro-app-template.schema.json`
- Test: `locksmith-micro-app-designer/tests/micro_app_template/test_authz_field.py` (Create)

**Interfaces:**
- Produces: a JSON-Schema definition `authz` usable on `commands[]` and `reactions[]`: `{"method": "open"|"aid"|"allowlist"|"credential", "aid"?: str, "aids"?: [str], "schema_said"?: str, "issuer"?: str}` with `method` required and `additionalProperties:false`.

- [ ] **Step 1: Write the failing test**

```python
# tests/micro_app_template/test_authz_field.py
import json, pathlib, jsonschema
SCHEMA = json.loads(pathlib.Path("docs/superpowers/specs/schemas/micro-app-template.schema.json").read_text())

def _defs():
    return SCHEMA.get("$defs", SCHEMA.get("definitions", {}))

def test_authz_open_validates():
    authz = _defs()["authz"]
    jsonschema.validate({"method": "open"}, authz)

def test_authz_credential_requires_schema_said():
    authz = _defs()["authz"]
    jsonschema.validate({"method": "credential", "schema_said": "EAAA"}, authz)

def test_authz_rejects_unknown_method():
    authz = _defs()["authz"]
    try:
        jsonschema.validate({"method": "nope"}, authz); assert False
    except jsonschema.ValidationError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template/test_authz_field.py -q --import-mode=importlib`
Expected: FAIL (KeyError: `authz` not in `$defs`).

- [ ] **Step 3: Add the `authz` definition + reference it from command/reaction**

Add to `$defs` in the schema:

```json
"authz": {
  "type": "object",
  "additionalProperties": false,
  "required": ["method"],
  "properties": {
    "method": {"enum": ["open", "aid", "allowlist", "credential"]},
    "aid": {"type": "string"},
    "aids": {"type": "array", "items": {"type": "string"}},
    "schema_said": {"type": "string"},
    "issuer": {"type": "string"}
  }
}
```

Add `"authz": {"$ref": "#/$defs/authz"}` to the `properties` of the command object and the reaction object (do NOT mark required — fail-closed is enforced by the loader, not the schema; an absent `authz` means "not externally invocable").

- [ ] **Step 4: Run test to verify it passes**

Run: `cd locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template/test_authz_field.py -q --import-mode=importlib`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/schemas/micro-app-template.schema.json tests/micro_app_template/test_authz_field.py
git commit -m "feat(template): add KERI-native structured authz field (open/aid/allowlist/credential)"
```

### Task G0.2: Remove the vestigial `idempotency_key_expression`

**Files:**
- Modify: `locksmith-micro-app-designer/docs/superpowers/specs/schemas/micro-app-template.schema.json`
- Test: `locksmith-micro-app-designer/tests/micro_app_template/test_idempotency_removed.py` (Create)

**Rationale (BE-KERI-NATIVE scorecard ⚠️):** `keri_serviceaid/pipeline.py` already dedups on the exn SAID (`said = serder.said`; `idempotency.seen(said)`/`record(said, grant)`). The template's `idempotency_key_expression: hash(payload…)` is a *computed* key the runtime never reads. Remove it; message-SAID dedup is the native behavior.

- [ ] **Step 1: Write the failing test**

```python
# tests/micro_app_template/test_idempotency_removed.py
import json, pathlib
SCHEMA = json.loads(pathlib.Path("docs/superpowers/specs/schemas/micro-app-template.schema.json").read_text())

def test_idempotency_key_expression_is_not_a_command_property():
    cmd = SCHEMA["$defs"]["command"] if "command" in SCHEMA.get("$defs", {}) else None
    assert cmd is not None
    assert "idempotency_key_expression" not in cmd.get("properties", {})
    assert cmd.get("additionalProperties") is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd locksmith-micro-app-designer && ~/code/locksmith/.venv/bin/python -m pytest tests/micro_app_template/test_idempotency_removed.py -q --import-mode=importlib`
Expected: FAIL (`idempotency_key_expression` still present, or `additionalProperties` not false).

- [ ] **Step 3: Remove the property**

Delete the `idempotency_key_expression` key from the command object's `properties` in the schema. Confirm the command object has `"additionalProperties": false` so the field is now rejected.

- [ ] **Step 4: Run to verify it passes**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/schemas/micro-app-template.schema.json tests/micro_app_template/test_idempotency_removed.py
git commit -m "refactor(template): drop idempotency_key_expression (runtime dedups on exn SAID — native)"
```

### Task G0.3: Migrate the adopted reference template + re-validate

**Files:**
- Modify: `ugard/docs/micro-apps/regulator-grants-carrier-license/micro-app-template.json`
- Modify: `locksmith-micro-app-designer/skills/micro-app-template-gen/references/examples/regulator-grants-carrier-license/micro-app-template.json` (keep skill example in lockstep)

**Interfaces:**
- Produces: each command/reaction carries an explicit `authz` (the carrier-application reaction → `{"method":"open"}`; `grant_license`/`revoke_license` → `{"method":"open"}` for v1, since the DOI's authority is intrinsic and v1 demo runs the DOI as the bound role). No `idempotency_key_expression` anywhere.

- [ ] **Step 1: Edit both template copies** — add `"authz": {"method": "open"}` to each command and to each reaction's object; delete every `"idempotency_key_expression": …` line.

- [ ] **Step 2: Re-saidify (the edits changed `d`)**

```bash
PLUGIN=~/.claude/plugins/cache/locksmith-micro-app-designer/micro-app-template-gen/0.1.0
PYTHONPATH="$PLUGIN/src" ~/code/locksmith/.venv/bin/python "$PLUGIN/scripts/micro_app_saidify.py" \
  --input ~/code/ugard/docs/micro-apps/regulator-grants-carrier-license/micro-app-template.json --in-place
```
Expected: rewrites `d` to the new SAID, exit 0.

- [ ] **Step 3: Validate**

```bash
PYTHONPATH="$PLUGIN/src" ~/code/locksmith/.venv/bin/python "$PLUGIN/scripts/micro_app_validate.py" \
  --input ~/code/ugard/docs/micro-apps/regulator-grants-carrier-license/micro-app-template.json
PYTHONPATH="$PLUGIN/src" ~/code/locksmith/.venv/bin/python "$PLUGIN/scripts/micro_app_saidify.py" \
  --input ~/code/ugard/docs/micro-apps/regulator-grants-carrier-license/micro-app-template.json --verify
```
Expected: `OK: … validates …` and `OK: SAID matches`.

- [ ] **Step 4: Commit (two repos)**

```bash
cd ~/code/ugard && git add docs/micro-apps/regulator-grants-carrier-license && \
  git commit -m "refactor(micro-apps): structured authz + drop idempotency_key_expression on DOI template"
cd ~/code/locksmith-micro-app-designer && git add skills/micro-app-template-gen/references/examples && \
  git commit -m "refactor(skill): keep DOI example in lockstep with structured-authz format"
```

### Task G0.4: Update the skill's authoring guidance for `authz`

**Files:**
- Modify: `locksmith-micro-app-designer/skills/micro-app-template-gen/references/ten-step-process.md` (Step 4 Commands + Step 6 Reactions)
- Modify: `locksmith-micro-app-designer/skills/micro-app-template-gen/references/skeleton.json`

- [ ] **Step 1:** In `ten-step-process.md`, add to Step 4 and Step 6 a subsection: "Authorization (KERI-native): every externally-invocable command/reaction declares `authz`: `open` (any authenticated AID), `aid`/`allowlist` (specific AID(s)), or `credential` (`schema_said` [+ `issuer`]). Never express authorization as a UEL predicate — that is a defect (see BE-KERI-NATIVE). `auth_preconditions` are for *non-authz* validation only." Add `"authz": {"method": "open"}` to the command and reaction stanzas in `skeleton.json`.

- [ ] **Step 2: Commit**

```bash
git add skills/micro-app-template-gen/references/ten-step-process.md skills/micro-app-template-gen/references/skeleton.json
git commit -m "docs(skill): author authz KERI-natively; auth_preconditions are validation-only"
```

---

## Group 1 — `keri_serviceaid` substrate (keripy fork, branch `development`)

> Run keri_serviceaid tests with `~/code/locksmith/.venv/bin/python -m pytest ~/code/keripy/keri_serviceaid/tests/... --import-mode=importlib`. Create the tests dir if absent.

### Task G1.1: Characterize the credential gate (§6.2 — verify, do not rebuild)

**Files:**
- Test: `keripy/keri_serviceaid/tests/test_credgate.py` (Create)

**Rationale / API finding:** `providers/credgate.py::CredentialGate` is **already implemented** (intersects `reger.schms[schema]` ∩ `reger.subjs[sender]`, confirms `reger.saved`, re-checks TEL state) and `LocalRuntime` already wires it as the default authz. §6.2 is *verify + lock behavior with a test*, not build-from-scratch. This task pins it; if a gap surfaces, fix it here.

- [ ] **Step 1: Write the test** (fake reger exercising the gate's branches)

```python
# keripy/keri_serviceaid/tests/test_credgate.py
from types import SimpleNamespace
from keri_serviceaid.providers.credgate import CredentialGate
from keri_serviceaid.contract import ServiceAid, CredentialReq, Reply

def _svc():
    svc = ServiceAid(alias="doi")
    @svc.command(route="/x", issues="ESchemaX", requires_credential=CredentialReq(schema="ESchemaX"))
    def _fn(req): return Reply.none()
    return svc

class _FakeReger:
    def __init__(self, schms, subjs, saved, tever):
        self._schms, self._subjs, self._saved, self._tever = schms, subjs, saved, tever
        self.tevers = {"REG": tever}
    @property
    def schms(self): return SimpleNamespace(get=lambda keys: self._schms)
    @property
    def subjs(self): return SimpleNamespace(get=lambda keys: self._subjs)
    @property
    def saved(self): return SimpleNamespace(get=lambda keys: self._saved.get(keys))
    def cloneCred(self, said): return (SimpleNamespace(issuer="EIss", regid="REG"), None, None, None)

def test_denies_when_no_held_credential():
    svc = _svc()
    reger = _FakeReger(schms=[], subjs=[], saved={}, tever=None)
    gate = CredentialGate(hby=None, reger=reger, svc=svc)
    req = SimpleNamespace(route="/x", sender="ECaller")
    allow, reason = gate.authorize(req)
    assert allow is False and "no held credential" in reason
```

- [ ] **Step 2: Run to verify** — first as a characterization (it should PASS against the existing impl): `~/code/locksmith/.venv/bin/python -m pytest keripy/keri_serviceaid/tests/test_credgate.py -q --import-mode=importlib`. Expected: PASS. If it FAILS, that is a real §6.2 gap — fix `credgate.py` minimally to satisfy the test, then re-run.

- [ ] **Step 3: Commit**

```bash
cd ~/code/keripy && git add keri_serviceaid/tests/test_credgate.py && \
  git commit -m "test(serviceaid): pin CredentialGate deny-path (§6.2 credential gate)"
```

### Task G1.2: Add `Reply.revoke` to the contract (§6.1)

**Files:**
- Modify: `keripy/keri_serviceaid/contract.py:39-51` (Reply classmethods)
- Test: `keripy/keri_serviceaid/tests/test_reply_revoke.py` (Create)

**Interfaces:**
- Produces: `Reply.revoke(*, recipient: str, credential_said: str, reason: str = "") -> Reply` returning `Reply(kind="revoke", recipient=recipient, attributes={"credential_said": credential_said}, reason=reason)`.

- [ ] **Step 1: Write the failing test**

```python
# keripy/keri_serviceaid/tests/test_reply_revoke.py
from keri_serviceaid.contract import Reply
def test_reply_revoke_shape():
    r = Reply.revoke(recipient="EHolder", credential_said="ECredSAID", reason="cause")
    assert r.kind == "revoke"
    assert r.recipient == "EHolder"
    assert r.attributes == {"credential_said": "ECredSAID"}
    assert r.reason == "cause"
```

- [ ] **Step 2: Run to verify it fails** — `... -m pytest keripy/keri_serviceaid/tests/test_reply_revoke.py -q --import-mode=importlib`. Expected: FAIL (`Reply has no attribute revoke`).

- [ ] **Step 3: Add the classmethod** to `Reply`:

```python
    @classmethod
    def revoke(cls, *, recipient: str, credential_said: str, reason: str = "") -> "Reply":
        return cls(kind="revoke", recipient=recipient,
                   attributes={"credential_said": credential_said}, reason=reason)
```

- [ ] **Step 4: Run to verify it passes** — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/code/keripy && git add keri_serviceaid/contract.py keri_serviceaid/tests/test_reply_revoke.py && \
  git commit -m "feat(serviceaid): Reply.revoke (§6.1 revoke kind)"
```

### Task G1.3: Add `revoke` to the Issuer + a revoke notice frame

**Files:**
- Modify: `keripy/keri_serviceaid/providers/issue.py` (add `IpexGrantIssuer.revoke` + helper)
- Test: `keripy/keri_serviceaid/tests/test_issue_revoke.py` (Create — runs against a real temp Habery + Regery)

**Interfaces:**
- Consumes: `Context(hby, hab, rgy, registry_name)` (issue.py:32); `rgy.registryByName(name)`; `registry.revoke(said=…, dt=…)`; `_complete(...)`.
- Produces: `IpexGrantIssuer.revoke(self, reply: Reply, ctx: Context) -> bytearray` — fires the TEL `rev` event for `reply.attributes["credential_said"]`, anchors it (`hab.interact`), completes via `_complete`, and returns a CESR `/ipex/grant`-style revocation notice (reuse `_frame_grant` semantics by cloning the now-revoked cred's latest TEL event). For v1 (no-backer registry) this completes in-process.

- [ ] **Step 1: Write the failing test** (real keripy stack; mirrors existing keri_serviceaid issue tests — use a temp Habery, no-backer registry, issue then revoke)

```python
# keripy/keri_serviceaid/tests/test_issue_revoke.py
import pytest
from keri_serviceaid.providers.issue import IpexGrantIssuer, Context, ensure_registry
from keri_serviceaid.contract import Reply
from keri.app import habbing
from keri.vdr import credentialing

def _stack():
    hby = habbing.Habery(name="rev", temp=True, free=True)
    hab = hby.makeHab(name="rev", transferable=True, wits=[], toad=0,
                      isith="1", icount=1, nsith="1", ncount=1)
    rgy = credentialing.Regery(hby=hby, name="rev")
    ensure_registry(hby, hab, rgy, name="rev")
    return hby, hab, rgy

SCHEMA = "EBfdlu8R27Fbx-ehrqwImnK-8Cm79sqbAQ4MmvEAYqao"  # any registered schema SAID

def test_revoke_marks_tel_revoked(tmp_path):
    hby, hab, rgy = _stack()
    # register a trivial schema so Credentialer.create can validate
    from keri.core import scheming
    from keri.kering import Kinds
    sed = {"$id": "", "$schema": "https://json-schema.org/draft/2020-12/schema",
           "type": "object", "properties": {"d": {"type": "string"},
           "i": {"type": "string"}, "a": {"type": "object"}}}
    schemer = scheming.Schemer(sed=sed, kind=Kinds.json)
    hby.db.schema.pin(keys=(schemer.said,), val=schemer)
    iss = IpexGrantIssuer()
    ctx = Context(hby=hby, hab=hab, rgy=rgy, registry_name="rev")
    grant = iss.issue(Reply(kind="acdc", recipient=hab.pre, attributes={"a": 1},
                            schema_said=schemer.said), ctx)
    assert grant  # issued
    # capture the issued cred SAID from the registry, then revoke it
    reg = rgy.registryByName("rev")
    said = [s for s in rgy.reger.schms.get(keys=schemer.said.encode())][0].qb64
    out = iss.revoke(Reply.revoke(recipient=hab.pre, credential_said=said), ctx)
    assert out
    tever = rgy.reger.tevers[reg.regk]
    from keri.kering import Ilks
    assert tever.vcState(said).et in (Ilks.rev, Ilks.brv)
```

- [ ] **Step 2: Run to verify it fails** — `~/code/locksmith/.venv/bin/python -m pytest keripy/keri_serviceaid/tests/test_issue_revoke.py -q --import-mode=importlib`. Expected: FAIL (`IpexGrantIssuer has no attribute revoke`).

- [ ] **Step 3: Implement `revoke`** in `issue.py` (mirrors the issue path):

```python
    def revoke(self, reply, ctx) -> bytearray:
        from keri.core import eventing, serdering
        from keri.app import grouping
        from keri.vdr import credentialing, verifying
        said = reply.attributes["credential_said"]
        registry = ctx.rgy.registryByName(ctx.registry_name)
        rserder = registry.revoke(said=said)
        rseal = eventing.SealEvent(rserder.pre, rserder.snh, rserder.said)
        rseal = dict(i=rseal.i, s=rseal.s, d=rseal.d)
        anc = ctx.hab.interact(data=[rseal])
        aserder = serdering.SerderKERI(raw=bytes(anc))
        counselor = grouping.Counselor(hby=ctx.hby)
        registrar = credentialing.Registrar(hby=ctx.hby, rgy=ctx.rgy, counselor=counselor)
        registrar.revoke(creder=ctx.rgy.reger.cloneCreds([said])[0], serder=rserder, anc=aserder)
        _complete(ctx.rgy, registrar, rserder.pre, rserder.sn)
        return _frame_revoke(ctx.hby, ctx.hab, ctx.rgy, said, reply.recipient)
```

Add `_frame_revoke` mirroring `_frame_grant` but cloning the `rev` TEL event (use `rgy.reger.cloneTvtAt(said)` for the latest TEL event and `protocoling.ipexGrantExn(... iss=<rev event> ...)` as the carrier observes the revocation via its watcher/mailbox). If `Registrar.revoke`'s exact signature differs, adapt to the signature in `keripy/src/keri/vdr/credentialing.py` (read it first) — **do not invent it**.

- [ ] **Step 4: Run to verify it passes** — Expected: PASS (TEL state is `rev`).

- [ ] **Step 5: Commit**

```bash
cd ~/code/keripy && git add keri_serviceaid/providers/issue.py keri_serviceaid/tests/test_issue_revoke.py && \
  git commit -m "feat(serviceaid): IpexGrantIssuer.revoke + revoke notice frame (§6.1)"
```

### Task G1.4: Pipeline branch for `kind == "revoke"`

**Files:**
- Modify: `keripy/keri_serviceaid/pipeline.py:66-80` (the branch block)
- Test: `keripy/keri_serviceaid/tests/test_pipeline_revoke.py` (Create — fake providers, asserts issuer.revoke called + recorded + delivered)

**Interfaces:**
- Consumes: `Reply.revoke` (G1.2), `IpexGrantIssuer.revoke` (G1.3).
- Produces: in `process`, when `reply.kind == "revoke"`: `notice = svc.issuer.revoke(reply, ctx)`; `svc.idempotency.record(said, notice)` (before deliver, exactly-once); `svc.deliverer.deliver(notice, endpoint, ctx)`.

- [ ] **Step 1: Write the failing test** using fakes for verifier/authz/idempotency/issuer/deliverer/resolver, a ServiceAid with one `revoke` command whose fn returns `Reply.revoke(...)`, and a minimal `serder`/`state` stub (mirror the pattern any existing `test_pipeline*.py` uses; if none exists, build a `SimpleNamespace` serder with `.ked` and `.said`). Assert `fake_issuer.revoke` was called once and `fake_deliverer.deliver` got its return value.

```python
# sketch of the assertion core
def test_pipeline_revoke_path(monkeypatch):
    calls = {}
    # ... build state.svc with fakes; fake issuer.revoke returns b"NOTICE"
    # fn returns Reply.revoke(recipient="EH", credential_said="EC")
    from keri_serviceaid import pipeline
    pipeline.process(state, serder, attachments=[])
    assert calls["revoke"] == 1
    assert calls["delivered"] == b"NOTICE"
    assert calls["recorded_said"] == serder.said   # native: dedup on exn SAID
```

- [ ] **Step 2: Run to verify it fails** — Expected: FAIL (revoke not delivered; falls into the "no reply" branch).

- [ ] **Step 3: Add the branch** in `pipeline.process`, after the `acdc` branch:

```python
    if reply.kind == "revoke":
        ctx = Context(hby=state.hby, hab=state.hab, rgy=state.rgy,
                      registry_name=state.cfg.alias)
        notice = svc.issuer.revoke(reply, ctx)
        svc.idempotency.record(said, notice)
        endpoint = svc.resolver.resolve(sender, state.hby)
        svc.deliverer.deliver(notice, endpoint, ctx)
        logger.info("revoked + delivered notice for %s to %s", said, endpoint.eid)
        return
```

- [ ] **Step 4: Run to verify it passes** — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/code/keripy && git add keri_serviceaid/pipeline.py keri_serviceaid/tests/test_pipeline_revoke.py && \
  git commit -m "feat(serviceaid): pipeline revoke branch (§6.1) — record on exn SAID, then deliver"
```

---

## Group 2 — The loader (`concierge-api`)

> New package `concierge_api_local.loader`. Unit tests use `keri_serviceaid.TestRuntime` (no keripy stack). Run: `cd ~/code/concierge-api && ~/code/locksmith/.venv/bin/python -m pytest -q`. **Risk to clear first:** confirm `import keri_serviceaid` works under that venv; if not, add the keripy-fork root to `concierge-api/pyproject.toml`'s `[tool.pytest.ini_options] pythonpath`.

### Task G2.1: `DeployManifest` model

**Files:**
- Create: `concierge-api/src/concierge_api_local/loader/__init__.py`
- Create: `concierge-api/src/concierge_api_local/loader/manifest.py`
- Test: `concierge-api/tests/loader/test_manifest.py`

**Interfaces:**
- Produces: `@dataclass DeployManifest(role_aid: str, alias: str, witnesses: list[str], toad: int, compute: dict[str,str], schema_saids: dict[str,str], egf_acceptable_saids: list[str], oobis: list[str])` + `DeployManifest.from_json(path) -> DeployManifest`. `compute` maps a command route → a `"module:attr"` entry-point; `schema_saids` maps an export credential id → its schema SAID.

- [ ] **Step 1: Write the failing test**

```python
# tests/loader/test_manifest.py
import json
from concierge_api_local.loader.manifest import DeployManifest

def test_from_json(tmp_path):
    p = tmp_path / "deploy.json"
    p.write_text(json.dumps({
        "role_aid": "EDoiAID", "alias": "state-doi", "witnesses": [], "toad": 0,
        "compute": {"/insurance/cmd/submit_application": "doi_compute:grant"},
        "schema_saids": {"carrier_license": "ENRy4fo74JoBf2_1K2Olx1WJ6UqY_v98Y8S_qnw2GuDR"},
        "egf_acceptable_saids": ["ENRy4fo74JoBf2_1K2Olx1WJ6UqY_v98Y8S_qnw2GuDR"], "oobis": []}))
    m = DeployManifest.from_json(str(p))
    assert m.alias == "state-doi"
    assert m.compute["/insurance/cmd/submit_application"] == "doi_compute:grant"
    assert m.schema_saids["carrier_license"].startswith("E")
```

- [ ] **Step 2: Run to verify it fails** — `cd ~/code/concierge-api && ~/code/locksmith/.venv/bin/python -m pytest tests/loader/test_manifest.py -q`. Expected: FAIL (module not found).

- [ ] **Step 3: Implement** `manifest.py`:

```python
from __future__ import annotations
import json
from dataclasses import dataclass, field

@dataclass
class DeployManifest:
    role_aid: str
    alias: str
    witnesses: list[str] = field(default_factory=list)
    toad: int = 0
    compute: dict[str, str] = field(default_factory=dict)
    schema_saids: dict[str, str] = field(default_factory=dict)
    egf_acceptable_saids: list[str] = field(default_factory=list)
    oobis: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, path: str) -> "DeployManifest":
        with open(path, encoding="utf-8") as f:
            return cls(**json.load(f))
```
(Empty `loader/__init__.py`.)

- [ ] **Step 4: Run to verify it passes** — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/code/concierge-api && git add src/concierge_api_local/loader tests/loader && \
  git commit -m "feat(loader): DeployManifest model"
```

### Task G2.2: Structured-authz → provider binding

**Files:**
- Create: `concierge-api/src/concierge_api_local/loader/authz_map.py`
- Test: `concierge-api/tests/loader/test_authz_map.py`

**Interfaces:**
- Consumes: a command/reaction's `authz` dict (G0).
- Produces: `bind_authz(authz: dict, *, schema_saids: dict) -> tuple[Optional[CredentialReq], list[str]]` returning `(requires_credential, allowlist_aids)`. `open` → `(None, [])`; `aid` → `(None, [authz["aid"]])`; `allowlist` → `(None, authz["aids"])`; `credential` → `(CredentialReq(schema=resolve(authz["schema_said"]), issuer=authz.get("issuer")), [])`. Fail-closed: a missing/None `authz` raises `ValueError("command <route> has no authz; fail-closed")`.

- [ ] **Step 1: Write the failing test**

```python
# tests/loader/test_authz_map.py
import pytest
from concierge_api_local.loader.authz_map import bind_authz
from keri_serviceaid.contract import CredentialReq

def test_open(): assert bind_authz({"method": "open"}, schema_saids={}) == (None, [])
def test_allowlist(): assert bind_authz({"method": "allowlist", "aids": ["EA","EB"]}, schema_saids={}) == (None, ["EA","EB"])
def test_credential():
    req, aids = bind_authz({"method": "credential", "schema_said": "ES"}, schema_saids={})
    assert isinstance(req, CredentialReq) and req.schema == "ES" and aids == []
def test_fail_closed():
    with pytest.raises(ValueError): bind_authz(None, schema_saids={})
```

- [ ] **Step 2: Run to verify it fails.** Expected: FAIL (module not found).

- [ ] **Step 3: Implement** `authz_map.py`:

```python
from __future__ import annotations
from typing import Optional
from keri_serviceaid.contract import CredentialReq

def bind_authz(authz: Optional[dict], *, schema_saids: dict) -> tuple[Optional[CredentialReq], list[str]]:
    if not authz or "method" not in authz:
        raise ValueError("command has no authz; fail-closed")
    m = authz["method"]
    if m == "open":
        return None, []
    if m == "aid":
        return None, [authz["aid"]]
    if m == "allowlist":
        return None, list(authz["aids"])
    if m == "credential":
        return CredentialReq(schema=authz["schema_said"], issuer=authz.get("issuer")), []
    raise ValueError(f"unknown authz method {m!r}")
```

- [ ] **Step 4: Run to verify it passes.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/code/concierge-api && git add src/concierge_api_local/loader/authz_map.py tests/loader/test_authz_map.py && \
  git commit -m "feat(loader): KERI-native structured-authz -> Allowlist/CredentialReq (fail-closed)"
```

### Task G2.3: Compute entry-point binding

**Files:**
- Create: `concierge-api/src/concierge_api_local/loader/compute.py`
- Test: `concierge-api/tests/loader/test_compute.py`

**Interfaces:**
- Produces: `load_compute(ref: str) -> Callable[[Request], Reply]` — imports `module:attr` (Decision B local entry-point); raises `ValueError` on a malformed ref and `TypeError` if the attr is not callable.

- [ ] **Step 1: Write the failing test**

```python
# tests/loader/test_compute.py
import pytest
from concierge_api_local.loader.compute import load_compute

def test_loads_callable():
    fn = load_compute("json:dumps")
    assert callable(fn)

def test_bad_ref():
    with pytest.raises(ValueError): load_compute("noattrhere")
```

- [ ] **Step 2: Run to verify it fails.** Expected: FAIL.

- [ ] **Step 3: Implement** `compute.py`:

```python
from __future__ import annotations
import importlib
from typing import Callable

def load_compute(ref: str) -> Callable:
    if ":" not in ref:
        raise ValueError(f"compute ref must be 'module:attr', got {ref!r}")
    module_name, attr = ref.split(":", 1)
    fn = getattr(importlib.import_module(module_name), attr)
    if not callable(fn):
        raise TypeError(f"{ref} is not callable")
    return fn
```

- [ ] **Step 4: Run to verify it passes.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/code/concierge-api && git add src/concierge_api_local/loader/compute.py tests/loader/test_compute.py && \
  git commit -m "feat(loader): compute entry-point binding (module:attr, Decision B)"
```

### Task G2.4: SAID lockfile (§4.4)

**Files:**
- Create: `concierge-api/src/concierge_api_local/loader/lockfile.py`
- Test: `concierge-api/tests/loader/test_lockfile.py`

**Interfaces:**
- Produces: `build_lockfile(*, template_said: str, schema_saids: list[str], compute: dict[str,str], witness_oobis: list[str], role_aid: str, egf_acceptable_saids: list[str]) -> dict` — a dict with those fields plus a `d` SAID computed via `coring.Saider.saidify(sad=…, label="d")`. Deterministic (sorts lists).

- [ ] **Step 1: Write the failing test**

```python
# tests/loader/test_lockfile.py
from concierge_api_local.loader.lockfile import build_lockfile

def test_lockfile_is_saidified_and_deterministic():
    args = dict(template_said="ET", schema_saids=["ES2","ES1"], compute={"/r":"m:a"},
                witness_oobis=[], role_aid="EDoi", egf_acceptable_saids=["ES1"])
    a = build_lockfile(**args); b = build_lockfile(**args)
    assert a["d"].startswith("E") and a["d"] == b["d"]
    assert a["schema_saids"] == ["ES1","ES2"]   # sorted -> deterministic
```

- [ ] **Step 2: Run to verify it fails.** Expected: FAIL.

- [ ] **Step 3: Implement** `lockfile.py`:

```python
from __future__ import annotations

def build_lockfile(*, template_said, schema_saids, compute, witness_oobis,
                   role_aid, egf_acceptable_saids) -> dict:
    from keri.core import coring
    from keri.kering import Kinds
    sad = {
        "d": "",
        "template_said": template_said,
        "role_aid": role_aid,
        "schema_saids": sorted(schema_saids),
        "compute": dict(sorted(compute.items())),
        "witness_oobis": sorted(witness_oobis),
        "egf_acceptable_saids": sorted(egf_acceptable_saids),
    }
    _, out = coring.Saider.saidify(sad=sad, kind=Kinds.json, label="d")
    return out
```

- [ ] **Step 4: Run to verify it passes.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/code/concierge-api && git add src/concierge_api_local/loader/lockfile.py tests/loader/test_lockfile.py && \
  git commit -m "feat(loader): SAID lockfile = content-addressed build identity (§4.4)"
```

### Task G2.5: The compiler — `load(template, deploy) -> ServiceAid`

**Files:**
- Create: `concierge-api/src/concierge_api_local/loader/load.py`
- Test: `concierge-api/tests/loader/test_load.py`

**Interfaces:**
- Consumes: `DeployManifest` (G2.1), `bind_authz` (G2.2), `load_compute` (G2.3), `keri_serviceaid.ServiceAid`, `keri_serviceaid.contract.{Request,Reply,CredentialReq}`, `keri_serviceaid.TestRuntime`.
- Produces: `load(template: dict, deploy: DeployManifest) -> tuple[ServiceAid, dict]` returning `(svc, lockfile)`. For each template **command** whose route also appears in `deploy.compute`, register one `svc.command(route, issues=<the export schema SAID for the command's emitted credential>, payload_schema=<command.payload_schema>, requires_credential=<from authz>)` whose `fn = load_compute(deploy.compute[route])`. Empty-allowlist commands get `svc` default authz; non-empty allowlists are recorded on the svc via a `loader_allowlist` attribute consumed at hosting time (Phase-1: pass `base_authz` to `LocalRuntime`). Register each export schema via `svc.register_schema`. The collapsed reaction+command rule: a template command bound in `deploy.compute` IS the inbound handler (its route is the inbound exn route); the template's separate reaction is informational in Phase-1.

- [ ] **Step 1: Write the failing test** (pure, via `TestRuntime`)

```python
# tests/loader/test_load.py
import json, pathlib
from concierge_api_local.loader.load import load
from concierge_api_local.loader.manifest import DeployManifest
from keri_serviceaid.contract import TestRuntime, Reply

# a tiny compute entry-point importable by the test
import sys, types
mod = types.ModuleType("doi_compute_test")
def grant(req): return Reply.acdc(recipient=req.sender, attributes={"license_number": "X"})
mod.grant = grant
sys.modules["doi_compute_test"] = mod

def test_load_registers_command_and_runs_compute():
    template = {"header": {"id": "regulator-grants-carrier-license"},
        "credentials": {"exports": [{"id": "carrier_license",
            "schema": {"schema_said": "ENRy4fo74JoBf2_1K2Olx1WJ6UqY_v98Y8S_qnw2GuDR"}}], "imports": []},
        "commands": [{"id": "grant_license", "route": "/insurance/cmd/submit_application",
            "authz": {"method": "open"}, "emissions": [{"kind": "exchange",
            "exchange": {"exported_credential_id": "carrier_license", "verb": "grant"}}]}],
        "reactions": [], "d": "ETEMPLATE"}
    deploy = DeployManifest(role_aid="EDoi", alias="state-doi",
        compute={"/insurance/cmd/submit_application": "doi_compute_test:grant"},
        schema_saids={"carrier_license": "ENRy4fo74JoBf2_1K2Olx1WJ6UqY_v98Y8S_qnw2GuDR"})
    svc, lock = load(template, deploy)
    assert "/insurance/cmd/submit_application" in svc.routes
    rt = TestRuntime(svc)
    reply = rt.send(route="/insurance/cmd/submit_application", sender="ECarrier", payload={})
    assert reply.kind == "acdc" and reply.recipient == "ECarrier"
    assert lock["d"].startswith("E")
```

- [ ] **Step 2: Run to verify it fails.** Expected: FAIL (module not found).

- [ ] **Step 3: Implement** `load.py`:

```python
from __future__ import annotations
from keri_serviceaid.contract import ServiceAid
from .authz_map import bind_authz
from .compute import load_compute
from .lockfile import build_lockfile

def _export_schema_for(template, command) -> tuple[str, str]:
    """(export_credential_id, schema_said) emitted by this command, or ('','')."""
    for em in command.get("emissions", []):
        if em.get("kind") == "exchange":
            cid = em.get("exchange", {}).get("exported_credential_id")
            if cid:
                for ex in template["credentials"]["exports"]:
                    if ex["id"] == cid:
                        return cid, ex["schema"]["schema_said"]
    return "", ""

def load(template: dict, deploy) -> tuple[ServiceAid, dict]:
    svc = ServiceAid(alias=deploy.alias, witnesses=deploy.witnesses, toad=deploy.toad)
    issued_saids: list[str] = []
    allowlist_aids: list[str] = []
    for cmd in template.get("commands", []):
        route = cmd["route"]
        if route not in deploy.compute:
            continue                       # only routes the deploy binds are live handlers
        _cid, schema_said = _export_schema_for(template, cmd)
        if schema_said:
            issued_saids.append(schema_said)
        req_cred, aids = bind_authz(cmd.get("authz"), schema_saids=deploy.schema_saids)
        allowlist_aids.extend(aids)
        fn = load_compute(deploy.compute[route])
        svc.command(route=route, issues=schema_said,
                    payload_schema=cmd.get("payload_schema"),
                    requires_credential=req_cred)(fn)
    svc.loader_allowlist = allowlist_aids          # consumed by the host (LocalRuntime base_authz)
    lock = build_lockfile(template_said=template.get("d", ""),
                          schema_saids=sorted(set(issued_saids)),
                          compute=dict(deploy.compute), witness_oobis=deploy.oobis,
                          role_aid=deploy.role_aid,
                          egf_acceptable_saids=deploy.egf_acceptable_saids)
    return svc, lock
```

- [ ] **Step 4: Run to verify it passes.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/code/concierge-api && git add src/concierge_api_local/loader/load.py tests/loader/test_load.py && \
  git commit -m "feat(loader): load(template, deploy) -> (ServiceAid, lockfile) — pure compiler"
```

### Task G2.6: The DOI compute entry-point (the bound `fn`)

**Files:**
- Create: `concierge-api/src/concierge_api_local/computes/doi.py`
- Test: `concierge-api/tests/loader/test_doi_compute.py`

**Interfaces:**
- Produces: `grant(req: Request) -> Reply` — builds the `carrier_license` attributes from the application payload and returns `Reply.acdc(recipient=req.sender, attributes={...})`; `revoke(req: Request) -> Reply` returns `Reply.revoke(recipient=req.sender, credential_said=req.payload["license_said"], reason=req.payload.get("revocation_reason",""))`. This is the only domain-specific code; it computes over the request and emits a native Reply.

- [ ] **Step 1: Write the failing test**

```python
# tests/loader/test_doi_compute.py
from concierge_api_local.computes.doi import grant, revoke
from keri_serviceaid.contract import Request

def test_grant_builds_license_acdc():
    req = Request(sender="ECarrier", route="/insurance/cmd/submit_application",
                  payload={"license_number": "P-1", "jurisdiction": "US-UT",
                           "lines_of_business": ["property"]})
    r = grant(req)
    assert r.kind == "acdc" and r.recipient == "ECarrier"
    assert r.attributes["license_number"] == "P-1"

def test_revoke_returns_revoke_reply():
    req = Request(sender="ECarrier", route="/insurance/cmd/revoke_license",
                  payload={"license_said": "ECred", "revocation_reason": "cause"})
    r = revoke(req)
    assert r.kind == "revoke" and r.attributes["credential_said"] == "ECred"
```

- [ ] **Step 2: Run to verify it fails.** Expected: FAIL.

- [ ] **Step 3: Implement** `computes/doi.py`:

```python
from __future__ import annotations
from keri_serviceaid.contract import Request, Reply

def grant(req: Request) -> Reply:
    p = req.payload
    return Reply.acdc(recipient=req.sender, attributes={
        "license_number": p.get("license_number"),
        "jurisdiction": p.get("jurisdiction"),
        "lines_of_business": p.get("lines_of_business", []),
        "effective_date": p.get("effective_date"),
        "expiration_date": p.get("expiration_date"),
    })

def revoke(req: Request) -> Reply:
    p = req.payload
    return Reply.revoke(recipient=req.sender, credential_said=p["license_said"],
                        reason=p.get("revocation_reason", ""))
```

- [ ] **Step 4: Run to verify it passes.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/code/concierge-api && git add src/concierge_api_local/computes tests/loader/test_doi_compute.py && \
  git commit -m "feat(computes): DOI grant/revoke entry-points (Request -> native Reply)"
```

---

## Group 3 — CLIs (`concierge-api`)

> Thin argparse CLIs over the loader + the existing `BindingController`. Console scripts added to `pyproject.toml [project.scripts]`.

### Task G3.1: `said saidify`

**Files:**
- Create: `concierge-api/src/concierge_api_local/cli/said.py`
- Modify: `concierge-api/pyproject.toml` (`[project.scripts] said = "concierge_api_local.cli.said:main"`)
- Test: `concierge-api/tests/cli/test_said.py`

**Interfaces:**
- Produces: `main(argv=None) -> int`; `said saidify <file> [--label d]` prints the SAID and (with `--in-place`) writes `label` into the file. Uses `coring.Saider.saidify`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_said.py
import json
from concierge_api_local.cli.said import main

def test_saidify_prints_said(tmp_path, capsys):
    p = tmp_path / "x.json"; p.write_text(json.dumps({"d": "", "a": 1}))
    rc = main(["saidify", str(p)])
    out = capsys.readouterr().out.strip()
    assert rc == 0 and out.startswith("E")
```

- [ ] **Step 2: Run to verify it fails.** Expected: FAIL.

- [ ] **Step 3: Implement** `cli/said.py` (argparse; `saidify` subcommand reads JSON, calls `coring.Saider.saidify(sad=…, label=args.label)`, prints `out[args.label]`, writes back if `--in-place`).

- [ ] **Step 4: Run to verify it passes.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/code/concierge-api && git add src/concierge_api_local/cli/said.py tests/cli/test_said.py pyproject.toml && \
  git commit -m "feat(cli): said saidify (wraps keripy Saider)"
```

### Task G3.2: `micro-app build` (+ `bind`, `call` scaffolding)

**Files:**
- Create: `concierge-api/src/concierge_api_local/cli/microapp.py`
- Modify: `concierge-api/pyproject.toml` (`micro-app = "concierge_api_local.cli.microapp:main"`)
- Test: `concierge-api/tests/cli/test_microapp_build.py`

**Interfaces:**
- Produces: `main(argv) -> int`. `micro-app build --template <t.json> --deploy <d.json> --out <lock.json>` loads the template + manifest, calls `load(...)`, writes the lockfile to `--out`, prints the lockfile SAID. `bind`/`call` subcommands defined here delegate to `BindingController` (local hosting) — `bind` is exercised in G4 against a real vault; `build` is unit-testable headless.

- [ ] **Step 1: Write the failing test** (build is pure — no keripy stack needed)

```python
# tests/cli/test_microapp_build.py
import json, types, sys
from concierge_api_local.cli.microapp import main

def test_build_writes_lockfile(tmp_path, capsys):
    m = types.ModuleType("c2"); m.grant = lambda req: None; sys.modules["c2"] = m
    tpl = tmp_path/"t.json"; tpl.write_text(json.dumps({"header": {"id": "x"},
        "credentials": {"exports": [{"id": "carrier_license",
            "schema": {"schema_said": "ENRy4fo74JoBf2_1K2Olx1WJ6UqY_v98Y8S_qnw2GuDR"}}], "imports": []},
        "commands": [{"id": "g", "route": "/r", "authz": {"method": "open"},
            "emissions": [{"kind": "exchange", "exchange": {"exported_credential_id": "carrier_license"}}]}],
        "reactions": [], "d": "ET"}))
    dep = tmp_path/"d.json"; dep.write_text(json.dumps({"role_aid": "EDoi", "alias": "doi",
        "compute": {"/r": "c2:grant"}, "schema_saids": {"carrier_license": "ENRy4fo74JoBf2_1K2Olx1WJ6UqY_v98Y8S_qnw2GuDR"}}))
    out = tmp_path/"lock.json"
    rc = main(["build", "--template", str(tpl), "--deploy", str(dep), "--out", str(out)])
    assert rc == 0
    assert json.loads(out.read_text())["d"].startswith("E")
```

- [ ] **Step 2: Run to verify it fails.** Expected: FAIL.

- [ ] **Step 3: Implement** `cli/microapp.py`: argparse with `build` (reads template JSON + `DeployManifest.from_json`, calls `load`, writes lockfile, prints `lock["d"]`), and `bind`/`call` subcommands that import `BindingController` lazily and operate on a vault opened from `--vault-path` (real path only; covered by G4, not unit-tested headless).

- [ ] **Step 4: Run to verify it passes.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/code/concierge-api && git add src/concierge_api_local/cli/microapp.py tests/cli/test_microapp_build.py pyproject.toml && \
  git commit -m "feat(cli): micro-app build (loader) + bind/call scaffolding"
```

---

## Group 4 — Integration test (acceptance gate, §8)

### Task G4.1: Bash e2e — grant, verify, reject-unauthorized, revoke

**Files:**
- Create: `concierge-api/tests/integration/grant_license_e2e.sh`
- Create: `concierge-api/tests/integration/README.md`

**Interfaces:**
- Consumes: `kli` demo witnesses (`kli witness demo`), the `said`/`micro-app` CLIs (G3), the adopted template, the DOI compute (G2.6). Asserts via exit codes + `grep`; hermetic (temp keystores under `$TMPDIR`, cleaned in a `trap`).

- [ ] **Step 1: Write the test harness** as a bash script that:
  1. `trap 'kill $WIT_PID; rm -rf "$WORK"' EXIT`; `WORK=$(mktemp -d)`.
  2. Start demo witnesses: `kli witness demo &` `WIT_PID=$!`; wait for port readiness (`until nc -z localhost 5642; do sleep 0.2; done`).
  3. Create DOI + carrier AIDs via `kli init`/`kli incept` (salty, transferable) in `$WORK` keystores; resolve OOBIs both directions.
  4. Author a deploy manifest JSON binding `/insurance/cmd/submit_application` → `concierge_api_local.computes.doi:grant` and `/insurance/cmd/revoke_license` → `concierge_api_local.computes.doi:revoke`, `role_aid` = the DOI AID, witnesses = demo wits.
  5. `micro-app build --template <adopted> --deploy <manifest> --out lock.json`; assert `grep -q '"d": "E' lock.json`.
  6. `micro-app bind --vault-path $WORK/doi-vault --create-aid` then `micro-app build ... --host` to run the LocalRuntime on the bound DOI AID (host loop driven by RuntimePumpDoer for N ticks).
  7. **Grant:** carrier sends an `exn` on `/insurance/cmd/submit_application` (via `micro-app call --as carrier --route /insurance/cmd/submit_application --payload @app.json`); pump; assert the carrier received an `/ipex/grant` carrying a `carrier_license` (`grep` the carrier's mailbox/cred store; assert non-empty).
  8. **Reject unauthorized:** re-run with a command whose template `authz` is `{"method":"allowlist","aids":["<only the DOI>"]}` and a *different* sender; assert **no** grant delivered (`grep -c` == 0) and a log line `authorization denied`.
  9. **Revoke:** DOI calls `/insurance/cmd/revoke_license` with the issued `license_said`; pump; assert the credential's TEL state is `rev` (query via `kli vc list --revoked` or the reger).
  10. `echo "PASS"` and `exit 0` only if all asserts held.

```bash
#!/usr/bin/env bash
set -euo pipefail
WORK=$(mktemp -d); WIT_PID=""
trap '[ -n "$WIT_PID" ] && kill "$WIT_PID" 2>/dev/null || true; rm -rf "$WORK"' EXIT
# ... steps 2-9 as above, each with explicit assert + nonzero exit on failure ...
echo "PASS: grant + reject-unauthorized + revoke"
```

- [ ] **Step 2: Run to verify it fails** — `bash concierge-api/tests/integration/grant_license_e2e.sh; echo "exit=$?"`. Expected: FAIL (CLIs/host wiring incomplete) until G0–G3 land; this is the acceptance gate that turns green last.

- [ ] **Step 3: Make it pass** — implement any `micro-app call`/`--host` glue uncovered by the script (the script is the spec for that glue); iterate until `PASS` prints and `exit=0`.

- [ ] **Step 4: Commit**

```bash
cd ~/code/concierge-api && git add tests/integration && \
  git commit -m "test(integration): DOI grant/reject/revoke e2e — Phase-1 acceptance gate (§8)"
```

---

## Self-Review

**1. Spec coverage:** loader §4 (G2.5) ✓; §4.1 authz methods incl. `open` (G0.1, G2.2) ✓; §4.2 AID binding via BindingController (G3.2/G4) ✓; §4.4 SAID lockfile (G2.4) ✓; §5.2 local schema availability — `svc.register_schema` queues schemas; LocalRuntime/init pins them into `db.schema` (existing, exercised in G4) ✓; §6.1 registry revoke (G1.2–G1.4) ✓; §6.2 credential gate (G1.1, already implemented — verified) ✓; CLIs §7 (G3) ✓; integration test §8 (G4) ✓. **Phase-2 (aggregates/projections/workflows, named-registry targeting, UEL) correctly out of plan.** Gap accepted: §5.2 schema *registration into the local store* relies on existing `LocalRuntime`/`init` pinning (not a new task) — verified in G4, flagged if it regresses.

**2. Placeholder scan:** every code step has real code or a real command; no "TODO/handle errors/etc." The two places that say "adapt to the real signature" (G1.3 `Registrar.revoke`; G4 host glue) instruct reading the actual API first and are bounded, not placeholders.

**3. Type/signature consistency:** `load() -> (ServiceAid, dict)` consistent across G2.5/G3.2/G4; `bind_authz -> (Optional[CredentialReq], list[str])` consistent G2.2/G2.5; `Reply.revoke`/`IpexGrantIssuer.revoke`/pipeline branch consistent G1.2–G1.4; `DeployManifest` fields consistent G2.1/G2.5/G3.2/G4.
