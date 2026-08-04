"""Tests for the SAD/SAID + ACDC-schema compliance linter (S/T/F checks)."""
from __future__ import annotations

import copy
import json

from locksmith_micro_app_designer.template.lint import (
    LintFinding,
    LintResult,
    collect_edge_schema_pins,
    lint_schema_doc,
)
from locksmith_micro_app_designer.template.schema_said import saidify_schema_block

from .conftest import make_compliant_schema


def _codes(findings) -> set[str]:
    return {f.code for f in findings}


def _resaidify(schema: dict) -> dict:
    """Re-stamp nested attribute block then the envelope (bottom-up)."""
    schema = copy.deepcopy(schema)
    a_oneof = schema.get("properties", {}).get("a", {}).get("oneOf")
    if a_oneof and isinstance(a_oneof[-1], dict) and "$id" in a_oneof[-1]:
        a_oneof[-1] = saidify_schema_block(a_oneof[-1])
    return saidify_schema_block(schema)


def _resaidify_swapped(schema: dict) -> dict:
    schema = copy.deepcopy(schema)
    oneof = schema["properties"]["a"]["oneOf"]
    for i, br in enumerate(oneof):
        if isinstance(br, dict) and "$id" in br:
            oneof[i] = saidify_schema_block(br)
    return saidify_schema_block(schema)


def make_edge_section(pin_said: str, operator: str = "NI2I") -> dict:
    """An expanded-e-section oneOf like the carrier_license worked example."""
    return {
        "oneOf": [
            {"description": "Edge block SAID, compact form.", "type": "string"},
            {
                "$id": "",
                "description": "Edges.",
                "type": "object",
                "properties": {
                    "d": {"description": "Edge block SAID.", "type": "string"},
                    "application": {
                        "description": "Edge to the adjudicated application.",
                        "type": "object",
                        "properties": {
                            "n": {"description": "Node SAID.", "type": "string"},
                            "s": {
                                "description": "Node schema SAID.",
                                "type": "string",
                                "const": pin_said,
                            },
                            "o": {
                                "description": "Edge operator.",
                                "type": "string",
                                "const": operator,
                            },
                        },
                        "additionalProperties": False,
                        "required": ["n", "s", "o"],
                    },
                },
                "additionalProperties": False,
                "required": ["d", "application"],
            },
        ]
    }


def make_schema_with_edges(pin_said: str, operator: str = "NI2I") -> dict:
    schema = make_compliant_schema()
    schema["properties"]["e"] = make_edge_section(pin_said, operator)
    schema["properties"]["e"]["oneOf"][1] = saidify_schema_block(
        schema["properties"]["e"]["oneOf"][1]
    )
    schema["required"] = schema["required"] + ["e"]
    return saidify_schema_block(schema)


VALID_EXTERNAL_SAID = "ENbhxLlFINUDp1EU4mV5RVVL-CS6Ub72zXY89EcM7Ccb"


def test_compliant_schema_has_no_findings():
    assert lint_schema_doc(make_compliant_schema(), "schemas/x.json") == []


def test_compliant_schema_with_edges_has_no_findings():
    doc = make_schema_with_edges(VALID_EXTERNAL_SAID)
    assert lint_schema_doc(doc, "schemas/x.json") == []


def test_s01_missing_top_level_id():
    doc = make_compliant_schema()
    del doc["$id"]
    assert "S01" in _codes(lint_schema_doc(doc, "f"))


def test_s02_uri_prefixed_id():
    doc = make_compliant_schema()
    doc["$id"] = f"did:keri:{doc['$id']}"
    assert "S02" in _codes(lint_schema_doc(doc, "f"))


def test_s02_expanded_variant_missing_id():
    doc = make_compliant_schema()
    del doc["properties"]["a"]["oneOf"][1]["$id"]
    doc = saidify_schema_block(doc)
    assert "S02" in _codes(lint_schema_doc(doc, "f"))


def test_s03_top_level_tamper():
    doc = make_compliant_schema()
    doc["title"] = "Tampered"
    findings = lint_schema_doc(doc, "f")
    assert any(f.code == "S03" and f.path.startswith("<root>") for f in findings)


def test_s03_nested_tamper():
    doc = make_compliant_schema()
    doc["properties"]["a"]["oneOf"][1]["description"] = "tampered"
    doc = saidify_schema_block(doc)  # top-level re-stamped; nested left stale
    findings = lint_schema_doc(doc, "f")
    assert any(f.code == "S03" and "oneOf[1]" in f.path for f in findings)


def test_s04_wrong_or_missing_dialect():
    doc = make_compliant_schema()
    doc["$schema"] = "http://json-schema.org/draft-07/schema#"
    assert "S04" in _codes(lint_schema_doc(_resaidify(doc), "f"))
    doc2 = make_compliant_schema()
    del doc2["$schema"]
    assert "S04" in _codes(lint_schema_doc(_resaidify(doc2), "f"))


def test_s05_missing_or_malformed_version():
    doc = make_compliant_schema()
    del doc["version"]
    assert "S05" in _codes(lint_schema_doc(_resaidify(doc), "f"))
    doc2 = make_compliant_schema()
    doc2["version"] = "1.0"
    assert "S05" in _codes(lint_schema_doc(_resaidify(doc2), "f"))


def test_s06_nonlocal_and_dynamic_refs():
    doc = make_compliant_schema()
    doc["properties"]["extra"] = {"$ref": "https://example.com/x.json"}
    assert "S06" in _codes(lint_schema_doc(_resaidify(doc), "f"))
    doc2 = make_compliant_schema()
    doc2["properties"]["extra"] = {"$dynamicRef": "#thing"}
    assert "S06" in _codes(lint_schema_doc(_resaidify(doc2), "f"))


def test_s06_local_and_said_refs_allowed():
    doc = make_compliant_schema()
    doc["properties"]["extra"] = {"$ref": "#/properties/d"}
    doc["properties"]["extra2"] = {"$ref": VALID_EXTERNAL_SAID}
    assert "S06" not in _codes(lint_schema_doc(_resaidify(doc), "f"))


def test_s07_compact_variant_not_first():
    doc = make_compliant_schema()
    oneof = doc["properties"]["a"]["oneOf"]
    doc["properties"]["a"]["oneOf"] = [oneof[1], oneof[0]]
    assert "S07" in _codes(lint_schema_doc(_resaidify_swapped(doc), "f"))


def test_s07_compactable_oneof_missing_compact_variant():
    doc = make_compliant_schema()
    doc["properties"]["a"]["oneOf"] = [doc["properties"]["a"]["oneOf"][1]]
    assert "S07" in _codes(lint_schema_doc(_resaidify(doc), "f"))


def test_s08_reserved_label_type_divergence():
    doc = make_compliant_schema()
    doc["properties"]["a"]["oneOf"][1]["properties"]["dt"] = {
        "description": "wrong",
        "type": "object",
    }
    assert "S08" in _codes(lint_schema_doc(_resaidify(doc), "f"))


def test_s08_w_accepts_string_or_number():
    doc = make_compliant_schema()
    doc["properties"]["a"]["oneOf"][1]["properties"]["w"] = {
        "description": "weight",
        "type": "number",
    }
    assert "S08" not in _codes(lint_schema_doc(_resaidify(doc), "f"))


def test_s09_edge_missing_required_n():
    doc = make_schema_with_edges(VALID_EXTERNAL_SAID)
    edge = doc["properties"]["e"]["oneOf"][1]["properties"]["application"]
    edge["required"] = ["s", "o"]
    doc["properties"]["e"]["oneOf"][1] = saidify_schema_block(
        doc["properties"]["e"]["oneOf"][1]
    )
    assert "S09" in _codes(lint_schema_doc(saidify_schema_block(doc), "f"))


def test_s09_bad_edge_operator():
    doc = make_schema_with_edges(VALID_EXTERNAL_SAID, operator="X2X")
    assert "S09" in _codes(lint_schema_doc(doc, "f"))


def test_s09_malformed_edge_schema_pin():
    doc = make_schema_with_edges("not-a-said")
    assert "S09" in _codes(lint_schema_doc(doc, "f"))


def test_collect_edge_schema_pins():
    doc = make_schema_with_edges(VALID_EXTERNAL_SAID)
    pins = collect_edge_schema_pins(doc)
    assert pins == [
        ("properties.e.oneOf[1].properties.application.properties.s.const",
         VALID_EXTERNAL_SAID)
    ]


def test_lint_result_severity_partitions():
    r = LintResult(findings=[
        LintFinding("f", "p", "S05", "m", "error"),
        LintFinding("f", "p", "T03", "m", "warning"),
    ])
    assert len(r.errors) == 1 and len(r.warnings) == 1
    assert r.is_compliant is False


# ---------------------------------------------------------------------------
# Dir-level checks (T01-T07, F01/F02) and golden worked-example expectations
# ---------------------------------------------------------------------------

from pathlib import Path

import pytest

from locksmith_micro_app_designer.template.lint import lint_template_dir
from locksmith_micro_app_designer.template.saidify import saidify_document

from .conftest import write_template_dir

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLES = REPO_ROOT / "skills/micro-app-template-gen/references/examples"


def _read_dir(root: Path) -> tuple[dict, dict, dict]:
    template = json.loads((root / "micro-app-template.json").read_text())
    metadata = json.loads((root / "metadata.json").read_text())
    schemas = {
        p.name: json.loads(p.read_text())
        for p in sorted((root / "schemas").glob("*.json"))
    }
    return template, metadata, schemas


def test_compliant_dir_zero_findings(compliant_template_dir):
    result = lint_template_dir(compliant_template_dir)
    assert result.findings == []
    assert result.is_compliant is True


def test_t01_template_said_tamper(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["header"]["description"] = "tampered"
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert "T01" in _codes(r.errors)


def test_t02_missing_schema_file(compliant_template_dir):
    (compliant_template_dir / "schemas/test_credential.json").unlink()
    r = lint_template_dir(compliant_template_dir)
    assert "T02" in _codes(r.errors)


def test_t02_schema_said_mismatch(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["credentials"]["exports"][0]["schema"]["schema_said"] = (
        VALID_EXTERNAL_SAID
    )
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert "T02" in _codes(r.errors)


def test_t03_malformed_import_said_is_error(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["credentials"]["imports"] = [
        {"id": "other_credential", "expected_schema_said": "not-a-said"}
    ]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "T03" and f.severity == "error" for f in r.findings)


def test_t03_unresolved_import_said_is_external_warning(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["credentials"]["imports"] = [
        {"id": "other_credential", "expected_schema_said": VALID_EXTERNAL_SAID}
    ]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "T03" and f.severity == "warning" for f in r.findings)
    assert r.is_compliant is True


def test_t04_emission_and_authz_saids(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["commands"] = [{
        "id": "do_thing",
        "emissions": [{
            "kind": "credential",
            "verb": "grant",
            "schema_said_referenced": VALID_EXTERNAL_SAID,
        }],
        "authz": {"method": "credential", "schema_said": "not-a-said"},
    }]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    t04 = [f for f in r.findings if f.code == "T04"]
    assert any(f.severity == "warning" for f in t04)  # external emission SAID
    assert any(f.severity == "error" for f in t04)    # malformed authz SAID


def test_t05_metadata_said_mismatch(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    metadata["for_micro_app_said"] = VALID_EXTERNAL_SAID
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert "T05" in _codes(r.errors)


def test_t06_unresolved_edge_pin_warns(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    schema = make_schema_with_edges(VALID_EXTERNAL_SAID)
    template["credentials"]["exports"][0]["schema"]["schema_said"] = schema["$id"]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(
        compliant_template_dir, template, metadata,
        {"test_credential.json": schema},
    )
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "T06" and f.severity == "warning" for f in r.findings)


def test_t06_edge_pin_resolved_by_template_reference(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    schema = make_schema_with_edges(VALID_EXTERNAL_SAID)
    template["credentials"]["exports"][0]["schema"]["schema_said"] = schema["$id"]
    template["credentials"]["imports"] = [
        {"id": "other_credential", "expected_schema_said": VALID_EXTERNAL_SAID}
    ]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(
        compliant_template_dir, template, metadata,
        {"test_credential.json": schema},
    )
    r = lint_template_dir(compliant_template_dir)
    assert "T06" not in _codes(r.findings)


def test_t07_orphan_schema_warns(compliant_template_dir):
    orphan = make_compliant_schema()
    orphan["title"] = "Orphan Credential"  # distinct content -> distinct $id
    orphan = saidify_schema_block(orphan)
    (compliant_template_dir / "schemas/orphan.json").write_text(
        json.dumps(orphan, indent=2) + "\n"
    )
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "T07" and f.severity == "warning" for f in r.findings)


# --- T08: an import pin must point where the import says it points -------------
# B18. T02 has verified export pin/file correspondence from the start. Imports only
# GAINED `schema_path` in the contour-alignment redesign, after T02 was written, so
# they fell through to T03, which checks well-formedness and local existence and
# never correspondence. Measured verdicts on a corrupted import pin before T08:
# malformed -> T03 error; resolves to nothing local -> T03 warning; resolves to the
# WRONG local schema -> LINT OK, zero findings. The worst corruption was the
# quietest, and it is exactly what a hand-run SAID cascade produces.

def _add_second_schema(root, template, metadata, schemas, title="Other Credential"):
    """Vendor a second, distinct schema into the dir and return (schema, filename)."""
    other = make_compliant_schema()
    other["title"] = title  # distinct content -> distinct $id
    other = saidify_schema_block(other)
    schemas["other_credential.json"] = other
    return other


def test_t08_import_pin_at_the_wrong_local_schema_is_error(compliant_template_dir):
    """The silent row. The pin is well-formed AND resolves locally -- just not to the
    file the import itself declares. This is the sibling-schema mis-pin."""
    template, metadata, schemas = _read_dir(compliant_template_dir)
    _add_second_schema(compliant_template_dir, template, metadata, schemas)
    template["credentials"]["imports"] = [{
        "id": "other_credential",
        "schema_path": "schemas/other_credential.json",
        # ...but pinned at the EXPORT's schema -- a sibling in the same dir.
        "expected_schema_said": template["credentials"]["exports"][0]["schema"]["schema_said"],
    }]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert "T08" in _codes(r.errors)
    assert r.is_compliant is False


def test_t08_import_pin_matching_its_declared_path_is_clean(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    other = _add_second_schema(compliant_template_dir, template, metadata, schemas)
    template["credentials"]["imports"] = [{
        "id": "other_credential",
        "schema_path": "schemas/other_credential.json",
        "expected_schema_said": other["$id"],
    }]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert r.findings == []


def test_t08_external_pin_stays_a_warning_even_with_schema_path(compliant_template_dir):
    """The row T08 must NOT touch. A pin resolving to no local schema means the
    linter can confirm nothing locally -- including whether the vendored copy is
    current -- and "assumed external" is the right verdict: a counterparty schema
    legitimately lives in its own template dir, and mid-cascade a vendored copy can
    still carry a placeholder $id while the pin carries the minted SAID. T08 fires
    only when the pin definitively names a DIFFERENT schema this dir actually holds."""
    template, metadata, schemas = _read_dir(compliant_template_dir)
    _add_second_schema(compliant_template_dir, template, metadata, schemas)
    template["credentials"]["imports"] = [{
        "id": "other_credential",
        "schema_path": "schemas/other_credential.json",
        "expected_schema_said": VALID_EXTERNAL_SAID,
    }]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert "T08" not in _codes(r.findings)
    assert any(f.code == "T03" and f.severity == "warning" for f in r.findings)
    assert r.is_compliant is True


def test_t08_reads_the_declared_file_not_a_said_to_file_map(compliant_template_dir):
    """Two byte-identical schema files in one dir share a `$id`, so a SAID->file
    map keeps only one of them and an import declaring the other looks mis-pinned.
    T08 must read the `$id` of the file the import DECLARES -- which is what T02
    does for exports -- rather than ask a map where that SAID "lives"."""
    template, metadata, schemas = _read_dir(compliant_template_dir)
    twin = make_compliant_schema()  # identical content -> identical $id
    schemas["aaa_twin.json"] = twin
    schemas["zzz_twin.json"] = copy.deepcopy(twin)
    template["credentials"]["imports"] = [{
        "id": "twin",
        "schema_path": "schemas/aaa_twin.json",  # the one a sorted-glob map loses
        "expected_schema_said": twin["$id"],
    }]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert "T08" not in _codes(r.findings)
    assert r.is_compliant is True


def test_f01_missing_metadata(compliant_template_dir):
    (compliant_template_dir / "metadata.json").unlink()
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "F01" and f.file == "metadata.json" for f in r.errors)


def test_f01_missing_template(tmp_path):
    (tmp_path / "schemas").mkdir()
    r = lint_template_dir(tmp_path)
    assert any(
        f.code == "F01" and f.file == "micro-app-template.json"
        for f in r.errors
    )


def test_f02_unparseable_schema(compliant_template_dir):
    (compliant_template_dir / "schemas/broken.json").write_text("not json")
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "F02" and f.file == "schemas/broken.json" for f in r.errors)


@pytest.mark.parametrize("name", [
    "regulator-grants-carrier-license",
    "carrier-license-application",
])
def test_worked_examples_fully_compliant(name):
    """The bundled examples are fully lint-compliant since the 2026-07-16
    schema-version migration (owner-scheduled): `version` was added to both
    carrier schemas, re-SAIDing them and re-pinning every reference
    (templates, locksmith CarrierPlugin trust constant, concierge-api
    doi.py/deploy.json, integration fixtures, ugard mirrors). Only the
    expected cross-template external-SAID warnings remain."""
    result = lint_template_dir(EXAMPLES / name)
    assert result.errors == []
    assert result.is_compliant is True
    assert _codes(result.warnings) <= {"T03", "T04", "T06", "T07"}
    if name == "regulator-grants-carrier-license":
        # The regulator imports the carrier's application schema (external)
        # and spurns against it -- these external warnings MUST fire.
        assert {"T03", "T04"} <= _codes(result.warnings)


# ---------------------------------------------------------------------------
# Review-hardening round (whole-range review findings 1-7)
# ---------------------------------------------------------------------------


def test_s05_trailing_newline_version_rejected():
    doc = make_compliant_schema()
    doc["version"] = "1.0.0\n"
    assert "S05" in _codes(lint_schema_doc(_resaidify(doc), "f"))


def test_s07_plain_data_union_not_flagged():
    """A string-or-object union in an attribute payload is legitimate
    JSON-Schema authoring, not a compactable section -- no S07/S02."""
    doc = make_compliant_schema()
    doc["properties"]["a"]["oneOf"][1]["properties"]["contact"] = {
        "description": "Free-form contact.",
        "oneOf": [
            {"description": "Structured.", "type": "object",
             "properties": {"email": {"type": "string"}}},
            {"description": "Plain string.", "type": "string"},
        ],
    }
    codes = _codes(lint_schema_doc(_resaidify(doc), "f"))
    assert "S07" not in codes and "S02" not in codes


def test_s07_top_level_section_still_gated_without_saided_variant():
    """Top-level a/e/r sections are compactable by definition: an expanded
    variant with no $id still draws S02, and a missing compact variant S07."""
    doc = make_compliant_schema()
    del doc["properties"]["a"]["oneOf"][1]["$id"]
    doc = saidify_schema_block(doc)
    assert "S02" in _codes(lint_schema_doc(doc, "f"))


def test_s09_direct_object_e_section_checked():
    """An e section authored as a direct object (no oneOf) must not escape
    S09 edge checks."""
    doc = make_compliant_schema()
    doc["properties"]["e"] = {
        "description": "Edges.",
        "type": "object",
        "properties": {
            "d": {"description": "Edge block SAID.", "type": "string"},
            "application": {
                "description": "Edge.",
                "type": "object",
                "properties": {
                    "n": {"description": "Node SAID.", "type": "string"},
                    "o": {"description": "Operator.", "type": "string",
                          "const": "X2X"},
                },
                "required": ["n", "o"],
            },
        },
        "required": ["d", "application"],
    }
    assert "S09" in _codes(lint_schema_doc(_resaidify(doc), "f"))


def test_t02_malformed_export_schema_said(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["credentials"]["exports"][0]["schema"] = {
        "schema_path": None,
        "schema_said": "not-a-said",
    }
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    r = lint_template_dir(compliant_template_dir)
    assert "T02" in _codes(r.errors)


def test_t07_schema_referenced_only_by_edge_pin_not_orphan(compliant_template_dir):
    """A local schema referenced ONLY by another schema's edge pin is not an
    orphan (spec T07: '...or edge pin')."""
    template, metadata, schemas = _read_dir(compliant_template_dir)
    target = make_compliant_schema()
    target["title"] = "Edge Target Credential"
    target = saidify_schema_block(target)
    pinning = make_schema_with_edges(target["$id"])
    template["credentials"]["exports"][0]["schema"]["schema_said"] = pinning["$id"]
    template = saidify_document(template)
    metadata["for_micro_app_said"] = template["d"]
    write_template_dir(
        compliant_template_dir, template, metadata,
        {"test_credential.json": pinning, "edge_target.json": target},
    )
    r = lint_template_dir(compliant_template_dir)
    assert "T07" not in _codes(r.findings)
    assert "T06" not in _codes(r.findings)  # pin resolves locally too


def test_non_dict_artifacts_degrade_to_findings(compliant_template_dir):
    """Parseable-but-non-object JSON must produce findings, not crashes."""
    (compliant_template_dir / "schemas/arr.json").write_text("[]\n")
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "F02" and f.file == "schemas/arr.json" for f in r.errors)

    (compliant_template_dir / "metadata.json").write_text("[]\n")
    r = lint_template_dir(compliant_template_dir)
    assert any(f.code == "F02" and f.file == "metadata.json" for f in r.errors)

    (compliant_template_dir / "micro-app-template.json").write_text("[1, 2]\n")
    r = lint_template_dir(compliant_template_dir)  # must not raise
    assert any(
        f.code == "F02" and f.file == "micro-app-template.json"
        for f in r.errors
    )


def test_malformed_nested_template_shapes_do_not_crash(compliant_template_dir):
    template, metadata, schemas = _read_dir(compliant_template_dir)
    template["credentials"]["exports"].append("not-an-object")
    template["commands"] = "not-a-list"
    write_template_dir(compliant_template_dir, template, metadata, schemas)
    lint_template_dir(compliant_template_dir)  # must not raise
