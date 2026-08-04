"""Cross-reference validation for micro-app templates.

JSON-Schema validates structural shape. This module validates the
references *within* the document: rule_refs resolve to declared rule
ids, imported_credential_id references resolve to entries in
credentials.imports, lifecycle transition workflow references resolve to
declared workflows, etc.

THE INVARIANT, stated because three surfaces drifted from it: EVERY
doc-local credential reference must resolve, and the FIELD NAME picks the
pool -- `imported_`/`exported_credential_id` against their own pool only,
bare `credential_id` against either. Each surface that names credential ids
goes through `_pooled_credential_refs`/`_either_pool_ref` rather than
reading the fields itself, and no check is keyed on a `type`/`kind` branch
list. Both rules are scar tissue: an emission branch, a trigger type and a
whole trigger surface each went unchecked for exactly one of those reasons
(findings B14 + the 2026-08-04 sweep), and every one of them passed its own
tests while checking nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class XrefError:
    """A cross-reference that does not resolve."""
    path: str
    reference: str
    target_type: str

    @property
    def detail(self) -> str:
        """The finding without its path, for callers that carry `path` separately
        (`validate.ValidationError` does, matching the jsonschema half)."""
        return f"{self.target_type} {self.reference!r} not found"

    @property
    def message(self) -> str:
        return f"{self.path}: {self.detail}"


def _collect_rule_ids(doc: dict[str, Any]) -> set[str]:
    return {r["id"] for r in doc.get("rules", []) if "id" in r}


def _collect_credential_ids(doc: dict[str, Any]) -> tuple[set[str], set[str]]:
    creds = doc.get("credentials", {})
    import_ids = {c["id"] for c in creds.get("imports", []) if "id" in c}
    export_ids = {c["id"] for c in creds.get("exports", []) if "id" in c}
    return import_ids, export_ids


def _collect_workflow_ids(doc: dict[str, Any]) -> set[str]:
    return {w["id"] for w in doc.get("workflows", []) if "id" in w}


def _collect_command_ids(doc: dict[str, Any]) -> set[str]:
    return {c["id"] for c in doc.get("commands", []) if "id" in c}


def _collect_reaction_ids(doc: dict[str, Any]) -> set[str]:
    return {r["id"] for r in doc.get("reactions", []) if "id" in r}


def _collect_aggregate_ids(doc: dict[str, Any]) -> set[str]:
    return {a["id"] for a in doc.get("aggregates", []) if "id" in a}


def _driver_refs(node: dict[str, Any], key: str) -> list[tuple[str, str]]:
    """`(path suffix, name)` for each non-empty name declared under one driver key.

    ONE READING of the driver type, mirroring concierge-api's
    `loader/lifecycle.py::driver_names`. `via_command`/`via_reaction` are declared
    as arrays, but a bare string is what an author writes by hand and what the
    field these replaced used, so it reaches here — and iterating a bare string
    walks its CHARACTERS, emitting one bogus `command '<char>' not found` per
    character (17 for a 17-character typo) and burying the one real diagnostic.
    A non-string entry used to raise `TypeError` outright.

    An empty name is not a declaration, so it is not a dangling reference either;
    a transition that declares nothing is `missing_transition_driver`'s business
    (concierge-api's lifecycle analyser), not xref's. Non-string entries are the
    meta-schema's finding, so they are ignored rather than mistyped into one here.

    NO LONGER MIRRORED, and the retirement makes this file matter more, not less.
    This used to require byte-identical copies here and in
    `ugard/src/locksmith/micro_app_template/xref.py` — identical logic AND identical
    error text, because the two drifting is how the wrong reading survived in one of
    them. ugard retired its vendored copy on 2026-08-04 (canon Q2: the template
    library is code-anchored HERE), so this is the only copy, and ugard's gate 1
    imports THIS file through `ugard/scripts/_designer.py`. Nothing left to sync —
    and nothing left to cross-check it against either.
    """
    value = node.get(key)
    if isinstance(value, str):
        return [(key, value)] if value else []
    if isinstance(value, list):
        return [(f"{key}[{i}]", name) for i, name in enumerate(value)
                if isinstance(name, str) and name]
    return []


# Credential-id field -> the pool it resolves against, wherever the field appears
# (exchange emissions, reaction triggers, workflow triggers). The two pooled names
# are NOT interchangeable: `imported_credential_id` resolves against
# `credentials.imports[]` only. An issuer awaiting acknowledgement of a credential
# it *exported* therefore cannot name it in an exchange, which is a real
# inexpressiveness in the model (finding 45's remaining depth) and is why
# `regulator-grants-carrier-license`'s `workflow_adjudicate_filing` carries
# credential-less `expected_inbound` entries. Accepting either pool would paper
# over that rather than fix it.
_CREDENTIAL_ID_POOLS = (
    ("exported_credential_id", "credentials.exports"),
    ("imported_credential_id", "credentials.imports"),
)

# Bare `credential_id` (envelope edges, value_flow.implied_credentials, workflow
# triggers) declares no pool and canon gives it none -- for `implied_credentials[]`
# §6.3 says explicitly "in this template's exports list OR imported from
# elsewhere". So it resolves against EITHER pool and only a value in neither is a
# finding. Narrowing it to imports would match all three live edges yet false-fire
# on an `authorizes` edge to a self-issued export, which is a legal chain the
# corpus's own `self_issued: true` shape permits.
_EITHER_POOL = "credentials.imports/exports"


def _pooled_credential_refs(node: Any) -> list[tuple[str, str, str]]:
    """`(field, id, pool name)` for each pool-declaring credential id `node` names.

    ONE READING of "a node that names credential ids", shared by every surface that
    has them, so a surface cannot be half-covered again. An empty or non-string id
    is not a declaration; a non-dict node is the meta-schema's finding, not a
    reference to invent here.
    """
    if not isinstance(node, dict):
        return []
    return [(field, node[field], pool)
            for field, pool in _CREDENTIAL_ID_POOLS
            if isinstance(node.get(field), str) and node[field]]


def _exchange_refs(em: dict[str, Any]) -> list[tuple[str, str, str]]:
    """`(path suffix, id, pool name)` for each doc-local credential id an
    emission's `exchange` block names; `[]` when it names none.

    THE PATH IS NESTED, and that is the one way this differs from the
    `aggregate_event` branch beside it: `aggregate_id` sits alongside `kind`,
    whereas these sit one level under `exchange`. `em.get("exported_credential_id")`
    returns None on every live document -- a check written by analogy passes its
    own tests while checking nothing, which is exactly how this stayed missing.

    Two of the exchange `oneOf`'s three branches carry an id (`kind: "credential"`,
    with `exported_credential_id` or `imported_credential_id`); `kind: "message"`
    carries `route`/`schema_id` and no doc-local id, so it yields nothing rather
    than being over-corrected into a finding.
    """
    return [(f"exchange.{field}", cid, pool)
            for field, cid, pool in _pooled_credential_refs(em.get("exchange"))]


def _either_pool_ref(node: Any) -> str | None:
    """The bare `credential_id` `node` names, or None. See `_EITHER_POOL`."""
    if not isinstance(node, dict):
        return None
    value = node.get("credential_id")
    return value if isinstance(value, str) and value else None


def validate_xrefs(doc: dict[str, Any]) -> list[XrefError]:
    """Return a list of unresolved cross-references found in doc."""
    errors: list[XrefError] = []
    rule_ids = _collect_rule_ids(doc)
    import_ids, export_ids = _collect_credential_ids(doc)
    workflow_ids = _collect_workflow_ids(doc)
    command_ids = _collect_command_ids(doc)
    reaction_ids = _collect_reaction_ids(doc)
    aggregate_ids = _collect_aggregate_ids(doc)
    credential_pools = {
        "credentials.exports": export_ids,
        "credentials.imports": import_ids,
        _EITHER_POOL: import_ids | export_ids,
    }

    # credentials.exports[].rule_refs
    for i, c in enumerate(doc.get("credentials", {}).get("exports", [])):
        for j, ref in enumerate(c.get("rule_refs", [])):
            if ref not in rule_ids:
                errors.append(XrefError(
                    path=f"credentials.exports[{i}].rule_refs[{j}]",
                    reference=ref, target_type="rule",
                ))
        # envelope.edges[].credential_id -- meta-schema-REQUIRED, so a dangling one
        # is an ACDC chain reference pointing nowhere: the far node of an I2I/NI2I
        # edge names no credential this template declares.
        envelope = c.get("envelope")
        envelope = envelope if isinstance(envelope, dict) else {}
        for j, edge in enumerate(envelope.get("edges", []) or []):
            cid = _either_pool_ref(edge)
            if cid is not None and cid not in credential_pools[_EITHER_POOL]:
                errors.append(XrefError(
                    path=f"credentials.exports[{i}].envelope.edges[{j}].credential_id",
                    reference=cid, target_type=_EITHER_POOL,
                ))
        # value_flow.implied_credentials[].credential_id
        value_flow = c.get("value_flow")
        value_flow = value_flow if isinstance(value_flow, dict) else {}
        for j, implied in enumerate(value_flow.get("implied_credentials", []) or []):
            cid = _either_pool_ref(implied)
            if cid is not None and cid not in credential_pools[_EITHER_POOL]:
                errors.append(XrefError(
                    path=f"credentials.exports[{i}].value_flow."
                         f"implied_credentials[{j}].credential_id",
                    reference=cid, target_type=_EITHER_POOL,
                ))
        # lifecycle transitions
        for k, t in enumerate(c.get("lifecycle", {}).get("transitions", [])):
            wf = t.get("via_workflow")
            if wf is not None and wf not in workflow_ids:
                errors.append(XrefError(
                    path=f"credentials.exports[{i}].lifecycle.transitions[{k}].via_workflow",
                    reference=wf, target_type="workflow",
                ))
            # via_command / via_reaction: a dangling driver id silently disables
            # the transition (§5.2's defect, reintroduced on the replacement
            # fields unless checked here -- F4/F5/R10). `_driver_refs` gives the
            # type ONE reading; see its docstring for what iterating the raw value
            # did to a bare string.
            for suffix, vc in _driver_refs(t, "via_command"):
                if vc not in command_ids:
                    errors.append(XrefError(
                        path=f"credentials.exports[{i}].lifecycle.transitions[{k}].{suffix}",
                        reference=vc, target_type="command",
                    ))
            for suffix, vr in _driver_refs(t, "via_reaction"):
                if vr not in reaction_ids:
                    errors.append(XrefError(
                        path=f"credentials.exports[{i}].lifecycle.transitions[{k}].{suffix}",
                        reference=vr, target_type="reaction",
                    ))
            cond = t.get("condition_rule_ref")
            if cond is not None and cond not in rule_ids:
                errors.append(XrefError(
                    path=f"credentials.exports[{i}].lifecycle.transitions[{k}].condition_rule_ref",
                    reference=cond, target_type="rule",
                ))
            for m, req in enumerate(t.get("requires", []) or []):
                rr = req.get("rule_ref") if isinstance(req, dict) else None
                if rr is not None and rr not in rule_ids:
                    errors.append(XrefError(
                        path=f"credentials.exports[{i}].lifecycle.transitions[{k}].requires[{m}].rule_ref",
                        reference=rr, target_type="rule",
                    ))

    # commands[].*_preconditions
    for i, cmd in enumerate(doc.get("commands", [])):
        for kind in ("auth_preconditions", "state_preconditions", "temporal_preconditions"):
            for j, pre in enumerate(cmd.get(kind, []) or []):
                rr = pre.get("rule_ref") if isinstance(pre, dict) else None
                if rr is not None and rr not in rule_ids:
                    errors.append(XrefError(
                        path=f"commands[{i}].{kind}[{j}].rule_ref",
                        reference=rr, target_type="rule",
                    ))
        # commands[].mints_credential_id (replaces the removed advance-lifecycle
        # emission kind's exported_credential_id -- §6.4's derived-anchoring-act field)
        mints = cmd.get("mints_credential_id")
        if mints is not None and mints not in export_ids:
            errors.append(XrefError(
                path=f"commands[{i}].mints_credential_id",
                reference=mints, target_type="credentials.exports",
            ))
        # commands[].emissions: aggregate_event.aggregate_id, and the exchange
        # branch's nested credential ids (see `_exchange_refs` -- the branch used
        # to be skipped entirely, so a dangling exported_credential_id passed
        # every gate at zero errors).
        for j, em in enumerate(cmd.get("emissions", []) or []):
            if not isinstance(em, dict):
                continue
            kind = em.get("kind")
            if kind == "aggregate_event":
                aid = em.get("aggregate_id")
                if aid is not None and aid not in aggregate_ids:
                    errors.append(XrefError(
                        path=f"commands[{i}].emissions[{j}].aggregate_id",
                        reference=aid, target_type="aggregate",
                    ))
            elif kind == "exchange":
                for suffix, cid, pool in _exchange_refs(em):
                    if cid not in credential_pools[pool]:
                        errors.append(XrefError(
                            path=f"commands[{i}].emissions[{j}].{suffix}",
                            reference=cid, target_type=pool,
                        ))

    # reactions[].trigger / reactions[].emissions
    for i, rx in enumerate(doc.get("reactions", [])):
        # DELIBERATELY NOT keyed on trigger `type`. It used to be: one branch per
        # type, `credential_received` reading `imported_credential_id` and
        # `lifecycle_event` reading only `exported_credential_id` -- though canon
        # gives that type BOTH ("`exported_credential_id` (or
        # `imported_credential_id`)") and all four live `lifecycle_event` triggers in
        # the corpus name the imported one, so the single field covered there was the
        # one nobody uses. A per-type branch list is exactly what silently misses the
        # next member. The field NAME declares the pool on every type, so read the
        # fields and let the types that carry none (`exn_received`, `scheduled`)
        # yield nothing on their own.
        for field, cid, pool in _pooled_credential_refs(rx.get("trigger")):
            if cid not in credential_pools[pool]:
                errors.append(XrefError(
                    path=f"reactions[{i}].trigger.{field}",
                    reference=cid, target_type=pool,
                ))
        # reactions[].mints_credential_id (same field, reaction surface)
        rx_mints = rx.get("mints_credential_id")
        if rx_mints is not None and rx_mints not in export_ids:
            errors.append(XrefError(
                path=f"reactions[{i}].mints_credential_id",
                reference=rx_mints, target_type="credentials.exports",
            ))
        # Same two emission branches as commands[]. Reactions are not an
        # afterthought here: of the corpus's six live exchange ids, half sit on a
        # reaction (`carrier-license-application/on_license_granted`) or a refusal
        # command (`spurn_license`, `spurn_application`) rather than on a bundle's
        # headline command -- a fix that covered only commands[] would miss them.
        for j, em in enumerate(rx.get("emissions", []) or []):
            if not isinstance(em, dict):
                continue
            kind = em.get("kind")
            if kind == "aggregate_event":
                aid = em.get("aggregate_id")
                if aid is not None and aid not in aggregate_ids:
                    errors.append(XrefError(
                        path=f"reactions[{i}].emissions[{j}].aggregate_id",
                        reference=aid, target_type="aggregate",
                    ))
            elif kind == "exchange":
                for suffix, cid, pool in _exchange_refs(em):
                    if cid not in credential_pools[pool]:
                        errors.append(XrefError(
                            path=f"reactions[{i}].emissions[{j}].{suffix}",
                            reference=cid, target_type=pool,
                        ))

    # aggregates[].invariants
    for i, agg in enumerate(doc.get("aggregates", [])):
        for j, inv in enumerate(agg.get("invariants", []) or []):
            rr = inv.get("rule_ref") if isinstance(inv, dict) else None
            if rr is not None and rr not in rule_ids:
                errors.append(XrefError(
                    path=f"aggregates[{i}].invariants[{j}].rule_ref",
                    reference=rr, target_type="rule",
                ))

    # workflows[].trigger / workflows[].steps[].command_id / reaction_id / branches[].rule_ref
    for i, wf in enumerate(doc.get("workflows", [])):
        # workflows[].trigger -- this surface was not visited at all, so a dangling
        # id here resolved against nothing. `workflow_trigger` is a flat object (no
        # `oneOf`), carrying both pooled ids and a bare `credential_id`.
        for field, cid, pool in _pooled_credential_refs(wf.get("trigger")):
            if cid not in credential_pools[pool]:
                errors.append(XrefError(
                    path=f"workflows[{i}].trigger.{field}",
                    reference=cid, target_type=pool,
                ))
        wf_cid = _either_pool_ref(wf.get("trigger"))
        if wf_cid is not None and wf_cid not in credential_pools[_EITHER_POOL]:
            errors.append(XrefError(
                path=f"workflows[{i}].trigger.credential_id",
                reference=wf_cid, target_type=_EITHER_POOL,
            ))
        for j, step in enumerate(wf.get("steps", []) or []):
            cid = step.get("command_id")
            if cid is not None and cid not in command_ids:
                errors.append(XrefError(
                    path=f"workflows[{i}].steps[{j}].command_id",
                    reference=cid, target_type="command",
                ))
            rid = step.get("reaction_id")
            if rid is not None and rid not in reaction_ids:
                errors.append(XrefError(
                    path=f"workflows[{i}].steps[{j}].reaction_id",
                    reference=rid, target_type="reaction",
                ))
            for k, br in enumerate(step.get("branches", []) or []):
                rr = br.get("rule_ref") if isinstance(br, dict) else None
                if rr is not None and rr not in rule_ids:
                    errors.append(XrefError(
                        path=f"workflows[{i}].steps[{j}].branches[{k}].rule_ref",
                        reference=rr, target_type="rule",
                    ))
            # expected_inbound[].imported_credential_id
            for k, ei in enumerate(step.get("expected_inbound", []) or []):
                hid = ei.get("imported_credential_id") if isinstance(ei, dict) else None
                if hid is not None and hid not in import_ids:
                    errors.append(XrefError(
                        path=f"workflows[{i}].steps[{j}].expected_inbound[{k}].imported_credential_id",
                        reference=hid, target_type="credentials.imports",
                    ))

    # projections[].access.row_filter_rule_ref / lens_rule_ref
    for i, p in enumerate(doc.get("projections", [])):
        access = p.get("access") or {}
        rr = access.get("row_filter_rule_ref")
        if rr is not None and rr not in rule_ids:
            errors.append(XrefError(
                path=f"projections[{i}].access.row_filter_rule_ref",
                reference=rr, target_type="rule",
            ))
        lr = access.get("lens_rule_ref")
        if lr is not None and lr not in rule_ids:
            errors.append(XrefError(
                path=f"projections[{i}].access.lens_rule_ref",
                reference=lr, target_type="rule",
            ))

    # rules[].links (binding_link references)
    for i, r in enumerate(doc.get("rules", [])):
        for j, link in enumerate(r.get("links", []) or []):
            tid = link.get("rule_id") if isinstance(link, dict) else None
            if tid is not None and tid not in rule_ids:
                errors.append(XrefError(
                    path=f"rules[{i}].links[{j}].rule_id",
                    reference=tid, target_type="rule",
                ))

    return errors
