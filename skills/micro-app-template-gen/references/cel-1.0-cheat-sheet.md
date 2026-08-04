# CEL/1.0 — the pinned CEL profile

<!-- This file exists in two copies: ugard's `docs/canon/` (authoritative) and the
     `micro-app-template-gen` skill's `references/` (distribution). They must agree on
     substance; each localizes its own cross-repo pointers, so byte-identical is NOT the
     test. Contract: ugard `docs/vision/repo-and-doc-map.md`, "The sync contract for those
     four pairs". No gate enforces it — syncing is manual, and this file has already gone
     stale through a whole redesign once (payload_mapping, 2026-07-31). -->

`CEL/1.0` is the executable expression language for predicate, computational,
and validation rules, plus fold handlers (aggregate and projection), the
`lens_rule_ref` and `row_filter_rule_ref` slots.

**Claim discipline.** `CEL/1.0` **replaces** the framework's earlier bespoke
language (UEL) entirely — it does not rename it and does not equate it: UEL
is retired, not reinterpreted. `CEL/1.0` is also **not** an external
CEL-standard version — Google's Common Expression Language has no version
token of its own. `CEL/1.0` is a **framework-local profile declaration**,
read only by our own loader, validator, and Designer, which use it to
select the evaluator and the profile rules below. The `/1.0` versions *our
profile*; a future `CEL/1.1` means this document changed (a new extension
function, a new idiom ruling), not that Google shipped anything. This
document — the profile reference — is the token's definition, and it pins
the underlying evaluators: **`cel-python` 0.5.x** for the runtime today;
a `cel-js` evaluator (candidate: `cel-js` 0.8.2 or
`@marcbachmann/cel-js` 8.0.0) for the browser edge when that surface exists.

See `docs/superpowers/specs/2026-07-13-uel-cel-decision-design.md` for the
decision record this profile implements.

## 1. Two-phase model

Every CEL expression is parsed, type-checked against a *bound context*
(which variables and types are in scope), and then evaluated. A `state.foo`
reference fails to compile if `foo` isn't in the aggregate's state schema.
The bindings below are what the loader provides for each template
position — references to anything else are unbound-name errors.

## 2. Bound contexts by position

The compiler matches each expression's position in the template to one of
these bound contexts. Use only the variables listed; nothing else is in
scope.

| Where it appears | Bindings |
|---|---|
| `commands[].auth_preconditions[].rule_ref` (`predicate`, purpose `auth_precondition`) | `{ principal, command }` |
| `commands[].state_preconditions[].rule_ref` (purpose `state_precondition`) | `{ state, command, principal }` |
| `commands[].temporal_preconditions[].rule_ref` (purpose `temporal_precondition`) | `{ command, now() }` |
| Aggregate `fold.<event_type>` handler (op list or raw reducer) | `{ state, event }` — `state` is the folded state **before** this event's step is applied |
| ↳ …for an event a **command** emitted | `event.<prop>` for each declared property, bound by name from `command.<prop>`. There is no emission-side expression: an `aggregate_event` emission is `{kind, aggregate_id, event_type}` |
| ↳ …for an event a **`credential_received` reaction** emitted | `event.<prop>` bound by name from `event.credential.attributes.<prop>`, plus the envelope's `event.credential_said`, `event.credential_issuer`, `event.credential_edges.<name>` |
| ↳ …for an event an **`exn_received` reaction** emitted | `event.<prop>` bound by name from the inbound exn body's `<prop>` |
| ↳ …for an event a **`lifecycle_event` reaction** emitted | `event.<prop>` bound by name from the lifecycle event's payload; the transitioning credential's provenance arrives on the envelope as above |
| Aggregate invariant (`aggregates[].invariants[].rule_ref`) | `{ state, event }` — `state` is the **candidate** state, produced by speculatively applying the proposed event's fold step, before that event is appended |
| Projection `fold.<event_type>` handler (`shape: "collection"`) | `{ row, event }` — `row` is the routed row (selected by `primary_key`), or `null` before its first upsert |
| Projection `fold.<event_type>` handler (`shape: "object"`) | `{ state, event }` — same as an aggregate's fold; no `row`, no invariants |
| `projections[].access.row_filter_rule_ref` (purpose `projection_row_filter`) | `{ row, principal }` |
| `projections[].access.lens_rule_ref` (`computational` rule, `result_attribute: "row"`) | `{ row, principal }` — renamed from the old `lens_template`; a full CEL expression that *returns* the shaped row, not a string template |
| `credentials.exports[].lifecycle.transitions[].requires[].rule_ref` (purpose `lifecycle_transition_requires`) | `{ credential, state, event }` |
| `credentials.exports[].lifecycle.transitions[].condition_rule_ref` (purpose `lifecycle_transition_condition`) | `{ credential, state, event }` |
| `workflows[].steps[].branches[].rule_ref` (purpose `workflow_branch_condition`) | `{ state, command, workflow, principal }` |
| `rules[]` with purpose `derived_membership` | `{ principal, ecosystem }` |
| `rules[]` with type `computational` (credential-attribute derivation) | `{ attributes }` — produces the value assigned to `result_attribute` |
| `rules[]` with type `validation` (credential-level, outside an aggregate) | `{ event, state }` — evaluated at issuance/update |

`idempotency_key_expression` is gone — it was removed from the template
spec during canon consolidation. Don't author one. What provides dedup at
runtime is canon's determination, not this reference's:
`docs/canon/be-keri-native.md` § *Living scorecard*, Idempotency row (ugard
repo). Do not restate the mechanism here; a second copy is how the two
documents drift apart.

**Shapes:**

- `principal` — `{ aid: aid, credentials: list<{ type, holder, issuer, said, revoked }> }`
- `command` — fields of the command's `payload_schema`
- `state` — fields of the aggregate's `state_schema` (or an `object`-shape projection's `state_schema`)
- `event` — an envelope flattened together with the event's typed payload
  fields: `event.type`, `event.said`, `event.seq`, `event.source_aid`,
  `event.datetime` (the *event's* stated time — there is no wall clock in
  CEL, deliberately) alongside whatever fields the event's `payload_schema`
  declares (e.g. a `license_received` event with payload fields
  `jurisdiction`, `effective` is read as `event.jurisdiction`,
  `event.effective` — no `.payload.` nesting for the event being folded).
  Any of these five, plus the credential provenance triple
  (`credential_said`/`credential_issuer`/`credential_edges`), may also be
  *minted* into a differently-named payload property via a declared `from`
  on that property (ten-step-process.md §Step 4, "The declared mint")
- `event.credential` (reactions on `credential_received` and `lifecycle_event`) — `{ said, type, issuer, holder, attributes, validity, revoked }`
- `row` — fields of the projection's `row_schema`
- `attributes` — fields of the credential's `attributes` block
- `credential` (lifecycle `requires`/`condition` slots) — `{ said, type, issuer, holder, attributes, state }`, the credential instance transitioning
- `workflow` — `{ context: <workflow-scoped variables> }`, e.g. `workflow.context.application_id`
- `ecosystem` — the derived-membership evaluation context

## 3. Operators and macros

Core CEL. No custom per-template operators exist — see §5 for the fixed
extension-function set.

**Comparison:** `==`, `!=`, `<`, `<=`, `>`, `>=` (numbers, strings, datetimes, durations; `==`/`!=` work on any pair)

**Logical:** `&&`, `||`, `!`

**Arithmetic:** `+`, `-`, `*`, `/`, `%` (numbers); `+` also for strings (concat) and lists (concat); `datetime + duration → datetime`; `datetime - datetime → duration` (verified by execution against `cel-python` 0.5.0)

**Membership:** `x in xs` — tests presence in a `list` or a key in a `map`. This is the *only* membership test; there is no `.contains()` on lists (see §8).

**Conditional:** `cond ? then : else` (both branches must unify to the same type)

**No nullish coalescing.** `??` does not exist in CEL (`CELParseError`). See the idiom in §4.

**Macros** (only on `list<T>`; the bound identifier is declared with a
comma — CEL has no arrow-lambda syntax):

| Macro | Returns | Notes |
|---|---|---|
| `.filter(x, bool)` | `list<T>` | Keep matching |
| `.exists(x, bool)` | `bool` | Any match |
| `.all(x, bool)` | `bool` | All match |
| `.exists_one(x, bool)` | `bool` | Exactly one match |
| `.map(x, expr)` | `list<U>` | Transform |
| `has(m.field)` | `bool` | Presence check on a map/message field |

**Functions:**

| Function | Returns | Notes |
|---|---|---|
| `size(x)` | `number` | Cardinality of a `list`, `map`, `string`, or `bytes` — replaces the old `.length`/`.count` properties; also callable receiver-style as `x.size()` |

There is no `.find(pred)`, `.count(pred)`, `.distinct`, `.groupBy(...)`,
`.first`/`.last`, or bare `.length` property in core CEL — see §4 and §5.

**Record:** `obj.field`, `obj.nested.field`; build with
`{ "a": x, "b": y }`. Map-literal keys MUST be quoted strings: a key
position is itself a CEL expression, so a bare identifier key
(`{ a: x }`) evaluates `a` as a variable — an unbound-name error, not a
field name (verified failure on `cel-python` 0.5.0; see §8). CEL map
literals also have **no spread operator** — there is no
`{ ...base, "b": y }`. Compose fields explicitly, or use the profile's
`omit`/`pick` functions (§5) to derive a shaped copy of an existing map.

**Lists:** `[a, b, c]`; concat with `xs + ys`

## 4. The UEL → CEL gap table

Verified by execution against `cel-python` 0.5.0
(`docs/superpowers/specs/2026-07-13-uel-cel-decision-design.md` §2). These
five UEL constructs have no direct CEL equivalent — the "arrow becomes a
comma" framing covers the syntax change, not these:

| Old UEL construct | In CEL? | Replacement idiom (verified) |
|---|---|---|
| `.filter(x => …)` arrow lambdas | ❌ (syntax) | `.filter(x, …)` comma macros |
| `??` nullish coalescing | ❌ `CELParseError` | `has(m.x) ? m.x : fallback` |
| `.find(pred)` | ❌ | `.filter(x, …)[0]` with a size guard |
| `.count(pred)` | ❌ | `size(xs.filter(x, …))` |
| `.distinct()` / `.groupBy()` | ❌ in core CEL | carried into the profile as pinned extension functions (§5): `distinct(list) → list`, `groupBy(list, fieldName) → map<value, list>` |

`.groupBy` is field-name-based because CEL admits no custom macros with
bound variables — a custom macro is exactly what arbitrary-key grouping
would need. Arbitrary-key grouping composes from core CEL instead:
`rows.map(r, r.<expr>).distinct()` gives the distinct key set.

## 5. Profile extension functions

Core CEL plus this fixed, versioned function set — part of the `CEL/1.0`
profile, never extensible per-template. A future `CEL/1.1` may grow this
table; templates may not.

| Function | Signature | Purpose | Example |
|---|---|---|---|
| `notNull(x)` | `(T?) → bool` | Presence check | `notNull(state.assigned_adjuster)` |
| `said(value)` | `(any) → said` | Compute the SAID of a canonical-JSON value | `said(payload) == event.said` |
| `principal.holdsCredential(type, constraints)` | `(string, map) → bool` | Credential-possession predicate — **auth slots only** | `principal.holdsCredential("CarrierLicense", { "state": "active" })` |
| `omit(map, fields)` | `(map<string, any>, list<string>) → map<string, any>` | Copy of `map` without the named fields | `omit(row, ["holder_aid"])` |
| `pick(map, fields)` | `(map<string, any>, list<string>) → map<string, any>` | Copy of `map` with only the named fields | `pick(row, ["policy_said", "jurisdiction"])` |
| `distinct(list)` | `(list<T>) → list<T>` | Unique elements, order-preserving, receiver-style | `xs.distinct()` |
| `groupBy(list, fieldName)` | `(list<T>, string) → map<any, list<T>>` | Bucket rows by one field's value, receiver-style | `rows.groupBy("jurisdiction")` |

All seven are pinned and non-extensible per-template, and both
`distinct`/`groupBy` must be implemented identically in the `cel-js`
evaluator when it lands (they carry the same conformance-vector obligation
as the other five).

**Naming note.** Some historical worked examples (predating this profile)
once used a snake_case `principal.holds_credential(...)` call — that was
UEL-era shorthand, harmonized to camelCase across the canon and worked
examples during the 2026-07 migration. The `CEL/1.0` profile function is camelCase:
`principal.holdsCredential(...)`. Prefer the camelCase form in anything
authored against this profile.

## 6. Idiomatic patterns

**Does the principal currently hold a credential of type X?**

```
principal.credentials.exists(c, c.type == "CarrierLicense" && !c.revoked)
```

The pinned profile function is the shorthand:

```
principal.holdsCredential("CarrierLicense", { "state": "active" })
```

Use the shorthand when the spec or example shows it; use `.exists(...)`
when you need to inspect non-state fields (specific issuer, specific
holder, etc.) — `holdsCredential` only reasons over `constraints` shaped
like credential state.

**Is the credential's holder me?**

```
event.credential.holder == principal.aid
```

**Compute a derived attribute** (`computational` rule, returns the value
assigned to `result_attribute`):

```
attributes.base_rate * attributes.risk_multiplier * attributes.term_months / 12
```

**No duplicate active credential per jurisdiction** (`validation` rule,
evaluated over the aggregate's candidate state):

```
size(state.active_licenses.filter(l, l.jurisdiction == event.jurisdiction)) <= 1
```

**Aggregate invariant: at most one active license per jurisdiction:**

```
state.active_licenses.all(l,
  size(state.active_licenses.filter(o, o.jurisdiction == l.jurisdiction)) == 1
)
```

**Fold handler map: append on one event, remove on another** (the shared
`fold` primitive — an op list is the common case; a raw reducer is fully
equivalent):

```json
"fold": {
  "license_granted": [
    { "op": "append", "target": "state", "value": "{ \"license_said\": event.said, \"jurisdiction\": event.jurisdiction, \"granted_at\": event.granted_at }" }
  ],
  "license_revoked": [
    { "op": "remove", "target": "state", "where": "item.license_said == event.license_said" }
  ]
}
```

The equivalent raw reducer for the `license_revoked` handler above:

```
state.filter(l, l.license_said != event.license_said)
```

**Self-or-licensed row filter** (projection `row_filter_rule_ref`, purpose
`projection_row_filter`):

```
row.holder_aid == principal.aid
|| principal.holdsCredential("carrier_license", { "state": "active" })
```

**Per-principal lens** (projection `lens_rule_ref` — a `computational` rule
with `result_attribute: "row"`; no longer a string template):

```
principal.aid == row.holder_aid ? row : omit(row, ["holder_aid"])
```

**Workflow branch on aggregate state** (purpose `workflow_branch_condition`):

```
state.applications.exists(a, a.id == workflow.context.application_id && a.status == "submitted")
```

**Bucket rows by a field** (profile `groupBy`):

```
rows.groupBy("jurisdiction")
```

→ `map<string, list<row>>`, one bucket per distinct `jurisdiction` value.
For a distinct set of values on an arbitrary expression (not just a bare
field), compose from core CEL instead:

```
rows.map(r, r.jurisdiction).distinct()
```

## 7. Format pipes (templates, not predicates)

Used inside string templates: `display.columns[].display_template`, and
(where present) `summary_template` / `row_summary_template`. The template
itself is a string with `{ expr|pipe }` interpolations. `lens_rule_ref` is
**not** a template surface any more — it's a full CEL rule (§2, §6).

| Pipe | Input type | Output | Notes |
|---|---|---|---|
| `\|date` | datetime | string | `YYYY-MM-DD` |
| `\|datetime` | datetime | string | full timestamp |
| `\|duration` | duration | string | human-readable |
| `\|durationFrom:<expr>` | datetime | string | duration from the argument |
| `\|aid8` / `\|aid12` | aid \| string | string | truncated AID |
| `\|said8` | said \| string | string | truncated SAID |
| `\|schemaName` | said \| string | string | resolves SAID to display name |
| `\|enum` | string | string | enum display value |
| `\|number:<digits>` | number | string | fixed-precision number |

Pipes are for templates. Inside predicate / fold / computational
expressions, write the conversion directly (e.g. `c.said` not
`c.said|said8`).

## 8. Gotchas (real bugs)

- **Map-literal keys MUST be quoted strings.** A map literal's key position
  is a full CEL expression, not a JS-style identifier shorthand:
  `{ said: event.said }` evaluates `said` as a *variable* (an
  unbound-name error at evaluation time — verified failure on
  `cel-python` 0.5.0, whose grammar reads `mapinits : expr ":" expr`).
  Write `{ "said": event.said }`. Bare keys often *compile* and only
  blow up when evaluated, so a parse-check alone won't catch them.

- **No `.contains()` on lists.** Use the `in` operator: `y in xs` (was
  `xs.exists(x => x == y)` in UEL; now `y in xs` natively — no macro
  needed).

- **No map spread.** `{ ...base, b: y }` is not CEL syntax. Compose fields
  explicitly, or reshape an existing map with `omit`/`pick` (§5).

- **`principal.credentials` element does not expose `.attributes`.** To
  gate on a credential's attribute (a specific role attribute, a specific
  endorsed line of business), use a `pattern_*` credential-pattern rule
  under `auth_preconditions` (Stage-14 work), **not** a CEL predicate. CEL
  only sees `{ type, holder, issuer, said, revoked }` on each credential in
  `principal.credentials`.

- **Arithmetic on an untyped event field in a projection fold is
  rejected.** Fields arriving from a source event not typed against this
  projection's own schema are `any`, and `number + any` is a type error. If
  you need a running total, compute it in the source aggregate's state
  (typed) and project it.

- **Heterogeneous list literals feeding a schema-typed field are
  rejected.** `[1, "x"]` doesn't type-check against a uniform-element
  `state_schema`/`row_schema` array field; a record-literal list
  (`[{ "a": 1 }, { "a": 2 }]`) is fine.

- **Ternary branches must unify.** `cond ? state + [x] : null` is rejected
  because `list<T>` and `null` don't unify; use `cond ? state + [x] : state`.

- **A reaction's trigger decides where a declared property is looked up.**
  There is no expression to write, but the binding surface still differs:
  for `credential_received` a property binds from
  `event.credential.attributes.<name>`; for `exn_received` from the
  inbound exn body's `<name>`; for `lifecycle_event` from the lifecycle
  event's own payload, with `event.from_state`/`event.to_state` reachable
  from the fold. A `required` property with no same-named field on its
  trigger is an `unsupplied_property` error — so the failure surfaces at
  check time rather than as a silently-null field.

- **Don't reference `now()` in fold handlers.** These must be
  deterministic; runtime time is supplied via `event.datetime` (the
  event's own stated time, set when the event is appended), which **is**
  deterministic on replay. There is no wall clock in CEL, deliberately.

- **Pipes (`|aid8`) only work in templates.** They are a separate AST node
  and the parser only emits them in template mode. Inside a predicate or
  fold, write a normal expression (no pipe).

- **Old habits: `=>`, `??`, `.find`, `.count` don't parse.** If an
  expression fails to parse and it has an arrow, a `??`, a `.find(`, or a
  `.count(`, it's UEL muscle memory — see §4 for the idiom.

## 9. Quick reference: which position uses which return type

The compiler also enforces the expected return type:

| Position | Expected return |
|---|---|
| `predicate` (any purpose) | `bool` |
| Aggregate invariant | `bool` |
| `lifecycle_transition_requires` / `lifecycle_transition_condition` | `bool` |
| `validation` | `bool` |
| `projection_row_filter` | `bool` |
| Aggregate fold handler (op-list step, or raw-reducer `expression`) | same as the aggregate's `state_schema` (a raw reducer produces the *entire* next state) |
| Projection fold handler (`collection` shape) | same as the projection's `row_schema` (a raw reducer produces the next row, or `null` to delete it) |
| Projection fold handler (`object` shape) | same as the projection's `state_schema` |
| `computational` (credential attribute) | type of `result_attribute` |
| `computational` (projection lens, `result_attribute: "row"`) | same as the projection's `row_schema` (or a shaped subset via `omit`/`pick`) |
| `display_template` and other format-pipe templates | `string` |

If the return-shape doesn't match, the loader emits a `wrong-return-shape`
diagnostic — usually a sign that the expression returns the wrong type or
omits a required field.
