"""Full-chain (in-wallet): the DOI micro-app Service-AID runs INSIDE a real
Locksmith vault and issues a carrier_license when a carrier's grant_license
command exn is routed through the wallet's exchanger.

This is the faithful counterpart to concierge's hermetic gate. It proves the
architecturally-correct host: a Service-AID is an application a KERI node hosts,
not a node itself — here the **real Locksmith vault** owns transport (its
`vault.exc` exchanger + `vault.mbx` poller + Doist), and the micro-app, bound via
`BindingController`, plugs into it.

What is REAL: a real `Vault` (headless), the loader-compiled ServiceAid bound to
a vault hab, capture handlers registered on **`vault.exc`** (the injected host
exchanger — NOT `hby.exc`), a signed carrier exn **parsed through `vault.exc`**
so the wallet's exchanger routes it to the micro-app's handler, and a real
`carrier_license` minted into the vault's registry (TEL `iss`).

What is stubbed (transport, proven elsewhere — peer-mode IPEX + CDK 5x5): the
witness MAILBOX hop. Rather than a witnessed mailbox poll, the signed exn is fed
straight into `vault.exc` (exactly what `vault.mbx`'s poller would do after
pulling it). Delivery of the grant back to the carrier raises a suppressed
LookupError (the co-resident carrier has no endpoint); issuance happens before
delivery, so it is fully observable on the vault's own registry.

Run via tests/integration/microapp_in_vault_e2e.sh (sets the cross-repo
PYTHONPATH + offscreen Qt). Requires locksmith + concierge_api_local +
keri_serviceaid importable.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

# Cross-repo integration: requires locksmith + concierge_api_local + keri_serviceaid
# importable (the runner microapp_in_vault_e2e.sh sets PYTHONPATH). Skip cleanly
# under a plain `pytest tests/` that lacks those paths.
pytest.importorskip("locksmith.core.vaulting")
pytest.importorskip("concierge_api_local.binding")
pytest.importorskip("keri_serviceaid")

from hio.base import doing
from keri.app import habbing
from keri.core import scheming, signing, parsing
from keri.kering import Kinds, Vrsn_1_0, Ilks
from keri.vdr import credentialing

from locksmith.core import vaulting
from locksmith.db.basing import LocksmithBaser

from concierge_api_local.loader.load import load
from concierge_api_local.loader.manifest import DeployManifest
from concierge_api_local.binding import BindingController

FX = Path(__file__).resolve().parent / "fixtures" / "regulator-grants-carrier-license"
GRANT_ROUTE = "/insurance/cmd/grant_license"
REVOKE_ROUTE = "/insurance/cmd/revoke_license"
ALIAS = "state-doi"
APP = {"license_number": "P-12345", "jurisdiction": "US-UT",
       "lines_of_business": ["property"], "effective_date": "2026-01-01",
       "expiration_date": "2027-01-01"}


class _NoTurret(doing.DoDoer):
    def __init__(self, *a, **k):
        super().__init__(doers=[])


def bind_microapp(vault, template: dict, deploy_path: str, schema_sads: list[dict]):
    """Host helper (the future DesignerPlugin.on_vault_opened core): compile the
    micro-app, register its export schemas into the vault's schema store (host
    §5.2 step), and bind+start it on the vault via BindingController."""
    deploy = DeployManifest.from_json(deploy_path)
    svc, _lock = load(template, deploy)
    for sad in schema_sads:
        schemer = scheming.Schemer(sed=dict(sad), kind=Kinds.json)
        vault.hby.db.schema.pin(keys=(schemer.said,), val=schemer)
    store_path = os.path.join(os.path.dirname(deploy_path), f"{svc.alias}.binding.json")
    ctl = BindingController(vault, svc, role_name=svc.alias, store_path=store_path)
    ctl.bind_existing(svc.alias)
    ctl.start()
    return ctl


def _route_signed_exn_through_vault(vault, sender_hab, route, recipient, payload):
    """Build + sign a command exn and parse it through vault.exc — exactly what
    vault.mbx's poller does after pulling it from the witness mailbox — so the
    wallet's exchanger routes it to the micro-app's capture handler."""
    import inspect
    from keri.peer import exchanging
    params = inspect.signature(exchanging.exchange).parameters
    kw = {"route": route, "sender": sender_hab.pre}
    kw["payload" if "payload" in params else "attributes"] = payload
    kw["recipient" if "recipient" in params else "receiver"] = recipient
    exn, _ = exchanging.exchange(**kw)
    signed = sender_hab.endorse(exn)  # exn.raw + signatures (a CESR stream)
    parsing.Parser(exc=vault.exc, kvy=vault.kvy, rvy=vault.rvy,
                   version=Vrsn_1_0).parse(ims=bytearray(signed))
    return exn


def _issued_license_said(rgy, schema_said):
    saiders = list(rgy.reger.schms.get(keys=schema_said.encode("utf-8")))
    return saiders[0].qb64 if saiders else None


def test_microapp_issues_carrier_license_inside_real_vault(monkeypatch, tmp_path):
    # Light vault deps (same shims the proven headless-vault test uses).
    monkeypatch.setattr(vaulting, "LocksmithBaser",
                        lambda name, reopen=True: LocksmithBaser(
                            name=f"{name}-locksmith", headDirPath=str(tmp_path), reopen=reopen))
    monkeypatch.setattr(vaulting, "TurretDoer", _NoTurret)

    template = json.loads((FX / "micro-app-template.json").read_text())
    schema_sad = json.loads((FX / "schemas" / "carrier_license.json").read_text())
    schema_said = schema_sad["$id"]

    hby = habbing.Habery(name="vault-doi", temp=True,
                         salt=signing.Salter(raw=b'0123456789abcdef').qb64)
    rgy = credentialing.Regery(hby=hby, name=hby.name, temp=True)
    vault = None
    try:
        vault = vaulting.Vault(app=SimpleNamespace(), hby=hby, rgy=rgy)

        # DOI service hab inside the vault (unwitnessed for the in-process proof).
        doi = hby.makeHab(name=ALIAS, transferable=True, wits=[], toad=0)

        deploy_path = str(tmp_path / "deploy.json")
        json.dump({"role_aid": doi.pre, "alias": ALIAS, "witnesses": [], "toad": 0,
                   "compute": {GRANT_ROUTE: "concierge_api_local.computes.doi:grant",
                               REVOKE_ROUTE: "concierge_api_local.computes.doi:revoke"},
                   "schema_saids": {"carrier_license": schema_said},
                   "egf_acceptable_saids": [schema_said], "oobis": []},
                  open(deploy_path, "w"))

        ctl = bind_microapp(vault, template, deploy_path, [schema_sad])

        # The micro-app is bound on the vault, with handlers on the HOST exchanger.
        assert ctl.bound_hab().pre == doi.pre
        assert ctl.runtime.exc is vault.exc            # injected host exchanger
        assert ctl.runtime.exc is not hby.exc
        assert GRANT_ROUTE in vault.exc.routes         # routed here, not hby.exc
        assert GRANT_ROUTE not in hby.exc.routes

        # A carrier sends a grant_license command exn; it routes through vault.exc.
        carrier = hby.makeHab(name="carrier", transferable=True)
        _route_signed_exn_through_vault(vault, carrier, GRANT_ROUTE, doi.pre, APP)
        assert ctl.runtime._captures[GRANT_ROUTE].captured, \
            "vault.exc did not route the command exn to the micro-app handler"
        ctl.runtime.process_captured()

        # A real carrier_license was minted into the VAULT's registry (TEL iss).
        said = _issued_license_said(rgy, schema_said)
        assert said is not None, "no carrier_license issued into the vault registry"
        reg = rgy.registryByName(ALIAS)
        assert rgy.reger.tevers[reg.regk].vcState(said).et == Ilks.iss

        ctl.stop()
    finally:
        if vault is not None:
            vault.db.close()
            vault.rep.mbx.close()
            vault.notifier.noter.close()
        rgy.close()
        hby.close()
