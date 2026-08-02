"""Tests for micro-app-template validation."""
from __future__ import annotations

from pathlib import Path

import pytest

from locksmith_micro_app_designer.template.validate import (
    ValidationError,
    validate_against_meta_schema,
    validate_cross_references,
    validate_template,
)


# Path to the meta-schema (built in Tasks 4-8).
META_SCHEMA = Path(__file__).parent.parent.parent / "docs/superpowers/specs/schemas/micro-app-template.schema.json"


def test_minimal_valid_template_passes_meta_schema(minimal_valid_template, fixtures_dir):
    # This test asserts the schema accepts the minimal fixture once the
    # schema exists. It will be enabled fully in Task 4.
    if not META_SCHEMA.exists():
        pytest.skip("meta-schema not yet built")
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert errors == []


def test_missing_d_field_fails(minimal_valid_template):
    if not META_SCHEMA.exists():
        pytest.skip("meta-schema not yet built")
    bad = dict(minimal_valid_template)
    del bad["d"]
    errors = validate_against_meta_schema(bad, META_SCHEMA)
    assert any("'d'" in e.message or "d " in e.message for e in errors)


def test_dangling_rule_ref_caught_by_xref():
    doc = {
        "rules": [{"id": "real-rule", "type": "legal_prose", "title": "X", "body": "y"}],
        "credentials": {
            "imports": [],
            "exports": [
                {
                    "id": "cred-a",
                    "name": "Cred A",
                    "description": "x",
                    "envelope": {"holder_role": "x", "verifier_roles": [], "edges": [], "disclosure_mode": "full"},
                    "schema": {"schema_said": "E" + "x" * 43, "schema_path": "schemas/a.json"},
                    "lifecycle": {"states": ["active"], "initial": "active", "transitions": []},
                    "rule_refs": ["does-not-exist"],
                    "value_flow": {"implied_credentials": []},
                }
            ],
        },
    }
    errors = validate_cross_references(doc)
    assert any("does-not-exist" in e.message for e in errors)


def test_validate_template_combines_meta_and_xref(minimal_valid_template):
    if not META_SCHEMA.exists():
        pytest.skip("meta-schema not yet built")
    result = validate_template(minimal_valid_template, META_SCHEMA)
    assert result.is_valid
    assert result.errors == []


def test_validate_template_returns_typed_result(minimal_valid_template):
    if not META_SCHEMA.exists():
        pytest.skip("meta-schema not yet built")
    bad = dict(minimal_valid_template)
    del bad["role"]
    result = validate_template(bad, META_SCHEMA)
    assert not result.is_valid
    assert len(result.errors) > 0
    assert all(isinstance(e, ValidationError) for e in result.errors)


def test_meta_schema_file_exists():
    assert META_SCHEMA.exists(), f"meta-schema not found at {META_SCHEMA}"


def test_meta_schema_is_valid_jsonschema():
    import json
    import jsonschema
    with open(META_SCHEMA) as f:
        schema = json.load(f)
    jsonschema.Draft202012Validator.check_schema(schema)


def test_minimal_template_validates_against_meta_schema(minimal_valid_template):
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert errors == [], f"unexpected errors: {[e.message for e in errors]}"


def test_wrong_kind_fails(minimal_valid_template):
    minimal_valid_template["role"]["kind"] = "not_a_real_kind"
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert any("kind" in e.path or "kind" in e.message for e in errors)


def test_missing_required_top_level_fails(minimal_valid_template):
    del minimal_valid_template["role"]
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert any("role" in e.message for e in errors)


import pytest
from locksmith_micro_app_designer.template.xref import validate_xrefs


@pytest.mark.parametrize("doc,expected_substring", [
    # rule_ref in commands auth_preconditions
    (
        {
            "rules": [],
            "commands": [{
                "id": "c1", "name": "c", "description": "c", "route": "/x/cmd/c",
                "payload_schema": {}, "idempotency_key_expression": "hash(p)", "emissions": [],
                "auth_preconditions": [{"rule_ref": "missing-rule"}],
            }],
        },
        "missing-rule",
    ),
    # via_workflow on lifecycle transition
    (
        {
            "rules": [],
            "workflows": [],
            "credentials": {"imports": [], "exports": [{
                "id": "c1", "name": "n", "description": "d",
                "envelope": {"holder_role": "r", "verifier_roles": [], "edges": [], "disclosure_mode": "full"},
                "schema": {"schema_said": "E" + "x" * 43, "schema_path": "schemas/c.json"},
                "lifecycle": {"states": ["a"], "initial": "a", "transitions": [
                    {"id": "t1", "from": "a", "to": "a", "via_workflow": "missing-workflow"}
                ]},
                "rule_refs": [],
                "value_flow": {"implied_credentials": []},
            }]},
        },
        "missing-workflow",
    ),
    # workflow step command_id reference
    (
        {
            "commands": [],
            "workflows": [{
                "id": "w1", "name": "w", "description": "d",
                "trigger": {"type": "manual"},
                "steps": [{"id": "s1", "name": "s", "actor": "self", "command_id": "missing-command"}],
            }],
        },
        "missing-command",
    ),
    # reaction trigger imported_credential_id
    (
        {
            "credentials": {"imports": [], "exports": []},
            "reactions": [{
                "id": "r1", "description": "r",
                "trigger": {"type": "credential_received", "imported_credential_id": "missing-import"},
                "emissions": [],
            }],
        },
        "missing-import",
    ),
    # aggregate invariant rule_ref
    (
        {
            "rules": [],
            "aggregates": [{
                "id": "a1", "description": "a", "inception_event_type": "x",
                "state_schema": {}, "initial_state": {}, "log_scope": "private",
                "invariants": [{"rule_ref": "missing-rule"}],
            }],
        },
        "missing-rule",
    ),
    # projection access row_filter_rule_ref
    (
        {
            "rules": [],
            "projections": [{
                "id": "p1", "name": "p", "description": "p",
                "source_events": ["e1"], "output_schema": {}, "fold_expression": "state",
                "access": {"row_filter_rule_ref": "missing-rule"},
            }],
        },
        "missing-rule",
    ),
    # projection access lens_rule_ref
    (
        {
            "rules": [],
            "projections": [{
                "id": "p1", "name": "p", "description": "p",
                "source_events": ["e1"], "output_schema": {}, "fold_expression": "state",
                "access": {"lens_rule_ref": "missing-lens-rule"},
            }],
        },
        "missing-lens-rule",
    ),
    # rule binding_link links
    (
        {
            "rules": [
                {"id": "r1", "type": "binding_link", "title": "L",
                 "links": [{"rule_id": "missing-rule"}]},
            ],
        },
        "missing-rule",
    ),
    # command mints_credential_id (replaces the removed advance-lifecycle
    # emission kind's exported_credential_id -- §6.4's derived-anchoring-act field)
    (
        {
            "credentials": {"imports": [], "exports": []},
            "commands": [{
                "id": "c1", "name": "c", "description": "c", "route": "/x/cmd/c",
                "payload_schema": {}, "mints_credential_id": "missing-export",
                "emissions": [],
            }],
        },
        "missing-export",
    ),
    # reaction mints_credential_id (same field, reaction surface)
    (
        {
            "credentials": {"imports": [], "exports": []},
            "reactions": [{
                "id": "r1", "description": "r",
                "trigger": {"type": "scheduled", "cadence": "* * * * *"},
                "mints_credential_id": "missing-export-2",
                "emissions": [],
            }],
        },
        "missing-export-2",
    ),
    # command emission aggregate_event aggregate_id
    (
        {
            "aggregates": [],
            "commands": [{
                "id": "c1", "name": "c", "description": "c", "route": "/x/cmd/c",
                "payload_schema": {}, "idempotency_key_expression": "hash(p)",
                "emissions": [{"kind": "aggregate_event", "aggregate_id": "missing-agg", "event_type": "e"}],
            }],
        },
        "missing-agg",
    ),
])
def test_xref_catches_dangling_reference(doc, expected_substring):
    errors = validate_xrefs(doc)
    assert any(expected_substring in e.message for e in errors), (
        f"expected substring {expected_substring!r} not in any error: {[e.message for e in errors]}"
    )


def test_xref_passes_on_consistent_doc():
    """A document with all references resolving should produce no xref errors."""
    doc = {
        "rules": [{"id": "r1", "type": "legal_prose", "title": "T", "body": "B"}],
        "credentials": {
            "imports": [{"id": "h1", "expected_schema_said": "E" + "x" * 43}],
            "exports": [],
        },
        "commands": [],
        "aggregates": [],
        "reactions": [],
        "workflows": [],
        "projections": [],
    }
    errors = validate_xrefs(doc)
    assert errors == []


def test_credentials_fixture_validates(fixtures_dir):
    import json
    with open(fixtures_dir / "credentials_valid.json") as f:
        doc = json.load(f)
    errors = validate_against_meta_schema(doc, META_SCHEMA)
    assert errors == [], f"unexpected: {[e.message for e in errors]}"


def test_credentials_fixture_exports_all_three_targetedness_shapes(fixtures_dir):
    """The fixture is authored to exercise all three shapes the design spec's
    table names (§6.3, AMENDMENT-WAVE BLOCK, primitives-are-given): targeted at
    another, self-issued, and untargeted. `holder_role` absence is a legal
    shape, not an omission -- pin that the fixture actually carries one of
    each rather than asserting it only indirectly via the whole-doc validate."""
    import json
    with open(fixtures_dir / "credentials_valid.json") as f:
        doc = json.load(f)
    exports = {e["id"]: e for e in doc["credentials"]["exports"]}
    targeted_at_another = exports["policy"]["envelope"]
    assert targeted_at_another.get("holder_role") == "policyholder_individual"
    assert targeted_at_another.get("self_issued", False) is False

    untargeted = exports["solvency_attestation"]["envelope"]
    assert "holder_role" not in untargeted

    self_issued = exports["carrier_self_certification"]["envelope"]
    assert self_issued.get("holder_role") == doc["role"]["id"]
    assert self_issued.get("self_issued") is True


def test_invalid_edge_operator_fails(fixtures_dir):
    import json
    with open(fixtures_dir / "credentials_valid.json") as f:
        doc = json.load(f)
    doc["credentials"]["exports"][0]["envelope"]["edges"][0]["operator"] = "not_a_real_operator"
    errors = validate_against_meta_schema(doc, META_SCHEMA)
    assert any("operator" in e.path or "operator" in e.message for e in errors)


def test_invalid_disclosure_mode_fails(fixtures_dir):
    import json
    with open(fixtures_dir / "credentials_valid.json") as f:
        doc = json.load(f)
    doc["credentials"]["exports"][0]["envelope"]["disclosure_mode"] = "secret"
    errors = validate_against_meta_schema(doc, META_SCHEMA)
    assert any("disclosure_mode" in e.path or "secret" in e.message for e in errors)


def test_schema_path_must_be_in_schemas_dir(fixtures_dir):
    import json
    with open(fixtures_dir / "credentials_valid.json") as f:
        doc = json.load(f)
    doc["credentials"]["exports"][0]["schema"]["schema_path"] = "elsewhere/policy.json"
    errors = validate_against_meta_schema(doc, META_SCHEMA)
    assert any("schema_path" in e.path for e in errors)


def test_command_with_credential_emission_validates(minimal_valid_template):
    """The outbound-`verb` shape this test used to author (slotless apply,
    neither credential id set) is the one the owner ruled unwriteable in this
    profile (Task 4, 2026-08-02 ruling) -- outbound `verb` is derived, not
    authored, and a slotless exchange has no row in the derivation table. The
    current shape: the command declares `mints_credential_id` and its
    emission carries `exported_credential_id`, which derives to `grant`."""
    minimal_valid_template["commands"].append({
        "id": "submit_app",
        "name": "Submit Application",
        "description": "Submit a license application.",
        "route": "/insurance/cmd/submit_application",
        "counterparty_role": "regulator",
        "payload_schema": {
            "type": "object",
            "properties": {"jurisdiction": {"type": "string"}}
        },
        "auth_preconditions": [],
        "state_preconditions": [],
        "temporal_preconditions": [],
        "mints_credential_id": "carrier_license_application",
        "emissions": [
            {
                "kind": "exchange",
                "exchange": {
                    "kind": "credential",
                    "exported_credential_id": "carrier_license_application",
                    "schema_said_referenced": "EAbc0000000000000000000000000000000000000000"
                }
            }
        ]
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert errors == [], f"unexpected: {[e.message for e in errors]}"


def test_command_on_ipex_route_fails(minimal_valid_template):
    minimal_valid_template["commands"].append({
        "id": "bad",
        "name": "Bad",
        "description": "Tries to use /ipex/ route.",
        "route": "/ipex/apply",
        "payload_schema": {},
        "emissions": []
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert len(errors) > 0


def test_invalid_ipex_verb_fails(minimal_valid_template):
    minimal_valid_template["commands"].append({
        "id": "bad",
        "name": "Bad",
        "description": "Uses non-IPEX verb.",
        "route": "/insurance/cmd/x",
        "payload_schema": {},
        "emissions": [
            {
                "kind": "exchange",
                "exchange": {
                    "kind": "credential",
                    "verb": "yeet",
                    "imported_credential_id": None,
                    "exported_credential_id": None
                }
            }
        ]
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert len(errors) > 0


def test_aggregate_validates(minimal_valid_template):
    minimal_valid_template["aggregates"].append({
        "id": "license_registry",
        "description": "Tracks carrier license lifecycle.",
        "boundary": {
            "inception_event_type": "license_received",
            "instance_key": "event.license_id",
        },
        "state_schema": {
            "type": "object",
            "properties": {"active": {"type": "array"}}
        },
        "initial_state": {"active": []},
        "events": {
            "license_received": {
                "payload_schema": {
                    "type": "object",
                    "properties": {"license_id": {"type": "string"}},
                    "required": ["license_id"],
                    "additionalProperties": False,
                }
            }
        },
        "fold": {
            "license_received": [
                {"op": "append", "target": "active", "value": "event.license_id"}
            ]
        },
        "invariants": [],
        "log_scope": "private"
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert errors == []


def test_invalid_log_scope_fails(minimal_valid_template):
    minimal_valid_template["aggregates"].append({
        "id": "x",
        "description": "y",
        "inception_event_type": "z",
        "state_schema": {},
        "initial_state": {},
        "invariants": [],
        "log_scope": "public"
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert any("log_scope" in e.path or "public" in e.message for e in errors)


def test_reaction_validates(minimal_valid_template):
    """`verb` is derived on the outbound side; an inbound-branch exchange
    declaring neither `refuse` nor `present` derives to `admit` (§6.4's
    derivation table), so dropping the field is the like-for-like fix."""
    minimal_valid_template["reactions"].append({
        "id": "on_license_granted",
        "description": "Admit incoming license credential.",
        "trigger": {
            "type": "credential_received",
            "imported_credential_id": "carrier_license",
            "ipex_verb": "grant"
        },
        "emissions": [
            {
                "kind": "exchange",
                "exchange": {
                    "kind": "credential",
                    "imported_credential_id": "carrier_license"
                }
            }
        ],
        "failure_policy": {
            "on_validation_failure": "log_and_spurn",
            "timeout_seconds": None
        }
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert errors == [], f"unexpected: {[e.message for e in errors]}"


def test_workflow_validates(minimal_valid_template):
    minimal_valid_template["workflows"].append({
        "id": "license_application_carrier_side",
        "name": "License Application (Carrier)",
        "description": "Carrier-side license application flow.",
        "counterparty_role": "regulator",
        "trigger": {"type": "manual", "initiator_role": "carrier"},
        "steps": [
            {
                "id": "submit",
                "name": "Submit",
                "actor": "self",
                "command_id": "submit_application",
                "next_steps": ["await_response"]
            }
        ]
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert errors == [], f"unexpected: {[e.message for e in errors]}"


def test_projection_validates(minimal_valid_template):
    minimal_valid_template["projections"].append({
        "id": "active_policies",
        "name": "Active Policies",
        "description": "Currently in-force policies.",
        "source_events": ["policy_issued", "policy_revoked"],
        "shape": "collection",
        "primary_key": "policy_id",
        "row_schema": {
            "type": "object",
            "properties": {"policy_id": {"type": "string"}}
        },
        "fold": {
            "policy_issued": [
                {"op": "upsert", "set": {"policy_id": "event.policy_id"}}
            ],
            "policy_revoked": [
                {"op": "delete"}
            ]
        },
        "ordering": "source_seq",
        "display": {
            "view_type": "table",
            "columns": [{"field": "policy_id", "header": "Policy"}],
            "default_sort": {"column": "policy_id", "direction": "asc"},
            "empty_state": "No policies in force."
        }
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert errors == []


def test_invalid_view_type_fails(minimal_valid_template):
    minimal_valid_template["projections"].append({
        "id": "x",
        "name": "y",
        "description": "z",
        "source_events": ["e1"],
        "output_schema": {},
        "fold_expression": "state",
        "display": {"view_type": "spreadsheet"}
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert any("view_type" in e.path or "spreadsheet" in e.message for e in errors)


def test_legal_prose_rule_validates(minimal_valid_template):
    minimal_valid_template["rules"].append({
        "id": "warranty_disclaimer",
        "type": "legal_prose",
        "title": "Coverage Warranty",
        "body": "Carrier warrants accuracy of all attributes."
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert errors == []


def test_predicate_rule_requires_purpose(minimal_valid_template):
    minimal_valid_template["rules"].append({
        "id": "premium_paid",
        "type": "predicate",
        "title": "Premium Paid",
        "expression": "state.paid > 0",
        "language": "UEL/1.0"
        # missing purpose
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert any("purpose" in e.message for e in errors)


def test_predicate_rule_validates_with_purpose(minimal_valid_template):
    minimal_valid_template["rules"].append({
        "id": "premium_paid",
        "type": "predicate",
        "purpose": "lifecycle_transition_requires",
        "title": "Premium Paid",
        "expression": "state.paid > 0",
        "language": "UEL/1.0"
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert errors == []


def test_computational_rule_requires_result_attribute(minimal_valid_template):
    minimal_valid_template["rules"].append({
        "id": "premium",
        "type": "computational",
        "title": "Premium",
        "expression": "base * mult",
        "language": "UEL/1.0"
        # missing result_attribute
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert any("result_attribute" in e.message for e in errors)


def test_binding_link_requires_links(minimal_valid_template):
    minimal_valid_template["rules"].append({
        "id": "link_a",
        "type": "binding_link",
        "title": "Link"
        # missing links
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert any("links" in e.message for e in errors)


def test_legal_prose_requires_body(minimal_valid_template):
    minimal_valid_template["rules"].append({
        "id": "x",
        "type": "legal_prose",
        "title": "X"
        # missing body
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert any("body" in e.message for e in errors)


# --- Stage 5: fold-model semantic checks (accepted spec §14.2, §14.5) -----------------
# JSON-Schema already enforces the fold-model *structure* (boundary/fold/shape/
# primary_key/row_schema/ordering/on_unknown_event/test_vectors) via the amended
# meta-schema -- see test_aggregate_validates / test_projection_validates above. The
# two checks below are cross-field semantics no JSON-Schema keyword can express.

from locksmith_micro_app_designer.template.validate import validate_fold_semantics


def test_vector_coverage_floor_is_a_warning_not_an_error(minimal_valid_template):
    """§14.5 (deferred question, assigned to this stage): an aggregate/projection
    with zero test_vectors is a *lint warning* in v1, not a hard validation
    failure -- the proposal in the accepted spec ("warn in v1, decide after the
    first real templates")."""
    minimal_valid_template["aggregates"].append({
        "id": "no_vectors_agg",
        "description": "d",
        "boundary": {"inception_event_type": "e", "instance_key": "event.id"},
        "state_schema": {}, "initial_state": {},
        "events": {"e": {"payload_schema": {
            "type": "object", "properties": {"id": {"type": "string"}},
            "required": ["id"], "additionalProperties": False}}},
        "fold": {"e": [{"op": "set", "target": "x", "value": "1"}]},
        "invariants": [], "log_scope": "private",
        # test_vectors omitted entirely.
    })
    result = validate_template(minimal_valid_template, META_SCHEMA)
    assert result.is_valid, "a missing test_vectors[] must not fail validation"
    assert result.errors == []
    assert any(
        "no_vectors_agg" in w.message or "test_vectors" in w.path
        for w in result.warnings
    )
    assert all(w.severity == "warning" for w in result.warnings)


def test_vector_coverage_present_produces_no_warning(minimal_valid_template):
    minimal_valid_template["aggregates"].append({
        "id": "with_vectors_agg",
        "description": "d",
        "boundary": {"inception_event_type": "e", "instance_key": "event.id"},
        "state_schema": {}, "initial_state": {},
        "fold": {"e": [{"op": "set", "target": "x", "value": "1"}]},
        "invariants": [], "log_scope": "private",
        "test_vectors": [
            {"name": "v1", "events": [{"type": "e", "payload": {}}], "expected": {"x": 1}},
        ],
    })
    errors, warnings = validate_fold_semantics(minimal_valid_template)
    assert errors == []
    assert warnings == []


def test_commutative_ordering_forbids_raw_reducer_handlers():
    """§14.2: 'commutative ordering forbids raw reducers' -- the likely rule the
    accepted spec proposes for its own open question, since commutativity is
    undecidable for an arbitrary raw CEL reducer but is a static whitelist check
    for the op vocabulary."""
    doc = {
        "projections": [{
            "id": "counter",
            "name": "Counter",
            "description": "d",
            "source_events": ["bumped"],
            "shape": "object",
            "state_schema": {}, "initial_state": {"n": 0},
            "ordering": "commutative",
            "fold": {
                "bumped": {"expression": '{ "n": state.n + event.amount }'},
            },
        }],
    }
    errors, _warnings = validate_fold_semantics(doc)
    assert any(
        "commutative" in e.message and "counter" in e.message
        for e in errors
    )


def test_commutative_ordering_allows_whitelisted_ops():
    """An op-list handler under `ordering: "commutative"` is fine -- the op
    vocabulary is the whitelist the validator can statically prove commutes."""
    doc = {
        "projections": [{
            "id": "counter",
            "name": "Counter",
            "description": "d",
            "source_events": ["bumped"],
            "shape": "object",
            "state_schema": {}, "initial_state": {"n": 0},
            "ordering": "commutative",
            "fold": {
                "bumped": [{"op": "increment", "target": "n", "by": "event.amount"}],
            },
            "test_vectors": [
                {"name": "v", "events": [{"type": "bumped", "payload": {"amount": 1}}],
                 "expected": {"n": 1}},
            ],
        }],
    }
    errors, warnings = validate_fold_semantics(doc)
    assert errors == []
    assert warnings == []


def test_non_commutative_ordering_permits_raw_reducers():
    doc = {
        "projections": [{
            "id": "counter",
            "name": "Counter",
            "description": "d",
            "source_events": ["bumped"],
            "shape": "object",
            "state_schema": {}, "initial_state": {"n": 0},
            "ordering": "source_seq",
            "fold": {
                "bumped": {"expression": '{ "n": state.n + event.amount }'},
            },
            "test_vectors": [
                {"name": "v", "events": [{"type": "bumped", "payload": {"amount": 1}}],
                 "expected": {"n": 1}},
            ],
        }],
    }
    errors, warnings = validate_fold_semantics(doc)
    assert errors == []
    assert warnings == []


def test_validation_engine_surfaces_vector_coverage_as_a_warning_not_an_error(
    minimal_valid_template,
):
    """End-to-end through the Designer's ValidationEngine adapter
    (validation.py), not just the raw validate_fold_semantics() helper --
    guards against the adapter only reading raw.errors and silently
    dropping raw.warnings (a real bug found and fixed in this stage: the
    adapter never populated ValidationReport.warnings before)."""
    from locksmith_micro_app_designer.validation import ValidationEngine

    minimal_valid_template["aggregates"].append({
        "id": "no_vectors_agg",
        "description": "d",
        "boundary": {"inception_event_type": "e", "instance_key": "event.id"},
        "state_schema": {}, "initial_state": {},
        "events": {"e": {"payload_schema": {
            "type": "object", "properties": {"id": {"type": "string"}},
            "required": ["id"], "additionalProperties": False}}},
        "fold": {"e": [{"op": "set", "target": "x", "value": "1"}]},
        "invariants": [], "log_scope": "private",
    })
    report = ValidationEngine(META_SCHEMA).validate(minimal_valid_template)
    assert report.is_valid
    assert report.errors == ()
    assert any("no_vectors_agg" in w.message for w in report.warnings)
    assert all(w.severity == "warning" for w in report.warnings)


def test_both_worked_examples_pass_THIS_REPOS_fold_semantics_validator(fixtures_dir):
    """`validate_fold_semantics` only — NOT the binding gate, and not a clean bill of health.

    This test was previously named `..._pass_fold_semantics_cleanly`, and that name
    was the defect. Register finding 28 (ugard,
    `backlog/2026-07-25-ipc-corpus-cross-template-reconciliation.md`): for a period
    this test passed while both worked examples carried live binding defects — 5
    errors in `regulator-grants-carrier-license`, 1 in `carrier-license-application`
    under `micro-app check`. It passed because `validate_fold_semantics` does not
    look at emission bindings at all, while the test's name claimed exactly the
    cleanliness the gate refuted. These are the canonical examples every template
    author copies from, so a falsely-green test here is the propagation path that
    was blamed for five authors hitting the same defect class.

    The authoritative binding gate lives in a sibling repo and is deliberately NOT
    called from here — reimplementing it locally would be a second mechanism for one
    rule, which is the failure mode this corpus's register explicitly warns against.
    Run it separately; it is a numbered step in the skill's Validation block:

        cd ~/code/concierge-api && PYTHONPATH=src <keripy-venv-python> \\
            -m concierge_api_local.cli.microapp check --template <abs path>

    So: what this test proves is that the two examples satisfy THIS repo's
    fold-semantics validator. What it does not prove is that their emissions supply
    the fields their folds and routing selectors read.
    """
    import json
    examples_dir = (
        Path(__file__).parent.parent.parent
        / "skills/micro-app-template-gen/references/examples"
    )
    for name in ("carrier-license-application", "regulator-grants-carrier-license"):
        with open(examples_dir / name / "micro-app-template.json") as f:
            doc = json.load(f)
        errors, warnings = validate_fold_semantics(doc)
        assert errors == [], f"{name}: unexpected fold-semantics errors: {errors}"
        assert warnings == [], f"{name}: unexpected vector-coverage warnings: {warnings}"


METADATA_SCHEMA = Path(__file__).parent.parent.parent / "docs/superpowers/specs/schemas/metadata.schema.json"


def test_metadata_fixture_validates(fixtures_dir):
    import json
    with open(fixtures_dir / "minimal_valid_metadata.json") as f:
        doc = json.load(f)
    errors = validate_against_meta_schema(doc, METADATA_SCHEMA)
    assert errors == []


def test_metadata_requires_for_micro_app_said(fixtures_dir):
    import json
    with open(fixtures_dir / "minimal_valid_metadata.json") as f:
        doc = json.load(f)
    del doc["for_micro_app_said"]
    errors = validate_against_meta_schema(doc, METADATA_SCHEMA)
    assert any("for_micro_app_said" in e.message for e in errors)


def test_invalid_lineage_relation_fails(fixtures_dir):
    import json
    with open(fixtures_dir / "minimal_valid_metadata.json") as f:
        doc = json.load(f)
    doc["semantic_lineage"] = [{
        "relation": "loves",
        "target_said": "E" + "x" * 43,
        "note": "x"
    }]
    errors = validate_against_meta_schema(doc, METADATA_SCHEMA)
    assert any("loves" in e.message or "relation" in e.path for e in errors)
