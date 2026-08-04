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
                "payload_schema": {}, "emissions": [],
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
    # F4/F5/R10: transition via_command must resolve to a declared command id.
    # A dangling name is a permanently undrivable transition with zero findings
    # if unchecked -- the same defect §5.2 measured on the field it replaced.
    (
        {
            "rules": [],
            "workflows": [],
            "commands": [{
                "id": "activate_policy", "name": "n", "description": "d",
                "route": "/x/cmd/activate", "payload_schema": {}, "emissions": [],
            }],
            "credentials": {"imports": [], "exports": [{
                "id": "c1", "name": "n", "description": "d",
                "envelope": {"holder_role": "r", "verifier_roles": [], "edges": [], "disclosure_mode": "full"},
                "schema": {"schema_said": "E" + "x" * 43, "schema_path": "schemas/c.json"},
                "lifecycle": {"states": ["a", "b"], "initial": "a", "transitions": [
                    {"id": "t1", "from": "a", "to": "b", "via_command": ["missing-driver-command"]}
                ]},
                "rule_refs": [],
                "value_flow": {"implied_credentials": []},
            }]},
        },
        "missing-driver-command",
    ),
    # F4/F5/R10: transition via_reaction must resolve to a declared reaction id.
    (
        {
            "rules": [],
            "workflows": [],
            "reactions": [{
                "id": "on_lapse", "description": "d",
                "trigger": {"type": "scheduled", "cadence": "* * * * *"},
                "emissions": [],
            }],
            "credentials": {"imports": [], "exports": [{
                "id": "c1", "name": "n", "description": "d",
                "envelope": {"holder_role": "r", "verifier_roles": [], "edges": [], "disclosure_mode": "full"},
                "schema": {"schema_said": "E" + "x" * 43, "schema_path": "schemas/c.json"},
                "lifecycle": {"states": ["a", "b"], "initial": "a", "transitions": [
                    {"id": "t1", "from": "a", "to": "b", "via_reaction": ["missing-driver-reaction"]}
                ]},
                "rule_refs": [],
                "value_flow": {"implied_credentials": []},
            }]},
        },
        "missing-driver-reaction",
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
                "payload_schema": {},
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


# --- one reading of the driver type ------------------------------------------
# MIRROR of ugard's tests/micro_app_template/test_xref.py block of the same name.
# `via_command`/`via_reaction` are arrays, but a bare string is what an author
# writes by hand and what the field these replaced used, so it reaches xref.py.
# Iterating the raw value walked a bare string's CHARACTERS — 17 bogus
# `command '<char>' not found` findings for one 17-character typo, burying the one
# real diagnostic — and raised TypeError outright on a non-string entry. This is
# the exact mechanism canon §4.1 records as fixed, so it gets a pin in both repos.

def _driver_doc(via_command=None, via_reaction=None):
    """One export whose only transition declares the given driver(s), against a
    real command `activate_license` and a real reaction `on_paid`."""
    transition = {"id": "activate", "from": ["pending"], "to": "active"}
    if via_command is not None:
        transition["via_command"] = via_command
    if via_reaction is not None:
        transition["via_reaction"] = via_reaction
    return {
        "credentials": {"exports": [{
            "id": "license", "schema": {"schema_said": "ELIC"},
            "lifecycle": {"states": ["pending", "active"], "initial": "pending",
                          "transitions": [transition]}}]},
        "commands": [{"id": "activate_license"}],
        "reactions": [{"id": "on_paid"}],
    }


def test_bare_string_via_command_yields_exactly_one_finding():
    errors = validate_xrefs(_driver_doc(via_command="activatee_license"))
    assert [e.message for e in errors] == [
        "credentials.exports[0].lifecycle.transitions[0].via_command: "
        "command 'activatee_license' not found"]


def test_bare_string_via_reaction_yields_exactly_one_finding():
    errors = validate_xrefs(_driver_doc(via_reaction="on_paidd"))
    assert [e.message for e in errors] == [
        "credentials.exports[0].lifecycle.transitions[0].via_reaction: "
        "reaction 'on_paidd' not found"]


def test_bare_string_that_resolves_produces_no_error():
    assert validate_xrefs(_driver_doc(via_command="activate_license",
                                      via_reaction="on_paid")) == []


def test_empty_driver_declarations_are_not_references():
    """An empty NAME names nothing, so it is not a dangling reference either —
    same reading as concierge-api's `driver_names` (loader/lifecycle.py). The
    absent-driver finding is the lifecycle analyser's, not xref's."""
    assert validate_xrefs(_driver_doc(via_command="", via_reaction=[""])) == []


def test_non_string_driver_entries_are_ignored_not_crashed():
    """A wrongly-typed entry is the meta-schema's finding. xref must not raise,
    and must not report a `None`/`42` as a dangling command name."""
    assert validate_xrefs(_driver_doc(via_command=[None, 42], via_reaction=7)) == []


def test_mixed_driver_list_reports_only_the_dangling_entry_at_its_own_index():
    errors = validate_xrefs(
        _driver_doc(via_command=["activate_license", "activatee_license"]))
    assert [e.message for e in errors] == [
        "credentials.exports[0].lifecycle.transitions[0].via_command[1]: "
        "command 'activatee_license' not found"]


# --- exchange emissions carry doc-local ids too --------------------------------
# B14. The `aggregate_event` branch was cross-referenced from the start; the
# `exchange` branch was argued out of it by a comment claiming exchange "carries
# no doc-local id to cross-reference here". False: two of the three exchange
# branches carry one. THE TRAP these tests exist to catch — the id is NESTED at
# `emissions[j].exchange.exported_credential_id`, whereas `aggregate_id` sits
# alongside `kind`. A fix written by analogy reads `em.get("exported_credential_id")`,
# gets None on every live document, and checks nothing while looking checked. Every
# fixture below nests the id, and every assertion pins the `.exchange.` path
# segment, so the by-analogy version fails all of them.

def _exchange_doc(exchange, surface="commands"):
    """One command (or reaction) whose only emission is the given exchange, against
    a real export `license` and a real import `application`."""
    emission = {"kind": "exchange", "exchange": exchange}
    doc = {
        "credentials": {
            "imports": [{"id": "application", "expected_schema_said": "E" + "x" * 43}],
            "exports": [{"id": "license", "schema": {"schema_said": "E" + "y" * 43}}],
        },
        "commands": [],
        "reactions": [],
    }
    if surface == "commands":
        doc["commands"] = [{"id": "c1", "emissions": [emission]}]
    else:
        doc["reactions"] = [{"id": "r1", "emissions": [emission]}]
    return doc


def test_command_exchange_exported_credential_id_must_resolve():
    errors = validate_xrefs(_exchange_doc(
        {"kind": "credential", "exported_credential_id": "no_such_credential_at_all"}))
    assert [e.message for e in errors] == [
        "commands[0].emissions[0].exchange.exported_credential_id: "
        "credentials.exports 'no_such_credential_at_all' not found"]


def test_command_exchange_imported_credential_id_must_resolve():
    errors = validate_xrefs(_exchange_doc(
        {"kind": "credential", "imported_credential_id": "no_such_credential_at_all",
         "refuse": True}))
    assert [e.message for e in errors] == [
        "commands[0].emissions[0].exchange.imported_credential_id: "
        "credentials.imports 'no_such_credential_at_all' not found"]


def test_reaction_exchange_credential_id_must_resolve():
    """Half the corpus's six live exchange ids sit on a reaction or a refusal
    command rather than a bundle's headline command, so the reaction surface is not
    an afterthought: live example `carrier-license-application/on_license_granted`."""
    errors = validate_xrefs(_exchange_doc(
        {"kind": "credential", "imported_credential_id": "typoed_license"},
        surface="reactions"))
    assert [e.message for e in errors] == [
        "reactions[0].emissions[0].exchange.imported_credential_id: "
        "credentials.imports 'typoed_license' not found"]


def test_exchange_ids_that_resolve_produce_no_error():
    assert validate_xrefs(_exchange_doc(
        {"kind": "credential", "exported_credential_id": "license"})) == []
    assert validate_xrefs(_exchange_doc(
        {"kind": "credential", "imported_credential_id": "application"})) == []


def test_exchange_message_branch_carries_no_doc_local_id():
    """`kind: "message"` holds `route`/`schema_id` and genuinely names no doc-local
    id — the one branch of the three that must not be flagged. Live example:
    `regulator-grants-carrier-license/spurn_application` emission 1."""
    assert validate_xrefs(_exchange_doc(
        {"kind": "message", "pattern": "notification",
         "route": "/insurance/note/application_denied"})) == []


def test_exchange_pools_are_not_crossed():
    """`imported_credential_id` resolves against `credentials.imports[]` ONLY, and
    vice versa. An issuer awaiting acknowledgement of a credential it exported
    cannot name it here; that inexpressiveness is finding 45's remaining depth, not
    a bug in the pool split. Widening the check to accept either pool papers over it."""
    errors = validate_xrefs(_exchange_doc(
        {"kind": "credential", "exported_credential_id": "application"}))
    assert [e.message for e in errors] == [
        "commands[0].emissions[0].exchange.exported_credential_id: "
        "credentials.exports 'application' not found"]
    errors = validate_xrefs(_exchange_doc(
        {"kind": "credential", "imported_credential_id": "license"}))
    assert [e.message for e in errors] == [
        "commands[0].emissions[0].exchange.imported_credential_id: "
        "credentials.imports 'license' not found"]


def test_malformed_exchange_block_is_not_xrefs_finding():
    """A non-dict `exchange`, or a missing one, is the meta-schema's finding. xref
    must not raise and must not invent a reference."""
    assert validate_xrefs(_exchange_doc("not-an-object")) == []
    assert validate_xrefs({"commands": [{"id": "c1", "emissions": [{"kind": "exchange"}]}]}) == []


# --- the rest of the same branch union -----------------------------------------
# The exchange branch (above) was one of four places a credential id hid from xref.
# Measured 2026-08-04 on the live corpus, each silent at zero errors: a
# `lifecycle_event` reaction trigger's `imported_credential_id` (4 live ids, and
# ZERO live triggers use the `exported_credential_id` that branch did check);
# `workflows[].trigger`, never visited at all (1 live id); and
# `envelope.edges[].credential_id`, meta-schema-REQUIRED with 3 live ids, where a
# dangling value is an ACDC chain reference pointing nowhere.
#
# Pool discipline splits by field name, because that is what the names declare.
# `imported_`/`exported_` resolve against their own pool only. Bare `credential_id`
# declares no pool and canon does not give it one -- for `implied_credentials[]` it
# says explicitly "in this template's exports list OR imported from elsewhere"
# (authoring canon §6.3) -- so it resolves against EITHER, and only a value in
# neither pool is a finding. Narrowing it to imports would false-fire on an edge to
# a self-issued export, which the corpus's own `self_issued: true` shape permits.

def _cred_doc(**sections):
    """A doc with one export `license` and one import `application`, plus whatever
    sections the case adds."""
    doc = {
        "credentials": {
            "imports": [{"id": "application", "expected_schema_said": "E" + "x" * 43}],
            "exports": [{"id": "license", "schema": {"schema_said": "E" + "y" * 43}}],
        },
    }
    doc["credentials"]["exports"][0].update(sections.pop("export_extra", {}))
    doc.update(sections)
    return doc


def _rx(trigger):
    return _cred_doc(reactions=[{"id": "r1", "trigger": trigger}])


def test_reaction_lifecycle_event_imported_credential_id_must_resolve():
    """The branch checked only the field nobody uses. All four live `lifecycle_event`
    triggers in the corpus name `imported_credential_id`; none name the exported one."""
    errors = validate_xrefs(_rx(
        {"type": "lifecycle_event", "imported_credential_id": "typoed_license",
         "to_state": "revoked"}))
    assert [e.message for e in errors] == [
        "reactions[0].trigger.imported_credential_id: "
        "credentials.imports 'typoed_license' not found"]


def test_reaction_lifecycle_event_both_ids_keep_their_own_pools():
    errors = validate_xrefs(_rx(
        {"type": "lifecycle_event", "imported_credential_id": "license",
         "exported_credential_id": "application"}))
    assert sorted(e.message for e in errors) == [
        "reactions[0].trigger.exported_credential_id: "
        "credentials.exports 'application' not found",
        "reactions[0].trigger.imported_credential_id: "
        "credentials.imports 'license' not found",
    ]
    assert validate_xrefs(_rx(
        {"type": "lifecycle_event", "imported_credential_id": "application",
         "exported_credential_id": "license"})) == []


def test_workflow_trigger_imported_credential_id_must_resolve():
    """`workflows[].trigger` was never visited. Live id:
    `regulator-grants-carrier-license/license_grant_workflow`."""
    errors = validate_xrefs(_cred_doc(workflows=[{
        "id": "w1", "trigger": {"type": "credential_received",
                                "imported_credential_id": "typoed_application"}}]))
    assert [e.message for e in errors] == [
        "workflows[0].trigger.imported_credential_id: "
        "credentials.imports 'typoed_application' not found"]


def test_workflow_trigger_credential_id_resolves_against_either_pool():
    for named in ("license", "application"):
        assert validate_xrefs(_cred_doc(workflows=[{
            "id": "w1", "trigger": {"type": "lifecycle_event",
                                    "credential_id": named}}])) == []
    errors = validate_xrefs(_cred_doc(workflows=[{
        "id": "w1", "trigger": {"type": "lifecycle_event",
                                "credential_id": "neither_pool"}}]))
    assert [e.message for e in errors] == [
        "workflows[0].trigger.credential_id: "
        "credentials.imports/exports 'neither_pool' not found"]


def test_workflow_trigger_without_credential_ids_is_not_a_reference():
    assert validate_xrefs(_cred_doc(workflows=[
        {"id": "w1", "trigger": {"type": "manual", "initiator_role": "carrier"}},
        {"id": "w2", "trigger": {"type": "scheduled", "cadence": "* * * * *"}},
        {"id": "w3"},
    ])) == []


def _edge_doc(credential_id):
    return _cred_doc(export_extra={"envelope": {"edges": [
        {"edge_name": "authority", "credential_id": credential_id,
         "cardinality": "one", "operator": "authorizes"}]}})


def test_edge_credential_id_must_resolve():
    errors = validate_xrefs(_edge_doc("no_such_credential_at_all"))
    assert [e.message for e in errors] == [
        "credentials.exports[0].envelope.edges[0].credential_id: "
        "credentials.imports/exports 'no_such_credential_at_all' not found"]


def test_edge_credential_id_may_name_an_import_or_an_export():
    """All three live edges point at an import, but `authorizes` on a self-issued
    export is a legal chain and the corpus authors `self_issued: true`. Pinning this
    to imports alone would break that, so both pools resolve."""
    assert validate_xrefs(_edge_doc("application")) == []
    assert validate_xrefs(_edge_doc("license")) == []


def test_implied_credential_id_must_resolve():
    doc = _cred_doc(export_extra={"value_flow": {"implied_credentials": [
        {"credential_id": "ghost_credential", "relationship": "per_emission"}]}})
    errors = validate_xrefs(doc)
    assert [e.message for e in errors] == [
        "credentials.exports[0].value_flow.implied_credentials[0].credential_id: "
        "credentials.imports/exports 'ghost_credential' not found"]


def test_implied_credential_id_resolves_against_either_pool():
    for named in ("license", "application"):
        assert validate_xrefs(_cred_doc(export_extra={"value_flow": {
            "implied_credentials": [{"credential_id": named,
                                     "relationship": "issuer_grants"}]}})) == []


def test_xref_error_reaches_validation_without_a_doubled_path():
    """`XrefError.message` embeds its own path -- the driver tests above pin that, and
    it is right for a standalone xref caller. But `ValidationError` carries `path` as
    its own field, the way the jsonschema half does, so the adapter must hand over the
    PATHLESS detail. Otherwise every caller that prints "{path}: {message}" -- ugard's
    gate 1 does -- prints the path twice, which it has been doing for every xref
    finding, `aggregate_id` included."""
    errors = validate_cross_references(
        _exchange_doc({"kind": "credential", "exported_credential_id": "ghost"}))
    assert [(e.path, e.message) for e in errors] == [(
        "commands[0].emissions[0].exchange.exported_credential_id",
        "credentials.exports 'ghost' not found")]


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


def test_missing_credential_slot_names_the_cause(minimal_valid_template):
    # F9: a slotless credential exchange (the outbound apply/offer shape this
    # profile excludes) must say WHY, not just fail an opaque oneOf.
    minimal_valid_template["commands"].append({
        "id": "bad",
        "name": "Bad",
        "description": "Slotless credential exchange.",
        "route": "/insurance/cmd/x",
        "payload_schema": {},
        "emissions": [
            {
                "kind": "exchange",
                "exchange": {
                    "kind": "credential",
                    "schema_said_referenced": "EAbc0000000000000000000000000000000000000000"
                }
            }
        ]
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert any("missing_credential_slot" in e.message for e in errors), (
        f"expected an explanatory missing_credential_slot message, got: {[e.message for e in errors]}"
    )
    assert not any("not valid under any of the given schemas" in e.message for e in errors)


def test_ambiguous_credential_slot_names_the_cause(minimal_valid_template):
    # Same defect, opposite shape: both slots declared at once.
    minimal_valid_template["commands"].append({
        "id": "bad2",
        "name": "Bad2",
        "description": "Exchange declaring both credential slots.",
        "route": "/insurance/cmd/y",
        "payload_schema": {},
        "emissions": [
            {
                "kind": "exchange",
                "exchange": {
                    "kind": "credential",
                    "exported_credential_id": "a",
                    "imported_credential_id": "b"
                }
            }
        ]
    })
    errors = validate_against_meta_schema(minimal_valid_template, META_SCHEMA)
    assert any("ambiguous_credential_slot" in e.message for e in errors), (
        f"expected an explanatory ambiguous_credential_slot message, got: {[e.message for e in errors]}"
    )


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
