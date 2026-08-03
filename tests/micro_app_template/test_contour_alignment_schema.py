"""The meta-schema after the primitives-are-given change.

Every case here is a SHAPE THE PROTOCOL PERMITS. Three verification rounds of the
design spec found fourteen rules that forbade legal shapes, so this file's job is
to prove the schema does not.
"""
import json
import pathlib
import jsonschema
import pytest

SCHEMA = json.loads(
    (pathlib.Path(__file__).parents[2]
     / "docs/superpowers/specs/schemas/micro-app-template.schema.json").read_text()
)


def _validate(fragment, defn):
    """Validate a fragment against one $defs entry."""
    sub = {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{defn}"}
    jsonschema.validate(fragment, sub)


def _rejects(fragment, defn):
    with pytest.raises(jsonschema.ValidationError):
        _validate(fragment, defn)


def test_untargeted_export_omits_holder_role():
    _validate({
        "id": "rating_attestation", "name": "R", "description": "d",
        "envelope": {"verifier_roles": [], "edges": [], "disclosure_mode": "full"},
        "schema": {"schema_said": "E" + "a" * 43, "schema_path": "schemas/r.json"},
        "lifecycle": {"states": ["issued"], "initial": "issued", "transitions": []},
    }, "exported_credential")


def test_self_issued_flag_is_expressible():
    _validate({
        "id": "app", "name": "A", "description": "d",
        "envelope": {"holder_role": "carrier", "self_issued": True,
                     "verifier_roles": [], "edges": [], "disclosure_mode": "full"},
        "schema": {"schema_said": "E" + "a" * 43, "schema_path": "schemas/a.json"},
        "lifecycle": {"states": ["issued"], "initial": "issued", "transitions": []},
    }, "exported_credential")


def test_explicit_self_issued_false_on_an_untargeted_export_is_expressible():
    """The counterpart of R6, on a different field.

    A `dependentRequired: {"self_issued": ["holder_role"]}` was proposed as the
    meta-schema half of concierge-api's `self_issued_holder_role_conflict`. It is
    key-PRESENCE keyed, so it would reject this shape — an untargeted attestation
    stating `self_issued: false` explicitly, exactly matching the field's own
    documented `default: false` — which is the class-3 over-reach R6 removed from
    `refuse`/`present`. It was NOT added (design spec §13's row for that rule
    records why: the only half JSON-Schema can express is a strict subset of the
    checker rule, with a worse message). This test is the pin that keeps the shape
    legal if anyone proposes it again.
    """
    _validate({
        "id": "rating_attestation", "name": "R", "description": "d",
        "envelope": {"self_issued": False, "verifier_roles": [], "edges": [],
                     "disclosure_mode": "full"},
        "schema": {"schema_said": "E" + "a" * 43, "schema_path": "schemas/r.json"},
        "lifecycle": {"states": ["issued"], "initial": "issued", "transitions": []},
    }, "exported_credential")


def test_transition_has_no_tel_primitive_and_takes_a_driver_list():
    _validate({"id": "suspend", "from": ["active"], "to": "suspended",
               "via_command": ["suspend_licence"], "trigger": "automatic",
               "condition_rule_ref": "premium_lapsed"}, "transition")


def test_transition_rejects_tel_primitive():
    _rejects({"id": "t", "from": "a", "to": "b", "tel_primitive": "issue"}, "transition")


def test_edge_operator_is_optional_and_keeps_all_three():
    for op in ("authorizes", "references", "authorizes-via-delegate"):
        _validate({"edge_name": "e", "credential_id": "c", "cardinality": "one",
                   "operator": op}, "edge")
    _validate({"edge_name": "e", "credential_id": "c", "cardinality": "one"}, "edge")


def test_presentation_of_a_held_credential_is_expressible():
    _validate({"kind": "credential", "imported_credential_id": "carrier_license",
               "present": True}, "exchange")


def test_explicit_spurn_with_both_keys_stated_is_expressible():
    # F1/R6: refuse/present exclusion must test TRUTH, not key PRESENCE.
    # {refuse: true, present: false} is the unambiguous explicit spurn; a
    # presence-keyed `not: {required: [refuse, present]}` wrongly rejects it
    # because both keys are present, even though only one is true.
    _validate({"kind": "credential", "imported_credential_id": "carrier_license",
               "refuse": True, "present": False}, "exchange")


def test_explicit_admit_with_both_keys_false_is_expressible():
    # Same defect: the explicit default admit shape (both fields false,
    # matching their documented `default: false`) must validate.
    _validate({"kind": "credential", "imported_credential_id": "carrier_license",
               "refuse": False, "present": False}, "exchange")


def test_explicit_present_with_refuse_false_is_expressible():
    # Same defect: a generator that writes every declared default alongside
    # an explicit `present: true` must not be punished for spelling out the
    # default.
    _validate({"kind": "credential", "imported_credential_id": "carrier_license",
               "refuse": False, "present": True}, "exchange")


def test_exchange_still_rejects_refuse_and_present_both_true():
    # The truth test must still forbid the actually-contradictory shape.
    _rejects({"kind": "credential", "imported_credential_id": "carrier_license",
              "refuse": True, "present": True}, "exchange")


def test_exchange_rejects_the_outbound_verb():
    _rejects({"kind": "credential", "exported_credential_id": "x", "verb": "grant"}, "exchange")


def test_exchange_rejects_both_credential_slots():
    _rejects({"kind": "credential", "exported_credential_id": "x",
              "imported_credential_id": "y"}, "exchange")


def test_command_declares_a_mint():
    _validate({"id": "grant_licence", "name": "G", "description": "d",
               "route": "/x/cmd/g", "payload_schema": {"type": "object"},
               "mints_credential_id": "carrier_license", "emissions": []}, "command")


def test_lifecycle_advance_emission_is_gone():
    _rejects({"kind": "lifecycle_advance", "exported_credential_id": "x",
              "to_state": "active"}, "emission")


def test_inbound_ipex_verb_keeps_all_six():
    for v in ("apply", "offer", "agree", "grant", "admit", "spurn"):
        _validate({"trigger_type": "credential_received", "ipex_verb": v,
                   "on_match": "next_step:s"}, "expected_inbound")


def test_imports_carry_schema_and_exporter_template_references():
    _validate({"id": "carrier_license", "expected_schema_said": "E" + "a" * 43,
               "schema_path": "schemas/cl.json",
               "exporter_template_said": "E" + "b" * 43}, "imported_credential")
