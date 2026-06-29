#!/usr/bin/env bash
# Full-chain (in-wallet) acceptance: the DOI micro-app Service-AID runs INSIDE a
# real Locksmith vault and issues a carrier_license when a carrier's
# grant_license command exn is routed through the wallet's exchanger (vault.exc).
#
# Cross-repo: imports locksmith (venv editable) + keri (venv) + concierge_api_local
# (../concierge-api/src) + keri_serviceaid (../keripy). Headless via offscreen Qt.
# This is the faithful counterpart to concierge's grant_license_e2e.sh; the witness
# MAILBOX hop is the only stubbed leg (proven elsewhere: peer-mode + CDK federation).
#
# Usage: bash tests/integration/microapp_in_vault_e2e.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-$HOME/code/locksmith/.venv/bin/python}"

export QT_QPA_PLATFORM=offscreen
export PYTHONPATH="$REPO/src:$REPO/../concierge-api/src:$REPO/../keripy"

echo "== micro-app inside a real Locksmith vault: grant -> issue (TEL iss) =="
"$PY" -m pytest "$HERE/test_microapp_in_vault.py" -q --import-mode=importlib
echo "PASS: micro-app Service-AID issued a carrier_license hosted by the real vault"
