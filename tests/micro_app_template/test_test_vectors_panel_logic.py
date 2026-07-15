# -*- encoding: utf-8 -*-
"""Pure-logic tests for the vector-runner panel (editors/test_vectors.py).

Per Stage 5 repo practice: the existing editor pages (aggregates.py,
projections.py, rules.py) ship with no dedicated unit tests today -- they
are display-only Qt panes exercised only by the integration smoke test
(tests/integration/test_designer_smoke.py). `editors/test_vectors.py`
follows the same pattern: the Qt widget class is thin and untested here;
what *is* tested is the pure model<->view-model mapping it's built on
(`summarize_outcomes`, `row_view_models`), which needs no QApplication and
carries the actual logic (pass/fail summarization, actual/expected
JSON rendering) worth regressing against.
"""
from __future__ import annotations

from locksmith_micro_app_designer.editors.test_vectors import (
    row_view_models,
    summarize_outcomes,
)
from locksmith_micro_app_designer.template.fold_runner import VectorOutcome


def test_summarize_outcomes_all_passing():
    outcomes = [
        VectorOutcome(name="a", kind="fold", passed=True),
        VectorOutcome(name="b", kind="invariant", passed=True),
    ]
    assert summarize_outcomes(outcomes) == "2/2 vectors passing"


def test_summarize_outcomes_some_failing():
    outcomes = [
        VectorOutcome(name="a", kind="fold", passed=True),
        VectorOutcome(name="b", kind="fold", passed=False),
    ]
    assert summarize_outcomes(outcomes) == "1/2 vectors passing"


def test_summarize_outcomes_empty():
    assert summarize_outcomes([]) == "no test_vectors declared"


def test_row_view_models_runs_aggregate_entry():
    entry = {
        "id": "class_roster",
        "fold": {
            "class_scheduled": [
                {"op": "set", "target": "capacity", "value": "event.capacity"}
            ],
        },
        "initial_state": {"capacity": 0},
        "invariants": [],
        "test_vectors": [
            {
                "name": "sets capacity",
                "events": [{"type": "class_scheduled", "payload": {"capacity": 5}}],
                "expected": {"capacity": 5},
            },
        ],
    }
    rows = row_view_models(entry, entry_kind="aggregate", doc={"rules": []})
    assert len(rows) == 1
    assert rows[0].name == "sets capacity"
    assert rows[0].passed is True
    assert rows[0].actual == {"capacity": 5}


def test_row_view_models_reports_failure_with_actual_and_expected():
    entry = {
        "id": "class_roster",
        "fold": {
            "class_scheduled": [
                {"op": "set", "target": "capacity", "value": "event.capacity"}
            ],
        },
        "initial_state": {"capacity": 0},
        "invariants": [],
        "test_vectors": [
            {
                "name": "wrong expectation",
                "events": [{"type": "class_scheduled", "payload": {"capacity": 5}}],
                "expected": {"capacity": 999},
            },
        ],
    }
    rows = row_view_models(entry, entry_kind="aggregate", doc={"rules": []})
    assert len(rows) == 1
    assert rows[0].passed is False
    assert rows[0].actual == {"capacity": 5}
    assert rows[0].expected == {"capacity": 999}


def test_row_view_models_empty_when_no_vectors():
    entry = {"id": "x", "fold": {}, "initial_state": {}}
    assert row_view_models(entry, entry_kind="aggregate", doc={"rules": []}) == []
