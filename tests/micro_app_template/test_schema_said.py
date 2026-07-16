"""Tests for ACDC-schema SAID computation (kli-saidify parity)."""
from __future__ import annotations

import json
from pathlib import Path

from locksmith_micro_app_designer.template.schema_said import (
    SAID_LABEL,
    compute_schema_said,
    is_bare_said,
    iter_said_blocks,
    saidify_schema_block,
    verify_schema_said,
)

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLE_SCHEMA = (
    REPO_ROOT
    / "skills/micro-app-template-gen/references/examples"
    / "regulator-grants-carrier-license/schemas/carrier_license.json"
)


def _minimal_block() -> dict:
    return {
        "$id": "",
        "description": "test block",
        "type": "object",
        "properties": {"d": {"type": "string"}},
    }


def test_saidify_then_verify_roundtrip():
    stamped = saidify_schema_block(_minimal_block())
    assert stamped["$id"].startswith("E")
    assert len(stamped["$id"]) == 44
    assert verify_schema_said(stamped) is True


def test_verify_fails_on_tamper():
    stamped = saidify_schema_block(_minimal_block())
    stamped["description"] = "tampered"
    assert verify_schema_said(stamped) is False


def test_verify_fails_on_missing_or_empty_id():
    assert verify_schema_said({"type": "object"}) is False
    assert verify_schema_said({"$id": "", "type": "object"}) is False


def test_saidify_does_not_mutate_input():
    block = _minimal_block()
    saidify_schema_block(block)
    assert block["$id"] == ""


def test_worked_example_saids_verify_top_and_nested():
    """Pins kli-saidify parity against a real artifact stamped by kli."""
    doc = json.loads(EXAMPLE_SCHEMA.read_text())
    for path, block in iter_said_blocks(doc):
        assert verify_schema_said(block), f"SAID at {path} does not verify"


def test_insertion_order_sensitivity():
    """Schema SAIDs bind to file key order — a sorted rehash MISMATCHES.

    This is the load-bearing difference from template-d saidify (which
    sorts recursively). If this test ever fails, kli parity broke.
    """
    doc = json.loads(EXAMPLE_SCHEMA.read_text())

    def sort_rec(o):
        if isinstance(o, dict):
            return {k: sort_rec(o[k]) for k in sorted(o)}
        if isinstance(o, list):
            return [sort_rec(x) for x in o]
        return o

    assert compute_schema_said(doc) == doc["$id"]
    assert compute_schema_said(sort_rec(doc)) != doc["$id"]


def test_iter_said_blocks_yields_root_first_with_paths():
    doc = {
        "$id": "root-said",
        "properties": {
            "a": {
                "oneOf": [
                    {"type": "string"},
                    {"$id": "nested-said", "type": "object"},
                ]
            }
        },
    }
    got = list(iter_said_blocks(doc))
    assert got[0][0] == "<root>"
    assert got[0][1]["$id"] == "root-said"
    assert got[1][0] == "properties.a.oneOf[1]"
    assert got[1][1]["$id"] == "nested-said"


def test_is_bare_said():
    doc = json.loads(EXAMPLE_SCHEMA.read_text())
    good = doc["$id"]
    assert is_bare_said(good) is True
    assert is_bare_said(f"did:keri:{good}") is False
    assert is_bare_said(f"sad:{good}") is False
    assert is_bare_said(f"https://example.com/{good}") is False
    assert is_bare_said("not-a-said") is False
    assert is_bare_said("E" + "x" * 20) is False
    assert is_bare_said("") is False
    assert is_bare_said(None) is False
