# Concierge Local Runtime — keri_serviceaid core (Plan 1 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-wallet (`LocalRuntime`) adapter to `keri_serviceaid` — driving the existing `ServiceAid`/pipeline/providers against a wallet's LMDB `Habery` and one bound AID — plus the supporting `LMDBLedger`, `BoundResolver`, `CredentialGate`, and a `requires_credential` declaration on `@command`.

**Architecture:** `keri_serviceaid`'s `contract.py`/`pipeline.py` are substrate-agnostic; the cloud path is `runtime.py` (DynamoDB/Lambda). This plan adds the *local* sibling: a `LocalRuntime` that takes an already-resolved `(hby, hab, rgy)`, wires local-variant providers, registers per-route capture handlers on the wallet's `Exchanger`, and drains them through `pipeline.process`. Everything here is headless-testable against a temp `Habery` — no Qt, no wallet, no live mailbox. The wallet/plugin layer is Plan 2.

**Tech Stack:** Python 3.13+, keripy 2.0 (`keri.app.habbing`, `keri.vdr.credentialing`/`verifying`, `keri.db.subing`, `keri.peer.exchanging`, `keri.app.indirecting`), pytest. All work is in the `~/code/keripy` repo; package `keri_serviceaid/`, tests `tests/serviceaid/`.

**Conventions:**
- All commands run from `~/code/keripy`.
- Run a single test file with: `python -m pytest tests/serviceaid/<file> -v`
- Tests reuse the existing fixtures in `tests/serviceaid/conftest.py`: `issuer_hby` (temp `Habery`), `rating_schema` (saidified RATING schema → `(said, sad)`), `recipient_pre` (a transferable AID whose KEL is parsed into `issuer_hby`).
- New shared test schema lives in `tests/serviceaid/_schema.py` (already importable via the conftest `sys.path` shim).

---

## File Structure

**Created:**
- `keri_serviceaid/_capture.py` — the `_CaptureHandler` Exchanger behavior (extracted from `runtime.py` so both runtimes share it without `local_runtime` importing the DynamoDB-laden `runtime.py`).
- `keri_serviceaid/providers/credgate.py` — `CredentialGate` authorizer (present-then-cache enforcement).
- `keri_serviceaid/local_runtime.py` — `LocalCfg`, `LocalState`, `LocalRuntime`.
- `tests/serviceaid/test_providers_credgate.py`, `tests/serviceaid/test_local_runtime.py`.

**Modified:**
- `keri_serviceaid/providers/idempotency.py` — add `LMDBLedger`.
- `keri_serviceaid/contract.py` — add `CredentialReq` + `Command.requires_credential` + decorator param.
- `keri_serviceaid/providers/resolve.py` — add `BoundResolver`.
- `keri_serviceaid/providers/__init__.py` + `keri_serviceaid/__init__.py` — export the new names.
- `keri_serviceaid/runtime.py` — import `_CaptureHandler` from `_capture` (delete the inline copy).
- `tests/serviceaid/_schema.py` — add `BROKER_SCHEMA_SAD`.
- `tests/serviceaid/test_providers_idempotency.py` — add `LMDBLedger` tests.
- `tests/serviceaid/test_contract_v2.py` — add a `requires_credential` test.

---

### Task 1: `LMDBLedger` idempotency store

`DynamoLedger` already works over any `db` via `subing.Suber`; `LMDBLedger` is the LMDB-backed sibling the local runtime defaults to. A keripy `Baser` (`hby.db`) is an `LMDBer`, and `Suber(db=<LMDBer>, subkey="proc.")` opens its own named sub-db on it.

**Files:**
- Modify: `keri_serviceaid/providers/idempotency.py`
- Modify: `keri_serviceaid/providers/__init__.py`, `keri_serviceaid/__init__.py`
- Test: `tests/serviceaid/test_providers_idempotency.py`

- [ ] **Step 1: Write the failing test** — append to `tests/serviceaid/test_providers_idempotency.py`:

```python
from keri_serviceaid import LMDBLedger


def test_lmdb_unseen_returns_none(issuer_hby):
    assert LMDBLedger(issuer_hby.db).seen("ENeverSeen") is None


def test_lmdb_record_then_seen_roundtrips_grant_bytes(issuer_hby):
    led = LMDBLedger(issuer_hby.db)
    grant = b'{"v":"KERI10JSON","t":"exn"}-attachments'
    led.record("EReqSaid", grant)
    assert led.seen("EReqSaid") == grant


def test_lmdb_record_overwrites(issuer_hby):
    led = LMDBLedger(issuer_hby.db)
    led.record("EReqSaid", b"first")
    led.record("EReqSaid", b"second")
    assert led.seen("EReqSaid") == b"second"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/serviceaid/test_providers_idempotency.py -v -k lmdb`
Expected: FAIL — `ImportError: cannot import name 'LMDBLedger'`.

- [ ] **Step 3: Implement** — append to `keri_serviceaid/providers/idempotency.py`:

```python
class LMDBLedger:
    """Idempotency store on a keripy LMDB database (a Baser/LMDBer, e.g. hby.db).

    Same shape as DynamoLedger — both go through subing.Suber, which opens its own
    named sub-db on whatever LMDBer it is handed. Used by the local (in-wallet)
    runtime where storage is LMDB rather than DynamoDB.
    """

    def __init__(self, db):
        self.db = db
        self.proc = subing.Suber(db=db, subkey=PROC_STORE)

    def seen(self, said: str) -> bytes | None:
        raw = self.proc.get(keys=(said,))
        if raw is None:
            return None
        return raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)

    def record(self, said: str, grant: bytes) -> None:
        self.proc.pin(keys=(said,), val=bytes(grant))
```

- [ ] **Step 4: Export it.** In `keri_serviceaid/providers/__init__.py`, change the idempotency import + `__all__`:

```python
from .idempotency import IdempotencyStore, DynamoLedger, LMDBLedger
```
and add `"LMDBLedger"` to that file's `__all__`. In `keri_serviceaid/__init__.py`, add `LMDBLedger` to both the `from .providers import (...)` block and `__all__` (next to `DynamoLedger`).

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest tests/serviceaid/test_providers_idempotency.py -v -k lmdb`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add keri_serviceaid/providers/idempotency.py keri_serviceaid/providers/__init__.py keri_serviceaid/__init__.py tests/serviceaid/test_providers_idempotency.py
git commit -m "feat(serviceaid): LMDBLedger idempotency store for the local runtime"
```

---

### Task 2: `CredentialReq` + `@command(requires_credential=...)`

Per-command authorization is *declared* on `@command` (mirroring `issues`, which the Issuer consumes); `CredentialGate` (Task 5) enforces it. This task only adds the declaration.

**Files:**
- Modify: `keri_serviceaid/contract.py`
- Modify: `keri_serviceaid/__init__.py`
- Test: `tests/serviceaid/test_contract_v2.py`

- [ ] **Step 1: Write the failing test** — append to `tests/serviceaid/test_contract_v2.py`:

```python
from keri_serviceaid import ServiceAid, CredentialReq


def test_command_records_requires_credential():
    svc = ServiceAid(alias="rating-engine")

    @svc.command(route="/rate", issues="Equote",
                 requires_credential=CredentialReq(schema="Ebroker"))
    def rate(req):
        ...

    cmd = svc.lookup("/rate")
    assert cmd.requires_credential == CredentialReq(schema="Ebroker")
    assert cmd.requires_credential.presentation == "cache"
    assert cmd.requires_credential.cadence == "revocation-recheck"


def test_command_requires_credential_defaults_none():
    svc = ServiceAid(alias="rating-engine")

    @svc.command(route="/ping")
    def ping(req):
        ...

    assert svc.lookup("/ping").requires_credential is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/serviceaid/test_contract_v2.py -v -k requires_credential`
Expected: FAIL — `ImportError: cannot import name 'CredentialReq'`.

- [ ] **Step 3: Implement** — in `keri_serviceaid/contract.py`, add the dataclass above `class Command`:

```python
@dataclass(frozen=True)
class CredentialReq:
    """Per-command inbound credential requirement, enforced by CredentialGate.

    `schema` is the required ACDC schema SAID the caller must hold (as issuee).
    `issuer`, when set, additionally constrains who issued it. `presentation`
    and `cadence` are the declared ceremony policy (v1 default: present once via
    IPEX grant, cache, re-check TEL revocation per request)."""
    schema: str
    issuer: Optional[str] = None
    presentation: str = "cache"          # "cache" | "embed" | "thread"
    cadence: str = "revocation-recheck"
```

Add the field to `Command` (after `issues`):

```python
    fn: Callable[[Request], Reply]
    requires_credential: Optional[CredentialReq] = None
```

Update the decorator signature and the `Command(...)` construction inside `command`:

```python
    def command(self, *, route: str, issues: str = "",
                payload_schema: dict | None = None,
                requires_credential: Optional["CredentialReq"] = None):
        if route.startswith("/ipex/"):
            raise ValueError(f"route {route!r} is reserved: /ipex/* is owned by "
                             "the IPEX protocol and may not be a command route")

        def deco(fn: Callable[[Request], Reply]):
            if route in self._commands:
                raise ValueError(f"duplicate route registered: {route}")
            self._commands[route] = Command(route=route, payload_schema=payload_schema,
                                             issues=issues, fn=fn,
                                             requires_credential=requires_credential)
            return fn
        return deco
```

> Note: `Command` is a `@dataclass`; `requires_credential` must be declared *after* the existing fields and have a default (`= None`) since `fn` has no default — keep the field order `route, payload_schema, issues, fn, requires_credential`. `payload_schema` already has no default but is passed positionally by keyword here, so this is consistent with the current constructor call.

- [ ] **Step 4: Export it.** In `keri_serviceaid/contract.py` nothing else changes. In `keri_serviceaid/__init__.py`, add `CredentialReq` to the `from .contract import (...)` line and to `__all__`:

```python
from .contract import ServiceAid, Request, Reply, Command, CredentialReq, TestRuntime
```

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest tests/serviceaid/test_contract_v2.py -v -k requires_credential`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add keri_serviceaid/contract.py keri_serviceaid/__init__.py tests/serviceaid/test_contract_v2.py
git commit -m "feat(serviceaid): declare per-command requires_credential on @command"
```

---

### Task 3: `BoundResolver`

`OracleResolver` raises when a `Habery` holds more than one hab (`resolve.py:54-56`). A wallet `Habery` holds many AIDs, so the local runtime must resolve against the *bound* hab explicitly.

**Files:**
- Modify: `keri_serviceaid/providers/resolve.py`
- Modify: `keri_serviceaid/providers/__init__.py`, `keri_serviceaid/__init__.py`
- Test: `tests/serviceaid/test_providers_resolve.py` (new)

- [ ] **Step 1: Write the failing test** — create `tests/serviceaid/test_providers_resolve.py`:

```python
"""BoundResolver resolves endsFor on a specified hab, not 'the one hab'."""
import pytest

from keri_serviceaid import BoundResolver, Endpoint


class FakeHab:
    """Minimal hab stub exposing endsFor(pre) -> {role: {eid: {scheme: url}}}."""
    def __init__(self, ends):
        self._ends = ends

    def endsFor(self, pre):
        return self._ends


def test_bound_resolver_picks_highest_priority_role_https():
    hab = FakeHab({
        "witness": {"Ewit": {"http": "http://wit/"}},
        "mailbox": {"Embx": {"https": "https://mbx/", "http": "http://mbx/"}},
    })
    ep = BoundResolver(hab).resolve("Esender", hby=None)
    assert ep == Endpoint(role="mailbox", eid="Embx", url="https://mbx/")


def test_bound_resolver_raises_when_no_endpoint():
    with pytest.raises(LookupError):
        BoundResolver(FakeHab({})).resolve("Esender", hby=None)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/serviceaid/test_providers_resolve.py -v`
Expected: FAIL — `ImportError: cannot import name 'BoundResolver'`.

- [ ] **Step 3: Implement** — append to `keri_serviceaid/providers/resolve.py` (reuses the module-level `_ROLE_PRIORITY`):

```python
class BoundResolver:
    """Resolver bound to one explicit hab — for the local (in-wallet) runtime,
    whose Habery holds many AIDs (so OracleResolver's single-hab assumption does
    not hold). Reads the bound hab's endsFor and picks the highest-priority role,
    https preferred."""

    def __init__(self, hab):
        self.hab = hab

    def resolve(self, sender: str, hby) -> Endpoint:
        ends = self.hab.endsFor(sender)            # role -> eid -> scheme -> url
        for role in _ROLE_PRIORITY:
            if role in ends and ends[role]:
                eid, locs = next(iter(ends[role].items()))
                url = locs.get("https") or locs.get("http") or next(iter(locs.values()), "")
                if url:
                    return Endpoint(role=role, eid=eid, url=url)
        raise LookupError(f"no reachable endpoint for {sender} via bound hab")
```

- [ ] **Step 4: Export it.** In `keri_serviceaid/providers/__init__.py`:

```python
from .resolve import Resolver, OracleResolver, BoundResolver, Endpoint
```
add `"BoundResolver"` to that `__all__`. In `keri_serviceaid/__init__.py`, add `BoundResolver` to the providers import + `__all__` (next to `OracleResolver`).

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest tests/serviceaid/test_providers_resolve.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add keri_serviceaid/providers/resolve.py keri_serviceaid/providers/__init__.py keri_serviceaid/__init__.py tests/serviceaid/test_providers_resolve.py
git commit -m "feat(serviceaid): BoundResolver for multi-hab (wallet) Haberies"
```

---

### Task 4: Extract `_CaptureHandler` to a shared module

`runtime.py` (Lambda) defines `_CaptureHandler` but also imports `keri.db.dynamodbing`. The local runtime must reuse `_CaptureHandler` without dragging in DynamoDB, so move the class to a dependency-light module both import.

**Files:**
- Create: `keri_serviceaid/_capture.py`
- Modify: `keri_serviceaid/runtime.py`
- Test: `tests/serviceaid/test_capture.py` (new)

- [ ] **Step 1: Write the failing test** — create `tests/serviceaid/test_capture.py`:

```python
"""_CaptureHandler stashes verified exns for synchronous drain."""
from keri_serviceaid._capture import _CaptureHandler


class FakeSerder:
    pass


def test_capture_handle_then_drain_returns_and_clears():
    h = _CaptureHandler(resource="/rate")
    assert h.resource == "/rate"
    assert h.verify(FakeSerder()) is True

    s1, s2 = FakeSerder(), FakeSerder()
    h.handle(s1, attachments=[b"a"])
    h.handle(s2)
    drained = h.drain()
    assert [d[0] for d in drained] == [s1, s2]
    assert drained[0][1] == [b"a"]
    assert h.drain() == []        # buffer cleared after drain
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/serviceaid/test_capture.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'keri_serviceaid._capture'`.

- [ ] **Step 3: Implement** — create `keri_serviceaid/_capture.py` with the class currently in `runtime.py`:

```python
"""Exchanger behavior that stashes verified exns for synchronous dispatch.

Shared by both runtimes (Lambda and local) so neither has to re-implement it and
the local runtime need not import the DynamoDB-laden runtime.py."""
from __future__ import annotations


class _CaptureHandler:
    """Exchanger behavior that stashes verified exns for synchronous dispatch."""

    def __init__(self, resource):
        self.resource = resource
        self.captured = []   # list of (serder, attachments)

    def verify(self, serder, attachments=None, **kw):
        return True

    def handle(self, serder, attachments=None, **kw):
        self.captured.append((serder, attachments or []))

    def drain(self):
        """Return all captured exns and clear the buffer (sole read path —
        prevents a stale capture from a prior request leaking into a later
        response on a warm runtime)."""
        out, self.captured = self.captured, []
        return out
```

- [ ] **Step 4: Update `runtime.py`** — delete the inline `class _CaptureHandler:` block (the `class _CaptureHandler` through its `drain` method) and add this import near the other `from .` imports:

```python
from ._capture import _CaptureHandler
```

- [ ] **Step 5: Run to verify both still work**

Run: `python -m pytest tests/serviceaid/test_capture.py -v`
Expected: PASS (1 passed).
Run: `python -c "import keri_serviceaid.runtime"` (confirms the extraction didn't break runtime's imports).
Expected: no output, exit 0.

- [ ] **Step 6: Commit**

```bash
git add keri_serviceaid/_capture.py keri_serviceaid/runtime.py tests/serviceaid/test_capture.py
git commit -m "refactor(serviceaid): extract _CaptureHandler to a shared module"
```

---

### Task 5: `CredentialGate` authorizer

Enforces a command's declared `requires_credential` by querying the concierge's held credentials: schema ∩ subject(sender), confirmed via `reger.saved`, with a TEL revocation re-check. Commands without `requires_credential` fall through to a base `Allowlist`.

**Files:**
- Create: `keri_serviceaid/providers/credgate.py`
- Modify: `keri_serviceaid/providers/__init__.py`, `keri_serviceaid/__init__.py`
- Modify: `tests/serviceaid/_schema.py` (add `BROKER_SCHEMA_SAD`)
- Test: `tests/serviceaid/test_providers_credgate.py` (new)

- [ ] **Step 1: Add the gating schema** — append to `tests/serviceaid/_schema.py`:

```python
BROKER_SCHEMA_SAD = {
    "$id": "",
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "BrokerLicense",
    "type": "object",
    "properties": {
        "v": {"type": "string"},
        "d": {"type": "string"},
        "i": {"type": "string"},
        "ri": {"type": "string"},
        "s": {"type": "string"},
        "a": {
            "oneOf": [
                {"type": "string"},
                {
                    "type": "object",
                    "properties": {
                        "d": {"type": "string"},
                        "i": {"type": "string"},
                        "dt": {"type": "string", "format": "date-time"},
                        "license": {"type": "string"},
                    },
                    "additionalProperties": False,
                    "required": ["d", "i", "dt", "license"],
                },
            ]
        },
    },
    "additionalProperties": False,
    "required": ["v", "d", "i", "ri", "s", "a"],
}
```

- [ ] **Step 2: Write the failing test** — create `tests/serviceaid/test_providers_credgate.py`:

```python
"""CredentialGate enforces requires_credential against held (presented) ACDCs.

The gating credential is issued to `recipient_pre` (the issuee/presenter) into the
gate's own reger via the proven IpexGrantIssuer issuance path, then queried by the
gate. (Live present-then-cache admission over IPEX is covered by Plan 2's
integration test; here we exercise the gate's query + revocation logic.)"""
import pytest

from keri.core import scheming
from keri.core.signing import Salter
from keri.kering import Kinds, Ilks
from keri.vdr import credentialing

from keri_serviceaid import (ServiceAid, Request, CredentialReq, CredentialGate,
                             IpexGrantIssuer)

from _schema import BROKER_SCHEMA_SAD, RATING_SCHEMA_SAD


@pytest.fixture
def broker_schema(issuer_hby):
    schemer = scheming.Schemer(sed=dict(BROKER_SCHEMA_SAD), kind=Kinds.json)
    issuer_hby.db.schema.pin(keys=(schemer.said,), val=schemer)
    return schemer.said


@pytest.fixture
def quote_schema(issuer_hby):
    schemer = scheming.Schemer(sed=dict(RATING_SCHEMA_SAD), kind=Kinds.json)
    issuer_hby.db.schema.pin(keys=(schemer.said,), val=schemer)
    return schemer.said


@pytest.fixture
def gated_svc(broker_schema, quote_schema):
    svc = ServiceAid(alias="rating-engine")

    @svc.command(route="/rate", issues=quote_schema,
                 requires_credential=CredentialReq(schema=broker_schema))
    def rate(req):
        ...

    @svc.command(route="/ping")          # ungated → base Allowlist
    def ping(req):
        ...
    return svc


@pytest.fixture
def gate_with_broker_cred(issuer_hby, recipient_pre, broker_schema, gated_svc):
    """Issue a broker license to recipient_pre into the gate's reger, return
    (gate, rgy, auth_hab) for follow-on revocation."""
    auth = issuer_hby.makeHab(name="auth")
    rgy = credentialing.Regery(hby=issuer_hby, name="concierge")
    IpexGrantIssuer()._issue_grant(
        issuer_hby, auth, rgy,
        schema_said=broker_schema, recipient=recipient_pre,
        attributes={"license": "B-123"}, registry_name="concierge")
    gate = CredentialGate(hby=issuer_hby, reger=rgy.reger, svc=gated_svc)
    return gate, rgy, auth


def test_allows_holder_of_valid_credential(gate_with_broker_cred, recipient_pre):
    gate, _, _ = gate_with_broker_cred
    allow, reason = gate.authorize(
        Request(sender=recipient_pre, route="/rate", payload={}, message_said="Ex"))
    assert allow is True, reason


def test_denies_sender_without_credential(gate_with_broker_cred):
    gate, _, _ = gate_with_broker_cred
    allow, reason = gate.authorize(
        Request(sender="EsomeOtherAID", route="/rate", payload={}, message_said="Ey"))
    assert allow is False
    assert "EsomeOtherAID" in reason


def test_ungated_command_falls_through_to_base_allowlist(gate_with_broker_cred):
    gate, _, _ = gate_with_broker_cred
    # empty allowlist ⇒ any verified sender allowed
    allow, _ = gate.authorize(
        Request(sender="EanyAID", route="/ping", payload={}, message_said="Ez"))
    assert allow is True


def test_denies_after_revocation(gate_with_broker_cred, recipient_pre):
    gate, rgy, auth = gate_with_broker_cred
    # find the issued credential and revoke it in its TEL
    saids = {s.qb64 for s in rgy.reger.schms.get(
        keys=gate.svc.lookup("/rate").requires_credential.schema.encode("utf-8"))}
    subj = [s for s in rgy.reger.subjs.get(keys=recipient_pre.encode("utf-8"))
            if s.qb64 in saids]
    said = subj[0].qb64
    creder, _, _, _ = rgy.reger.cloneCred(said=said)
    reg = rgy.registryByName("concierge")
    rev = reg.revoke(said=said)
    rseal = dict(i=rev.pre, s=rev.snh, d=rev.said)
    auth.interact(data=[rseal])
    from keri.core import serdering
    # process the revocation so the Tever advances
    rgy.processEscrows()

    allow, reason = gate.authorize(
        Request(sender=recipient_pre, route="/rate", payload={}, message_said="Ew"))
    assert allow is False, reason
```

> If `reg.revoke(...)`/`processEscrows()` does not advance the Tever to `rev` in-process (no-backer registries normally complete synchronously), drive it with the same `_complete` loop `IpexGrantIssuer` uses: `from keri_serviceaid.providers.issue import _complete; _complete(rgy, registrar, rev.pre, rev.sn)`. The implementer verifies the Tever state flips before asserting.

- [ ] **Step 3: Run to verify it fails**

Run: `python -m pytest tests/serviceaid/test_providers_credgate.py -v`
Expected: FAIL — `ImportError: cannot import name 'CredentialGate'`.

- [ ] **Step 4: Implement** — create `keri_serviceaid/providers/credgate.py`:

```python
"""CredentialGate authorizer — present-then-cache enforcement.

Enforces a command's declared CredentialReq by querying the concierge's HELD
credentials (populated when an IPEX presentation was admitted): the intersection
of `reger.schms[schema]` and `reger.subjs[sender]`, confirmed verified via
`reger.saved`, with a per-request TEL revocation re-check. Commands with no
requires_credential fall through to a base Allowlist (so a single authz provider
serves both gated and ungated routes — mirrors how the Issuer reads cmd.issues)."""
from __future__ import annotations

from keri.kering import Ilks

from .authz import Allowlist


class CredentialGate:
    def __init__(self, *, hby, reger, svc, base=None):
        self.hby = hby
        self.reger = reger
        self.svc = svc
        self.base = base if base is not None else Allowlist([])

    def authorize(self, req) -> tuple[bool, str]:
        cmd = self.svc.lookup(req.route)
        cred_req = getattr(cmd, "requires_credential", None) if cmd is not None else None
        if cred_req is None:
            return self.base.authorize(req)        # ungated → base policy

        schema_saids = {s.qb64 for s in self.reger.schms.get(
            keys=cred_req.schema.encode("utf-8"))}
        if not schema_saids:
            return False, f"no held credential of schema {cred_req.schema}"

        for saider in self.reger.subjs.get(keys=req.sender.encode("utf-8")):
            said = saider.qb64
            if said not in schema_saids:
                continue
            if self.reger.saved.get(keys=said) is None:
                continue                            # not fully verified
            creder, _prefixer, _number, _diger = self.reger.cloneCred(said=said)
            if cred_req.issuer and creder.issuer != cred_req.issuer:
                continue
            try:
                tever = self.reger.tevers[creder.regid]
            except KeyError:
                continue                            # registry TEL not held
            state = tever.vcState(said)
            if state is None or state.et in (Ilks.rev, Ilks.brv):
                continue                            # never issued / revoked
            return True, ""

        return False, (f"sender {req.sender} holds no valid "
                       f"{cred_req.schema} credential")
```

> `creder.issuer`, `creder.regid`, and `creder.said` are `SerderACDC` accessors. `reger.tevers` is keyed by the registry id (`creder.regid`); `Tever.vcState(said)` returns a state whose `.et` is the TEL ilk (`iss`/`bis`/`rev`/`brv`).

- [ ] **Step 5: Export it.** In `keri_serviceaid/providers/__init__.py` add:

```python
from .credgate import CredentialGate
```
and `"CredentialGate"` to that `__all__`. In `keri_serviceaid/__init__.py`, add `CredentialGate` to the providers import + `__all__`.

- [ ] **Step 6: Run to verify it passes**

Run: `python -m pytest tests/serviceaid/test_providers_credgate.py -v`
Expected: PASS (4 passed). If the revocation test needs the `_complete` drive noted above, add it, then re-run.

- [ ] **Step 7: Commit**

```bash
git add keri_serviceaid/providers/credgate.py keri_serviceaid/providers/__init__.py keri_serviceaid/__init__.py tests/serviceaid/_schema.py tests/serviceaid/test_providers_credgate.py
git commit -m "feat(serviceaid): CredentialGate authorizer (present-then-cache + revocation)"
```

---

### Task 6: `LocalRuntime` (provider wiring + capture + drain)

The adapter itself: given `(svc, hby, hab, rgy)`, wire local-variant providers, register a capture handler per command route on `hby.exc`, and drain them through `pipeline.process`. Headless-testable: feed a command exn into the exchanger, then drain.

**Files:**
- Create: `keri_serviceaid/local_runtime.py`
- Modify: `keri_serviceaid/__init__.py`
- Test: `tests/serviceaid/test_local_runtime.py` (new)

- [ ] **Step 1: Write the failing test** — create `tests/serviceaid/test_local_runtime.py`:

```python
"""LocalRuntime wires local providers, registers capture handlers, and drains
them through the pipeline. Uses a fake deliverer to capture the issued grant."""
import pytest

from keri.core import scheming
from keri.kering import Kinds
from keri.peer import exchanging
from keri.vdr import credentialing

from keri_serviceaid import (ServiceAid, Reply, LocalRuntime, BoundResolver,
                             LMDBLedger, CredentialGate)

from _schema import RATING_SCHEMA_SAD


class FakeDeliverer:
    def __init__(self):
        self.delivered = []

    def deliver(self, msg, endpoint, ctx):
        self.delivered.append((msg, endpoint))


@pytest.fixture
def quote_schema(issuer_hby):
    schemer = scheming.Schemer(sed=dict(RATING_SCHEMA_SAD), kind=Kinds.json)
    issuer_hby.db.schema.pin(keys=(schemer.said,), val=schemer)
    return schemer.said


def test_localruntime_wires_local_providers(issuer_hby, quote_schema):
    hab = issuer_hby.makeHab(name="rating-engine")
    rgy = credentialing.Regery(hby=issuer_hby, name="rating-engine")
    svc = ServiceAid(alias="rating-engine")

    @svc.command(route="/ping")
    def ping(req):
        return Reply.none()

    rt = LocalRuntime(svc, hby=issuer_hby, hab=hab, rgy=rgy)

    assert isinstance(svc.resolver, BoundResolver)
    assert isinstance(svc.idempotency, LMDBLedger)
    assert isinstance(svc.authz, CredentialGate)
    # a capture handler is registered per route
    assert "/ping" in issuer_hby.exc.routes


def test_localruntime_processes_captured_command_and_delivers(issuer_hby, quote_schema, recipient_pre):
    hab = issuer_hby.makeHab(name="rating-engine")
    rgy = credentialing.Regery(hby=issuer_hby, name="rating-engine")
    svc = ServiceAid(alias="rating-engine")

    @svc.command(route="/rate", issues=quote_schema)     # ungated; open allowlist
    def rate(req):
        return Reply.acdc(recipient=req.sender,
                          attributes={"i": req.sender, "score": 42})

    fake = FakeDeliverer()
    svc.deliverer = fake
    rt = LocalRuntime(svc, hby=issuer_hby, hab=hab, rgy=rgy)

    # Build + sign a /rate command exn FROM recipient_pre, addressed to the hab.
    exn, _end = exchanging.exchange(route="/rate", sender=recipient_pre,
                                    recipient=hab.pre, payload={"coverage": "auto"})
    # Inject as a verified capture (bypasses live mailbox): hand it to the handler.
    rt._captures["/rate"].handle(exn, attachments=[])

    rt.process_captured()

    assert len(fake.delivered) == 1     # one Quote grant delivered
```

> `exchanging.exchange(...)` returns `(serder, end)`; the capture handler stores the serder. Driving the handler directly is the headless analogue of the live mailbox path (Task 7). The pipeline's `verify` step reads key state from `issuer_hby.kevers`; `recipient_pre` is already parsed in by the fixture, so `OracleVerifier(tier="receipts")` passes (unwitnessed AID → tier-1-equivalent).

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/serviceaid/test_local_runtime.py -v`
Expected: FAIL — `ImportError: cannot import name 'LocalRuntime'`.

- [ ] **Step 3: Implement** — create `keri_serviceaid/local_runtime.py`:

```python
"""LocalRuntime — the in-wallet adapter.

Drives the keri_serviceaid pipeline against a wallet's LMDB Habery and ONE bound
AID (hab) + its registry (rgy). Wires the local-variant providers, registers a
capture handler per command route on hby.exc, and drains them through
pipeline.process. The live mailbox transport is add_mailbox_doer (Task 7); for
tests/headless use, feed exns to the exchanger and call process_captured().

No DynamoDB, no Qt — pure keripy. The wallet/plugin layer (concierge-api-local)
constructs this after binding an AID."""
from __future__ import annotations

from dataclasses import dataclass

from keri.vdr import verifying

from . import pipeline
from ._capture import _CaptureHandler
from .contract import ServiceAid
from .providers import (Allowlist, OracleVerifier, BoundResolver,
                       IpexGrantIssuer, PostmanDeliverer, LMDBLedger, CredentialGate)


@dataclass
class LocalCfg:
    alias: str            # registry name (pipeline reads state.cfg.alias)


@dataclass
class LocalState:
    cfg: LocalCfg
    hby: object
    hab: object
    rgy: object
    svc: ServiceAid


class LocalRuntime:
    def __init__(self, svc: ServiceAid, *, hby, hab, rgy,
                 idempotency=None, base_authz=None, verifier_tier="receipts"):
        self.svc = svc
        self.hby = hby
        self.hab = hab
        self.rgy = rgy

        # Wire local-variant providers for any the dev left None.
        if svc.verifier is None:
            svc.verifier = OracleVerifier(tier=verifier_tier)
        if svc.resolver is None:
            svc.resolver = BoundResolver(hab)
        if svc.issuer is None:
            svc.issuer = IpexGrantIssuer()
        if svc.deliverer is None:
            svc.deliverer = PostmanDeliverer()
        if svc.idempotency is None:
            svc.idempotency = idempotency or LMDBLedger(hby.db)
        if svc.authz is None:
            svc.authz = CredentialGate(hby=hby, reger=rgy.reger, svc=svc,
                                       base=Allowlist(base_authz or []))

        # Credential verifier for admitting IPEX presentations on the live path.
        self.cred_verifier = verifying.Verifier(hby=hby, reger=rgy.reger)

        self.state = LocalState(cfg=LocalCfg(alias=svc.alias),
                                hby=hby, hab=hab, rgy=rgy, svc=svc)

        # One capture handler per command route.
        self._captures: dict = {}
        for route in svc.routes:
            handler = _CaptureHandler(resource=route)
            self._captures[route] = handler
            hby.exc.addHandler(handler)

    def process_captured(self) -> None:
        """Drain every capture handler and drive the pipeline per verified exn."""
        for handler in self._captures.values():
            for serder, attachments in handler.drain():
                pipeline.process(self.state, serder, attachments)
```

- [ ] **Step 4: Export it.** In `keri_serviceaid/__init__.py`, add:

```python
from .local_runtime import LocalRuntime, LocalState, LocalCfg
```
and add `"LocalRuntime"`, `"LocalState"`, `"LocalCfg"` to `__all__`.

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest tests/serviceaid/test_local_runtime.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add keri_serviceaid/local_runtime.py keri_serviceaid/__init__.py tests/serviceaid/test_local_runtime.py
git commit -m "feat(serviceaid): LocalRuntime adapter (provider wiring + capture drain)"
```

---

### Task 7: `LocalRuntime` live mailbox inbound doer

A `MailboxDirector` mounted on the host's Doist polls the bound AID's witness mailbox, verifies/admits credentials, and routes command exns to `hby.exc` (which the capture handlers feed). This is the live transport the wallet (Plan 2) mounts via `get_doers()`.

**Files:**
- Modify: `keri_serviceaid/local_runtime.py`
- Test: `tests/serviceaid/test_local_runtime.py`

- [ ] **Step 1: Write the failing test** — append to `tests/serviceaid/test_local_runtime.py`:

```python
from keri.app.indirecting import MailboxDirector


def test_mailbox_doer_built_with_exchanger_and_verifier(issuer_hby, quote_schema):
    hab = issuer_hby.makeHab(name="rating-engine")
    rgy = credentialing.Regery(hby=issuer_hby, name="rating-engine")
    svc = ServiceAid(alias="rating-engine")

    @svc.command(route="/ping")
    def ping(req):
        return Reply.none()

    rt = LocalRuntime(svc, hby=issuer_hby, hab=hab, rgy=rgy)
    doer = rt.mailbox_doer(topics=["/credential", "/receipt"])

    assert isinstance(doer, MailboxDirector)
    assert doer.exc is issuer_hby.exc          # command exns route to our exchanger
    assert "/credential" in doer.topics
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/serviceaid/test_local_runtime.py -v -k mailbox`
Expected: FAIL — `AttributeError: 'LocalRuntime' object has no attribute 'mailbox_doer'`.

- [ ] **Step 3: Implement** — add to `LocalRuntime` in `keri_serviceaid/local_runtime.py`, and add the import at the top:

```python
from keri.app.indirecting import MailboxDirector
```

```python
    def mailbox_doer(self, topics=None):
        """A MailboxDirector (a hio DoDoer) that polls the bound AID's witness
        mailbox, admits presented credentials (verifier), and routes command exns
        to hby.exc — where this runtime's capture handlers receive them. Mount it
        on the host Doist (the wallet does this via the plugin's get_doers()), then
        call process_captured() on a cue/timer to drive the pipeline."""
        if topics is None:
            topics = ["/receipt", "/credential", "/reply"]
        return MailboxDirector(hby=self.hby, topics=topics,
                               verifier=self.cred_verifier, exc=self.hby.exc)
```

> The wallet (Plan 2) owns *when* to call `process_captured()` — typically right after the director's escrow/poll cycle. Whether the concierge runs its own `MailboxDirector` or hooks the wallet's existing one is a Plan 2 decision; this method is the standalone option and the construction contract.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/serviceaid/test_local_runtime.py -v -k mailbox`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add keri_serviceaid/local_runtime.py tests/serviceaid/test_local_runtime.py
git commit -m "feat(serviceaid): LocalRuntime mailbox-poll inbound doer"
```

---

### Task 8: Headless end-to-end — gated Rating Engine

Capstone: admit a broker credential for the sender, then process a gated `/rate` command, and assert a signed Quote grant is issued + delivered. Exercises CredentialGate + the full pipeline + issuance on the local runtime, headless.

**Files:**
- Test: `tests/serviceaid/test_local_runtime_e2e.py` (new)

- [ ] **Step 1: Write the failing test** — create `tests/serviceaid/test_local_runtime_e2e.py`:

```python
"""End-to-end (headless): a broker-gated /rate command issues a signed Quote.

Admits the gating credential into the runtime's reger via the proven issuance
path (standing in for live IPEX present-then-cache, which Plan 2 integration-
tests in the wallet), then drives a /rate command and asserts a Quote grant is
delivered."""
import pytest

from keri.core import scheming
from keri.kering import Kinds
from keri.peer import exchanging
from keri.vdr import credentialing

from keri_serviceaid import (ServiceAid, Reply, CredentialReq, LocalRuntime,
                             IpexGrantIssuer)

from _schema import RATING_SCHEMA_SAD, BROKER_SCHEMA_SAD


class FakeDeliverer:
    def __init__(self):
        self.delivered = []

    def deliver(self, msg, endpoint, ctx):
        self.delivered.append(msg)


def _register(hby, sad):
    schemer = scheming.Schemer(sed=dict(sad), kind=Kinds.json)
    hby.db.schema.pin(keys=(schemer.said,), val=schemer)
    return schemer.said


def test_gated_rate_issues_quote(issuer_hby, recipient_pre):
    broker_said = _register(issuer_hby, BROKER_SCHEMA_SAD)
    quote_said = _register(issuer_hby, RATING_SCHEMA_SAD)

    hab = issuer_hby.makeHab(name="rating-engine")
    rgy = credentialing.Regery(hby=issuer_hby, name="rating-engine")

    svc = ServiceAid(alias="rating-engine")

    @svc.command(route="/rate", issues=quote_said,
                 requires_credential=CredentialReq(schema=broker_said))
    def rate(req):
        return Reply.acdc(recipient=req.sender,
                          attributes={"i": req.sender, "score": 7})

    fake = FakeDeliverer()
    svc.deliverer = fake
    rt = LocalRuntime(svc, hby=issuer_hby, hab=hab, rgy=rgy)

    # Admit the broker credential for recipient_pre into the runtime's reger.
    IpexGrantIssuer()._issue_grant(
        issuer_hby, hab, rgy, schema_said=broker_said, recipient=recipient_pre,
        attributes={"license": "B-123"}, registry_name="rating-engine")

    # Deliver a /rate command from recipient_pre.
    exn, _ = exchanging.exchange(route="/rate", sender=recipient_pre,
                                 recipient=hab.pre, payload={"coverage": "auto"})
    rt._captures["/rate"].handle(exn, attachments=[])
    rt.process_captured()

    assert len(fake.delivered) == 1          # gated request → signed Quote grant


def test_gated_rate_denied_without_credential(issuer_hby, recipient_pre):
    broker_said = _register(issuer_hby, BROKER_SCHEMA_SAD)
    quote_said = _register(issuer_hby, RATING_SCHEMA_SAD)

    hab = issuer_hby.makeHab(name="rating-engine")
    rgy = credentialing.Regery(hby=issuer_hby, name="rating-engine")

    svc = ServiceAid(alias="rating-engine")

    @svc.command(route="/rate", issues=quote_said,
                 requires_credential=CredentialReq(schema=broker_said))
    def rate(req):
        return Reply.acdc(recipient=req.sender, attributes={"i": req.sender, "score": 7})

    fake = FakeDeliverer()
    svc.deliverer = fake
    rt = LocalRuntime(svc, hby=issuer_hby, hab=hab, rgy=rgy)

    # No credential admitted → CredentialGate denies → silent drop.
    exn, _ = exchanging.exchange(route="/rate", sender=recipient_pre,
                                 recipient=hab.pre, payload={"coverage": "auto"})
    rt._captures["/rate"].handle(exn, attachments=[])
    rt.process_captured()

    assert fake.delivered == []              # denied → nothing issued or delivered
```

- [ ] **Step 2: Run to verify it fails first, then passes**

Run: `python -m pytest tests/serviceaid/test_local_runtime_e2e.py -v`
Expected (before any fix): the deny test PASSES immediately; the allow test may FAIL if issuance/admission doesn't land the cred in `reger.saved` synchronously. If so, after `_issue_grant` add `rt.cred_verifier.processEscrows()` and `rgy.processEscrows()` before the command, and re-run.
Final expected: PASS (2 passed).

- [ ] **Step 3: Commit**

```bash
git add tests/serviceaid/test_local_runtime_e2e.py
git commit -m "test(serviceaid): headless e2e — broker-gated Rating Engine issues a Quote"
```

---

### Task 9: Full-suite regression + provider exports sanity

- [ ] **Step 1: Run the whole serviceaid suite**

Run: `python -m pytest tests/serviceaid/ -v`
Expected: all pass (pre-existing tests + the new ones). Integration-marked tests that need moto are deselected by default — that is expected.

- [ ] **Step 2: Confirm the public API imports cleanly**

Run:
```bash
python -c "from keri_serviceaid import (LocalRuntime, LocalState, LMDBLedger, BoundResolver, CredentialGate, CredentialReq); print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: If anything regressed, fix and re-run before proceeding.** No commit needed if step 1 was already green; otherwise commit the fix:

```bash
git add -A && git commit -m "fix(serviceaid): address local-runtime suite regressions"
```

---

## Self-Review

**Spec coverage (§ of `2026-06-23-concierge-api-local-runtime-design.md`):**
- §6.1 `LocalRuntime` → Tasks 6–7. `LMDBLedger` → Task 1. `CredentialGate` → Task 5. `@command requires_credential` → Task 2. ✅
- §6.1 `BoundResolver` (multi-hab fix, discovered during planning) → Task 3. ✅
- §7/§8 two-direction authority + present-then-cache: inbound `CredentialGate` enforcement → Task 5; outbound issue-as-self via reused `IpexGrantIssuer` → Tasks 6/8 (edge-chaining is `Reply.acdc(edges=...)`, already supported by the issuer — no new code). ✅
- §10 error policy (silent-drop, exactly-once) → inherited from `pipeline.process` (unchanged); exercised in Task 8's deny test. ✅
- §10 no-backer TEL → reused `IpexGrantIssuer`/`ensure_registry` (`noBackers=True`); no new code. ✅
- §12 testing: `TestRuntime` already exists; headless e2e → Task 8. ✅
- **Out of this plan (Plan 2):** `ConciergePlugin`, `BindingController`, `AidSelectorPage`, repo scaffolding, the ui-tester integration, and *which* component calls `process_captured()`/owns the mailbox doer in the wallet. AI skill is a later follow-up entirely.

**Placeholder scan:** No TBD/TODO. Two tasks (5, 8) flag a *verification* the implementer performs (whether revocation/issuance completes synchronously) with the exact remedy (`_complete` / `processEscrows()`) — these are real instructions, not placeholders.

**Type consistency:** `CredentialReq(schema, issuer, presentation, cadence)`, `Command.requires_credential`, `CredentialGate(hby, reger, svc, base)`, `BoundResolver(hab)`, `LMDBLedger(db)`, `LocalRuntime(svc, *, hby, hab, rgy, ...)`, `LocalState(cfg, hby, hab, rgy, svc)`, `LocalCfg(alias)`, `_CaptureHandler(resource)` are used consistently across tasks and match the keripy signatures grounded during planning (`reger.schms/subjs/saved`, `cloneCred(said=...) -> (creder, prefixer, number, diger)`, `tevers[regid].vcState(said).et`, `MailboxDirector(hby, topics, verifier, exc)`).
