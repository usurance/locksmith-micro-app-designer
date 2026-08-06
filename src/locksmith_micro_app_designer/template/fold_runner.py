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

This module is SUBORDINATE to the reference: it must track
`computes/fold_engine.py`, never the other way round, and a disagreement
between the two is a bug here to file, not a judgement call. Behavioral
equivalence is asserted, not assumed: `tests/micro_app_template/
test_fold_runner.py` reproduces the accepted spec's §10 gym conformance
vectors verbatim (the same vectors `concierge-api`'s
`tests/computes/test_cel_profile.py` uses), mirrors the reference's
`tests/computes/test_declared_mint.py` behavioral pins, and runs every
`test_vectors[]` entry shipped by both worked examples green.

Three things the reference grew on 2026-07-28 (owner ruling, register
findings 36/37) and this re-implementation tracks: the eight-name envelope
including the credential provenance triple; the declared mint (§6.5 `from`)
materialized before routing, handling and invariants; and bare-name-only
routing read off the flattened event, with the CEL branch deleted.

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


def _first_nested_eval_error(value: Any, _depth: int = 0) -> "CELEvalError | None":
    """The first `CELEvalError` anywhere in a celpy result tree, or None.

    `CelEnv.eval` already rejects an error that IS the result. It is the nested case
    that matters most in practice: every append handler builds a map literal, and
    celpy returns an erroring member as a VALUE rather than raising. Left unchecked
    that error object is written into projected state and surfaces one event later as
    an unrelated ValueError from `json_to_cel`, naming neither the slot nor the rule.

    Mirrors `computes/cel_env.py::_first_nested_eval_error` exactly -- this module is
    subordinate to that reference and must track it, never the reverse.
    """
    if isinstance(value, CELEvalError):
        return value
    if _depth > 32:                      # cycle/pathology guard; real results are shallow
        return None
    if isinstance(value, dict):
        for k, v in value.items():
            found = (_first_nested_eval_error(k, _depth + 1)
                     or _first_nested_eval_error(v, _depth + 1))
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _first_nested_eval_error(item, _depth + 1)
            if found is not None:
                return found
    return None


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
        nested = _first_nested_eval_error(result)
        if nested is not None:
            raise CelExpressionError(f"{expression!r}: {nested}") from nested
        return _to_python(result)


def cel_env(slot: str) -> CelEnv:
    return CelEnv(slot)


#: ASCII, deliberately, mirroring the reference's `computes/cel_env.py`. `\w`
#: is Unicode-aware in Python 3, so a `\w` class routes `café` while
#: `micro-app check`'s `classify_selector` -- whose class is ASCII -- calls it
#: `complex` and ERRORs. That divergence was measured in the reference's own
#: fix round; this re-implementation inherits the fix rather than the bug.
_BARE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_bare_identifier(expression: str) -> bool:
    """True if `expression` is a plain field name -- the whole of what
    `_route_key` accepts as a collection `primary_key`.

    Does NOT strip: the checker's `classify_selector` strips before it
    classifies, so a caller must strip first to reach the same verdict.
    `_route_key` does."""
    return bool(_BARE_IDENTIFIER.fullmatch(expression))


# --- the fold/try_append engine (accepted spec §8, §11) --------------------------------

@dataclass
class FoldDefinition:
    """One aggregate's or projection's `fold` primitive (accepted spec §5).

    `kind` selects the bound-variable name used when evaluating handler/op
    expressions: `"state"` for aggregates and `object`-shape projections,
    `"collection"` for `collection`-shape projections (per-row, keyed by
    `primary_key`).

    `mints` is the declared mint (authoring spec §6.5 `from`; owner ruling
    2026-07-28, register finding 37): event type -> {property -> envelope
    slot}. It is a property of the EVENT TYPE, not of the unit folding it, so
    an aggregate reads it off its own `events` declaration and a projection
    off the declarations of whichever aggregates declare its source events.
    """

    fold: dict[str, Any]
    initial_state: Any
    kind: str = "state"                       # "state" | "collection"
    primary_key: Optional[str] = None
    invariants: list[dict] = field(default_factory=list)
    ordering: str = "source_seq"
    on_unknown_event: str = "ignore"          # the only v1 policy (§9.3)
    mints: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def aggregate(cls, *, fold: dict, initial_state: Any,
                  invariants: Optional[list[dict]] = None,
                  ordering: str = "source_seq",
                  mints: Optional[dict[str, dict[str, str]]] = None) -> "FoldDefinition":
        return cls(fold=fold, initial_state=initial_state, kind="state",
                   invariants=invariants or [], ordering=ordering,
                   mints=mints or {})

    @classmethod
    def object_projection(cls, *, fold: dict, initial_state: Any,
                           ordering: str = "source_seq",
                           mints: Optional[dict[str, dict[str, str]]] = None) -> "FoldDefinition":
        return cls(fold=fold, initial_state=initial_state, kind="state",
                   ordering=ordering, mints=mints or {})

    @classmethod
    def collection_projection(cls, *, fold: dict, primary_key: str,
                               ordering: str = "source_seq",
                               mints: Optional[dict[str, dict[str, str]]] = None) -> "FoldDefinition":
        return cls(fold=fold, initial_state={}, kind="collection",
                   primary_key=primary_key, ordering=ordering,
                   mints=mints or {})


def _flatten_event(event: dict) -> dict:
    """`event` always carries an envelope alongside the typed payload
    (accepted spec §4.1/§9.4; cheat-sheet §2): `event.type`, `event.said`,
    `event.seq`, `event.source_aid`, `event.datetime`, the credential
    provenance triple, plus every payload field at the top level.

    `credential_said` / `credential_issuer` / `credential_edges` carry the
    protocol facts about the ACDC behind an event -- the SAID of the
    credential a reaction received or a command just issued, its issuer, and
    its resolved edge SAIDs. They are envelope rather than payload because
    with `payload_mapping` removed there is no expression that could copy
    them in, and because they are facts the protocol establishes rather than
    data a producer authored.

    All eight stamps come AFTER the merge, so all eight names are reserved: a
    payload supplying one has its value silently discarded. The authoring
    spec (§6.5) forbids declaring them; this is the runtime half of that rule
    (register finding 36)."""
    flat = dict(event.get("payload", {}) or {})
    flat["type"] = event.get("type", "")
    flat["said"] = event.get("said", "")
    flat["seq"] = event.get("seq", 0)
    flat["source_aid"] = event.get("source_aid", "")
    flat["datetime"] = event.get("datetime", "")
    flat["credential_said"] = event.get("credential_said", "")
    flat["credential_issuer"] = event.get("credential_issuer", "")
    flat["credential_edges"] = dict(event.get("credential_edges") or {})
    return flat


#: The eight slots a declared mint may name (§6.5), DERIVED from
#: `_flatten_event` rather than re-listed beside it. A second copy of the list
#: is a second thing to drift, and drift between two mechanisms implementing
#: one rule is the class register finding 36 is about.
ENVELOPE_SLOTS = frozenset(_flatten_event({}))


def materialize_mints(event: dict, mints: dict[str, dict[str, str]]) -> dict:
    """Fill an event's declared mints from its envelope (§6.5 `from`).

    The declared mint is §5.7's kind-3 mint step made schema-visible: the
    moment a credential's SAID becomes a domain identity is declared on the
    event type, once, instead of being buried in whichever producer runs
    first. Materializing it here -- before routing, before handlers, before
    invariants -- is what lets everything downstream treat it as ordinary
    payload data: a fold reads `event.application_id` without knowing it was
    minted, a projection routes on it, and a test vector never mentions it.

    The envelope value WINS over any payload value a producer supplies for
    that property. That is the finding-36 rule reaching one name further, and
    it is also why a vector cannot shadow a mint: vectors supply payloads, and
    the envelope overwrites them.

    The value is read out of `_flatten_event`, so a slot's default (`""`,
    `0`, a fresh `{}`) is by construction the same value a handler reading
    that envelope name directly would see. A slot outside the eight is
    refused: `micro-app check` reports it as `invalid_from_slot`, and reading
    a same-named payload field instead would silently implement the rename
    the ruling forbids. Never mutates the input event."""
    declared = mints.get(event.get("type")) if mints else None
    if not declared:
        return event
    flat = _flatten_event(event)
    payload = dict(event.get("payload") or {})
    for prop, slot in declared.items():
        if slot not in ENVELOPE_SLOTS:
            raise ValueError(
                f"declared mint {prop!r} names {slot!r}, which is not one of the "
                f"eight envelope slots {sorted(ENVELOPE_SLOTS)}; `from` is a closed "
                "enumeration (§6.5, owner ruling 2026-07-28, finding 37)")
        payload[prop] = flat[slot]
    return {**event, "payload": payload}


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


def _route_key(primary_key: str, event: dict) -> Any:
    """Resolve which row `event` routes to: a bare field name, read off the
    FLATTENED event.

    Flattened, not `event["payload"]`: since credential provenance moved to
    the envelope, a projection that keys on the SAID of the credential behind
    the event names `credential_said`, which is an envelope field and appears
    in no payload. Reading the raw payload made such a selector unroutable
    while `micro-app check` -- which does know the envelope names -- passed
    it. A declared mint (§6.5 `from`) is already in that flattened payload by
    the time routing runs, which is what lets a minted key and a carried key
    of the same name share a row.

    THE CEL BRANCH IS DELETED, NOT FIXED (owner ruling 2026-07-28, decision
    D1): a non-bare selector used to route at runtime while `micro-app check`
    could only report `unanalysable_selector` and skip every routing rule for
    the container. What the router accepts is now exactly what the checker's
    `classify_selector` calls a `field` -- a bare identifier, or the
    `event.<name>` spelling with the prefix stripped. Hence the `.strip()`
    (the checker strips before classifying, so a padded `"k "` must route
    rather than be refused at fold time) and the ASCII identifier class.

    A bare name the event does not carry raises `KeyError`: such an event is
    un-appendable, not mis-folded, and the caller must see that rather than a
    phantom row."""
    selector = primary_key.strip() if isinstance(primary_key, str) else ""
    name = selector[len("event."):] if selector.startswith("event.") else selector
    if not is_bare_identifier(name):
        raise ValueError(
            f"primary_key {primary_key!r} is not routable: a routing selector must be "
            "a bare field name (optionally spelled `event.<name>`) — constants and CEL "
            "expressions were removed by the owner ruling of 2026-07-28 "
            "(register finding 37, decision D1)")
    return _flatten_event(event)[name]


def fold(defn: FoldDefinition, events: list[dict], env: CelEnv) -> Any:
    """Reference fold loop (accepted spec §11, verbatim in structure).

    For `kind == "collection"`, returns a `dict[key, row]`; otherwise
    returns the folded `state` object.

    Each event is materialized (§6.5 `from`) before it is routed or handled,
    on BOTH branches: `_flatten_event` merges the payload first, so a minted
    property is then visible to a handler as `event.<prop>` and to
    `_route_key` as a routable field, indistinguishable from a carried one."""
    if defn.kind == "collection":
        rows: dict[Any, dict] = dict(defn.initial_state or {})
        for event in ordered(events, defn.ordering):
            event = materialize_mints(event, defn.mints)
            handler = defn.fold.get(event["type"])
            if handler is None:
                continue  # on_unknown_event: ignore (§9.3)
            key = _route_key(defn.primary_key, event)
            new_row = _apply_row_handler(handler, rows.get(key), event, env)
            if new_row is None:
                rows.pop(key, None)
            else:
                rows[key] = new_row
        return rows

    state = copy.deepcopy(defn.initial_state)
    for event in ordered(events, defn.ordering):
        event = materialize_mints(event, defn.mints)
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
    failing invariant. `current` is never mutated.

    The proposed event is materialized (§6.5 `from`) FIRST, so both the
    speculative fold and the invariants see the minted property. Append time
    is where the mint happens, and an invariant is the last thing evaluated
    before the append -- a guard that could not read the identity the event is
    about would be guarding the wrong event."""
    proposed_event = materialize_mints(proposed_event, agg.mints)
    handler = agg.fold[proposed_event["type"]]
    candidate = _apply_state_handler(handler, current, proposed_event, env)
    flat_event = _flatten_event(proposed_event)
    for inv in agg.invariants:
        if not invariant_env.eval(inv["expression"], state=candidate, event=flat_event):
            raise InvariantViolation(inv["rule_ref"])
    return candidate


# --- template-doc adapters: build a FoldDefinition straight from JSON -------------------

def minted_properties(decl: dict) -> dict[str, str]:
    """property name -> the envelope slot it is minted from (§6.5 `from`),
    for one event type's `events` declaration.

    TOTAL over garbage: `projection_mints` calls this for every aggregate
    declaring a projection's source events, so one aggregate's malformed
    `payload_schema` must not raise out of an unrelated projection's build.
    The value is returned as authored -- `materialize_mints` is what decides
    whether a slot is one of the eight, so an `invalid_from_slot` reaches the
    Designer's panel as that unit's loud failure rather than vanishing here.
    """
    schema = decl.get("payload_schema")
    props = (schema if isinstance(schema, dict) else {}).get("properties")
    if not isinstance(props, dict):
        return {}
    return {name: sub["from"] for name, sub in props.items()
            if isinstance(sub, dict) and "from" in sub}


def aggregate_mints(agg: dict) -> dict[str, dict[str, str]]:
    """event type -> {property -> envelope slot} for one aggregate's own
    `events` declarations (§6.5 `from`)."""
    out: dict[str, dict[str, str]] = {}
    for event_type, decl in (agg.get("events") or {}).items():
        mints = minted_properties(decl if isinstance(decl, dict) else {})
        if mints:
            out[event_type] = mints
    return out


def projection_mints(template: dict, proj: dict) -> dict[str, dict[str, str]]:
    """The mints a projection may rely on, per source event type.

    A projection folds any event of that type, whichever aggregate declared
    it, so it may only rely on what EVERY declaring aggregate guarantees --
    the agreeing intersection. Two aggregates minting one property from
    different slots agree on nothing, so that property is not minted at all
    and shows up as the absent value it is. Within one template event type
    names are unique (§6.5), so in practice each type has one declaration.

    THIS READ CROSSES UNITS, so it is total: a malformed aggregate contributes
    nothing rather than raising, and the Designer's panel renders one unit's
    vectors without a sibling unit's garbage taking them down. Compare
    `aggregate_mints`, which reads an aggregate's OWN declaration."""
    out: dict[str, dict[str, str]] = {}
    aggregates = (template or {}).get("aggregates")
    if not isinstance(aggregates, list):
        return out
    for event_type in proj.get("source_events") or []:
        agreed: Optional[dict[str, str]] = None
        for agg in aggregates:
            events = agg.get("events") if isinstance(agg, dict) else None
            decl = events.get(event_type) if isinstance(events, dict) else None
            if decl is None:
                continue
            mints = minted_properties(decl if isinstance(decl, dict) else {})
            agreed = (mints if agreed is None
                      else {p: s for p, s in agreed.items() if mints.get(p) == s})
        if agreed:
            out[event_type] = agreed
    return out


def fold_definition_from_aggregate(agg: dict, *, rules_by_id: dict[str, dict]) -> FoldDefinition:
    """Build a `FoldDefinition` from an `aggregates[]` entry, resolving each
    `invariants[].rule_ref` against `rules_by_id` (id -> rule dict) into its
    CEL `expression`, exactly as `xref.py` resolves the same references.

    `mints` come off the aggregate's OWN `events` declarations (§6.5)."""
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
        ordering=agg.get("ordering", "source_seq"),
        mints=aggregate_mints(agg),
    )


def fold_definition_from_projection(proj: dict, *,
                                     doc: Optional[dict] = None) -> FoldDefinition:
    """Build a `FoldDefinition` from a `projections[]` entry. `shape`
    defaults to `"collection"` per the meta-schema.

    `doc` (the whole template) is what the mints are read from: `from` is
    declared on the event type in some aggregate's `events`, never on the
    projection (§6.5). Without it a projection folds unminted -- which is the
    honest answer when the caller has only the entry, and the reason the
    Designer's panel hands the whole document down."""
    shape = proj.get("shape", "collection")
    ordering = proj.get("ordering", "source_seq")
    mints = projection_mints(doc or {}, proj)
    if shape == "object":
        return FoldDefinition.object_projection(
            fold=proj.get("fold", {}) or {},
            initial_state=proj.get("initial_state"),
            ordering=ordering,
            mints=mints,
        )
    return FoldDefinition.collection_projection(
        fold=proj.get("fold", {}) or {},
        primary_key=proj.get("primary_key", ""),
        ordering=ordering,
        mints=mints,
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
    need `rules[]` to resolve `invariants[].rule_ref` -> `expression`, and
    for projections whose source events carry a declared mint (§6.5 `from`
    lives on the event type in `aggregates[].events`, never on the
    projection). An aggregate's own mints come off `entry` itself.
    """
    vectors = entry.get("test_vectors") or []
    if not vectors:
        return []

    if entry_kind == "aggregate":
        rules_by_id = {r["id"]: r for r in (doc or {}).get("rules", []) if "id" in r}
        defn = fold_definition_from_aggregate(entry, rules_by_id=rules_by_id)
        is_collection = False
    elif entry_kind == "projection":
        defn = fold_definition_from_projection(entry, doc=doc)
        is_collection = entry.get("shape", "collection") == "collection"
    else:
        raise ValueError(f"unknown entry_kind: {entry_kind!r}")

    return [run_vector(defn, v, is_collection=is_collection) for v in vectors]
