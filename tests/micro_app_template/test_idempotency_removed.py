import json, pathlib
SCHEMA = json.loads(pathlib.Path("docs/superpowers/specs/schemas/micro-app-template.schema.json").read_text())

def test_idempotency_key_expression_is_not_a_command_property():
    cmd = SCHEMA["$defs"]["command"] if "command" in SCHEMA.get("$defs", {}) else None
    assert cmd is not None
    assert "idempotency_key_expression" not in cmd.get("properties", {})
    assert cmd.get("additionalProperties") is False
