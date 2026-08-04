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
import os
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


def test_from_enum_is_exactly_the_eight_envelope_names():
    """The enum's CONTENTS, not just its closedness.

    `test_from_outside_the_enum_is_rejected` proves a non-member is refused, which
    stays true no matter how much of the enum you delete -- a mutation removing two
    values from the meta-schema produced ZERO failures across the whole suite. The
    hole that leaves is the check-red/runtime-green direction: an author declares
    `"from": "credential_issuer"`, the engine would mint it perfectly well, and the
    meta-schema refuses a legal template. So assert EQUALITY, as a set: the enum is
    the eight names the envelope supplies, no more and no fewer.
    """
    enum = _defs()["event_declaration"]["properties"]["payload_schema"]["properties"][
        "properties"
    ]["additionalProperties"]["properties"]["from"]["enum"]
    assert set(enum) == set(RESERVED_ENVELOPE_NAMES)
    assert len(enum) == len(RESERVED_ENVELOPE_NAMES), f"duplicate entries: {enum}"


# --------------------------------------------------------------------------------
# The landed corpus, per bundle
#
# CROSS-REPO COUPLING. `$UGARD_ROOT` (default ~/code/ugard) is a checkout of another
# repository at whatever revision it happens to be on -- the same override, spelled the
# same way, as concierge-api's `tests/cli/test_emission_bindings_calibration.py`. Point
# it at the branch worktree to see the migrated corpus. A failure here means one of:
# that checkout predates the migration; someone regressed a bundle in ugard; or this
# meta-schema regressed. Only the last is a bug in this repo.
#
# Per BUNDLE, not one monolithic loop: a single assertion over a glob reports the first
# bundle that breaks and hides the rest, and it cannot carry a per-bundle exemption.
# --------------------------------------------------------------------------------

UGARD = pathlib.Path(os.environ.get("UGARD_ROOT", pathlib.Path.home() / "code" / "ugard"))
CORPUS = UGARD / "docs" / "micro-apps"

#: Membership is in flux through ugard's actuarial-HOA corpus work
#: (`docs/superpowers/plans/2026-08-03-actuarial-hoa-b-the-corpus.md`), which changes it
#: FOUR times, and ALL FOUR HAVE NOW LANDED (2026-08-04): +cuo-declares-product-mandate
#: (task 2), +actuary-attests-rate-program (task 3), +designer-assembles-product-bundle
#: (task 4), and -3 at task 5b retiring the pre-redesign triangle. Each of the four
#: reddened this suite until the list caught up. Nothing in ugard's own six-gate runner (`scripts/gate_corpus.sh`)
#: runs THIS suite, so each of those changes reddens `test_corpus_covers_every_bundle_present`
#: here until this list catches up -- and that is the guard working, not a nuisance: it caught
#: bundle 1 within the hour. Recorded on the ugard side as plan defect B10.
CORPUS_BUNDLES = [
    "actuary-attests-rate-program",
    "carrier-license-application",
    "cuo-declares-product-mandate",
    "designer-assembles-product-bundle",
    "regulator-grants-carrier-license",
]

#: EMPTY as of 2026-08-04, and deliberately kept rather than deleted. Both descoped
#: bundles (`actuary-attests-product-rating`, `chief-underwriting-officer-approves-\
#: product-launch`) were RETIRED by ugard plan task 5b -- superseded by
#: `actuary-attests-rate-program` and `cuo-declares-product-mandate`, which are authored
#: at 0.2 and validate cleanly, so the exemption has no subjects left. The mechanism
#: stays because it is the right shape for the next owner-descoped bundle: an exemption
#: keyed by BUNDLE IDENTITY, never by path, mapped to the backlog item it waits on.
DESCOPED: dict[str, str] = {}


def descoped_reason(bundle):
    """The one wording for this exemption, shared verbatim with concierge-api's
    `tests/cli/test_emission_bindings_calibration.py`. Two suites, one sentence, so a
    grep for either backlog item finds both."""
    return (
        f"descoped by owner ruling 2026-07-31: {bundle} stays at "
        f"micro-app-template/0.1 with its payload_mapping until the redesign in "
        f"ugard {DESCOPED[bundle]} lands. strict=True -- when it lands and the "
        f"bundle migrates, this XPASSes and the suite goes red until the "
        f"exemption is deleted."
    )


_CORPUS_PARAMS = [
    pytest.param(
        b,
        marks=pytest.mark.xfail(strict=True, reason=descoped_reason(b)),
    ) if b in DESCOPED else b
    for b in CORPUS_BUNDLES
]


#: What the primitives-are-given meta-schema (this repo's Task 4, 2026-08-02) reports
#: against each landed, non-DESCOPED bundle TODAY. All five corpus bundles -- these
#: three included -- are being deleted and re-authored through the new KERI-shape pass
#: (owner ruling 2026-07-31, ugard `backlog/2026-07-31-delete-and-reauthor-the-ipc-corpus.md`);
#: repairing them here is out of scope for the whole plan this test file's changes belong
#: to (`docs/superpowers/plans/2026-08-02-keri-primitive-contour-alignment.md`). Unlike the
#: two DESCOPED bundles above, these three are not blocked on a narrower redesign item and
#: are not yet known-broken for a *different* reason (`payload_mapping`) -- they are already
#: at `micro-app-template/0.2` and fail on exactly the three surfaces this meta-schema wave
#: removed (the credential-lifecycle-transition state-primitive field, the outbound exchange
#: verb, and the advance-the-lifecycle emission kind), so an `errors == []` assertion is the
#: wrong shape for them now. Mirrors the identical re-pin concierge-api's Task 12 did to
#: `tests/cli/test_emission_bindings_calibration.py`'s `EXPECTED_ERROR_COUNT` map for
#: these same three bundles -- same date, same reasoning, DIFFERENT numbers (concierge-api's
#: map there reads {"carrier-license-application": 3, "product-designer-publishes-product-version":
#: 8, "regulator-grants-carrier-license": 6}): that map counts loader/binding errors
#: (`emission_bindings.check_template`, e.g. `missing_subject_selector`); this one counts
#: meta-schema validation errors (`jsonschema` against `micro-app-template.schema.json`) --
#: two different checkers looking at the same bundles for two different reasons. Do not
#: reconcile one map to the other. Assertion is `==`, so it catches a regression (count
#: rises) AND a silent over-fix (count falls) equally; when a bundle is re-authored and
#: either drops out of CORPUS_BUNDLES or validates cleanly, delete its row.
EXPECTED_ERROR_COUNT = {
    # Rows for the carrier pair DELETED 2026-08-02: both bundles were re-authored
    # from scratch through the KERI-shape pass (ugard
    # backlog/2026-07-31-delete-and-reauthor-the-ipc-corpus.md) and now validate
    # cleanly -- 3 -> 0 and 10 -> 0. Every one of those 13 errors was the deleted
    # vocabulary itself (`tel_primitive`, `lifecycle_advance`, the restated outbound
    # `exchange.verb`), which is why they cleared together. Deleting the rows is what
    # this map's docstring prescribes for exactly this case, so a future regression in
    # either bundle now fails against zero rather than against a tolerated count.
    # Row for product-designer-publishes-product-version (16) DELETED 2026-08-04: the
    # bundle was RETIRED by ugard plan task 5b, superseded by
    # designer-assembles-product-bundle, which validates cleanly. Same disposition the
    # carrier pair got above -- when a bundle stops existing its tolerated count must go
    # with it, or the map silently tolerates errors for a path nothing can validate.
}


@pytest.mark.skipif(not CORPUS.is_dir(), reason="ugard corpus not checked out")
@pytest.mark.parametrize("bundle", _CORPUS_PARAMS)
def test_landed_corpus_still_validates(bundle):
    """The widening must not regress the landed bundles.

    Non-DESCOPED bundles are checked against `EXPECTED_ERROR_COUNT`, dated
    2026-08-02, rather than "zero errors" -- see the map's docstring for why.
    """
    path = CORPUS / bundle / "micro-app-template.json"
    assert path.is_file(), f"missing bundle: {path} (corpus at {CORPUS})"
    validator = jsonschema.Draft202012Validator(SCHEMA)
    errors = list(validator.iter_errors(json.loads(path.read_text())))
    expected = EXPECTED_ERROR_COUNT.get(bundle, 0)
    assert len(errors) == expected, (
        f"{bundle}: expected {expected} errors, got {len(errors)}: "
        f"{[e.message for e in errors]}"
    )


@pytest.mark.skipif(not CORPUS.is_dir(), reason="ugard corpus not checked out")
def test_corpus_covers_every_bundle_present():
    """UNMARKED, and it must stay that way: a sixth bundle must not slip past the
    per-bundle validation above by simply not being listed. This replaces the reach
    of the old glob, which the fixed list would otherwise have lost."""
    found = sorted(p.parent.name for p in CORPUS.glob("*/micro-app-template.json"))
    assert found == sorted(CORPUS_BUNDLES), (
        f"corpus membership changed; add the new bundle to CORPUS_BUNDLES "
        f"(found {found} at {CORPUS})"
    )
