"""SAD/SAID + ACDC-schema compliance linter for micro-app template dirs.

Design (normative check catalog + severities):
docs/superpowers/specs/2026-07-16-acdc-schema-compliance-linter-design.md

Checks S01-S09 run per schemas/*.json document; T01-T08 run across
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
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
# Top-level compactable section properties (a/e/r): compact-form-first is
# normative here even when the author forgot the expanded variant's $id.
SECTION_PATHS = ("properties.a", "properties.e", "properties.r")
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
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
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

    # S07 -- compact-form-first (ACDC most-compact-form constraint R35).
    # A oneOf is treated as a compactable section iff an expanded variant
    # carries a $id, or it sits at a top-level section property (a/e/r).
    # A plain string-or-object data union in an attribute payload is
    # legitimate JSON-Schema authoring and is NOT gated.
    for path, node in _walk(doc):
        oneof = node.get("oneOf")
        if not isinstance(oneof, list):
            continue
        has_saided_expanded = any(
            _is_expanded_variant(br) and SAID_LABEL in br for br in oneof
        )
        has_expanded = any(_is_expanded_variant(br) for br in oneof)
        is_section = path in SECTION_PATHS
        compact_idx = [i for i, br in enumerate(oneof) if _is_compact_variant(br)]
        if not (has_saided_expanded or (is_section and has_expanded)):
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
    other than the reserved labels d/u/o. Handles both the canonical
    oneOf-wrapped section and an e section authored directly as an object
    block (the latter is an S07 smell but must not escape S09/T06).
    """
    e_section = doc.get("properties", {}).get("e")
    if not isinstance(e_section, dict):
        return
    oneof = e_section.get("oneOf")
    if isinstance(oneof, list):
        branches = [
            (f"properties.e.oneOf[{i}]", br)
            for i, br in enumerate(oneof) if _is_expanded_variant(br)
        ]
    elif isinstance(e_section.get("properties"), dict):
        branches = [("properties.e", e_section)]
    else:
        branches = []
    for base, branch in branches:
        props = branch.get("properties")
        if not isinstance(props, dict):
            continue
        for name, sub in props.items():
            if name in ("d", "u", "o"):
                continue
            if isinstance(sub, dict) and sub.get("type") == "object":
                yield (f"{base}.properties.{name}", name, sub)


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


TEMPLATE_FILE = "micro-app-template.json"
METADATA_FILE = "metadata.json"

# Template keys whose string values are schema-SAID references (T03/T04).
_SAID_REF_KEYS = ("expected_schema_said", "schema_said_referenced", "schema_said")


def _load_json(path: Path, rel: str, findings: list[LintFinding]) -> Any | None:
    """Load a JSON object file; on absence, parse failure, or a non-object
    root record F01/F02 and return None."""
    if not path.exists():
        findings.append(LintFinding(rel, "", "F01", f"{rel} not found"))
        return None
    try:
        doc = json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        findings.append(LintFinding(rel, "", "F02", f"unparseable JSON: {e}"))
        return None
    if not isinstance(doc, dict):
        findings.append(LintFinding(
            rel, "", "F02",
            f"JSON root must be an object, got {type(doc).__name__}",
        ))
        return None
    return doc


def _iter_template_said_refs(
    template: dict[str, Any],
) -> Iterator[tuple[str, str, Any, dict[str, Any]]]:
    """Yield (path, key, value, node) for every schema-SAID reference field in
    the template. `schema_said` paired with a sibling `schema_path` is the export
    pin handled by T02 and is skipped here.

    The owning `node` comes along because a pin's sibling `schema_path` is what
    T08 checks correspondence against; without it the checker holds a declared
    path it cannot read."""
    for path, node in _walk(template):
        for key in _SAID_REF_KEYS:
            if key not in node:
                continue
            if key == "schema_said" and "schema_path" in node:
                continue  # exports[].schema -- T02's job
            value = node[key]
            if value is None:
                continue
            yield (f"{path}.{key}" if path != "<root>" else key, key, value, node)


def lint_template_dir(template_dir: Path) -> LintResult:
    """Lint one micro-app template directory. Never raises on bad artifacts:
    missing/unparseable files become F01/F02 findings and remaining checks
    still run where their inputs exist."""
    findings: list[LintFinding] = []
    template_dir = Path(template_dir)

    template = _load_json(template_dir / TEMPLATE_FILE, TEMPLATE_FILE, findings)
    metadata = _load_json(template_dir / METADATA_FILE, METADATA_FILE, findings)

    # Schema files: S01-S09 each, plus collect $ids and edge pins.
    schema_docs: dict[str, dict[str, Any]] = {}
    schemas_dir = template_dir / "schemas"
    if schemas_dir.is_dir():
        for path in sorted(schemas_dir.glob("*.json")):
            rel = f"schemas/{path.name}"
            doc = _load_json(path, rel, findings)
            if doc is not None:
                schema_docs[rel] = doc
                findings.extend(lint_schema_doc(doc, rel))

    local_saids = {
        doc[SAID_LABEL]: rel for rel, doc in schema_docs.items()
        if isinstance(doc.get(SAID_LABEL), str) and doc[SAID_LABEL]
    }

    referenced_paths: set[str] = set()
    referenced_saids: set[str] = set()

    if template is not None:
        # T01 -- template's own SAID
        if not verify_said(template):
            findings.append(LintFinding(
                TEMPLATE_FILE, "d", "T01",
                "template d SAID does not verify against the canonical "
                "(sorted-keys) form",
            ))

        # T02 -- export schema pins
        credentials = template.get("credentials")
        credentials = credentials if isinstance(credentials, dict) else {}
        exports = credentials.get("exports")
        exports = exports if isinstance(exports, list) else []
        for i, export in enumerate(exports):
            if not isinstance(export, dict):
                continue
            schema_ref = export.get("schema")
            if not isinstance(schema_ref, dict):
                continue
            base = f"credentials.exports[{i}].schema"
            schema_path = schema_ref.get("schema_path")
            schema_said = schema_ref.get("schema_said")
            if schema_said is not None and not is_bare_said(schema_said):
                findings.append(LintFinding(
                    TEMPLATE_FILE, f"{base}.schema_said", "T02",
                    f"schema_said {schema_said!r} is not a well-formed bare "
                    "SAID",
                ))
            if schema_path:
                referenced_paths.add(schema_path)
                if schema_path not in schema_docs:
                    findings.append(LintFinding(
                        TEMPLATE_FILE, f"{base}.schema_path", "T02",
                        f"schema_path {schema_path!r} not found in template "
                        "directory",
                    ))
                elif schema_docs[schema_path].get(SAID_LABEL) != schema_said:
                    findings.append(LintFinding(
                        TEMPLATE_FILE, f"{base}.schema_said", "T02",
                        f"schema_said {schema_said!r} does not match "
                        f"{schema_path}'s $id "
                        f"{schema_docs[schema_path].get(SAID_LABEL)!r}",
                    ))
            if isinstance(schema_said, str):
                referenced_saids.add(schema_said)

        # T03/T04 -- every other schema-SAID reference in the template
        # T08 -- ...and, when the pin declares its own schema_path, that the pin
        # is the $id of THAT file. Only T02's export half checked correspondence;
        # imports gained schema_path later and fell through to T03, which checks
        # well-formedness and local existence only. So a pin at a sibling schema
        # in the same dir -- what a hand-run SAID cascade produces -- was the one
        # corruption the linter reported nothing at all for.
        for path, key, value, node in _iter_template_said_refs(template):
            code = "T03" if key == "expected_schema_said" else "T04"
            if not is_bare_said(value):
                findings.append(LintFinding(
                    TEMPLATE_FILE, path, code,
                    f"{key} {value!r} is not a well-formed bare SAID",
                ))
                continue
            referenced_saids.add(value)
            declared_path = node.get("schema_path")
            if value not in local_saids:
                # Deliberately still a warning even when schema_path is present:
                # resolving to nothing local means the linter can confirm nothing
                # locally -- a counterparty schema legitimately lives in its own
                # template dir, and mid-cascade a vendored copy can carry a
                # placeholder $id while the pin already carries the minted SAID.
                findings.append(LintFinding(
                    TEMPLATE_FILE, path, code,
                    f"{key} {value!r} does not match any local schemas/*.json "
                    "$id -- assumed external; verify against the ecosystem "
                    "schema registry (future EGF resolver)",
                    severity="warning",
                ))
            elif (declared_path
                  and schema_docs.get(declared_path, {}).get(SAID_LABEL) != value):
                # Reads the DECLARED file's own $id -- T02's comparison exactly,
                # one field over -- not a SAID->file map. Two byte-identical
                # schemas in one dir share a $id, so a map keeps only one and
                # would call an import declaring the other mis-pinned.
                findings.append(LintFinding(
                    TEMPLATE_FILE, path, "T08",
                    f"{key} {value!r} is the $id of {local_saids[value]}, not of "
                    f"the declared schema_path {declared_path!r}",
                ))

        # T05 -- metadata binds to this template
        if metadata is not None:
            if metadata.get("for_micro_app_said") != template.get("d"):
                findings.append(LintFinding(
                    METADATA_FILE, "for_micro_app_said", "T05",
                    f"for_micro_app_said "
                    f"{metadata.get('for_micro_app_said')!r} does not match "
                    f"the template's d {template.get('d')!r}",
                ))

    # T06 -- edge `s` const pins resolve against known SAIDs
    pin_saids: set[str] = set()
    all_pins: list[tuple[str, str, str]] = []
    for rel, doc in schema_docs.items():
        for path, said in collect_edge_schema_pins(doc):
            all_pins.append((rel, path, said))
            pin_saids.add(said)
    known_saids = set(local_saids) | referenced_saids
    for rel, path, said in all_pins:
        if said not in known_saids:
            findings.append(LintFinding(
                rel, path, "T06",
                f"edge schema pin {said!r} does not resolve to a local "
                "schema $id or any template-referenced SAID -- assumed "
                "external",
                severity="warning",
            ))

    # T07 -- orphan schema files (edge pins count as references too)
    for rel, doc in schema_docs.items():
        said = doc.get(SAID_LABEL)
        if rel not in referenced_paths and said not in (referenced_saids | pin_saids):
            findings.append(LintFinding(
                rel, "", "T07",
                "schema file is not referenced by any export schema_path, "
                "import/emission SAID, or edge pin",
                severity="warning",
            ))

    return LintResult(findings=findings)
