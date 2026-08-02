# -*- encoding: utf-8 -*-
"""Pure-logic tests for widgets/state_machine_diagram.py's edge_style().

`edge_style` is the Qt-free logic behind the state-machine diagram's colour
key (Task 14). The diagram used to be colour-coded by `tel_primitive`, a
field this wave deleted (`StateTransition.tel_primitive` no longer exists);
it is now re-keyed off the transition's driver: `via_command`, `via_reaction`,
`via_workflow`, or `trigger: "automatic"`. A transition may declare several
drivers at once (legal per the authoring spec §6.3 driver-list ruling), and
an undriven transition is a defect that must render as a distinct colour,
not fall through to blank.

Widget construction itself (`StateMachineDiagram`) needs a QApplication and
is exercised via the integration smoke test, matching existing repo
practice (see test_fold_map_widget_logic.py's docstring) for editor/widget
panes.
"""
from __future__ import annotations

from locksmith_micro_app_designer.widgets.state_machine_diagram import edge_style


def test_edges_are_keyed_by_driver_kind_not_tel_primitive():
    assert edge_style({"via_command": ["c"]})["driver"] == "command"
    assert edge_style({"via_reaction": ["r"]})["driver"] == "reaction"
    assert edge_style({"via_workflow": "w"})["driver"] == "workflow"
    assert edge_style({"trigger": "automatic"})["driver"] == "automatic"


def test_multiple_drivers_render_as_multi():
    assert edge_style({"via_command": ["c"], "trigger": "automatic"})["driver"] == "multi"


def test_undriven_edge_is_flagged():
    assert edge_style({})["driver"] == "none"


def test_each_driver_kind_has_a_distinct_colour():
    kinds = ["command", "reaction", "workflow", "automatic", "multi", "none"]
    colours = {edge_style(spec)["colour"] for spec in [
        {"via_command": ["c"]}, {"via_reaction": ["r"]}, {"via_workflow": "w"},
        {"trigger": "automatic"}, {"via_command": ["c"], "trigger": "automatic"}, {}]}
    assert len(colours) == len(kinds)


def test_empty_driver_lists_do_not_count_as_declared():
    """An empty `via_command`/`via_reaction` list (falsy) is not a driver --
    matches the schema's "at least one" `missing_transition_driver` rule."""
    assert edge_style({"via_command": [], "via_reaction": []})["driver"] == "none"


def test_trigger_manual_alone_is_not_a_driver():
    """`trigger: "manual"` names no command -- it is the pre-driver-list
    vocabulary's leftover, not one of the four driver kinds itself."""
    assert edge_style({"trigger": "manual"})["driver"] == "none"


def test_three_or_more_drivers_still_render_as_multi():
    spec = {"via_command": ["c"], "via_reaction": ["r"], "via_workflow": "w",
            "trigger": "automatic"}
    assert edge_style(spec)["driver"] == "multi"
