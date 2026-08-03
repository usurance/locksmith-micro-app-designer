# -*- encoding: utf-8 -*-
"""The worked examples' subject selector is the RESERVED name, in both copies.

Authoring spec §11.2 fixes `credential_said` as the name a command uses to say
"which ACDC does this act operate on", retiring the ad-hoc `license_said` /
`application_said` / `<thing>_said` family. The worked examples are what an author
copies, so a stale name there re-teaches the defect the wave exists to abolish.

Why this file exists rather than "the rename was done once, carefully": on
2026-08-02 the rename landed in *this* repo's two copies while
`concierge-api/src/concierge_api_local/computes/doi.py` still read
`p["license_said"]` — and because `revoke_license.payload_schema` carries
`additionalProperties: false`, the retired name was not merely absent from the
contract, it was FORBIDDEN. Nothing in either repo noticed:

  - the only test that binds a designer fixture to that compute,
    `tests/integration/test_microapp_in_vault.py`, has no revoke leg AND
    `importorskip`s away under a plain `pytest tests/`;
  - no test in this repo read the payload_schema property names at all.

The compute-side half is pinned in concierge-api
(`tests/loader/test_doi_compute.py` builds the payload FROM the contract). This
is the contract-side half: it fails if either copy drifts back, and it fails if
the two copies disagree with each other.
"""
from __future__ import annotations

import json
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: The regulator bundle in both places it is published. Keyed by a label that
#: names which copy failed, because "one of them" is the hard part to debug.
COPIES = {
    "skill-reference-example":
        REPO_ROOT / "skills/micro-app-template-gen/references/examples"
        / "regulator-grants-carrier-license" / "micro-app-template.json",
    "integration-fixture":
        REPO_ROOT / "tests/integration/fixtures"
        / "regulator-grants-carrier-license" / "micro-app-template.json",
}

#: Commands whose payload names an ALREADY-EXISTING credential as its subject.
#: `grant_license` is deliberately absent: it MINTS its subject, so §11.2's
#: selector does not apply to it (its `mints_credential_id` determines the target).
SUBJECT_TAKING = ("suspend_license", "reinstate_license", "revoke_license")

#: The ad-hoc names §11.2 retired. `license_said` is the one that actually shipped.
RETIRED = ("license_said", "application_said", "credential_id")


def _commands(path: pathlib.Path) -> dict[str, dict]:
    return {c["id"]: c for c in json.loads(path.read_text())["commands"]}


@pytest.mark.parametrize("label", sorted(COPIES))
@pytest.mark.parametrize("command_id", SUBJECT_TAKING)
def test_subject_taking_command_declares_the_reserved_selector(label, command_id):
    schema = _commands(COPIES[label])[command_id]["payload_schema"]
    assert "credential_said" in schema["properties"], (
        f"{label}/{command_id} does not declare the reserved selector "
        f"`credential_said` (§11.2); it declares {sorted(schema['properties'])}")
    assert "credential_said" in schema["required"], (
        f"{label}/{command_id} declares `credential_said` but does not require it")


@pytest.mark.parametrize("label", sorted(COPIES))
@pytest.mark.parametrize("command_id", SUBJECT_TAKING)
def test_subject_taking_command_does_not_declare_a_retired_name(label, command_id):
    schema = _commands(COPIES[label])[command_id]["payload_schema"]
    for name in RETIRED:
        assert name not in schema["properties"], (
            f"{label}/{command_id} still declares the retired selector {name!r} "
            f"(§11.2 replaced it with `credential_said`)")


@pytest.mark.parametrize("command_id", SUBJECT_TAKING)
def test_the_two_copies_agree_on_the_payload_contract(command_id):
    """The two copies are mirrors. A unilateral rename in one of them is the
    2026-08-02 defect, so make disagreement itself the failure."""
    contracts = {label: _commands(path)[command_id]["payload_schema"]
                 for label, path in COPIES.items()}
    reference = contracts["skill-reference-example"]
    for label, schema in contracts.items():
        assert sorted(schema["properties"]) == sorted(reference["properties"]), (
            f"{label}/{command_id}'s payload properties diverge from the skill copy")
        assert sorted(schema["required"]) == sorted(reference["required"]), (
            f"{label}/{command_id}'s required list diverges from the skill copy")


@pytest.mark.parametrize("label", sorted(COPIES))
def test_the_retired_name_is_forbidden_not_merely_absent(label):
    """`additionalProperties: false` is what turned the rename into a live break:
    a compute reading the old name can never be fed a valid payload. Pin the flag,
    so nobody "fixes" a future drift by loosening the contract instead."""
    for command_id in SUBJECT_TAKING:
        schema = _commands(COPIES[label])[command_id]["payload_schema"]
        assert schema.get("additionalProperties") is False, (
            f"{label}/{command_id} no longer closes its payload contract")
