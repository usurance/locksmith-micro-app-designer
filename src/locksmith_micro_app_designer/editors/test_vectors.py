# -*- encoding: utf-8 -*-
"""TestVectorsPanel: the vector runner — THE DECISION §5's Designer-plugin
row ("op forms, vector runner").

Wired into both `aggregates.py` and `projections.py`'s section panes: lists
a definition's `test_vectors[]`, runs each vector in-process against the
self-contained `cel-python`-backed fold engine
(`template/fold_runner.py`), and shows pass/fail with the actual vs.
expected folded state/row on failure.

Display-only, consistent with the rest of the editor surfaces in this
repo (`RuleChipStrip`, `SourceEventChipStrip`, … are all "Phase 3b ships
this display-only"): there is no vector *authoring* UI here yet, only
running the vectors the template document already declares. The pure
model<->view-model mapping (`row_view_models`, `summarize_outcomes`) is
Qt-free and unit-tested directly (see
tests/micro_app_template/test_test_vectors_panel_logic.py); the widget
class itself is exercised only by the integration smoke test, matching
how the sibling editor panes are tested today.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from locksmith_micro_app_designer.template.fold_runner import (
    VectorOutcome, run_test_vectors,
)


def row_view_models(
    entry: dict[str, Any], *, entry_kind: str, doc: Optional[dict[str, Any]] = None,
) -> list[VectorOutcome]:
    """Run every `test_vectors[]` entry on `entry` and return one
    `VectorOutcome` per vector. Thin wrapper over
    `fold_runner.run_test_vectors` — the seam the panel renders from and
    the seam these tests exercise without touching Qt."""
    return run_test_vectors(entry, entry_kind=entry_kind, doc=doc)


def summarize_outcomes(outcomes: list[VectorOutcome]) -> str:
    """One-line pass/fail summary for the panel header."""
    if not outcomes:
        return "no test_vectors declared"
    passed = sum(1 for o in outcomes if o.passed)
    return f"{passed}/{len(outcomes)} vectors passing"


def _pretty(value: Any) -> str:
    if value is None:
        return "null"
    return json.dumps(value, indent=2, sort_keys=True)


class _VectorRow(QFrame):
    def __init__(self, outcome: VectorOutcome, parent=None):
        super().__init__(parent=parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(8)
        glyph = "✓" if outcome.passed else "✗"
        color = "#2a8a4a" if outcome.passed else "#c0392b"
        status = QLabel(glyph)
        status.setStyleSheet(f"color:{color};font-weight:700;")
        head.addWidget(status)
        name = QLabel(outcome.name)
        name.setStyleSheet("color:#1A1C20;font-weight:600;font-size:12px;")
        head.addWidget(name)
        kind_chip = QLabel(outcome.kind)
        kind_chip.setStyleSheet(
            "background:#f0f2f5;color:#666;border-radius:8px;"
            "padding:1px 7px;font-size:10px;"
        )
        head.addWidget(kind_chip)
        head.addStretch(1)
        lay.addLayout(head)

        if not outcome.passed:
            from locksmith_micro_app_designer.widgets.dark_code_block import (
                DarkCodeBlock,
            )
            if outcome.error:
                err = QLabel(f"error: {outcome.error}")
                err.setStyleSheet("color:#c0392b;font-size:11px;")
                err.setWordWrap(True)
                lay.addWidget(err)
            elif outcome.kind == "invariant":
                detail = QLabel(
                    f"expected rejection by {outcome.expected!r}, "
                    f"got {outcome.rejected_by!r}"
                )
                detail.setStyleSheet("color:#c0392b;font-size:11px;")
                detail.setWordWrap(True)
                lay.addWidget(detail)
            else:
                diff_row = QHBoxLayout()
                diff_row.setSpacing(8)
                actual_col = QVBoxLayout()
                actual_lbl = QLabel("ACTUAL")
                actual_lbl.setStyleSheet(
                    "color:#888;font-size:9px;font-weight:600;"
                )
                actual_col.addWidget(actual_lbl)
                actual_col.addWidget(DarkCodeBlock(_pretty(outcome.actual)))
                expected_col = QVBoxLayout()
                expected_lbl = QLabel("EXPECTED")
                expected_lbl.setStyleSheet(
                    "color:#888;font-size:9px;font-weight:600;"
                )
                expected_col.addWidget(expected_lbl)
                expected_col.addWidget(DarkCodeBlock(_pretty(outcome.expected)))
                diff_row.addLayout(actual_col)
                diff_row.addLayout(expected_col)
                lay.addLayout(diff_row)


class TestVectorsPanel(QWidget):
    """A section wired into the aggregates/projections section panes."""

    navigated = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._entry: dict[str, Any] = {}
        self._entry_kind: str = "aggregate"
        self._doc: Optional[dict[str, Any]] = None
        self._outcomes: list[VectorOutcome] = []
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        header = QHBoxLayout()
        self._summary_label = QLabel("no test_vectors declared")
        self._summary_label.setStyleSheet("color:#444;font-size:11px;")
        header.addWidget(self._summary_label)
        header.addStretch(1)
        self._rerun_button = QPushButton("↻ Re-run")
        self._rerun_button.setFlat(True)
        self._rerun_button.setStyleSheet(
            "QPushButton{color:#0ABFB0;background:transparent;border:0;"
            "padding:2px 9px;font-size:11px;font-weight:600;}"
            "QPushButton:hover{color:#1A1C20;}"
        )
        self._rerun_button.clicked.connect(self._rerun)
        header.addWidget(self._rerun_button)
        lay.addLayout(header)

        self._rows_holder = QVBoxLayout()
        lay.addLayout(self._rows_holder)

    def set_entry(
        self, entry: dict[str, Any], *, entry_kind: str,
        doc: Optional[dict[str, Any]] = None,
    ) -> None:
        self._entry = entry
        self._entry_kind = entry_kind
        self._doc = doc
        self._rerun()

    def _rerun(self) -> None:
        self._outcomes = row_view_models(
            self._entry, entry_kind=self._entry_kind, doc=self._doc,
        )
        self._summary_label.setText(summarize_outcomes(self._outcomes))

        while self._rows_holder.count():
            item = self._rows_holder.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        for outcome in self._outcomes:
            self._rows_holder.addWidget(_VectorRow(outcome))

    def outcomes(self) -> list[VectorOutcome]:
        return list(self._outcomes)

    def all_passing(self) -> bool:
        return all(o.passed for o in self._outcomes)

    def text_summary(self) -> str:
        parts = [summarize_outcomes(self._outcomes)]
        for o in self._outcomes:
            parts.append(o.name)
        return " ".join(parts)
