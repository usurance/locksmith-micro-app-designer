# -*- encoding: utf-8 -*-
"""Tests for the Designer's self-contained CEL/1.0 fold engine
(`locksmith_micro_app_designer.template.fold_runner`).

Two duties, per the Stage 5 controller resolution:

1. **Behavioral equivalence** with the reference engine in
   `concierge-api` (`computes/cel_env.py` + `computes/fold_engine.py`):
   reproduce the accepted spec's §10 gym conformance vectors verbatim
   (the same vectors `concierge-api`'s `tests/computes/test_cel_profile.py`
   exercises) and assert this engine gets the same answer.
2. **Vector-runner behavior**: `run_test_vectors()` against the two worked
   examples' own `test_vectors[]` must report every vector green, and must
   correctly report a deliberately-broken vector as failed (so a false
   "all green" isn't silently possible).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from locksmith_micro_app_designer.template.fold_runner import (
    ENVELOPE_SLOTS,
    FoldDefinition,
    InvariantViolation,
    _flatten_event,
    _route_key,
    cel_env,
    fold,
    fold_definition_from_aggregate,
    fold_definition_from_projection,
    materialize_mints,
    run_test_vectors,
    try_append,
)


EXAMPLES_DIR = (
    Path(__file__).parent.parent.parent
    / "skills/micro-app-template-gen/references/examples"
)


# --- op-level sanity (§8) ---------------------------------------------------------------

def test_op_set_replaces_a_field():
    defn = FoldDefinition.aggregate(
        fold={"e": [{"op": "set", "target": "capacity", "value": "event.capacity"}]},
        initial_state={"capacity": 0},
    )
    state = fold(defn, [{"type": "e", "payload": {"capacity": 5}}], cel_env("aggregate_fold"))
    assert state == {"capacity": 5}


def test_op_upsert_creates_then_overwrites_named_fields():
    defn = FoldDefinition.collection_projection(
        primary_key="application_id",
        fold={"e": [{"op": "upsert", "set": {
            "application_id": "event.application_id",
            "status": "'pending'",
        }}]},
    )
    env = cel_env("projection_fold")
    rows = fold(defn, [{"type": "e", "payload": {"application_id": "A1"}}], env)
    assert rows == {"A1": {"application_id": "A1", "status": "pending"}}


def test_unknown_event_type_is_skipped_without_error():
    defn = FoldDefinition.aggregate(
        fold={"e": [{"op": "set", "target": "capacity", "value": "event.capacity"}]},
        initial_state={"capacity": 0},
    )
    events = [
        {"type": "e", "payload": {"capacity": 3}},
        {"type": "some_future_event_type", "payload": {"whatever": "value"}},
    ]
    state = fold(defn, events, cel_env("aggregate_fold"))
    assert state == {"capacity": 3}


# --- accepted spec §10 conformance vectors (gym class_roster / schedule_board) ----------
# Reproduced verbatim from concierge-api's tests/computes/test_cel_profile.py, which
# exercises the same vectors against the reference engine (cel_env.py + fold_engine.py).
# This is the behavioral-equivalence guard: two independently-implemented engines must
# agree on the same conformance data.

CLASS_ROSTER = FoldDefinition.aggregate(
    fold={
        "class_scheduled": [
            {"op": "set", "target": "capacity", "value": "event.capacity"},
        ],
        "member_booked": [
            {"op": "append", "target": "attendees", "value": "event.member_id"},
        ],
        "booking_cancelled": [
            {"op": "remove", "target": "attendees", "where": "item == event.member_id"},
        ],
        "member_checked_in": [
            {"op": "increment", "target": "checked_in", "by": "1"},
        ],
        "class_cancelled": {
            "expression": (
                '{ "status": "cancelled", "capacity": state.capacity, '
                '"attendees": [], "checked_in": 0 }'
            ),
        },
    },
    initial_state={"status": "scheduled", "capacity": 0, "attendees": [], "checked_in": 0},
    invariants=[
        {"rule_ref": "class_never_over_capacity",
         "expression": "size(state.attendees) <= state.capacity"},
        {"rule_ref": "no_duplicate_booking",
         "expression": "size(state.attendees.filter(a, a == event.member_id)) <= 1"},
    ],
)

SCHEDULE_BOARD = FoldDefinition.collection_projection(
    primary_key="class_id",
    fold={
        "class_scheduled": [
            {"op": "upsert", "set": {
                "class_id": "event.class_id",
                "discipline": "event.discipline",
                "instructor": "event.instructor_name",
                "starts": "event.start_time",
                "spots_left": "event.capacity",
                "status": "'open'",
            }},
        ],
        "member_booked": [
            {"op": "update", "set": {
                "spots_left": "row.spots_left - 1",
                "status": "row.spots_left - 1 == 0 ? 'full' : 'open'",
            }},
        ],
        "booking_cancelled": [
            {"op": "update", "set": {
                "spots_left": "row.spots_left + 1",
                "status": "'open'",
            }},
        ],
        "class_cancelled": [
            {"op": "update", "set": {"status": "'cancelled'", "spots_left": "0"}},
        ],
    },
)


def test_schedule_board_fold_vector_booking_then_cancellation_restores_capacity():
    """Accepted spec §10, vector "booking then cancellation restores
    capacity" -- reproduced verbatim; must agree with concierge-api."""
    events = [
        {"type": "class_scheduled", "payload": {
            "class_id": "C1", "capacity": 2, "discipline": "yoga",
            "instructor_name": "Ada", "start_time": "2026-08-01T09:00:00Z",
        }},
        {"type": "member_booked", "payload": {"class_id": "C1", "member_id": "M1"}},
        {"type": "member_booked", "payload": {"class_id": "C1", "member_id": "M2"}},
        {"type": "booking_cancelled", "payload": {"class_id": "C1", "member_id": "M1"}},
    ]

    rows = fold(SCHEDULE_BOARD, events, cel_env("projection_fold"))

    assert rows == {
        "C1": {
            "class_id": "C1", "discipline": "yoga", "instructor": "Ada",
            "starts": "2026-08-01T09:00:00Z", "spots_left": 1, "status": "open",
        }
    }


def test_class_roster_invariant_vector_third_booking_rejected_by_capacity():
    """Accepted spec §10, vector "third booking is rejected by capacity
    invariant" -- reproduced verbatim; must agree with concierge-api."""
    setup_events = [
        {"type": "class_scheduled", "payload": {"class_id": "C1", "capacity": 2}},
        {"type": "member_booked", "payload": {"class_id": "C1", "member_id": "M1"}},
        {"type": "member_booked", "payload": {"class_id": "C1", "member_id": "M2"}},
    ]
    proposed = {"type": "member_booked", "payload": {"class_id": "C1", "member_id": "M3"}}

    env = cel_env("aggregate_fold")
    inv_env = cel_env("invariant")
    current = fold(CLASS_ROSTER, setup_events, env)

    with pytest.raises(InvariantViolation) as excinfo:
        try_append(CLASS_ROSTER, current, proposed, env, inv_env)

    assert excinfo.value.rule_ref == "class_never_over_capacity"


def test_gym_vectors_via_run_test_vectors_helper():
    """Same two gym vectors, but driven through the public
    `run_test_vectors()` entry point the Designer's panel calls -- exercises
    the vector-shape dispatch (fold vector vs. invariant vector) end to end."""
    aggregate_entry = {
        "id": "class_roster",
        "fold": CLASS_ROSTER.fold,
        "initial_state": CLASS_ROSTER.initial_state,
        "invariants": [{"rule_ref": r["rule_ref"]} for r in CLASS_ROSTER.invariants],
        "test_vectors": [
            {
                "name": "third booking is rejected by capacity invariant",
                "events": [
                    {"type": "class_scheduled", "payload": {"class_id": "C1", "capacity": 2}},
                    {"type": "member_booked", "payload": {"class_id": "C1", "member_id": "M1"}},
                    {"type": "member_booked", "payload": {"class_id": "C1", "member_id": "M2"}},
                ],
                "append": {"type": "member_booked", "payload": {"class_id": "C1", "member_id": "M3"}},
                "expect_rejected_by": "class_never_over_capacity",
            },
        ],
    }
    doc = {
        "rules": [
            {"id": r["rule_ref"], "type": "validation", "expression": r["expression"]}
            for r in CLASS_ROSTER.invariants
        ],
    }
    outcomes = run_test_vectors(aggregate_entry, entry_kind="aggregate", doc=doc)
    assert len(outcomes) == 1
    assert outcomes[0].passed
    assert outcomes[0].kind == "invariant"
    assert outcomes[0].rejected_by == "class_never_over_capacity"

    projection_entry = {
        "id": "schedule_board",
        "shape": "collection",
        "primary_key": "class_id",
        "fold": SCHEDULE_BOARD.fold,
        "test_vectors": [
            {
                "name": "booking then cancellation restores capacity",
                "events": [
                    {"type": "class_scheduled", "payload": {
                        "class_id": "C1", "capacity": 2, "discipline": "yoga",
                        "instructor_name": "Ada", "start_time": "2026-08-01T09:00:00Z",
                    }},
                    {"type": "member_booked", "payload": {"class_id": "C1", "member_id": "M1"}},
                    {"type": "member_booked", "payload": {"class_id": "C1", "member_id": "M2"}},
                    {"type": "booking_cancelled", "payload": {"class_id": "C1", "member_id": "M1"}},
                ],
                "expected": {
                    "rows": {
                        "C1": {
                            "class_id": "C1", "discipline": "yoga", "instructor": "Ada",
                            "starts": "2026-08-01T09:00:00Z", "spots_left": 1, "status": "open",
                        }
                    }
                },
            },
        ],
    }
    outcomes = run_test_vectors(projection_entry, entry_kind="projection", doc=None)
    assert len(outcomes) == 1
    assert outcomes[0].passed
    assert outcomes[0].kind == "fold"


def test_run_test_vectors_reports_a_failing_vector_as_failed():
    """A deliberately-wrong `expected` must report failed=False with the
    actual/expected mismatch surfaced -- guards against a runner that
    always reports green."""
    projection_entry = {
        "id": "schedule_board",
        "shape": "collection",
        "primary_key": "class_id",
        "fold": SCHEDULE_BOARD.fold,
        "test_vectors": [
            {
                "name": "deliberately wrong expectation",
                "events": [
                    {"type": "class_scheduled", "payload": {
                        "class_id": "C1", "capacity": 2, "discipline": "yoga",
                        "instructor_name": "Ada", "start_time": "2026-08-01T09:00:00Z",
                    }},
                ],
                "expected": {"rows": {"C1": {"spots_left": 999}}},
            },
        ],
    }
    outcomes = run_test_vectors(projection_entry, entry_kind="projection", doc=None)
    assert len(outcomes) == 1
    assert not outcomes[0].passed
    assert outcomes[0].actual != outcomes[0].expected


def test_run_test_vectors_returns_empty_list_when_none_declared():
    assert run_test_vectors({"id": "x", "fold": {}}, entry_kind="aggregate", doc={}) == []


# --- worked-example equivalence: every shipped vector must run green -------------------

def _load_example(name: str) -> dict:
    path = EXAMPLES_DIR / name / "micro-app-template.json"
    with open(path) as f:
        return json.load(f)


WORKED_EXAMPLES = [
    "carrier-license-application",
    "regulator-grants-carrier-license",
]


@pytest.mark.parametrize("example_name", WORKED_EXAMPLES)
def test_worked_example_aggregate_vectors_all_pass(example_name):
    doc = _load_example(example_name)
    ran_any = False
    for agg in doc.get("aggregates", []):
        if not agg.get("test_vectors"):
            continue
        ran_any = True
        outcomes = run_test_vectors(agg, entry_kind="aggregate", doc=doc)
        failures = [o for o in outcomes if not o.passed]
        assert not failures, (
            f"{example_name}: aggregate {agg['id']!r} failing vectors: "
            f"{[(o.name, o.error, o.actual, o.expected) for o in failures]}"
        )
    assert ran_any, f"{example_name}: expected at least one aggregate test_vectors entry"


@pytest.mark.parametrize("example_name", WORKED_EXAMPLES)
def test_worked_example_projection_vectors_all_pass(example_name):
    doc = _load_example(example_name)
    ran_any = False
    for proj in doc.get("projections", []):
        if not proj.get("test_vectors"):
            continue
        ran_any = True
        outcomes = run_test_vectors(proj, entry_kind="projection", doc=doc)
        failures = [o for o in outcomes if not o.passed]
        assert not failures, (
            f"{example_name}: projection {proj['id']!r} failing vectors: "
            f"{[(o.name, o.error, o.actual, o.expected) for o in failures]}"
        )
    assert ran_any, f"{example_name}: expected at least one projection test_vectors entry"


def test_fold_definition_from_aggregate_resolves_invariant_rule_refs():
    doc = _load_example("carrier-license-application")
    agg = next(a for a in doc["aggregates"] if a["id"] == "license_registry")
    rules_by_id = {r["id"]: r for r in doc["rules"] if "id" in r}
    defn = fold_definition_from_aggregate(agg, rules_by_id=rules_by_id)
    assert defn.invariants
    for inv in defn.invariants:
        assert inv["expression"], f"unresolved invariant rule_ref: {inv['rule_ref']!r}"


def test_fold_definition_from_projection_defaults_shape_to_collection():
    proj = {"id": "p", "primary_key": "k", "fold": {}}
    defn = fold_definition_from_projection(proj)
    assert defn.kind == "collection"
    assert defn.primary_key == "k"


# =========================================================================================
# Tracking the reference: envelope triple, declared mint, bare-name routing
# =========================================================================================
#
# `fold_runner` is subordinate to concierge's `computes/fold_engine.py`; if the
# two disagree that is a bug HERE. These pins mirror the reference's
# `tests/computes/test_declared_mint.py` and `test_envelope_provenance.py` in
# this repo's idiom, so a reference change that this module has not tracked
# shows up as a red row rather than as a quiet divergence.

# --- the eight-name envelope (register finding 36) ---------------------------------------

def test_the_credential_provenance_triple_is_visible_to_a_handler():
    """With `payload_mapping` gone, the envelope is the ONLY way a fold can
    reach the protocol facts about the ACDC behind an event."""
    defn = FoldDefinition.aggregate(
        fold={"e": [
            {"op": "set", "target": "said", "value": "event.credential_said"},
            {"op": "set", "target": "issuer", "value": "event.credential_issuer"},
            {"op": "set", "target": "edges", "value": "event.credential_edges"},
        ]},
        initial_state={},
    )
    state = fold(defn, [{"type": "e", "credential_said": "EC1",
                         "credential_issuer": "EIss", "payload": {},
                         "credential_edges": {"version": "EV1"}}],
                 cel_env("aggregate_fold"))
    assert state == {"said": "EC1", "issuer": "EIss", "edges": {"version": "EV1"}}


@pytest.mark.parametrize("slot,default", [
    ("said", ""), ("seq", 0), ("source_aid", ""), ("datetime", ""),
    ("credential_said", ""), ("credential_issuer", ""), ("credential_edges", {}),
])
def test_an_absent_envelope_slot_flattens_to_its_own_default(slot, default):
    assert _flatten_event({"type": "e", "payload": {}})[slot] == default


@pytest.mark.parametrize("name", sorted(ENVELOPE_SLOTS))
def test_a_payload_cannot_shadow_any_of_the_eight_envelope_names(name):
    """All eight stamps land AFTER the payload merge, so all eight names are
    reserved and a payload supplying one has its value discarded."""
    event = {"type": "e", "said": "ES", "seq": 7, "source_aid": "EA",
             "datetime": "2026-07-28T00:00:00Z", "credential_said": "EC",
             "credential_issuer": "EI", "credential_edges": {"v": "EV"},
             "payload": {name: "PAYLOAD_WINS_NOT"}}
    assert _flatten_event(event)[name] != "PAYLOAD_WINS_NOT"


def test_the_flattened_credential_edges_is_a_copy_not_the_envelopes_object():
    edges = {"version": "EV1"}
    flat = _flatten_event({"type": "e", "credential_edges": edges, "payload": {}})
    assert flat["credential_edges"] == edges and flat["credential_edges"] is not edges


def test_the_envelope_slot_enumeration_is_derived_from_the_flattener():
    """One list, not two: `ENVELOPE_SLOTS` is what `_flatten_event` produces,
    so the mint's closed enumeration cannot drift from the envelope itself."""
    assert ENVELOPE_SLOTS == {"type", "said", "seq", "source_aid", "datetime",
                              "credential_said", "credential_issuer",
                              "credential_edges"}


# --- the declared mint: §6.5 `from`, materialized at append time -------------------------

def test_the_slot_value_lands_in_the_payload_under_the_property_name():
    minted = materialize_mints(
        {"type": "application_received", "credential_said": "EApp1",
         "payload": {"jurisdiction": "US-CA"}},
        {"application_received": {"application_id": "credential_said"}})
    assert minted["payload"] == {"jurisdiction": "US-CA", "application_id": "EApp1"}


def test_materialize_mints_never_mutates_the_input_event():
    """`fold` replays a caller's list; minting in place would rewrite the log
    -- and in the Designer that list is the document the user is editing."""
    event = {"type": "e", "credential_said": "EApp1", "payload": {"j": "US-CA"}}
    materialize_mints(event, {"e": {"application_id": "credential_said"}})
    assert event == {"type": "e", "credential_said": "EApp1", "payload": {"j": "US-CA"}}


def test_the_envelope_wins_over_a_payload_supplied_value():
    """Finding 36's rule reaching one name further -- and why a vector cannot
    shadow a mint: vectors supply payloads, and the envelope overwrites them."""
    minted = materialize_mints(
        {"type": "e", "credential_said": "EFromEnvelope",
         "payload": {"application_id": "EFromPayload"}},
        {"e": {"application_id": "credential_said"}})
    assert minted["payload"]["application_id"] == "EFromEnvelope"


@pytest.mark.parametrize("slot,default", [
    ("said", ""), ("source_aid", ""), ("datetime", ""),
    ("credential_said", ""), ("credential_issuer", ""),
    ("seq", 0), ("credential_edges", {}),
])
def test_an_absent_slot_mints_the_slots_own_default(slot, default):
    """Read through `_flatten_event`, so the defaults cannot drift: an event
    with no credential behind it mints `""`, not a missing key."""
    minted = materialize_mints({"type": "e", "payload": {}}, {"e": {"k": slot}})
    assert minted["payload"]["k"] == default


def test_the_eighth_slot_is_the_event_type_itself():
    minted = materialize_mints({"type": "e", "payload": {}}, {"e": {"k": "type"}})
    assert minted["payload"]["k"] == "e"


def test_a_credential_edges_mint_copies_the_map():
    """The mint must not alias the envelope's dict: two events defaulting to
    the same object would let one fold's mutation leak into another's."""
    edges = {"version": "EVersion1"}
    minted = materialize_mints({"type": "e", "credential_edges": edges, "payload": {}},
                               {"e": {"provenance": "credential_edges"}})
    assert minted["payload"]["provenance"] == {"version": "EVersion1"}
    assert minted["payload"]["provenance"] is not edges


def test_an_event_type_with_no_declared_mint_passes_through():
    event = {"type": "other", "payload": {"j": "US-CA"}}
    assert materialize_mints(event, {"e": {"k": "credential_said"}}) is event
    assert materialize_mints(event, {}) is event


def test_a_from_slot_outside_the_eight_is_refused_loudly():
    """The enumeration is closed (§6.5). Reading a same-named payload field
    instead would silently implement the rename the ruling forbids."""
    with pytest.raises(ValueError, match="envelope"):
        materialize_mints({"type": "e", "payload": {"license_said": "EL1"}},
                          {"e": {"application_id": "license_said"}})


def test_a_state_fold_reads_a_minted_property_as_ordinary_payload():
    defn = FoldDefinition.aggregate(
        fold={"e": [{"op": "append", "target": "ids", "value": "event.application_id"}]},
        initial_state={"ids": []},
        mints={"e": {"application_id": "credential_said"}},
    )
    state = fold(defn, [{"type": "e", "credential_said": "EApp1", "payload": {}}],
                 cel_env("aggregate_fold"))
    assert state == {"ids": ["EApp1"]}


def test_a_minted_event_and_a_carried_event_land_on_the_same_row():
    """FINDING 37, reduced to two events -- the reason the ruling exists.
    `application_received` mints `application_id` from the SAID of the
    credential its emission just issued; `license_granted`, produced by a
    different command, carries the same name forward. One row -- which only
    holds if routing happens after materialization."""
    defn = FoldDefinition.collection_projection(
        fold={
            "application_received": [{"op": "upsert", "set": {
                "application_id": "event.application_id", "status": "'received'"}}],
            "license_granted": [{"op": "update", "set": {"status": "'licensed'"}}],
        },
        primary_key="application_id",
        mints={"application_received": {"application_id": "credential_said"}},
    )
    rows = fold(defn, [
        {"type": "application_received", "credential_said": "EApp1", "payload": {}},
        {"type": "license_granted", "payload": {"application_id": "EApp1"}},
    ], cel_env("projection_fold"))
    assert rows == {"EApp1": {"application_id": "EApp1", "status": "licensed"}}


def test_try_append_materializes_before_the_invariant_reads_the_event():
    """Invariants run between fold and append over `{state, event}`; the mint
    has to be in the payload by then or the guard reads an undefined field."""
    agg = FoldDefinition.aggregate(
        fold={"e": [{"op": "append", "target": "seen", "value": "event.application_id"}]},
        initial_state={"seen": []},
        invariants=[{"rule_ref": "never_twice", "expression":
                     "size(state.seen.filter(s, s == event.application_id)) <= 1"}],
        mints={"e": {"application_id": "credential_said"}},
    )
    env, inv = cel_env("aggregate_fold"), cel_env("invariant")
    proposed = {"type": "e", "credential_said": "EApp1", "payload": {}}
    candidate = try_append(agg, {"seen": []}, proposed, env, inv)
    assert candidate == {"seen": ["EApp1"]}
    with pytest.raises(InvariantViolation):
        try_append(agg, candidate, proposed, env, inv)


# --- _route_key: exactly the checker's `field`, and nothing else (decision D1) ------------

def test_route_key_reads_a_bare_field_name():
    assert _route_key("application_id",
                      {"type": "e", "payload": {"application_id": "A1"}}) == "A1"


def test_route_key_reads_an_envelope_name_that_appears_in_no_payload():
    """The migrated carrier bundle keys `my_active_licenses` on
    `credential_said`; reading `event["payload"]` made that unroutable while
    `micro-app check` -- which knows the envelope names -- passed it."""
    assert _route_key("credential_said",
                      {"type": "e", "credential_said": "EC1", "payload": {}}) == "EC1"


def test_route_key_accepts_the_event_dot_spelling():
    assert _route_key("event.application_id",
                      {"type": "e", "payload": {"application_id": "A1"}}) == "A1"


@pytest.mark.parametrize("selector", [
    "'license_registry'",                 # constant -- no longer a routable form
    '"license_registry"',
    "event.a + event.b",                  # concatenation
    "event.credential.said",              # dotted path
    "has(event.x) ? event.x : 'z'",       # conditional
])
def test_route_key_refuses_anything_that_is_not_a_bare_field(selector):
    with pytest.raises(ValueError, match="bare field name"):
        _route_key(selector, {"type": "e", "payload": {"a": "1", "b": "2"}})


def test_a_routed_field_the_event_omits_is_still_a_keyerror():
    """An event that cannot be routed is un-appendable, and the caller must
    see that rather than a phantom row."""
    with pytest.raises(KeyError):
        _route_key("application_id", {"type": "e", "payload": {}})


#: The reference measured these edges in a fix round that aligned its router
#: with `micro-app check`'s `classify_selector`: the checker STRIPS before it
#: classifies (so `"k "` is a check-green template the router must not refuse
#: at fold time -- the dangerous direction), and the checker's identifier class
#: is ASCII (so `café`, which a Unicode-aware `\w` would route, must be
#: refused). This repo has no `classify_selector` to cross-check against, so
#: the reference's verdicts are transcribed as an executable table: name to
#: route on, or `None` meaning refused.
_SELECTOR_EDGES = [
    ("k", "k"), ("_k9", "_k9"), ("K", "K"), ("application_id", "application_id"),
    ("k ", "k"), (" k", "k"), ("  k  ", "k"), ("k\t", "k"), ("k\n", "k"),
    ("event.k", "k"), ("event.k ", "k"), (" event.k", "k"), ("event", "event"),
    ("café", None), ("naïve_id", None),
    ("'const'", None), ('"const"', None),
    ("event.a + event.b", None), ("event.credential.said", None),
    ("2k", None), ("k-1", None), ("k.j", None), ("event.", None),
    ("", None), ("   ", None), (None, None), (123, None),
]


@pytest.mark.parametrize("selector,routes_on", _SELECTOR_EDGES)
def test_route_key_matches_the_references_selector_verdicts(selector, routes_on):
    event = {"type": "e", "payload": {"k": "K1", "application_id": "A1",
                                      "_k9": "N1", "K": "U1", "event": "E1",
                                      "café": "C1", "naïve_id": "N2"}}
    if routes_on is None:
        with pytest.raises(ValueError):
            _route_key(selector, event)
    else:
        assert _route_key(selector, event) == event["payload"][routes_on], selector


# --- where `mints` come from: the template-doc adapters ----------------------------------

_MINT_TPL = {
    "aggregates": [{
        "id": "reg",
        "initial_state": {"ids": []},
        "events": {
            "application_received": {"payload_schema": {
                "properties": {"application_id": {"type": "string",
                                                  "from": "credential_said"},
                               "jurisdiction": {"type": "string"}},
                "required": ["application_id", "jurisdiction"],
                "additionalProperties": False}},
            "license_granted": {"payload_schema": {
                "properties": {"application_id": {"type": "string"}},
                "required": ["application_id"], "additionalProperties": False}},
        },
        "fold": {"application_received": [], "license_granted": []},
    }],
    "projections": [
        {"id": "board", "shape": "collection", "primary_key": "application_id",
         "source_events": ["application_received", "license_granted"], "fold": {}},
        {"id": "summary", "shape": "object", "initial_state": {"c": 0},
         "source_events": ["application_received"], "fold": {}},
    ],
}


def test_an_aggregate_reads_mints_from_its_own_events_declaration():
    defn = fold_definition_from_aggregate(_MINT_TPL["aggregates"][0], rules_by_id={})
    assert defn.mints == {"application_received": {"application_id": "credential_said"}}


@pytest.mark.parametrize("proj_id", ["board", "summary"])
def test_a_projection_reads_mints_from_the_declaring_aggregates(proj_id):
    """`from` is a property of the event schema, never of the projection
    (§6.5), so both shapes take it from the aggregates via the whole doc."""
    proj = next(p for p in _MINT_TPL["projections"] if p["id"] == proj_id)
    defn = fold_definition_from_projection(proj, doc=_MINT_TPL)
    assert defn.mints == {"application_received": {"application_id": "credential_said"}}


def test_a_projection_built_without_the_doc_mints_nothing():
    """The honest answer when the caller has only the entry -- and the reason
    the Designer's panel hands the whole document down."""
    proj = _MINT_TPL["projections"][0]
    assert fold_definition_from_projection(proj).mints == {}


def test_two_aggregates_disagreeing_on_a_slot_mint_nothing():
    """A projection may only rely on what EVERY declaring aggregate
    guarantees. Two aggregates minting one property from different slots
    guarantee nothing, so the property is visibly absent rather than silently
    one side's guess."""
    import copy as _copy
    tpl = _copy.deepcopy(_MINT_TPL)
    other = _copy.deepcopy(tpl["aggregates"][0])
    other["id"] = "other"
    (other["events"]["application_received"]["payload_schema"]
        ["properties"]["application_id"]["from"]) = "source_aid"
    tpl["aggregates"].append(other)
    assert fold_definition_from_projection(tpl["projections"][0], doc=tpl).mints == {}


def test_a_garbage_aggregate_the_projection_never_sources_does_not_break_its_build():
    """The cross-unit read is total: the Designer renders one unit's vectors
    while a sibling the user is mid-edit on is malformed. An aggregate that
    declares nothing for this event type contributes nothing -- it must not
    raise out of, or empty, an unrelated projection's mints."""
    import copy as _copy
    tpl = _copy.deepcopy(_MINT_TPL)
    tpl["aggregates"].append({"id": "broken", "events": "oops"})
    tpl["aggregates"].append({"id": "alsobroken"})
    assert fold_definition_from_projection(tpl["projections"][0], doc=tpl).mints == {
        "application_received": {"application_id": "credential_said"}}


def test_a_garbage_declaration_of_a_sourced_event_type_mints_nothing():
    """A second declarer whose `payload_schema` is unreadable guarantees
    nothing, so the intersection honestly collapses -- absent, not raised, and
    not the other side's guess."""
    import copy as _copy
    tpl = _copy.deepcopy(_MINT_TPL)
    tpl["aggregates"].append({"id": "broken",
                              "events": {"application_received": "oops"}})
    assert fold_definition_from_projection(tpl["projections"][0], doc=tpl).mints == {}


# --- through the vector runner: a vector never declares the minted property ---------------

def _mint_vector_template():
    return {
        "aggregates": [{
            "id": "reg",
            "initial_state": {"ids": []},
            "events": {"application_received": {"payload_schema": {
                "properties": {"application_id": {"type": "string",
                                                  "from": "credential_said"}},
                "required": ["application_id"], "additionalProperties": False}}},
            "fold": {"application_received": [
                {"op": "append", "target": "ids", "value": "event.application_id"}]},
            "test_vectors": [{
                "name": "the mint is what the fold sees",
                "events": [{"type": "application_received",
                            "credential_said": "EApp1", "payload": {}}],
                "expected": {"ids": ["EApp1"]},
            }],
        }],
        "projections": [{
            "id": "board", "shape": "collection", "primary_key": "application_id",
            "source_events": ["application_received"],
            "fold": {"application_received": [{"op": "upsert", "set": {
                "application_id": "event.application_id"}}]},
            "test_vectors": [{
                "name": "the minted key routes the row",
                "events": [{"type": "application_received",
                            "credential_said": "EApp1", "payload": {}}],
                "expected": {"rows": {"EApp1": {"application_id": "EApp1"}}},
            }],
        }],
    }


def test_run_test_vectors_materializes_a_mint_for_an_aggregate_vector():
    doc = _mint_vector_template()
    outcomes = run_test_vectors(doc["aggregates"][0], entry_kind="aggregate", doc=doc)
    assert [(o.name, o.passed, o.error) for o in outcomes] == [
        ("the mint is what the fold sees", True, None)]


def test_run_test_vectors_materializes_a_mint_a_projection_never_declares():
    """The projection half is the one that can silently regress: the mint
    lives in `aggregates[]`, which the projection entry knows nothing about."""
    doc = _mint_vector_template()
    outcomes = run_test_vectors(doc["projections"][0], entry_kind="projection", doc=doc)
    assert [(o.name, o.passed, o.error) for o in outcomes] == [
        ("the minted key routes the row", True, None)]
