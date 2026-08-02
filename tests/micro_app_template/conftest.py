"""Shared fixtures for micro-app-template tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from locksmith_micro_app_designer.template.canonical_json import canonicalize
from locksmith_micro_app_designer.template.saidify import saidify_document
from locksmith_micro_app_designer.template.schema_said import saidify_schema_block


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def minimal_valid_template() -> dict:
    """A minimal document that conforms to the meta-schema once it is built.

    Used as the smoke-test seed across validation tests.
    """
    return {
        "d": "#" * 44,
        "spec_version": "micro-app-template/0.1",
        "header": {
            "id": "minimal-test",
            "display_name": "Minimal Test Template",
            "description": "Smallest valid template used as a test fixture.",
            "version": "0.1",
            "expression_language": "UEL/1.0",
        },
        "role": {
            "id": "tester",
            "display_name": "Test Actor",
            "description": "A placeholder role used for fixtures.",
            "kind": "individual",
            "keri_infrastructure": {
                "witness_pool": False,
                "watcher_network": False,
                "mailbox": True,
                "acdc_registry": False,
            },
        },
        "credentials": {"imports": [], "exports": []},
        "commands": [],
        "aggregates": [],
        "reactions": [],
        "workflows": [],
        "projections": [],
        "rules": [],
    }


def make_compliant_schema() -> dict:
    """A minimal fully-lint-compliant ACDC schema (envelope + attribute block)."""
    schema = {
        "$id": "",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Test Credential",
        "description": "Minimal compliant ACDC schema for lint tests.",
        "type": "object",
        "credentialType": "TestCredential",
        "version": "1.0.0",
        "properties": {
            "v": {"description": "ACDC version string.", "type": "string"},
            "d": {"description": "Credential SAID.", "type": "string"},
            "i": {"description": "Issuer AID.", "type": "string"},
            "ri": {"description": "Registry identifier.", "type": "string"},
            "s": {"description": "Schema SAID.", "type": "string"},
            "a": {
                "oneOf": [
                    {"description": "Attributes block SAID, compact form.", "type": "string"},
                    {
                        "$id": "",
                        "description": "Attributes block.",
                        "type": "object",
                        "properties": {
                            "d": {"description": "Attributes block SAID.", "type": "string"},
                            "i": {"description": "Issuee AID.", "type": "string"},
                            "dt": {
                                "description": "Issuance date-time.",
                                "type": "string",
                                "format": "date-time",
                            },
                            "claim": {"description": "A test claim.", "type": "string"},
                        },
                        "additionalProperties": False,
                        "required": ["d", "i", "dt", "claim"],
                    },
                ]
            },
        },
        "additionalProperties": False,
        "required": ["v", "d", "i", "ri", "s", "a"],
    }
    schema["properties"]["a"]["oneOf"][1] = saidify_schema_block(
        schema["properties"]["a"]["oneOf"][1]
    )
    return saidify_schema_block(schema)


def write_template_dir(root, template: dict, metadata: dict, schemas: dict) -> None:
    """Write a template dir. `schemas` maps filename -> doc. Schemas are
    written in insertion order (json.dumps, NOT canonicalize) because their
    SAIDs bind to key order; template/metadata use the canonical form."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "micro-app-template.json").write_text(canonicalize(template))
    (root / "metadata.json").write_text(canonicalize(metadata))
    schemas_dir = root / "schemas"
    schemas_dir.mkdir(exist_ok=True)
    for name, doc in schemas.items():
        (schemas_dir / name).write_text(json.dumps(doc, indent=2) + "\n")


@pytest.fixture
def compliant_template_dir(tmp_path, minimal_valid_template):
    """A fully lint-compliant template dir; lint must return zero findings."""
    schema = make_compliant_schema()
    template = copy.deepcopy(minimal_valid_template)
    template["credentials"]["exports"] = [
        {
            "id": "test_credential",
            "name": "Test Credential",
            "description": "Minimal exported credential for lint tests.",
            "envelope": {
                # holder_role equals the fixture's own role.id ("tester") --
                # self_issued: true disambiguates this from targeting another
                # holder of the same role (design spec §6.3, primitives-are-
                # given, 2026-08-02: "without it the self-issued shape is
                # indistinguishable from targeting another holder of my own
                # role").
                "holder_role": "tester",
                "self_issued": True,
                "verifier_roles": ["tester"],
                "edges": [],
                "disclosure_mode": "full",
            },
            "schema": {
                "schema_path": "schemas/test_credential.json",
                "schema_said": schema["$id"],
            },
            "lifecycle": {
                "states": ["issued"],
                "initial": "issued",
                "transitions": [],
            },
        }
    ]
    template = saidify_document(template)
    metadata = {"for_micro_app_said": template["d"]}
    root = tmp_path / "tester-minimal"
    write_template_dir(root, template, metadata, {"test_credential.json": schema})
    return root
