"""Witnessed-roundtrip host: open a kli-created WITNESSED DOI keystore as a real
Locksmith vault, bind the micro-app, and run the vault's Doist so its mailbox
poller (vault.mbx) pulls the carrier's already-deposited grant_license command
exn from the witness mailbox, routes it through vault.exc to the micro-app, and
issues a carrier_license. Asserts the credential lands in the vault's registry.

Invoked by microapp_in_vault_witnessed.sh (sets PYTHONPATH + offscreen Qt).
Args: <keri_base> <keystore_name> <alias> <template.json> <schema.json> <deploy.json> <timeout_s>
"""
import json
import os
import sys
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from hio.base import doing
from keri.app import habbing
from keri.core import scheming
from keri.kering import Kinds, Ilks
from keri.vdr import credentialing

from locksmith.core import vaulting
from locksmith.db.basing import LocksmithBaser

from concierge_api_local.loader.load import load
from concierge_api_local.loader.manifest import DeployManifest
from concierge_api_local.binding import BindingController

base, ks_name, alias, template_path, schema_path, deploy_path, timeout_s = (
    sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], float(sys.argv[7]))

import tempfile
_tmp = tempfile.mkdtemp(prefix="wvh-")
vaulting.LocksmithBaser = lambda name, reopen=True: LocksmithBaser(
    name=f"{name}-locksmith", headDirPath=_tmp, reopen=reopen)
class _NoTurret(doing.DoDoer):
    def __init__(self, *a, **k): super().__init__(doers=[])
vaulting.TurretDoer = _NoTurret

template = json.load(open(template_path))
schema_sad = json.load(open(schema_path))
schema_said = schema_sad["$id"]


def _issued(rgy):
    saiders = list(rgy.reger.schms.get(keys=schema_said.encode("utf-8")))
    return saiders[0].qb64 if saiders else None


# Open the kli-created keystore (holds the witnessed DOI hab) as the vault's Habery.
hby = habbing.Habery(name=ks_name, base=base, bran=None)
rgy = credentialing.Regery(hby=hby, name=hby.name, base=base, temp=False)
vault = vaulting.Vault(app=SimpleNamespace(), hby=hby, rgy=rgy)

doi = hby.habByName(alias)
print(f"[host] opened vault on keystore {ks_name!r}; DOI={doi.pre if doi else None} "
      f"wits={getattr(doi.kever, 'wits', None) if doi else None}", flush=True)

# Register the export schema + bind the AID (no doers added yet — safe pre-enter).
schemer = scheming.Schemer(sed=dict(schema_sad), kind=Kinds.json)
hby.db.schema.pin(keys=(schemer.said,), val=schemer)
deploy = DeployManifest.from_json(deploy_path)
svc, _lock = load(template, deploy)
ctl = BindingController(vault, svc, role_name=svc.alias,
                        store_path=os.path.join(_tmp, f"{svc.alias}.binding.json"))
ctl.bind_existing(svc.alias)

# Enter the vault node FIRST, then start the runtime — exactly like the wallet's
# on_vault_opened fires while the node is already running. ctl.start() then
# extends the RUNNING vault.doers + vault.mbx, so the pump + poller are wound
# (extending a not-yet-entered DoDoer leaves retyme=None -> hio scheduling error).
doist = doing.Doist(doers=[vault], tock=0.125, real=True)
doist.enter()
ctl.start()
print(f"[host] bound on running vault; runtime.exc is vault.exc: "
      f"{ctl.runtime.exc is vault.exc}; command_topics={ctl.runtime.command_topics}; "
      f"pollers={len(vault.mbx.pollers)}", flush=True)

# Drive the loop: vault.mbx polls the witness mailbox, pulls the carrier's
# already-deposited exn (topic = command_topics), routes via vault.exc -> handler
# -> RuntimePumpDoer -> pipeline -> issue. Stop as soon as the credential lands.
issued = None
deadline = time.time() + timeout_s
try:
    while time.time() < deadline:
        doist.recur()
        time.sleep(doist.tock)
        issued = _issued(rgy)
        if issued:
            break
finally:
    doist.exit()

if issued:
    reg = rgy.registryByName(alias)
    state = rgy.reger.tevers[reg.regk].vcState(issued).et
    ok = state == Ilks.iss
    print(f"[host] carrier_license issued in vault.rgy: {issued} TEL={state} "
          f"-> {'PASS' if ok else 'UNEXPECTED'}", flush=True)
    rc = 0 if ok else 2
else:
    print("[host] FAIL: vault did not pull+issue within timeout "
          "(witness mailbox poll did not deliver the command exn)", flush=True)
    rc = 1

try:
    vault.db.close(); vault.rep.mbx.close(); vault.notifier.noter.close()
except Exception:
    pass
hby.close()
sys.exit(rc)
