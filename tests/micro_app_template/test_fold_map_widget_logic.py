# -*- encoding: utf-8 -*-
"""Pure-logic tests for editors/_shared.py's fold-map rendering helpers.

`validate_fold_target_paths` is the Qt-free logic behind the aggregates.py
and projections.py fold-handler-map sections' inline "field pickers
validated against state_schema" behavior (M-Task 5 Step 1/2). The widget
construction itself (`build_fold_map_widget`) needs a QApplication to
instantiate and is exercised via the integration smoke test, matching
existing repo practice for editor panes.
"""
from __future__ import annotations

from locksmith_micro_app_designer.editors._shared import validate_fold_target_paths


STATE_SCHEMA = {
    "type": "object",
    "properties": {
        "capacity": {"type": "integer"},
        "attendees": {"type": "array"},
    },
}


def test_no_warnings_when_all_targets_resolve():
    fold_map = {
        "class_scheduled": [
            {"op": "set", "target": "capacity", "value": "event.capacity"},
        ],
        "member_booked": [
            {"op": "append", "target": "attendees", "value": "event.member_id"},
        ],
    }
    assert validate_fold_target_paths(fold_map, STATE_SCHEMA) == {}


def test_warns_on_unknown_target_field():
    fold_map = {
        "class_scheduled": [
            {"op": "set", "target": "nonexistent_field", "value": "1"},
        ],
    }
    warnings = validate_fold_target_paths(fold_map, STATE_SCHEMA)
    assert "class_scheduled" in warnings
    assert "nonexistent_field" in warnings["class_scheduled"][0]


def test_dotted_target_path_checks_only_leading_segment():
    fold_map = {
        "e": [{"op": "set", "target": "capacity.nested", "value": "1"}],
    }
    # "capacity" is a declared top-level field; a nested path under it is
    # not flagged (this is a display-time hint, not a full nested-schema
    # walk).
    assert validate_fold_target_paths(fold_map, STATE_SCHEMA) == {}


def test_raw_reducer_handlers_are_not_path_checked():
    fold_map = {
        "e": {"expression": '{ "whatever": 1 }'},
    }
    assert validate_fold_target_paths(fold_map, STATE_SCHEMA) == {}


def test_no_schema_properties_means_no_warnings():
    fold_map = {
        "e": [{"op": "set", "target": "anything", "value": "1"}],
    }
    assert validate_fold_target_paths(fold_map, {}) == {}
    assert validate_fold_target_paths(fold_map, None) == {}


def test_collection_upsert_set_fields_checked_against_row_schema():
    row_schema = {"type": "object", "properties": {"class_id": {"type": "string"}}}
    fold_map = {
        "class_scheduled": [
            {"op": "upsert", "set": {"class_id": "event.class_id", "bogus": "1"}},
        ],
    }
    warnings = validate_fold_target_paths(fold_map, row_schema)
    assert "class_scheduled" in warnings
    assert any("bogus" in w for w in warnings["class_scheduled"])
