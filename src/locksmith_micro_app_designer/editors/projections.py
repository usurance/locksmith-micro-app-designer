# -*- encoding: utf-8 -*-
"""ProjectionsEditorPage: 'I see …' surface.

Right-pane sections (fold-model schema, accepted spec
`2026-07-10-cel-declarative-aggregates-and-projections.md` §7):
  Identity · Source events · Shape + primary key · Row/state schema ·
  Fold (op-lists / raw reducers, §5/§8) · Ordering (with a multi-source
  `source_seq` warning, §9.2) · Access (row filter + lens rule pickers) ·
  Display · Test vectors (vector runner) · Entry JSON · Used-by.

Canonical schema fields (post fold-model migration):
  Required: id, name, description, source_events[], fold.
  Also present: shape ("collection" default | "object"), primary_key +
    row_schema (collection) or state_schema + initial_state (object),
    ordering, on_unknown_event, test_vectors[].
  Optional: access.{row_filter_rule_ref, lens_rule_ref},
            display.{view_type, columns[], default_sort, empty_state}.

The old single `fold_expression` + `output_schema` shape (and the
`locksmith.uel.evaluator` "live preview" that never had a real evaluator
behind it) is retired: the fold handler map is now the shared primitive
(`editors/_shared.build_fold_map_widget`) and the "live preview" slot is
replaced by the vector runner (`editors/test_vectors.TestVectorsPanel`),
which actually executes the projection's `test_vectors[]` in-process.
"""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
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


def _ordering_warning(entry: dict[str, Any]) -> str | None:
    """Accepted spec §9.2: `ordering: "source_seq"` is "invalid if
    `source_events` resolve to more than one log". The template doesn't
    carry per-event-type log annotations at this layer, so this is a
    display-time heuristic, not a hard validation rule (that distinction
    belongs to `template/validate.py`): more than one distinct source
    event type under the default/explicit `source_seq` ordering is flagged
    for the author to double check, since multi-source-log projections are
    exactly the case `source_seq` cannot handle."""
    ordering = entry.get("ordering", "source_seq")
    source_events = entry.get("source_events") or []
    if ordering == "source_seq" and len(set(source_events)) > 1:
        return (
            "ordering: \"source_seq\" assumes a single source log — "
            "double check these source events don't span more than one "
            "log (KEL/TEL). Multi-source projections need "
            "\"datetime_said\" or \"commutative\" (accepted spec §9.2)."
        )
    return None


class _ProjectionSectionPane(QWidget):
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
        from locksmith_micro_app_designer.widgets.view_type_chip_picker import (
            ViewTypeChipPicker,
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        # Header block.
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
        outer.addWidget(self._header_frame)

        # Two-column body.
        body = QHBoxLayout()
        body.setSpacing(14)

        # LEFT column.
        left = QVBoxLayout()
        left.setSpacing(14)

        self._sources_section = make_section("Source events · fold from")
        self._sources_holder = QVBoxLayout()
        self._sources_section.layout().addLayout(self._sources_holder)
        left.addWidget(self._sources_section)

        # Shape + primary key (collection) side-by-side.
        shape_row = QHBoxLayout()
        shape_row.setSpacing(14)
        self._shape_section = make_section("Shape")
        self._shape_chip = QLabel("(unset)")
        self._shape_chip.setStyleSheet(
            "background:#f3edfb;color:#A36AE6;border-radius:9px;"
            "padding:2px 9px;font-size:11px;font-weight:600;"
        )
        self._shape_section.layout().addWidget(self._shape_chip)
        shape_row.addWidget(self._shape_section, 1)
        self._primary_key_section = make_section("Primary key")
        self._primary_key_value = QLabel("(n/a)")
        self._primary_key_value.setStyleSheet(
            "color:#1A1C20;font-size:11px;font-family:monospace;"
        )
        self._primary_key_section.layout().addWidget(self._primary_key_value)
        shape_row.addWidget(self._primary_key_section, 1)
        left.addLayout(shape_row)

        self._row_schema_section = make_section("Row schema · state schema")
        self._row_schema_holder = QVBoxLayout()
        self._row_schema_section.layout().addLayout(self._row_schema_holder)
        left.addWidget(self._row_schema_section)

        self._fold_section = make_section("Fold")
        self._fold_holder = QVBoxLayout()
        self._fold_section.layout().addLayout(self._fold_holder)
        cheat = QLabel("↗ CEL/1.0 cheat-sheet · test expression")
        cheat.setStyleSheet("color:#0ABFB0;font-size:10px;")
        self._fold_section.layout().addWidget(cheat)
        left.addWidget(self._fold_section)

        self._ordering_section = make_section("Ordering")
        self._ordering_chip = QLabel("(unset)")
        self._ordering_chip.setStyleSheet(
            "background:#e8f4f4;color:#0a8a82;border-radius:9px;"
            "padding:2px 9px;font-size:11px;font-weight:600;"
        )
        self._ordering_section.layout().addWidget(self._ordering_chip)
        self._ordering_warning_label = QLabel("")
        self._ordering_warning_label.setStyleSheet(
            "color:#a5641a;font-size:10px;"
        )
        self._ordering_warning_label.setWordWrap(True)
        self._ordering_warning_label.setVisible(False)
        self._ordering_section.layout().addWidget(self._ordering_warning_label)
        left.addWidget(self._ordering_section)

        self._access_section = make_section("Access · who can see")
        self._row_filter_label = QLabel("Row filter:")
        self._row_filter_label.setStyleSheet("color:#666;font-size:11px;")
        self._access_section.layout().addWidget(self._row_filter_label)
        self._row_filter_holder = QVBoxLayout()
        self._access_section.layout().addLayout(self._row_filter_holder)
        self._lens_label = QLabel("Lens:")
        self._lens_label.setStyleSheet("color:#666;font-size:11px;")
        self._access_section.layout().addWidget(self._lens_label)
        self._lens_holder = QVBoxLayout()
        self._access_section.layout().addLayout(self._lens_holder)
        left.addWidget(self._access_section)

        self._view_type_section = make_section("View type")
        self._view_picker = ViewTypeChipPicker(active="table")
        self._view_type_section.layout().addWidget(self._view_picker)
        left.addWidget(self._view_type_section)

        left.addStretch(1)

        left_w = QWidget()
        left_w.setLayout(left)
        body.addWidget(left_w, 3)

        # RIGHT column — the vector runner (THE DECISION §5's
        # Designer-plugin row: "op forms, vector runner"). Replaces the old
        # "Live preview" slot, which only ever showed the raw expression
        # text behind an "evaluator pending" note -- `locksmith.uel.evaluator`
        # was never a real module. The fold engine now actually exists
        # (`template/fold_runner.py`), so the right column runs it.
        self._vectors_section = make_section("Test vectors")
        self._vectors_panel = TestVectorsPanel()
        self._vectors_section.layout().addWidget(self._vectors_panel)
        body.addWidget(self._vectors_section, 2)

        outer.addLayout(body, 1)

        # Used by.
        self._used_by = make_section("Used by")
        self.chip_strip = CrossRefChipStrip()
        self._used_by.layout().addWidget(self.chip_strip)
        outer.addWidget(self._used_by)

    def set_entry(self, entry: dict[str, Any]) -> None:
        from locksmith_micro_app_designer.widgets.source_event_chip_strip import (
            SourceEventChipStrip,
        )
        from locksmith_micro_app_designer.widgets.payload_schema_table import (
            PayloadSchemaTable,
        )
        from locksmith_micro_app_designer.widgets.rule_chip_strip import (
            RuleChipStrip,
        )

        self._name_label.setText(entry.get("name") or entry.get("id") or "(unnamed)")
        self._id_chip.setText(entry.get("id", ""))
        self._description_label.setText(entry.get("description", ""))

        def _clear(layout) -> None:
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget() if item is not None else None
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()

        _clear(self._sources_holder)
        self._sources_holder.addWidget(
            SourceEventChipStrip(entry.get("source_events") or [])
        )

        shape = entry.get("shape", "collection")
        self._shape_chip.setText(shape)
        if shape == "collection":
            self._primary_key_value.setText(entry.get("primary_key") or "(unset)")
        else:
            self._primary_key_value.setText("(n/a — object shape)")

        _clear(self._row_schema_holder)
        schema = entry.get("row_schema") if shape == "collection" else entry.get("state_schema")
        self._row_schema_holder.addWidget(PayloadSchemaTable(schema or {}))

        _clear(self._fold_holder)
        self._fold_holder.addWidget(
            build_fold_map_widget(entry.get("fold") or {}, schema=schema)
        )

        ordering = entry.get("ordering", "source_seq")
        self._ordering_chip.setText(ordering)
        warning = _ordering_warning(entry)
        self._ordering_warning_label.setText(warning or "")
        self._ordering_warning_label.setVisible(bool(warning))

        access = entry.get("access") or {}
        _clear(self._row_filter_holder)
        rf = access.get("row_filter_rule_ref")
        self._row_filter_holder.addWidget(RuleChipStrip([rf] if rf else []))
        _clear(self._lens_holder)
        lr = access.get("lens_rule_ref")
        self._lens_holder.addWidget(RuleChipStrip([lr] if lr else []))

        view = (entry.get("display") or {}).get("view_type", "table")
        # set_active is a no-op if same; toggle via setting first and
        # then back if we need to force the restyle.
        self._view_picker._active = view
        self._view_picker._restyle()

        doc = self._model.doc if self._model is not None else None
        self._vectors_panel.set_entry(entry, entry_kind="projection", doc=doc)

        self.chip_strip.set_refs(
            self._crossrefs.consumers_of(f"projection:{entry.get('id', '')}")
        )

    def preview_text(self) -> str:
        return self._vectors_panel.text_summary()

    def preview_visible(self) -> bool:
        return self._vectors_section.isVisible()


def _projection_subtitle(p: dict) -> str:
    parts: list[str] = []
    shape = p.get("shape", "collection")
    parts.append(shape)
    n = len(p.get("source_events") or [])
    if n:
        parts.append(f"folds {n} event{'s' if n != 1 else ''}")
    return " · ".join(parts) if parts else ""


class ProjectionsEditorPage(QWidget):
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
                id=p.get("id", ""),
                label=p.get("name") or p.get("id") or "(unnamed)",
                subtitle=_projection_subtitle(p),
                kind_color=color,
                has_errors=False,
            )
            for p in model.doc.get("projections", [])
        ]
        self.shell = PrimitiveEditorShell(
            surface_label="Projections",
            template_label=model.doc.get("header", {}).get("display_name", "(untitled)"),
            items=items,
            add_label="+ Add projection",
            item_count=len(items),
            role_label=model.doc.get("role", {}).get("id", ""),
            is_valid=True,
            parent=self,
        )
        self._pane = _ProjectionSectionPane(crossrefs=crossrefs, model=model)
        if items:
            self._pane.set_entry(model.doc["projections"][0])
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
        for p in self._model.doc.get("projections", []):
            if p.get("id") == item_id:
                self._pane.set_entry(p)
                return

    def preview_visible(self) -> bool:
        return self._pane.preview_visible()

    def preview_text(self) -> str:
        return self._pane.preview_text()
