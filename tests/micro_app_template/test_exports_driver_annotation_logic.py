# -*- encoding: utf-8 -*-
"""Pure-logic tests for editors/exports.py's Lifecycle-tab driver annotation.

`transition_driver_text` is the Qt-free logic behind the Lifecycle tab's
per-transition annotation label (Task 14, scope extension from Task 13's
review). Before this task the annotation covered only `via_workflow`
("via ..."); a transition driven solely by `via_command`/`via_reaction`/
`trigger: "automatic"` rendered with no annotation at all -- an invisible
driver is the same "legal shape renders as blank" hazard the diagram's
`edge_style()` fixes. This extends the annotation to all four driver kinds
plus the legal multi-driver case, and gives the no-driver case (a defect,
per the schema's `missing_transition_driver` rule) a distinct, non-blank
text rather than silence.
"""
from __future__ import annotations

from locksmith_micro_app_designer.editors.exports import transition_driver_text


def test_via_workflow_only():
    assert transition_driver_text({"via_workflow": "exit_product_line"}) == (
        "via workflow exit_product_line"
    )


def test_via_command_single():
    assert transition_driver_text({"via_command": ["suspend_licence"]}) == (
        "via command suspend_licence"
    )


def test_via_command_multiple_joins_with_commas():
    assert transition_driver_text(
        {"via_command": ["suspend_licence", "revoke_licence"]}
    ) == "via command suspend_licence, revoke_licence"


def test_via_reaction_single():
    assert transition_driver_text({"via_reaction": ["premium_lapsed_rx"]}) == (
        "via reaction premium_lapsed_rx"
    )


def test_automatic_trigger():
    assert transition_driver_text({"trigger": "automatic"}) == "automatic"


def test_manual_trigger_alone_is_not_a_named_driver():
    assert transition_driver_text({"trigger": "manual"}) == "no driver (defect)"


def test_multi_driver_combines_all_declared_segments():
    # A licence suspended by a regulator command *or* on premium lapse --
    # the authoring spec §6.3 worked example for a legitimate multi-driver
    # transition.
    text = transition_driver_text({
        "via_command": ["suspend_licence"], "trigger": "automatic",
        "condition_rule_ref": "premium_lapsed",
    })
    assert text == "via command suspend_licence · automatic"


def test_all_four_kinds_combine_in_fixed_order():
    text = transition_driver_text({
        "via_command": ["c"], "via_reaction": ["r"], "via_workflow": "w",
        "trigger": "automatic",
    })
    assert text == "via command c · via reaction r · via workflow w · automatic"


def test_no_driver_reads_as_a_defect_not_blank():
    assert transition_driver_text({}) == "no driver (defect)"


def test_empty_driver_lists_do_not_count_as_declared():
    assert transition_driver_text({"via_command": [], "via_reaction": []}) == (
        "no driver (defect)"
    )
