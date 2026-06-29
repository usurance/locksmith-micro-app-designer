# tests/micro_app_template/test_authz_field.py
import json, pathlib, jsonschema
SCHEMA = json.loads(pathlib.Path("docs/superpowers/specs/schemas/micro-app-template.schema.json").read_text())

def _defs():
    return SCHEMA.get("$defs", SCHEMA.get("definitions", {}))

def test_authz_open_validates():
    authz = _defs()["authz"]
    jsonschema.validate({"method": "open"}, authz)

def test_authz_credential_requires_schema_said():
    authz = _defs()["authz"]
    jsonschema.validate({"method": "credential", "schema_said": "EAAA"}, authz)

def test_authz_rejects_unknown_method():
    authz = _defs()["authz"]
    try:
        jsonschema.validate({"method": "nope"}, authz); assert False
    except jsonschema.ValidationError:
        pass
