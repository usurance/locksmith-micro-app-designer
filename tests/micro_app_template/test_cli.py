"""Tests for micro-app-template CLI wrappers."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.parent
SAIDIFY = REPO_ROOT / "scripts/micro_app_saidify.py"
VALIDATE = REPO_ROOT / "scripts/micro_app_validate.py"


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
    )


def test_saidify_stamps_d_field(tmp_path, minimal_valid_template):
    doc = dict(minimal_valid_template)
    doc["d"] = "#" * 44
    src = tmp_path / "t.json"
    src.write_text(json.dumps(doc))
    result = _run(SAIDIFY, "--input", str(src), "--in-place")
    assert result.returncode == 0, result.stderr
    out = json.loads(src.read_text())
    assert out["d"] != "#" * 44
    assert len(out["d"]) == 44


def test_saidify_verify_passes_on_stamped(tmp_path, minimal_valid_template):
    doc = dict(minimal_valid_template)
    doc["d"] = "#" * 44
    src = tmp_path / "t.json"
    src.write_text(json.dumps(doc))
    _run(SAIDIFY, "--input", str(src), "--in-place")
    result = _run(SAIDIFY, "--input", str(src), "--verify")
    assert result.returncode == 0, result.stderr


def test_saidify_verify_fails_on_tampered(tmp_path, minimal_valid_template):
    doc = dict(minimal_valid_template)
    doc["d"] = "#" * 44
    src = tmp_path / "t.json"
    src.write_text(json.dumps(doc))
    _run(SAIDIFY, "--input", str(src), "--in-place")
    out = json.loads(src.read_text())
    out["header"]["display_name"] = "TAMPERED"
    src.write_text(json.dumps(out))
    result = _run(SAIDIFY, "--input", str(src), "--verify")
    assert result.returncode != 0


def test_validate_passes_on_valid(tmp_path, minimal_valid_template):
    doc = dict(minimal_valid_template)
    src = tmp_path / "t.json"
    src.write_text(json.dumps(doc))
    result = _run(VALIDATE, "--input", str(src))
    assert result.returncode == 0, result.stderr + result.stdout


def test_validate_fails_on_invalid(tmp_path, minimal_valid_template):
    doc = dict(minimal_valid_template)
    del doc["role"]
    src = tmp_path / "t.json"
    src.write_text(json.dumps(doc))
    result = _run(VALIDATE, "--input", str(src))
    assert result.returncode != 0
    assert "role" in (result.stdout + result.stderr).lower()


EXAMPLES = REPO_ROOT / "skills/micro-app-template-gen/references/examples"


def test_validate_lint_compliant_dir_exits_zero(compliant_template_dir):
    result = _run(
        VALIDATE,
        "--input", str(compliant_template_dir / "micro-app-template.json"),
        "--lint",
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "LINT OK" in result.stdout


def test_validate_lint_passes_on_worked_example():
    """Compliant since the 2026-07-16 schema-version migration."""
    template = (
        EXAMPLES / "regulator-grants-carrier-license/micro-app-template.json"
    )
    result = _run(VALIDATE, "--input", str(template), "--lint")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "LINT OK" in result.stdout


def test_validate_lint_exits_one_on_error_finding(compliant_template_dir):
    """Exit-1-on-error contract: strip `version` from the fixture schema
    (re-saidified so only S05 fires) and expect a lint failure."""
    import json

    from locksmith_micro_app_designer.template.schema_said import (
        saidify_schema_block,
    )

    schema_path = compliant_template_dir / "schemas/test_credential.json"
    schema = json.loads(schema_path.read_text())
    del schema["version"]
    schema = saidify_schema_block(schema)
    schema_path.write_text(json.dumps(schema, indent=2) + "\n")

    template_path = compliant_template_dir / "micro-app-template.json"
    template = json.loads(template_path.read_text())
    template["credentials"]["exports"][0]["schema"]["schema_said"] = schema["$id"]

    from locksmith_micro_app_designer.template.canonical_json import canonicalize
    from locksmith_micro_app_designer.template.saidify import saidify_document

    template = saidify_document(template)
    template_path.write_text(canonicalize(template))
    metadata_path = compliant_template_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["for_micro_app_said"] = template["d"]
    metadata_path.write_text(canonicalize(metadata))

    result = _run(VALIDATE, "--input", str(template_path), "--lint")
    assert result.returncode == 1
    assert "S05" in result.stderr
    assert "LINT FAIL" in result.stderr


def test_validate_without_lint_unchanged_on_worked_example():
    template = (
        EXAMPLES / "regulator-grants-carrier-license/micro-app-template.json"
    )
    result = _run(VALIDATE, "--input", str(template))
    assert result.returncode == 0
    assert "S05" not in result.stdout + result.stderr
