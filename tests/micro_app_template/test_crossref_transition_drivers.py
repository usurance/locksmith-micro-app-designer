# -*- encoding: utf-8 -*-
"""Tests for crossref.py's lifecycle-transition walk (Task 14 scope extension).

`compute_crossrefs` walked only `via_workflow` out of a transition into the
"Used by" reverse index, so a command or reaction that drives a transition
produced no link on the command/reaction editor's "Used by" panel -- the
transition's driver was invisible from the producer side, the same hazard
Task 14 fixes in the diagram and the Lifecycle-tab annotation. This extends
the walk to `via_command` and `via_reaction` (both lists) alongside the
pre-existing `via_workflow` (a string).
"""
from __future__ import annotations

from locksmith_micro_app_designer.crossref import compute_crossrefs


def _doc_with_transition(transition: dict) -> dict:
    return {
        "credentials": {"exports": [{
            "id": "carrier_license",
            "name": "Carrier License",
            "lifecycle": {"transitions": [transition]},
        }]},
    }


def test_via_command_transition_links_to_the_command():
    doc = _doc_with_transition({
        "id": "suspend", "from": "active", "to": "suspended",
        "via_command": ["suspend_licence"],
    })
    refs = compute_crossrefs(doc).consumers_of("command:suspend_licence")
    assert len(refs) == 1
    assert refs[0].surface == "exports"
    assert refs[0].primitive_label == "Carrier License"
    assert refs[0].primitive_path == "/credentials/exports/0"


def test_via_reaction_transition_links_to_the_reaction():
    doc = _doc_with_transition({
        "id": "lapse", "from": "active", "to": "suspended",
        "via_reaction": ["premium_lapsed_rx"],
    })
    refs = compute_crossrefs(doc).consumers_of("reaction:premium_lapsed_rx")
    assert len(refs) == 1
    assert refs[0].surface == "exports"
    assert refs[0].primitive_path == "/credentials/exports/0"


def test_multiple_via_command_ids_each_produce_their_own_crossref():
    doc = _doc_with_transition({
        "id": "terminate", "from": ["active", "suspended"], "to": "terminated",
        "via_command": ["revoke_licence", "surrender_licence"],
    })
    index = compute_crossrefs(doc)
    assert len(index.consumers_of("command:revoke_licence")) == 1
    assert len(index.consumers_of("command:surrender_licence")) == 1


def test_via_workflow_still_links_to_the_workflow_preexisting_behavior():
    doc = _doc_with_transition({
        "id": "exit_line", "from": "active", "to": "exited",
        "via_workflow": "exit_product_line",
    })
    refs = compute_crossrefs(doc).consumers_of("workflow:exit_product_line")
    assert len(refs) == 1
    assert refs[0].surface == "exports"


def test_multi_driver_transition_links_every_declared_driver():
    doc = _doc_with_transition({
        "id": "suspend", "from": "active", "to": "suspended",
        "via_command": ["suspend_licence"], "trigger": "automatic",
        "condition_rule_ref": "premium_lapsed",
    })
    index = compute_crossrefs(doc)
    assert len(index.consumers_of("command:suspend_licence")) == 1
    assert len(index.consumers_of("rule:premium_lapsed")) == 1


def test_undriven_transition_produces_no_command_or_reaction_crossref():
    doc = _doc_with_transition({"id": "t", "from": "a", "to": "b"})
    index = compute_crossrefs(doc)
    assert index.all_keys() == ()
