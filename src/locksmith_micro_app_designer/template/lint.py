"""SAD/SAID + ACDC-schema compliance linter for micro-app template dirs.

Design (normative check catalog + severities):
docs/superpowers/specs/2026-07-16-acdc-schema-compliance-linter-design.md

Checks S01-S09 run per schemas/*.json document; T01-T07 run across
micro-app-template.json + metadata.json + schemas/; F01/F02 are
file-level (missing / unparseable). Severity "error" = ACDC-spec MUST
violation or SAID/xref integrity failure; "warning" = well-formed but
locally unresolvable (assumed external) or hygiene.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from locksmith_micro_app_designer.template.saidify import verify_said
from locksmith_micro_app_designer.template.schema_said import (
    SAID_LABEL,
    is_bare_said,
    iter_said_blocks,
    verify_schema_said,
)

ACDC_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
EDGE_OPERATORS = ("I2I", "NI2I", "DI2I")
DYNAMIC_REF_KEYWORDS = (
    "$dynamicRef", "$dynamicAnchor", "$recursiveRef", "$recursiveAnchor",
)

# ACDC reserved field labels -> JSON-Schema types they may declare.
# None = any type acceptable (cargo). Per keri:acdc references/acdc-structure.md.
RESERVED_LABEL_TYPES: dict[str, tuple[str, ...] | None] = {
    "d": ("string",),
    "u": ("string",),
    "i": ("string",),
    "rd": ("string",),
    "dt": ("string",),
    "n": ("string",),
    "o": ("string",),
    "w": ("string", "number", "integer"),
    "l": ("string",),
    "cargo": None,
}


@dataclass
class LintFinding:
    """A single compliance finding."""
    file: str
    path: str
    code: str
    message: str
    severity: str = "error"  # error | warning


@dataclass
class LintResult:
    """All findings for one template directory."""
    findings: list[LintFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def is_compliant(self) -> bool:
        return not self.errors


def _walk(node: Any, path: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (path, d) for every dict in node, depth-first, insertion order."""
    if isinstance(node, dict):
        yield (path or "<root>", node)
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from _walk(item, f"{path}[{i}]")


def _is_compact_variant(branch: Any) -> bool:
    return isinstance(branch, dict) and branch.get("type") == "string"


def _is_expanded_variant(branch: Any) -> bool:
    return isinstance(branch, dict) and branch.get("type") == "object"


def lint_schema_doc(doc: dict[str, Any], file: str) -> list[LintFinding]:
    """Run per-schema-file checks S01-S09; return findings (file tagged)."""
    findings: list[LintFinding] = []

    # S01 -- top-level $id present and non-empty
    top = doc.get(SAID_LABEL)
    if not isinstance(top, str) or not top:
        findings.append(LintFinding(
            file, SAID_LABEL, "S01", "top-level $id missing or empty",
        ))

    # S02/S03 -- every $id block: bare SAID that verifies
    for path, block in iter_said_blocks(doc):
        value = block.get(SAID_LABEL)
        if not isinstance(value, str) or not value:
            if path != "<root>":  # root covered by S01
                findings.append(LintFinding(
                    file, f"{path}.{SAID_LABEL}", "S02",
                    "bundled sub-schema $id missing or empty",
                ))
            continue
        if not is_bare_said(value):
            findings.append(LintFinding(
                file, f"{path}.{SAID_LABEL}", "S02",
                f"$id {value!r} is not a bare SAID (URI prefixes are "
                "forbidden; must parse as a CESR digest)",
            ))
            continue
        if not verify_schema_said(block):
            findings.append(LintFinding(
                file, f"{path}.{SAID_LABEL}", "S03",
                f"$id does not verify: SAID recomputed over the block's "
                f"content differs from claimed {value!r} (schema SAIDs "
                "hash the file's insertion order; see design spec)",
            ))

    # S04 -- $schema dialect
    if doc.get("$schema") != ACDC_DIALECT:
        findings.append(LintFinding(
            file, "$schema", "S04",
            f"$schema must be {ACDC_DIALECT!r} (ACDC 1.0), "
            f"got {doc.get('$schema')!r}",
        ))

    # S05 -- version present, major.minor.patch
    version = doc.get("version")
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        findings.append(LintFinding(
            file, "version", "S05",
            f"version field must be present in 'major.minor.patch' form "
            f"(ACDC Schema Versioning MUST), got {version!r}",
        ))

    # S06 -- static-schema rules: no dynamic refs; $ref local or SAIDified
    for path, node in _walk(doc):
        for kw in DYNAMIC_REF_KEYWORDS:
            if kw in node:
                findings.append(LintFinding(
                    file, f"{path}.{kw}", "S06",
                    f"dynamic schema reference {kw} is forbidden "
                    "(static-schema rule)",
                ))
        ref = node.get("$ref")
        if isinstance(ref, str):
            local = ref.startswith("#")
            saidified = (
                is_bare_said(ref)
                or ref.startswith("sad:")
                or ref.startswith("did:")
            )
            if not (local or saidified):
                findings.append(LintFinding(
                    file, f"{path}.$ref", "S06",
                    f"non-local $ref {ref!r} is forbidden (must be local "
                    "'#...' or a static SAIDified reference: bare SAID, "
                    "'sad:SAID', or 'did:...')",
                ))

    # S07 -- compact-form-first (ACDC most-compact-form constraint R35)
    for path, node in _walk(doc):
        oneof = node.get("oneOf")
        if not isinstance(oneof, list):
            continue
        has_saided_expanded = any(
            _is_expanded_variant(br) and SAID_LABEL in br for br in oneof
        )
        has_expanded = any(_is_expanded_variant(br) for br in oneof)
        compact_idx = [i for i, br in enumerate(oneof) if _is_compact_variant(br)]
        if not (has_saided_expanded or (has_expanded and compact_idx)):
            continue  # not a compactable-section oneOf
        if not compact_idx:
            findings.append(LintFinding(
                file, f"{path}.oneOf", "S07",
                "compactable section oneOf has no compact (string SAID) "
                "variant (R35)",
            ))
        elif compact_idx[0] != 0 or _is_expanded_variant(oneof[0]):
            findings.append(LintFinding(
                file, f"{path}.oneOf", "S07",
                "compact (string SAID) variant must be FIRST in a "
                "compactable section's oneOf (R35)",
            ))
        for i, br in enumerate(oneof):
            if _is_expanded_variant(br) and SAID_LABEL not in br:
                findings.append(LintFinding(
                    file, f"{path}.oneOf[{i}]", "S02",
                    "expanded variant of a compactable section must carry "
                    "its own verifiable $id (bundled sub-schema rule)",
                ))

    # S08 -- reserved field labels keep their spec types
    for path, node in _walk(doc):
        props = node.get("properties")
        if not isinstance(props, dict):
            continue
        for label, allowed in RESERVED_LABEL_TYPES.items():
            sub = props.get(label)
            if allowed is None or not isinstance(sub, dict):
                continue
            declared = sub.get("type")
            declared_types = (
                [declared] if isinstance(declared, str)
                else declared if isinstance(declared, list) else None
            )
            if declared_types is None:
                continue
            if not set(declared_types) <= set(allowed):
                findings.append(LintFinding(
                    file, f"{path}.properties.{label}.type", "S08",
                    f"reserved ACDC field label {label!r} redefined with "
                    f"divergent type {declared!r} (spec type: "
                    f"{'/'.join(allowed)})",
                ))

    # S09 -- edge blocks: n required; o const in I2I/NI2I/DI2I; s const a SAID
    for path, edge_name, edge in _iter_edge_blocks(doc):
        required = edge.get("required", [])
        if "n" not in required:
            findings.append(LintFinding(
                file, f"{path}.required", "S09",
                f"edge block {edge_name!r} must require 'n' (node SAID)",
            ))
        edge_props = edge.get("properties", {})
        o_const = edge_props.get("o", {}).get("const") if isinstance(
            edge_props.get("o"), dict) else None
        if o_const is not None and o_const not in EDGE_OPERATORS:
            findings.append(LintFinding(
                file, f"{path}.properties.o.const", "S09",
                f"edge operator const {o_const!r} must be one of "
                f"{'/'.join(EDGE_OPERATORS)}",
            ))
        s_const = edge_props.get("s", {}).get("const") if isinstance(
            edge_props.get("s"), dict) else None
        if s_const is not None and not is_bare_said(s_const):
            findings.append(LintFinding(
                file, f"{path}.properties.s.const", "S09",
                f"edge schema pin const {s_const!r} is not a well-formed "
                "bare SAID",
            ))

    return findings


def _iter_edge_blocks(
    doc: dict[str, Any],
) -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Yield (path, edge_name, edge_block) for every edge definition in the
    expanded variant(s) of the top-level `e` section.

    An edge definition is any object-typed property of the expanded e-block
    other than the reserved labels d/u/o.
    """
    e_section = doc.get("properties", {}).get("e")
    if not isinstance(e_section, dict):
        return
    for i, branch in enumerate(e_section.get("oneOf", [])):
        if not _is_expanded_variant(branch):
            continue
        for name, sub in branch.get("properties", {}).items():
            if name in ("d", "u", "o"):
                continue
            if isinstance(sub, dict) and sub.get("type") == "object":
                yield (
                    f"properties.e.oneOf[{i}].properties.{name}", name, sub,
                )


def collect_edge_schema_pins(doc: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (path, said) for every well-formed `s` const pin in the
    expanded e-section edge blocks. T06 resolves these against the known-
    SAID set; S09 already reports malformed ones."""
    pins: list[tuple[str, str]] = []
    for path, _name, edge in _iter_edge_blocks(doc):
        s_sub = edge.get("properties", {}).get("s")
        if isinstance(s_sub, dict):
            s_const = s_sub.get("const")
            if isinstance(s_const, str) and is_bare_said(s_const):
                pins.append((f"{path}.properties.s.const", s_const))
    return pins
