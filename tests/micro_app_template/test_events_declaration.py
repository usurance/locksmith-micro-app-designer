# tests/micro_app_template/test_events_declaration.py
"""The `aggregates[].events` declaration (authoring spec §6.5).

Landed 2026-07-28 by the declared-event-schema decision
(ugard docs/superpowers/specs/2026-07-28-declared-event-schema-design.md).

`events` is OPTIONAL at micro-app-template/0.1 and REQUIRED at 0.2. At 0.1 its
purpose is forward-compatible authoring: the three remaining IPC children declare
their event contracts now, and the concierge-api checks land afterwards. The
aggregate definition carries `additionalProperties: false`, so without this
widening the block could not be authored at all — that is why the meta-schema
change is on the children's critical path and the checker is not.

Three rules ARE enforced here rather than deferred to the checker, because they are
load-bearing and the checker is follow-on work:

  1. `additionalProperties: false` on the payload_schema. A contract that is not
     closed merely restates the inference the declaration exists to replace.
  2. The eight envelope-reserved names. `computes/fold_engine._flatten_event`
     stamps type/said/seq/source_aid/datetime, plus the credential provenance
     triple (credential_said/credential_issuer/credential_edges), OVER the
     payload, so a payload property with one of those names is silently
     discarded at fold time. Grown from five to eight 2026-07-28 to match the
     checker's `emission_bindings.RESERVED_ENVELOPE` (register finding 37) --
     a prior-session gap where two mechanisms disagreed on one rule.
  3. The declared mint (`from`). An event-schema property may instead declare
     `"from": "<envelope slot>"` -- a closed enum of the eight names above,
     nothing else: no expressions, no renames. The property name IS the
     domain name; `from` only names which envelope slot mints its value at
     append time. One declaration per event type. Owner ruling 2026-07-28,
     register finding 37; authoring spec §6.5.
"""
import json
import pathlib

import jsonschema
import pytest

SCHEMA = json.loads(
    pathlib.Path("docs/superpowers/specs/schemas/micro-app-template.schema.json").read_text()
)

RESERVED_ENVELOPE_NAMES = [
    "type", "said", "seq", "source_aid", "datetime",
    "credential_said", "credential_issuer", "credential_edges",
]


def _defs():
    return SCHEMA.get("$defs", SCHEMA.get("definitions", {}))


def _declaration(properties=None, additional_properties=False, description="A thing happened."):
    payload_schema = {
        "type": "object",
        "properties": {"license_said": {"type": "string"}} if properties is None else properties,
        "required": ["license_said"],
    }
    if additional_properties is not None:
        payload_schema["additionalProperties"] = additional_properties
    decl = {"payload_schema": payload_schema}
    if description is not None:
        decl["description"] = description
    return decl


def _validator_for(definition):
    """Validate a `$defs` fragment with the full schema as the resolution root.

    `event_map` refs `event_declaration`, so validating the bare fragment the way
    the older meta-schema tests do (they validate ref-free fragments) raises
    PointerToNowhere instead of testing anything.
    """
    return jsonschema.Draft202012Validator(
        {"$ref": f"#/$defs/{definition}", "$defs": SCHEMA["$defs"]}
    )


def _validate_declaration(decl):
    _validator_for("event_declaration").validate(decl)


def _schema():
    return SCHEMA


def _emission_errors(emission):
    return list(_validator_for("emission").iter_errors(emission))


def test_payload_mapping_is_rejected_not_merely_unrequired():
    """$defs/emission has no additionalProperties:false, so dropping the key
    from `required` alone would leave it silently permitted."""
    em = {"kind": "aggregate_event", "aggregate_id": "a", "event_type": "e",
          "payload_mapping": '{ "x": command.x }'}
    assert _emission_errors(em), "payload_mapping must be rejected"


def test_spec_id_is_0_2():
    assert _schema()["$id"].endswith("micro-app-template/0.2")


def test_aggregate_accepts_an_events_map():
    """The widening itself: an aggregate with `events` validates."""
    _validator_for("event_map").validate({"license_received": _declaration()})


def test_events_is_required_on_the_aggregate():
    """0.2 posture. This test is the deliberate inversion of the 0.1-era
    `test_events_is_optional_on_the_aggregate`, which asserted the opposite.

    The flip is not a mistake and must not be flipped back. At 0.1 `events` was
    optional because the declaration was forward-compatible authoring and the
    concierge-api checks had not landed. At 0.2 `payload_mapping` is REMOVED, so
    the declaration is the *only* description of an event's contract — there is
    no mapping left to infer one from. An aggregate without `events` would
    therefore have no checkable event contract at all, which is precisely the
    inference the removal exists to end.

    Driven by: owner review 2026-07-28; ugard
    `backlog/2026-07-28-remove-payload-mapping.md`.
    """
    assert "events" in _defs()["aggregate"]["required"]
    assert "events" in _defs()["aggregate"]["properties"]


def test_well_formed_declaration_validates():
    _validate_declaration(_declaration())


def test_description_is_optional():
    _validate_declaration(_declaration(description=None))


def test_payload_schema_is_required():
    with pytest.raises(jsonschema.ValidationError):
        _validate_declaration({"description": "no schema"})


def test_unknown_key_in_declaration_is_rejected():
    decl = _declaration()
    decl["bogus"] = 1
    with pytest.raises(jsonschema.ValidationError):
        _validate_declaration(decl)


def test_open_contract_is_rejected_when_additional_properties_omitted():
    with pytest.raises(jsonschema.ValidationError):
        _validate_declaration(_declaration(additional_properties=None))


def test_open_contract_is_rejected_when_additional_properties_true():
    with pytest.raises(jsonschema.ValidationError):
        _validate_declaration(_declaration(additional_properties=True))


@pytest.mark.parametrize("reserved", RESERVED_ENVELOPE_NAMES)
def test_envelope_reserved_name_is_rejected(reserved):
    """A payload property named for an envelope field is dead on arrival — the
    fold engine overwrites it. Reject at authoring time instead."""
    decl = _declaration(
        properties={"license_said": {"type": "string"}, reserved: {"type": "string"}}
    )
    with pytest.raises(jsonschema.ValidationError):
        _validate_declaration(decl)


def test_reserved_list_matches_the_fold_engine():
    """Pins the list against the reason it exists. If `_flatten_event` ever stamps
    a sixth envelope field, this list and the meta-schema must grow with it."""
    guard = _defs()["event_declaration"]["properties"]["payload_schema"]["properties"][
        "properties"
    ]["propertyNames"]["not"]["enum"]
    assert sorted(guard) == sorted(RESERVED_ENVELOPE_NAMES)


# --------------------------------------------------------------------------------
# The declared mint (`from`) -- owner ruling 2026-07-28, register finding 37
# --------------------------------------------------------------------------------

def test_from_mint_on_credential_said_validates():
    """The worked corpus example (authoring spec §6.5): `application_id` is a
    stable business key minted, at this event type, from the credential SAID the
    same emission just admitted. The property name is the domain name;
    `from` only names which envelope slot supplies its value."""
    decl = _declaration(
        properties={
            "license_said": {"type": "string"},
            "application_id": {"type": "string", "from": "credential_said"},
        }
    )
    _validate_declaration(decl)


def test_from_outside_the_enum_is_rejected():
    """`from` is a closed enumeration of the eight envelope names -- no
    expressions, no near-miss spellings, nothing computed."""
    decl = _declaration(
        properties={
            "license_said": {"type": "string"},
            "application_id": {"type": "string", "from": "credential"},
        }
    )
    with pytest.raises(jsonschema.ValidationError):
        _validate_declaration(decl)


def test_from_on_a_reserved_property_name_is_rejected():
    """A property can never be NAMED one of the eight reserved names, `from` or
    not -- `from` mints INTO a differently-named domain property; it is not a
    loophole for declaring the reserved name itself under a fresh alias. Also
    pins the propertyNames growth from five to eight (change 1): `credential_said`
    was not in the old five-name exclusion."""
    decl = _declaration(
        properties={
            "license_said": {"type": "string"},
            "credential_said": {"type": "string", "from": "credential_said"},
        }
    )
    with pytest.raises(jsonschema.ValidationError):
        _validate_declaration(decl)


def test_credential_issuer_property_name_is_rejected_without_from():
    """Pins the five-to-eight catch-up (change 1) on a name the old exclusion
    missed outright: `credential_issuer` is not in RESERVED_ENVELOPE_NAMES's
    original five, so a bare (no `from`) payload_schema property under that name
    used to validate silently -- dead on arrival at fold time, same as the
    original five."""
    decl = _declaration(
        properties={
            "license_said": {"type": "string"},
            "credential_issuer": {"type": "string"},
        }
    )
    with pytest.raises(jsonschema.ValidationError):
        _validate_declaration(decl)


def test_landed_corpus_still_validates():
    """The widening must not regress the five landed bundles. Read out of ugard's
    working tree, mirroring concierge-api's calibration test."""
    corpus = sorted(
        pathlib.Path("/Users/seriouscoderone/code/ugard/docs/micro-apps").glob(
            "*/micro-app-template.json"
        )
    )
    if not corpus:
        pytest.skip("ugard corpus not available in this checkout")
    validator = jsonschema.Draft202012Validator(SCHEMA)
    for path in corpus:
        errors = list(validator.iter_errors(json.loads(path.read_text())))
        assert not errors, f"{path.parent.name}: {[e.message for e in errors]}"
