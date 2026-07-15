# -*- encoding: utf-8 -*-
"""A self-contained CEL/1.0 fold engine for the Designer's vector runner.

M-Task 5 (Stage 5 of the UEL->CEL migration): the Designer plugin's op
forms and raw-reducer editors need a way to *run* an aggregate's or
projection's `test_vectors[]` in-process and show pass/fail. `concierge-api`
already has the reference evaluator (`computes/cel_env.py`) and fold engine
(`computes/fold_engine.py`) for accepted spec
`2026-07-10-cel-declarative-aggregates-and-projections.md` §8 (ops) and §11
(engine semantics) -- but it is a sibling repo, not a published package, so
importing it directly here would be a cross-repo import (out of bounds per
the migration plan). This module re-implements the same semantics,
self-contained, so the Designer never depends on concierge-api at runtime.

Behavioral equivalence with the reference engine is asserted, not assumed:
`tests/micro_app_template/test_fold_runner.py` reproduces the accepted
spec's §10 gym conformance vectors verbatim (the same vectors
`concierge-api`'s `tests/computes/test_cel_profile.py` uses) and additionally
runs every `test_vectors[]` entry shipped by both worked examples
(`carrier-license-application`, `regulator-grants-carrier-license`) green.

Only what the vector runner needs is implemented here: `fold()` (replay a
handler map over an ordered event list) and `try_append()` (fold one
candidate event speculatively, then check it against `invariants[]`). There
is no persistence, no Service-AID wiring -- this is authoring-time
conformance checking, not the runtime.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import celpy
import celpy.celtypes as celtypes
from celpy.adapter import CELJSONEncoder
from celpy.evaluation import CELEvalError

try:
    from keri.core.coring import Saider
except ImportError:  # pragma: no cover - keri is expected importable in the
    Saider = None     # shared locksmith venv this plugin runs under.


class CelExpressionError(Exception):
    """A CEL/1.0 expression failed to compile or evaluate."""


class InvariantViolation(Exception):
    """Raised by `try_append` when a candidate state fails an invariant.

    `rule_ref` is the failing rule's id (accepted spec §6.2's "between fold
    and append" check).
    """

    def __init__(self, rule_ref: str):
        self.rule_ref = rule_ref
        super().__init__(f"invariant violated: {rule_ref}")


def _to_python(value: Any) -> Any:
    """Unwrap a celpy value tree (CELType wrappers) into plain Python."""
    return CELJSONEncoder.to_python(value)


# --- profile extension functions (accepted spec §4.2 + amendment 3; cheat-sheet §5) ----

def _not_null(x: Any) -> celtypes.BoolType:
    return celtypes.BoolType(x is not None)


def _said(value: Any) -> celtypes.StringType:
    if Saider is None:  # pragma: no cover - import-time guard, not a runtime path
        raise CelExpressionError("said(): keri.core.coring.Saider is not importable")
    py = _to_python(value)
    if not isinstance(py, dict):
        raise CelExpressionError("said(value) requires a map value")
    sad = dict(py)
    sad.setdefault("d", "")
    saider, _sad = Saider.saidify(sad=sad, label="d")
    return celtypes.StringType(saider.qb64)


def _holds_credential(principal: Any, cred_type: Any, constraints: Any) -> celtypes.BoolType:
    principal_py = _to_python(principal)
    creds = principal_py.get("credentials", []) or []
    want_type = str(cred_type)
    want = _to_python(constraints)
    for cred in creds:
        if cred.get("type") != want_type:
            continue
        if all(cred.get(k) == v for k, v in want.items()):
            return celtypes.BoolType(True)
    return celtypes.BoolType(False)


def _omit(m: Any, fields: Any) -> celtypes.MapType:
    drop = {str(f) for f in fields}
    py = _to_python(m)
    return celpy.json_to_cel({k: v for k, v in py.items() if k not in drop})


def _pick(m: Any, fields: Any) -> celtypes.MapType:
    keep = {str(f) for f in fields}
    py = _to_python(m)
    return celpy.json_to_cel({k: v for k, v in py.items() if k in keep})


def _distinct(xs: Any) -> celtypes.ListType:
    seen: list = []
    out: list = []
    for item in xs:
        if item not in seen:
            seen.append(item)
            out.append(item)
    return celtypes.ListType(out)


def _group_by(rows: Any, field_name: Any) -> celtypes.MapType:
    buckets: dict = {}
    order: list = []
    for row in rows:
        key = row[field_name]
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(row)
    return celtypes.MapType({key: celtypes.ListType(buckets[key]) for key in order})


EXTENSION_FUNCTIONS: dict[str, Any] = {
    "notNull": _not_null,
    "said": _said,
    "holdsCredential": _holds_credential,
    "omit": _omit,
    "pick": _pick,
    "distinct": _distinct,
    "groupBy": _group_by,
}


# --- per-slot pinned binding environments (accepted spec §4.1; cheat-sheet §2) ---------

SLOT_BINDINGS: dict[str, tuple[str, ...]] = {
    "aggregate_fold": ("state", "event"),
    "projection_fold": ("row", "event"),
    "invariant": ("state", "event"),
}


class CelEnv:
    """A pinned CEL/1.0 evaluator scoped to one template expression slot.

    Binds *exactly* the variables `SLOT_BINDINGS[slot]` lists. Compiled
    programs are cached by expression text within one `CelEnv` instance,
    since a fold re-evaluates the same handler expression once per matching
    event.
    """

    def __init__(self, slot: str):
        if slot not in SLOT_BINDINGS:
            raise ValueError(f"unknown CEL/1.0 slot: {slot!r}")
        self.slot = slot
        self.variables = SLOT_BINDINGS[slot]
        self._environment = celpy.Environment()
        self._programs: dict[str, Any] = {}

    def _program(self, expression: str):
        prgm = self._programs.get(expression)
        if prgm is None:
            ast = self._environment.compile(expression)
            prgm = self._environment.program(ast, functions=EXTENSION_FUNCTIONS)
            self._programs[expression] = prgm
        return prgm

    def eval(self, expression: str, **bindings: Any) -> Any:
        given = set(bindings)
        expected = set(self.variables)
        if given != expected:
            raise ValueError(
                f"slot {self.slot!r} requires bindings {sorted(expected)}, "
                f"got {sorted(given)}"
            )
        prgm = self._program(expression)
        activation = celpy.json_to_cel(bindings)
        try:
            result = prgm.evaluate(activation)
        except CELEvalError as ex:
            raise CelExpressionError(f"{expression!r}: {ex}") from ex
        if isinstance(result, CELEvalError):
            raise CelExpressionError(f"{expression!r}: {result}") from result
        return _to_python(result)


def cel_env(slot: str) -> CelEnv:
    return CelEnv(slot)


_BARE_IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")


def is_bare_identifier(expression: str) -> bool:
    """True if `expression` is a plain field name (the common case for
    `primary_key`/`instance_key`) rather than a real CEL expression."""
    return bool(_BARE_IDENTIFIER.fullmatch(expression))


# --- the fold/try_append engine (accepted spec §8, §11) --------------------------------

@dataclass
class FoldDefinition:
    """One aggregate's or projection's `fold` primitive (accepted spec §5).

    `kind` selects the bound-variable name used when evaluating handler/op
    expressions: `"state"` for aggregates and `object`-shape projections,
    `"collection"` for `collection`-shape projections (per-row, keyed by
    `primary_key`).
    """

    fold: dict[str, Any]
    initial_state: Any
    kind: str = "state"                       # "state" | "collection"
    primary_key: Optional[str] = None
    invariants: list[dict] = field(default_factory=list)
    ordering: str = "source_seq"
    on_unknown_event: str = "ignore"          # the only v1 policy (§9.3)

    @classmethod
    def aggregate(cls, *, fold: dict, initial_state: Any,
                  invariants: Optional[list[dict]] = None,
                  ordering: str = "source_seq") -> "FoldDefinition":
        return cls(fold=fold, initial_state=initial_state, kind="state",
                   invariants=invariants or [], ordering=ordering)

    @classmethod
    def object_projection(cls, *, fold: dict, initial_state: Any,
                           ordering: str = "source_seq") -> "FoldDefinition":
        return cls(fold=fold, initial_state=initial_state, kind="state",
                   ordering=ordering)

    @classmethod
    def collection_projection(cls, *, fold: dict, primary_key: str,
                               ordering: str = "source_seq") -> "FoldDefinition":
        return cls(fold=fold, initial_state={}, kind="collection",
                   primary_key=primary_key, ordering=ordering)


def _flatten_event(event: dict) -> dict:
    """`event` always carries an envelope alongside the typed payload
    (accepted spec §4.1/§9.4; cheat-sheet §2)."""
    flat = dict(event.get("payload", {}) or {})
    flat["type"] = event.get("type", "")
    flat["said"] = event.get("said", "")
    flat["seq"] = event.get("seq", 0)
    flat["source_aid"] = event.get("source_aid", "")
    flat["datetime"] = event.get("datetime", "")
    return flat


def ordered(events: list[dict], ordering: str) -> list[dict]:
    """Determine fold order per accepted spec §9.2. `source_seq` and
    `commutative` both fold events in the order handed in; `datetime_said`
    sorts by the event's stated `datetime`, tiebreaking on `said`."""
    if ordering in ("source_seq", "commutative"):
        return list(events)
    if ordering == "datetime_said":
        return sorted(events, key=lambda e: (e.get("datetime", ""), e.get("said", "")))
    raise ValueError(f"unknown ordering: {ordering!r}")


def _get_path(obj: dict, path: str, default: Any = None) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _set_path(obj: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def _apply_state_op(op: dict, state: dict, flat_event: dict, env: CelEnv) -> dict:
    """Desugar and apply one §8.1 object-state op."""
    kind = op["op"]
    if kind == "set":
        value = env.eval(op["value"], state=state, event=flat_event)
        _set_path(state, op["target"], value)
    elif kind == "append":
        value = env.eval(op["value"], state=state, event=flat_event)
        arr = _get_path(state, op["target"], default=[])
        _set_path(state, op["target"], list(arr) + [value])
    elif kind == "increment":
        delta = env.eval(op["by"], state=state, event=flat_event)
        cur = _get_path(state, op["target"], default=0)
        _set_path(state, op["target"], cur + delta)
    elif kind == "merge":
        overlay = env.eval(op["value"], state=state, event=flat_event)
        cur = _get_path(state, op["target"], default={}) or {}
        _set_path(state, op["target"], {**cur, **overlay})
    elif kind == "remove":
        expr = f"state.{op['target']}.filter(item, !({op['where']}))"
        kept = env.eval(expr, state=state, event=flat_event)
        _set_path(state, op["target"], kept)
    elif kind == "move":
        matched_expr = f"state.{op['from']}.filter(item, {op['match']})"
        remaining_expr = f"state.{op['from']}.filter(item, !({op['match']}))"
        matched = env.eval(matched_expr, state=state, event=flat_event)
        remaining = env.eval(remaining_expr, state=state, event=flat_event)
        to_cur = _get_path(state, op["to"], default=[])
        _set_path(state, op["from"], remaining)
        _set_path(state, op["to"], list(to_cur) + list(matched))
    else:
        raise ValueError(f"unknown object-state op: {kind!r}")
    return state


def _apply_state_handler(handler: Any, state: Any, event: dict, env: CelEnv) -> Any:
    flat_event = _flatten_event(event)
    if isinstance(handler, dict) and "expression" in handler:
        return env.eval(handler["expression"], state=state, event=flat_event)
    state = copy.deepcopy(state)
    for op in handler:
        state = _apply_state_op(op, state, flat_event, env)
    return state


def _apply_row_op(op: dict, row: Optional[dict], flat_event: dict, env: CelEnv) -> Optional[dict]:
    """Apply one §8.2 collection op. `row` is `None` before a row's first
    upsert; returning `None` signals "no row" (deleted, or never created)."""
    kind = op["op"]
    if kind == "upsert":
        base = dict(row) if row else {}
        for name, expr in op["set"].items():
            base[name] = env.eval(expr, row=row, event=flat_event)
        return base
    if kind == "update":
        if row is None:
            return row
        if "where" in op and not env.eval(op["where"], row=row, event=flat_event):
            return row
        new_row = dict(row)
        for name, expr in op["set"].items():
            new_row[name] = env.eval(expr, row=row, event=flat_event)
        return new_row
    if kind == "delete":
        if row is None:
            return None
        if "where" in op and not env.eval(op["where"], row=row, event=flat_event):
            return row
        return None
    raise ValueError(f"unknown collection op: {kind!r}")


def _apply_row_handler(handler: Any, row: Optional[dict], event: dict, env: CelEnv) -> Optional[dict]:
    flat_event = _flatten_event(event)
    if isinstance(handler, dict) and "expression" in handler:
        # A null raw-reducer result deletes the row (§5).
        return env.eval(handler["expression"], row=row, event=flat_event)
    for op in handler:
        row = _apply_row_op(op, row, flat_event, env)
    return row


def _route_key(primary_key: str, event: dict, env: CelEnv) -> Any:
    if is_bare_identifier(primary_key):
        return (event.get("payload") or {})[primary_key]
    return env.eval(primary_key, event=_flatten_event(event))


def fold(defn: FoldDefinition, events: list[dict], env: CelEnv) -> Any:
    """Reference fold loop (accepted spec §11, verbatim in structure).

    For `kind == "collection"`, returns a `dict[key, row]`; otherwise
    returns the folded `state` object."""
    if defn.kind == "collection":
        rows: dict[Any, dict] = dict(defn.initial_state or {})
        for event in ordered(events, defn.ordering):
            handler = defn.fold.get(event["type"])
            if handler is None:
                continue  # on_unknown_event: ignore (§9.3)
            key = _route_key(defn.primary_key, event, env)
            new_row = _apply_row_handler(handler, rows.get(key), event, env)
            if new_row is None:
                rows.pop(key, None)
            else:
                rows[key] = new_row
        return rows

    state = copy.deepcopy(defn.initial_state)
    for event in ordered(events, defn.ordering):
        handler = defn.fold.get(event["type"])
        if handler is None:
            continue  # on_unknown_event: ignore (§9.3)
        state = _apply_state_handler(handler, state, event, env)
    return state


def try_append(agg: FoldDefinition, current: Any, proposed_event: dict,
                env: CelEnv, invariant_env: CelEnv) -> Any:
    """Speculatively fold `proposed_event` onto `current`, then check every
    invariant over `{state: candidate, event: proposed_event}` (accepted
    spec §6.2/§11). Raises `InvariantViolation(rule_ref)` on the first
    failing invariant. `current` is never mutated."""
    handler = agg.fold[proposed_event["type"]]
    candidate = _apply_state_handler(handler, current, proposed_event, env)
    flat_event = _flatten_event(proposed_event)
    for inv in agg.invariants:
        if not invariant_env.eval(inv["expression"], state=candidate, event=flat_event):
            raise InvariantViolation(inv["rule_ref"])
    return candidate


# --- template-doc adapters: build a FoldDefinition straight from JSON -------------------

def fold_definition_from_aggregate(agg: dict, *, rules_by_id: dict[str, dict]) -> FoldDefinition:
    """Build a `FoldDefinition` from an `aggregates[]` entry, resolving each
    `invariants[].rule_ref` against `rules_by_id` (id -> rule dict) into its
    CEL `expression`, exactly as `xref.py` resolves the same references."""
    invariants: list[dict] = []
    for inv in agg.get("invariants", []) or []:
        rule_ref = inv.get("rule_ref")
        rule = rules_by_id.get(rule_ref) or {}
        invariants.append({
            "rule_ref": rule_ref,
            "expression": rule.get("expression", ""),
        })
    return FoldDefinition.aggregate(
        fold=agg.get("fold", {}) or {},
        initial_state=agg.get("initial_state"),
        invariants=invariants,
    )


def fold_definition_from_projection(proj: dict) -> FoldDefinition:
    """Build a `FoldDefinition` from a `projections[]` entry. `shape`
    defaults to `"collection"` per the meta-schema."""
    shape = proj.get("shape", "collection")
    ordering = proj.get("ordering", "source_seq")
    if shape == "object":
        return FoldDefinition.object_projection(
            fold=proj.get("fold", {}) or {},
            initial_state=proj.get("initial_state"),
            ordering=ordering,
        )
    return FoldDefinition.collection_projection(
        fold=proj.get("fold", {}) or {},
        primary_key=proj.get("primary_key", ""),
        ordering=ordering,
    )


# --- test_vectors[] runner (accepted spec §10) ------------------------------------------

@dataclass
class VectorOutcome:
    """One `test_vectors[]` entry's run result, as the Designer displays it."""

    name: str
    kind: str              # "fold" | "invariant"
    passed: bool
    actual: Any = None
    expected: Any = None
    rejected_by: Optional[str] = None
    error: Optional[str] = None


def _wrap_collection_actual(actual_rows: dict) -> dict:
    """Collection-projection fold vectors express `expected` as
    `{"rows": {...}}` (accepted spec §10; both worked examples). Wrap the
    engine's bare `dict[key, row]` the same way so the two compare
    directly."""
    return {"rows": actual_rows}


def run_vector(defn: FoldDefinition, vector: dict, *, is_collection: bool) -> VectorOutcome:
    """Run one `test_vectors[]` entry against `defn`.

    A **fold vector** (`events[]` + `expected`) asserts the fold. An
    **invariant vector** (`events[]` setup + `append` + `expect_rejected_by`
    / `expect_accepted`) asserts the write guard (§6.2). `defn.invariants`
    must already carry resolved `expression` strings (see
    `fold_definition_from_aggregate`) for invariant vectors to evaluate.
    """
    name = vector.get("name", "(unnamed vector)")
    is_invariant_vector = "append" in vector
    try:
        if is_invariant_vector:
            fold_env = cel_env("projection_fold" if is_collection else "aggregate_fold")
            inv_env = cel_env("invariant")
            setup = vector.get("events", [])
            current = fold(defn, setup, fold_env)
            proposed = vector["append"]
            rejected_by: Optional[str] = None
            try:
                try_append(defn, current, proposed, fold_env, inv_env)
            except InvariantViolation as exc:
                rejected_by = exc.rule_ref

            expect_rejected_by = vector.get("expect_rejected_by")
            expect_accepted = vector.get("expect_accepted")
            if expect_rejected_by is not None:
                passed = rejected_by == expect_rejected_by
            elif expect_accepted is not None:
                passed = (rejected_by is None) == bool(expect_accepted)
            else:
                passed = rejected_by is None
            return VectorOutcome(
                name=name, kind="invariant", passed=passed,
                rejected_by=rejected_by,
                expected=expect_rejected_by if expect_rejected_by is not None else expect_accepted,
            )

        fold_env = cel_env("projection_fold" if is_collection else "aggregate_fold")
        actual = fold(defn, vector.get("events", []), fold_env)
        expected = vector.get("expected")
        actual_comparable = _wrap_collection_actual(actual) if is_collection else actual
        passed = actual_comparable == expected
        return VectorOutcome(
            name=name, kind="fold", passed=passed,
            actual=actual_comparable, expected=expected,
        )
    except (CelExpressionError, ValueError, KeyError) as exc:
        return VectorOutcome(
            name=name, kind="invariant" if is_invariant_vector else "fold",
            passed=False, error=str(exc),
        )


def run_test_vectors(entry: dict, *, entry_kind: str,
                      doc: Optional[dict] = None) -> list[VectorOutcome]:
    """Run every `test_vectors[]` entry on an `aggregates[]` or
    `projections[]` dict, returning one `VectorOutcome` per vector.

    `entry_kind` is `"aggregate"` or `"projection"`. `doc` (the whole
    template document) is required for aggregates whose invariant vectors
    need `rules[]` to resolve `invariants[].rule_ref` -> `expression`.
    """
    vectors = entry.get("test_vectors") or []
    if not vectors:
        return []

    if entry_kind == "aggregate":
        rules_by_id = {r["id"]: r for r in (doc or {}).get("rules", []) if "id" in r}
        defn = fold_definition_from_aggregate(entry, rules_by_id=rules_by_id)
        is_collection = False
    elif entry_kind == "projection":
        defn = fold_definition_from_projection(entry)
        is_collection = entry.get("shape", "collection") == "collection"
    else:
        raise ValueError(f"unknown entry_kind: {entry_kind!r}")

    return [run_vector(defn, v, is_collection=is_collection) for v in vectors]
