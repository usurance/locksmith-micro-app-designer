#!/usr/bin/env bash
# WITNESSED full-chain (best-effort): a carrier mails a grant_license command exn
# over a REAL witness mailbox; a real Locksmith vault hosting the DOI micro-app
# POLLS the mailbox (vault.mbx), routes the exn through vault.exc, and issues a
# carrier_license. The faithful counterpart to microapp_in_vault_e2e.sh — here
# the witness MAILBOX hop is real, not stubbed.
#
# Deterministic ordering: the carrier mails FIRST (exn waits in the DOI's witness
# mailbox), THEN the vault opens + polls it. Demo witnesses; swapping in the
# deployed federation (ecosystems/keri_host/federation_aids.json) is a config-only
# change (witness prefixes + their OOBIs).
#
# STATE (keri 2.0.0-dev6, demo witnesses): REAL through the mail step — witnessed
# DOI AID (real witness receipts), a real Locksmith vault hosting the micro-app,
# vault.mbx with a poller for the bound DOI on its command topic ("insurance"),
# runtime.exc == vault.exc, and the carrier mails the exn rc=0. The remaining gap
# is the witness SERVING the mailbox poll back: the vault pulls 0 within the
# window. This same gap affects keripy's OWN `kli mailbox list` against these demo
# witnesses, so it is a demo-witness mailbox-serving issue in this env, NOT the
# micro-app/vault integration (which is fully proven by microapp_in_vault_e2e.sh,
# where the exn is fed into vault.exc directly). Re-run against the deployed
# federation for production-grade mailbox serving. Best-effort; exit 1 on the gap.
#
# Usage: bash tests/integration/microapp_in_vault_witnessed.sh
set -uo pipefail   # not -e: report partial progress

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-$HOME/code/locksmith/.venv/bin/python}"
KLI="$(dirname "$PY")/kli"
KERIPY="${KERIPY:-$REPO/../keripy}"
CONCIERGE="${CONCIERGE:-$REPO/../concierge-api}"
FX="$HERE/fixtures/regulator-grants-carrier-license"
WORK="$(mktemp -d)"
REL_BASE="microapp-vault-e2e"
WAN="BBilc4-L3tFUnfM_wJr4S4OJanAv_VmF_dJNN6vkf2Ha"; WURL="http://127.0.0.1:5642"
CTRL_OOBI="$WURL/oobi/$WAN/controller"
WITPID=""
export PYTHONPATH="$REPO/src:$CONCIERGE/src:$KERIPY"
export QT_QPA_PLATFORM=offscreen

_purge() { for d in "$HOME"/.keri/*/"$REL_BASE"; do [ -e "$d" ] && rm -rf "$d"; done
           for w in wan wil wes wit wub wyz; do rm -rf "$HOME/.keri/mbx/$w" 2>/dev/null; done; }
cleanup() { [ -n "$WITPID" ] && { kill "$WITPID" 2>/dev/null; pkill -P "$WITPID" 2>/dev/null; }
            _purge; rm -rf "$WORK"; }
trap cleanup EXIT
fail() { echo "PARTIAL: $*" >&2; exit 1; }

_purge
SCHEMA_SAID="$("$PY" -c "import json;print(json.load(open('$FX/schemas/carrier_license.json'))['\$id'])")"

echo "== 1/6: demo witnesses (from keripy dir so they advertise loc) =="
( cd "$KERIPY" && exec "$KLI" witness demo --base "$REL_BASE" ) >"$WORK/wit.log" 2>&1 &
WITPID=$!
for _ in $(seq 1 60); do nc -z localhost 5642 && break; sleep 0.3; done
nc -z localhost 5642 || fail "witnesses never came up (see $WORK/wit.log)"

echo "== 2/6: witnessed DOI + carrier keystores (--receipt-endpoint) + mailbox end-role =="
for ks in doi carrier; do
  "$KLI" init --name "$ks" --base "$REL_BASE" --nopasscode >/dev/null 2>&1 || fail "init $ks"
  "$KLI" oobi resolve --name "$ks" --base "$REL_BASE" --oobi-alias wan --oobi "$CTRL_OOBI" >/dev/null 2>&1 || fail "$ks resolve wan"
done
"$KLI" incept --name doi --base "$REL_BASE" --receipt-endpoint --alias state-doi --transferable \
  --wit "$WAN" --toad 1 --icount 1 --isith 1 --ncount 1 --nsith 1 >"$WORK/doi.icp" 2>&1 || { tail -3 "$WORK/doi.icp" >&2; fail "incept state-doi"; }
"$KLI" incept --name carrier --base "$REL_BASE" --receipt-endpoint --alias carrier --transferable \
  --wit "$WAN" --toad 1 --icount 1 --isith 1 --ncount 1 --nsith 1 >"$WORK/carrier.icp" 2>&1 || { tail -3 "$WORK/carrier.icp" >&2; fail "incept carrier"; }
"$KLI" ends add --name doi --base "$REL_BASE" --alias state-doi --eid "$WAN" --role mailbox >/dev/null 2>&1 || fail "doi ends add"
"$KLI" ends add --name carrier --base "$REL_BASE" --alias carrier --eid "$WAN" --role mailbox >/dev/null 2>&1 || fail "carrier ends add"

DOI="$("$KLI" aid --name doi --base "$REL_BASE" --alias state-doi 2>/dev/null)"
echo "   DOI=$DOI"

echo "== 3/6: carrier resolves DOI's witness OOBI =="
DOI_OOBI="$("$KLI" oobi generate --name doi --base "$REL_BASE" --alias state-doi --role witness | tail -1)"
case "$DOI_OOBI" in http*) : ;; *) fail "oobi generate doi: $DOI_OOBI";; esac
"$KLI" oobi resolve --name carrier --base "$REL_BASE" --oobi-alias state-doi --oobi "$DOI_OOBI" >/dev/null 2>&1 || fail "carrier->doi resolve"

echo "== 4/6: deploy manifest + payload =="
cat >"$WORK/deploy.json" <<JSON
{"role_aid":"$DOI","alias":"state-doi","witnesses":["$WAN"],"toad":1,
 "compute":{"/insurance/cmd/grant_license":"concierge_api_local.computes.doi:grant","/insurance/cmd/revoke_license":"concierge_api_local.computes.doi:revoke"},
 "schema_saids":{"carrier_license":"$SCHEMA_SAID"},"egf_acceptable_saids":["$SCHEMA_SAID"],"oobis":[]}
JSON
cat >"$WORK/app.json" <<'JSON'
{"license_number":"P-12345","jurisdiction":"US-UT","lines_of_business":["property"],"effective_date":"2026-01-01","expiration_date":"2027-01-01"}
JSON

echo "== 5/6: carrier MAILS the grant_license exn over the witness (deposits in DOI mailbox) =="
"$KLI" exn send --name carrier --base "$REL_BASE" --sender carrier --recipient state-doi \
  --route /insurance/cmd/grant_license --data "@$WORK/app.json" >"$WORK/send.log" 2>&1 || { tail -5 "$WORK/send.log" >&2; fail "exn send"; }
echo "   mailed (rc=0)"

echo "== 6/6: vault opens + polls the mailbox + issues (timeout 60s) =="
"$PY" "$HERE/_witnessed_vault_host.py" "$REL_BASE" doi state-doi \
  "$FX/micro-app-template.json" "$FX/schemas/carrier_license.json" "$WORK/deploy.json" 60
rc=$?
[ $rc -eq 0 ] && echo "PASS: witnessed roundtrip — carrier mailed -> vault polled -> carrier_license issued" \
             || echo "PARTIAL: vault did not issue from the polled mailbox (rc=$rc)"
exit $rc
