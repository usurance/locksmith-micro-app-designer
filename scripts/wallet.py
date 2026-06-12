#!/usr/bin/env python3
"""Drive the *running* Locksmith wallet from the shell, using the same driver
the integration tests use. Targets the default control socket.

Examples:
    python scripts/wallet.py create-vault automation noble
    python scripts/wallet.py open-vault automation noble
    python scripts/wallet.py open-designer
    python scripts/wallet.py screenshot /tmp/wallet.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the driver importable without installing anything.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "integration"))

from driver.client import Client  # noqa: E402
from driver import actions  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Drive the running Locksmith wallet")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create-vault")
    p_create.add_argument("name")
    p_create.add_argument("passcode")

    p_open = sub.add_parser("open-vault")
    p_open.add_argument("name")
    p_open.add_argument("passcode")

    sub.add_parser("open-designer")

    p_shot = sub.add_parser("screenshot")
    p_shot.add_argument("path")

    args = parser.parse_args()
    client = Client()

    if args.cmd == "create-vault":
        result = actions.create_vault(client, args.name, args.passcode)
    elif args.cmd == "open-vault":
        result = actions.open_vault(client, args.name, args.passcode)
    elif args.cmd == "open-designer":
        result = actions.open_designer(client)
    elif args.cmd == "screenshot":
        result = client.call("screenshot", path=args.path)
    else:  # pragma: no cover
        parser.error(f"unknown command {args.cmd!r}")

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
