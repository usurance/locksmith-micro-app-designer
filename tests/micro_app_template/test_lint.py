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
