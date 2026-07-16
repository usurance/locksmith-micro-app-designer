#!/usr/bin/env python3
"""CLI wrapper: validate a micro-app template against the meta-schema and cross-references."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from locksmith_micro_app_designer.template.validate import validate_template


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = REPO_ROOT / "docs/superpowers/specs/schemas/micro-app-template.schema.json"


def main() -> int:
    p = argparse.ArgumentParser(description="Validate a micro-app template.")
    p.add_argument("--input", required=True, type=Path, help="Path to micro-app-template.json")
    p.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Path to meta-schema (default: project meta-schema)")
    p.add_argument(
        "--lint", action="store_true",
        help="Also run the SAD/SAID + ACDC-schema compliance lint over the "
             "template directory (requires keripy from the Locksmith venv)",
    )
    args = p.parse_args()

    if not args.input.exists():
        print(f"error: file not found: {args.input}", file=sys.stderr)
        return 2
    if not args.schema.exists():
        print(f"error: schema not found: {args.schema}", file=sys.stderr)
        return 2

    doc = json.loads(args.input.read_text())
    result = validate_template(doc, args.schema)

    if result.is_valid:
        print(f"OK: {args.input} validates against {args.schema.name}")
    else:
        print(f"FAIL: {args.input}", file=sys.stderr)
        for e in result.errors:
            print(f"  {e.path}: {e.message}", file=sys.stderr)

    ok = result.is_valid

    if args.lint:
        try:
            from locksmith_micro_app_designer.template.lint import lint_template_dir
        except ImportError as e:
            print(
                "error: --lint requires keripy (install into / run from the "
                f"Locksmith venv, e.g. ~/code/locksmith/.venv): {e}",
                file=sys.stderr,
            )
            return 2

        lint_result = lint_template_dir(args.input.parent)
        for f in lint_result.findings:
            loc = f"{f.file}:{f.path}" if f.path else f.file
            line = f"  {f.severity.upper()} {f.code} {loc}: {f.message}"
            print(line, file=sys.stderr if f.severity == "error" else sys.stdout)
        if lint_result.is_compliant:
            print(
                f"LINT OK: {args.input.parent} "
                f"({len(lint_result.warnings)} warning(s))"
            )
        else:
            print(f"LINT FAIL: {args.input.parent}", file=sys.stderr)
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
