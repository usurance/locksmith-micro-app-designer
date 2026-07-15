# -*- encoding: utf-8 -*-
"""AggregatesEditorPage: 'I track …' surface.

V1 right-pane layout: header + boundary (inception-event + instance-key) +
log-scope chip + state-schema preview + initial-state preview + fold
handler-map (op-lists / raw reducers, per accepted spec §5/§8) +
invariants RuleChipStrip + test-vectors runner (TestVectorsPanel) + Used by.
"""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget,
)

from locksmith_micro_app_designer.crossref import CrossRefIndex
from locksmith_micro_app_designer.editors._shared import (
    build_fold_map_widget, kind_color_for, make_section,
)
from locksmith_micro_app_designer.editors.test_vectors import TestVectorsPanel
from locksmith_micro_app_designer.model import TemplateModel
from locksmith_micro_app_designer.widgets.cross_ref_chip import CrossRefChipStrip
from locksmith_micro_app_designer.widgets.kind_rail import RailItem
from locksmith_micro_app_designer.widgets.primitive_editor_shell import (
    PrimitiveEditorShell,
)


def _aggregate_subtitle(agg: dict) -> str:
    parts: list[str] = []
    scope = agg.get("log_scope")
    if scope:
        parts.append(f"{scope} log")
    invs = agg.get("invariants") or []
    parts.append(f"{len(invs)} invariant{'s' if len(invs) != 1 else ''}")
    return " · ".join(parts)


class _AggregateSectionPane(QWidget):
    def __init__(self, crossrefs: CrossRefIndex, model: TemplateModel | None = None,
                 parent=None):
        super().__init__(parent=parent)
        self._crossrefs = crossrefs
        self._model = model
        self.setObjectName("designer-section-pane")
        self.setStyleSheet(
            "#designer-section-pane QLabel{background:transparent;}"
        )
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        # Header.
        self._header_frame = QFrame()
        h = QVBoxLayout(self._header_frame)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self._name_label = QLabel("")
        self._name_label.setStyleSheet(
            "font-size:16px;font-weight:600;color:#1A1C20;"
        )
        title_row.addWidget(self._name_label)
        self._id_chip = QLabel("")
        self._id_chip.setStyleSheet(
            "color:#666;background:#f6f7f9;font-family:monospace;"
            "border-radius:6px;padding:2px 8px;font-size:10px;"
        )
        title_row.addWidget(self._id_chip)
        title_row.addStretch(1)
        h.addLayout(title_row)
        self._description_label = QLabel("")
        self._description_label.setStyleSheet("color:#444;font-size:12px;")
        self._description_label.setWordWrap(True)
        h.addWidget(self._description_label)
        lay.addWidget(self._header_frame)

        # Boundary (inception event + instance key) + log scope side-by-side.
        # `boundary` replaced the bare top-level `inception_event_type` field
        # (accepted spec §6.1): the aggregate's consistency-boundary routing
        # is now `{ inception_event_type, instance_key }` as one unit.
        ic_row = QHBoxLayout()
        ic_row.setSpacing(14)
        self._boundary_section = make_section("Boundary")
        boundary_lay = QVBoxLayout()
        boundary_lay.setSpacing(4)
        inception_row = QHBoxLayout()
        inception_row.setSpacing(6)
        inception_lbl = QLabel("inception event:")
        inception_lbl.setStyleSheet("color:#666;font-size:10px;")
        inception_row.addWidget(inception_lbl)
        self._inception_chip = QLabel("(unset)")
        self._inception_chip.setStyleSheet(
            "background:#f3edfb;color:#A36AE6;border-radius:9px;"
            "padding:2px 9px;font-size:11px;font-weight:600;"
            "font-family:monospace;"
        )
        inception_row.addWidget(self._inception_chip)
        inception_row.addStretch(1)
        boundary_lay.addLayout(inception_row)
        instance_key_row = QHBoxLayout()
        instance_key_row.setSpacing(6)
        instance_key_lbl = QLabel("instance key:")
        instance_key_lbl.setStyleSheet("color:#666;font-size:10px;")
        instance_key_row.addWidget(instance_key_lbl)
        self._instance_key_value = QLabel("(unset)")
        self._instance_key_value.setStyleSheet(
            "color:#1A1C20;font-size:11px;font-family:monospace;"
        )
        instance_key_row.addWidget(self._instance_key_value)
        instance_key_row.addStretch(1)
        boundary_lay.addLayout(instance_key_row)
        self._boundary_section.layout().addLayout(boundary_lay)
        ic_row.addWidget(self._boundary_section, 1)
        self._scope_section = make_section("Log scope")
        self._scope_chip = QLabel("(unset)")
        self._scope_chip.setStyleSheet(
            "background:#e8f4f4;color:#0a8a82;border-radius:9px;"
            "padding:2px 9px;font-size:11px;font-weight:600;"
        )
        self._scope_section.layout().addWidget(self._scope_chip)
        ic_row.addWidget(self._scope_section, 1)
        lay.addLayout(ic_row)

        # State schema preview.
        self._state_schema_section = make_section("State schema")
        self._state_schema_view = QPlainTextEdit()
        self._state_schema_view.setReadOnly(True)
        self._state_schema_view.setFrameShape(QFrame.NoFrame)
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(10)
        self._state_schema_view.setFont(mono)
        self._state_schema_view.setFixedHeight(80)
        self._state_schema_section.layout().addWidget(self._state_schema_view)
        lay.addWidget(self._state_schema_section)

        # Initial state preview.
        self._initial_section = make_section("Initial state")
        self._initial_view = QPlainTextEdit()
        self._initial_view.setReadOnly(True)
        self._initial_view.setFrameShape(QFrame.NoFrame)
        self._initial_view.setFont(mono)
        self._initial_view.setFixedHeight(50)
        self._initial_section.layout().addWidget(self._initial_view)
        lay.addWidget(self._initial_section)

        # Fold — the shared fold primitive (accepted spec §5): a per-event-type
        # handler map, each handler an op-list (§8.1) or a raw CEL reducer.
        self._fold_section = make_section("Fold")
        self._fold_holder = QVBoxLayout()
        self._fold_section.layout().addLayout(self._fold_holder)
        cheat = QLabel("↗ CEL/1.0 cheat-sheet · test expression")
        cheat.setStyleSheet("color:#0ABFB0;font-size:10px;")
        self._fold_section.layout().addWidget(cheat)
        lay.addWidget(self._fold_section)

        # Invariants.
        self._inv_section = make_section("Invariants")
        self._inv_holder = QVBoxLayout()
        self._inv_section.layout().addLayout(self._inv_holder)
        lay.addWidget(self._inv_section)

        # Test vectors — the vector runner (THE DECISION §5's Designer-plugin
        # row: "op forms, vector runner").
        self._vectors_section = make_section("Test vectors")
        self._vectors_panel = TestVectorsPanel()
        self._vectors_section.layout().addWidget(self._vectors_panel)
        lay.addWidget(self._vectors_section)

        # Used by.
        self._used_by = make_section("Used by")
        self.chip_strip = CrossRefChipStrip()
        self._used_by.layout().addWidget(self.chip_strip)
        lay.addWidget(self._used_by)
        lay.addStretch(1)

    def set_entry(self, entry: dict[str, Any]) -> None:
        from locksmith_micro_app_designer.widgets.rule_chip_strip import (
            RuleChipStrip,
        )

        self._name_label.setText(entry.get("name") or entry.get("id") or "(unnamed)")
        self._id_chip.setText(entry.get("id", ""))
        self._description_label.setText(entry.get("description") or "")
        boundary = entry.get("boundary") or {}
        self._inception_chip.setText(
            boundary.get("inception_event_type") or "(unset)"
        )
        self._instance_key_value.setText(boundary.get("instance_key") or "(unset)")
        scope = entry.get("log_scope")
        self._scope_chip.setText(scope or "(unset)")

        state_schema = entry.get("state_schema") or {}
        self._state_schema_view.setPlainText(
            json.dumps(state_schema, indent=2, sort_keys=True)
        )
        self._initial_view.setPlainText(
            json.dumps(entry.get("initial_state"), indent=2, sort_keys=True)
        )

        def _clear(layout) -> None:
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget() if item is not None else None
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()

        _clear(self._fold_holder)
        self._fold_holder.addWidget(
            build_fold_map_widget(entry.get("fold") or {}, schema=state_schema)
        )

        _clear(self._inv_holder)
        refs = [r.get("rule_ref", "") for r in (entry.get("invariants") or [])
                if r.get("rule_ref")]
        self._inv_holder.addWidget(RuleChipStrip(refs))

        doc = self._model.doc if self._model is not None else None
        self._vectors_panel.set_entry(entry, entry_kind="aggregate", doc=doc)

        self.chip_strip.set_refs(
            self._crossrefs.consumers_of(f"aggregate:{entry.get('id', '')}")
        )

    def text_summary(self) -> str:
        from locksmith_micro_app_designer.widgets.rule_chip_strip import (
            RuleChipStrip,
        )
        parts = [
            self._name_label.text(),
            self._id_chip.text(),
            self._description_label.text(),
            self._inception_chip.text(),
            self._instance_key_value.text(),
            self._scope_chip.text(),
            self._state_schema_view.toPlainText(),
            self._initial_view.toPlainText(),
            self._vectors_panel.text_summary(),
        ]
        for strip in self.findChildren(RuleChipStrip):
            parts.extend(strip.chip_texts())
        return " ".join(parts)


class AggregatesEditorPage(QWidget):
    navigated = Signal(str, str)

    def __init__(
        self,
        *,
        model: TemplateModel,
        crossrefs: CrossRefIndex,
        parent=None,
    ):
        super().__init__(parent=parent)
        self._model = model
        color = kind_color_for(model.doc.get("role", {}).get("kind", ""))
        items = [
            RailItem(
                id=a.get("id", ""),
                label=a.get("name") or a.get("id") or "(unnamed)",
                subtitle=_aggregate_subtitle(a),
                kind_color=color,
                has_errors=False,
            )
            for a in model.doc.get("aggregates", [])
        ]
        self.shell = PrimitiveEditorShell(
            surface_label="Aggregates",
            template_label=model.doc.get("header", {}).get(
                "display_name", "(untitled)"
            ),
            items=items,
            add_label="+ Add aggregate",
            item_count=len(items),
            role_label=model.doc.get("role", {}).get("id", ""),
            is_valid=True,
            parent=self,
        )
        self._pane = _AggregateSectionPane(crossrefs=crossrefs, model=model)
        if items:
            self._pane.set_entry(model.doc["aggregates"][0])
        self.shell.set_right_pane(self._pane)
        from locksmith_micro_app_designer.widgets.validation_panel import (
            ValidationPanel,
        )
        from locksmith_micro_app_designer.widgets.json_source_view import (
            JsonSourceView,
        )
        self._validation_panel = ValidationPanel()
        self._json_source_view = JsonSourceView()
        self.shell.set_side_panel(self._validation_panel)
        self.shell.set_bottom_panel(self._json_source_view)
        self.shell.item_selected.connect(self._on_select)
        self._pane.chip_strip.navigated.connect(self.navigated.emit)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.shell)

    def _on_select(self, item_id: str) -> None:
        for a in self._model.doc.get("aggregates", []):
            if a.get("id") == item_id:
                self._pane.set_entry(a)
                return

    def section_text(self) -> str:
        return self._pane.text_summary()
