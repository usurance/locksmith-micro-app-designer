"""Top-level validation for micro-app templates.

Combines JSON-Schema structural validation against the meta-schema with
cross-reference validation (rule_refs, credential ids, workflow ids,
etc.). Returns a unified result object.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

from locksmith_micro_app_designer.template.xref import XrefError, validate_xrefs


@dataclass
class ValidationError:
    """A single validation error."""
    path: str
    message: str
    severity: str = "error"  # error | warning


@dataclass
class ValidationResult:
    """Combined result of meta-schema + cross-reference validation."""
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)


def _exchange_slot_explanation(instance: Any) -> str | None:
    """F9: a credential-kind exchange failing its `oneOf` on the number of
    credential slots gets the bare jsonschema `oneOf` message, which names no
    cause and no remedy -- design spec §5.3/§13 require the diagnostic say
    *why*. The two credential-kind branches (exported/imported) are the only
    ones keyed on `kind: "credential"` with `exported_credential_id` /
    `imported_credential_id`, so this instance shape identifies them without
    depending on which sub-schema jsonschema attributes the failure to.

    Zero slots is not invalid protocol -- it is the outbound apply/offer
    shape this profile excludes (legal KERI, out of profile, deriving no
    verb); two slots is genuinely ambiguous (which credential is this
    exchange about?). Returns None for anything else, so the generic
    message is left alone.
    """
    if not isinstance(instance, dict) or instance.get("kind") != "credential":
        return None
    has_exported = "exported_credential_id" in instance
    has_imported = "imported_credential_id" in instance
    if has_exported and has_imported:
        return (
            "ambiguous_credential_slot: this exchange declares BOTH "
            "exported_credential_id and imported_credential_id -- a `kind: "
            "\"credential\"` exchange must name exactly one credential slot, "
            "since it is either about something this role exports or "
            "something it imports, never both at once."
        )
    if not has_exported and not has_imported:
        return (
            "missing_credential_slot: this exchange declares neither "
            "exported_credential_id nor imported_credential_id. A `kind: "
            "\"credential\"` exchange must name exactly one credential "
            "slot. If this was meant as the outbound apply/offer shape (no "
            "credential named yet, only a schema_said_referenced) -- that "
            "shape is legal KERI but is excluded from this profile, which "
            "derives the outbound verb from a named credential slot rather "
            "than authoring it (design spec §5.3/§13)."
        )
    return None


def _find_exchange_slot_error(
    e: jsonschema.ValidationError,
) -> jsonschema.ValidationError | None:
    """Find the `oneOf` sub-error (however deeply nested) whose instance is
    the credential-kind exchange itself. A command/reaction's `emissions[]`
    wraps `exchange` inside `emission`'s own `oneOf`, so the top-level error
    jsonschema reports is usually one or two levels above the exchange
    object; the exchange-shaped sub-error lives in `.context`.
    """
    if e.validator == "oneOf" and _exchange_slot_explanation(e.instance) is not None:
        return e
    for ctx in e.context or ():
        found = _find_exchange_slot_error(ctx)
        if found is not None:
            return found
    return None


def _jsonschema_error_to_validation(e: jsonschema.ValidationError) -> ValidationError:
    target = _find_exchange_slot_error(e)
    if target is not None:
        return ValidationError(
            path="/".join(str(p) for p in target.absolute_path) or "<root>",
            message=_exchange_slot_explanation(target.instance),
        )
    return ValidationError(
        path="/".join(str(p) for p in e.absolute_path) or "<root>",
        message=e.message,
    )


def _xref_error_to_validation(e: XrefError) -> ValidationError:
    return ValidationError(path=e.path, message=e.message)


def validate_against_meta_schema(
    doc: dict[str, Any], schema_path: Path
) -> list[ValidationError]:
    """Run JSON-Schema validation; return list of errors (empty if valid)."""
    with open(schema_path) as f:
        schema = json.load(f)
    validator = jsonschema.Draft202012Validator(schema)
    return [_jsonschema_error_to_validation(e) for e in validator.iter_errors(doc)]


def validate_cross_references(doc: dict[str, Any]) -> list[ValidationError]:
    """Run cross-reference checks; return list of errors."""
    return [_xref_error_to_validation(e) for e in validate_xrefs(doc)]


def _handler_is_raw_reducer(handler: Any) -> bool:
    return isinstance(handler, dict) and "expression" in handler


def validate_fold_semantics(
    doc: dict[str, Any],
) -> tuple[list[ValidationError], list[ValidationError]]:
    """Cross-field fold-model checks the meta-schema's JSON-Schema keywords
    cannot express on their own. Returns `(errors, warnings)`.

    Accepted spec `2026-07-10-cel-declarative-aggregates-and-projections.md`:

    - **§14.2** ("`commutative` verification... likely rule: `commutative`
      ordering forbids raw reducers"): a projection declaring
      `ordering: "commutative"` may only use op-list fold handlers. A raw
      `{"expression": ...}` reducer is undecidable for commutativity (the op
      vocabulary is the whitelist the validator *can* statically prove
      commutes) -- this is a hard validation **error**.
    - **§14.5** ("vector coverage floor... proposal: warn in v1"): an
      aggregate or projection with an empty/missing `test_vectors[]` is a
      lint **warning**, not a hard failure, in v1.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    for i, agg in enumerate(doc.get("aggregates", []) or []):
        if not agg.get("test_vectors"):
            warnings.append(ValidationError(
                path=f"aggregates[{i}].test_vectors",
                message=(
                    f"aggregate {agg.get('id', '?')!r} has no test_vectors "
                    "(§14.5 vector-coverage floor -- lint warning, not a hard "
                    "failure, in v1)"
                ),
                severity="warning",
            ))

    for i, proj in enumerate(doc.get("projections", []) or []):
        if not proj.get("test_vectors"):
            warnings.append(ValidationError(
                path=f"projections[{i}].test_vectors",
                message=(
                    f"projection {proj.get('id', '?')!r} has no test_vectors "
                    "(§14.5 vector-coverage floor -- lint warning, not a hard "
                    "failure, in v1)"
                ),
                severity="warning",
            ))
        if proj.get("ordering") == "commutative":
            for event_type, handler in (proj.get("fold") or {}).items():
                if _handler_is_raw_reducer(handler):
                    errors.append(ValidationError(
                        path=f"projections[{i}].fold.{event_type}",
                        message=(
                            f"projection {proj.get('id', '?')!r} declares "
                            'ordering: "commutative" but its handler for event '
                            f"type {event_type!r} is a raw {{expression}} "
                            "reducer; commutative ordering forbids raw "
                            "reducers -- commutativity is undecidable for an "
                            "arbitrary CEL expression, only the op-list "
                            "whitelist can be proven to commute (§14.2)"
                        ),
                    ))

    return errors, warnings


def validate_template(doc: dict[str, Any], schema_path: Path) -> ValidationResult:
    """Full validation: meta-schema + cross-references + fold semantics."""
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []
    errors.extend(validate_against_meta_schema(doc, schema_path))
    errors.extend(validate_cross_references(doc))
    fold_errors, fold_warnings = validate_fold_semantics(doc)
    errors.extend(fold_errors)
    warnings.extend(fold_warnings)
    return ValidationResult(
        is_valid=(len(errors) == 0), errors=errors, warnings=warnings,
    )
