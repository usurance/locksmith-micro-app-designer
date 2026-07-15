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
    FoldDefinition,
    InvariantViolation,
    cel_env,
    fold,
    fold_definition_from_aggregate,
    fold_definition_from_projection,
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
