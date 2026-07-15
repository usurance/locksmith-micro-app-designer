# -*- encoding: utf-8 -*-
"""Editor-side shared helpers reused across per-primitive editor pages."""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)


_ROLE_KIND_COLORS: dict[str, str] = {
    "government": "#0ABFB0",
    "organization": "#0ABFB0",
    "individual": "#D97757",
    "system": "#888888",
    "device": "#888888",
    "agent": "#A36AE6",
}


def kind_color_for(role_kind: str) -> str:
    """CSS hex color for a role kind. Falls back to neutral grey."""
    return _ROLE_KIND_COLORS.get(role_kind, "#888888")


def make_section(title: str) -> QFrame:
    """A right-pane section: uppercase teal label + content, no card chrome.

    Earlier iterations wrapped every section in its own white-bordered
    card, which produced a "every text in a grey box" effect (8 boxes
    stacked vertically per editor). The v1 mocks instead use flat
    sections — a small uppercase teal section header with content
    flowing beneath on the page's shared surface. This shape matches.

    The descendant-selector stylesheet on QLineEdit/QPlainTextEdit/
    QComboBox remains: macOS Qt paints the default field background
    dark unless we force light, so input widgets inside the section
    still need the explicit white-fill rule. Caught via the dev-control
    screenshot loop on the Commands editor.
    """
    frame = QFrame()
    frame.setObjectName("editor-section")
    frame.setStyleSheet(
        "#editor-section QLineEdit, #editor-section QPlainTextEdit, "
        "#editor-section QComboBox{"
        "background:#fff;color:#1A1C20;border:1px solid #e0e3ea;"
        "border-radius:4px;padding:6px 8px;}"
        "#editor-section QLineEdit:read-only, "
        "#editor-section QPlainTextEdit:read-only{"
        "background:#f6f7f9;color:#444;border:0;}"
    )
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(0, 0, 0, 4)
    lay.setSpacing(6)
    title_label = QLabel(title.upper())
    title_label.setStyleSheet(
        "font-size:10px;font-weight:600;color:#0ABFB0;"
        "letter-spacing:0.5px;background:transparent;"
    )
    lay.addWidget(title_label)
    return frame


# --- fold handler-map rendering (M-Task 5: aggregates.py + projections.py share this) --
# Accepted spec `2026-07-10-cel-declarative-aggregates-and-projections.md` §5 (the
# shared `fold` primitive) and §8 (the op vocabulary). A `fold` map is keyed by event
# type; each handler is either an op-list (§8.1 object-state ops / §8.2 collection ops)
# or a raw `{"expression": "<CEL>"}` reducer. Both aggregates.py (object-state ops
# against `state_schema`) and projections.py (collection ops against `row_schema`, or
# object-state ops for a `shape: "object"` projection's `state_schema`) render the same
# shape, so the logic lives here once.

_OP_FIELD_ORDER: tuple[str, ...] = (
    "target", "value", "where", "by", "from", "to", "match", "set",
)


def _schema_top_level_fields(schema: dict[str, Any] | None) -> set[str] | None:
    """Top-level property names declared by a JSON-Schema object, or `None`
    if the schema doesn't declare `properties` at all (nothing to validate
    against -- silence, not a false positive)."""
    if not isinstance(schema, dict):
        return None
    props = schema.get("properties")
    if not isinstance(props, dict):
        return None
    return set(props.keys())


def validate_fold_target_paths(
    fold_map: dict[str, Any], schema: dict[str, Any] | None,
) -> dict[str, list[str]]:
    """For each event-type handler in `fold_map`, return warnings for any
    op's `target` (or `set` field names, for collection ops) whose leading
    path segment isn't declared in `schema`'s top-level `properties`. Empty
    dict values mean "no warnings for that event type"; event types with no
    warnings at all are omitted from the returned dict's keys entirely only
    when `fold_map` itself has no handler for them (defensive; every present
    handler yields a — possibly empty — list).

    Raw `{"expression": ...}` reducers are not path-checked here (there is
    no static `target` to check for a raw reducer; the CEL compiler is the
    one that would type-check its output shape).
    """
    fields = _schema_top_level_fields(schema)
    warnings: dict[str, list[str]] = {}
    if fields is None:
        return warnings
    for event_type, handler in (fold_map or {}).items():
        if isinstance(handler, dict) and "expression" in handler:
            continue
        bad: list[str] = []
        for i, op in enumerate(handler or []):
            if not isinstance(op, dict):
                continue
            target = op.get("target")
            if isinstance(target, str):
                top = target.split(".")[0]
                if top and top not in fields:
                    bad.append(f"op[{i}] ({op.get('op')}): target {target!r} not in schema")
            set_map = op.get("set")
            if isinstance(set_map, dict):
                for field_name in set_map:
                    if field_name not in fields:
                        bad.append(
                            f"op[{i}] ({op.get('op')}): set field {field_name!r} not in schema"
                        )
        if bad:
            warnings[event_type] = bad
    return warnings


def _op_summary_row(op: dict[str, Any]) -> QWidget:
    row = QFrame()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 1, 0, 1)
    lay.setSpacing(6)
    op_chip = QLabel(str(op.get("op", "?")))
    op_chip.setStyleSheet(
        "background:#fdf3e7;color:#a5641a;border-radius:8px;"
        "padding:1px 7px;font-size:10px;font-weight:600;"
    )
    lay.addWidget(op_chip)
    for field_name in _OP_FIELD_ORDER:
        if field_name not in op:
            continue
        value = op[field_name]
        text = ", ".join(f"{k}: {v}" for k, v in value.items()) if isinstance(value, dict) else str(value)
        field_lbl = QLabel(f"{field_name}={text}")
        field_lbl.setStyleSheet("color:#444;font-size:11px;font-family:monospace;")
        lay.addWidget(field_lbl)
    lay.addStretch(1)
    return row


def build_fold_map_widget(
    fold_map: dict[str, Any], *, schema: dict[str, Any] | None = None,
) -> QWidget:
    """Render a `fold` handler map: one block per event type, each either an
    op-list (rendered as op-summary rows) or a raw reducer (rendered as a
    `DarkCodeBlock`). Op `target`/`set` fields that don't resolve against
    `schema` are flagged inline."""
    from locksmith_micro_app_designer.widgets.dark_code_block import DarkCodeBlock

    warnings = validate_fold_target_paths(fold_map, schema)

    host = QWidget()
    outer = QVBoxLayout(host)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(10)

    if not fold_map:
        empty = QLabel("No fold handlers declared.")
        empty.setStyleSheet("color:#aaa;font-style:italic;font-size:11px;")
        outer.addWidget(empty)
        return host

    for event_type, handler in fold_map.items():
        block = QFrame()
        block_lay = QVBoxLayout(block)
        block_lay.setContentsMargins(0, 0, 0, 0)
        block_lay.setSpacing(4)

        head = QHBoxLayout()
        chip = QLabel(event_type)
        chip.setStyleSheet(
            "background:#f3edfb;color:#A36AE6;border-radius:9px;"
            "padding:2px 9px;font-size:11px;font-weight:600;font-family:monospace;"
        )
        head.addWidget(chip)
        if isinstance(handler, dict) and "expression" in handler:
            kind_chip = QLabel("raw reducer")
        else:
            kind_chip = QLabel(f"{len(handler or [])} op{'s' if len(handler or []) != 1 else ''}")
        kind_chip.setStyleSheet("color:#888;font-size:10px;")
        head.addWidget(kind_chip)
        head.addStretch(1)
        block_lay.addLayout(head)

        if isinstance(handler, dict) and "expression" in handler:
            block_lay.addWidget(DarkCodeBlock(handler.get("expression", "")))
        else:
            for op in handler or []:
                if isinstance(op, dict):
                    block_lay.addWidget(_op_summary_row(op))

        for msg in warnings.get(event_type, []):
            warn_lbl = QLabel(f"⚠ {msg}")
            warn_lbl.setStyleSheet("color:#a5641a;font-size:10px;")
            warn_lbl.setWordWrap(True)
            block_lay.addWidget(warn_lbl)

        outer.addWidget(block)

    return host
