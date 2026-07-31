# Adversarial Review Checklist

Before declaring a template done, deliberately try to break it. Walk this checklist with the SME. Capture concerns in `metadata.json` `author_intent_notes` so reviewers see them.

**Walk 11–18 first.** Items 1–10 attack a model and ask whether it survives; items 11–18 ask whether
it is the right model. A defect in the shape cannot be found by attacking it — every one of the
findings that produced this section's checks passed items 1–10 and every automated gate. Reach
**`keri:chat`** to adjudicate any protocol claim the template's prose makes; it is hosted and can be
unavailable, in which case use `keri:acdc` / `keri:spec`, which carry the same normative text locally.

## 1. Impersonation

- *Can an impostor present a forged credential and have it pass auth_preconditions?*
- KERI's signature/credential machinery makes this "no by construction" when auth_preconditions correctly reference imported credentials with proper rule blocks. Verify that your auth_preconditions DO reference real credential checks (not just `true` or omitted).

## 2. Credential revocation timing

- *A credential is valid at command time but revoked by the time the resulting event is folded into an aggregate. Does the micro-app handle this gracefully?*
- Define the cut-off rule. Most ecosystems use "valid at command time" as authoritative; some require freshness checks.

## 3. Concurrent commands

- *Two commands arrive simultaneously on the same aggregate. What happens?*
- The aggregate's append order resolves it. The loser fails on a stale-state precondition. Is the loser's experience graceful? (UI message, retry guidance, etc.)

## 4. Missed events

- *A subscriber crashes during a multi-event sequence and resumes later. Can it catch up by replaying?*
- Projections must be idempotent under replay. Verify your fold_expression doesn't accumulate side effects on re-fold.

## 5. Counterparty bad behavior

- *The counterparty sends an unexpected message, refuses to advance, or spurns at a surprising moment. Are workflow time_bounds and spurn handlers complete?*
- Every workflow step that awaits the counterparty should have either a time_bound or a clear expected_inbound match for refusal.

## 6. Compromised actor keys

- *The role's keys are rotated under duress. The aggregate respects whatever key state was authoritative at command time.*
- Verify this is the behavior your micro-app needs. If freshness matters more than historical accuracy, document a different rule.

## 7. Schema versioning

- *The schema's SAID changes (because the underlying JSON-Schema changed). Old credentials are still valid; do projections handle multiple schema versions?*
- ACDC schemas are immutable per SAID; new schemas get new SAIDs. Your projections should fold events typed by schema SAID, not name.

## 8. Convention divergence

- *The micro-app references a credential type by name (`ProducerLicense`) but its schema_said differs from neighbor micro-apps. Is this intentional competition, or an avoidable accident?*
- Document the choice in `metadata.json` semantic_lineage or compatibility_hints.

## 9. Idempotency under network retry

- *The actor's transport layer retries an exn after a long delay. Does the recipient deduplicate correctly?*
- The command's `idempotency_key_expression` is the gate. Verify it's deterministic from payload alone (no state, no principal).

## 10. Permission escalation via chained credentials

- *An attacker holds a credential that chains from another via `authorizes`. Can they issue a credential they shouldn't be able to?*
- Trace the chain depth. Confirm that depth limits or scope constraints in the chain prevent unauthorized escalation. If unsure, document the assumption.

## Shape checks (11–18) — walk these first

Each of these was a shipped defect that passed every other gate. Reference:
`references/keri-shape-pass.md`.

## 11. Supersession spelled as a domain event

- *Does any event type name a state transition of a thing rather than an act someone took —
  `*_superseded`, `*_revoked`, `*_suspended`, `*_expired`, `*_reinstated`?*
- A credential's own lifecycle is a **TEL state change** (or a `supersedes` edge for verifiable
  lineage). A domain event needs a second emission and a TEL does not — and two emissions from one
  trigger context conform-bind the same routing key, so the second lands on the first's row.
- Then: *is the spelling recorded in `metadata.json`, and does it match what the rest of the corpus
  uses?* This corpus carries three spellings; only the domain event produced a blocker.

## 12. A status column set by a fold literal

- *Is any `status` / `state` / `disposition` field assigned a string literal by a fold handler?*
- Then status is a function of which event arrived. For an issued artifact, standing is its TEL state
  and "current" is a **dated query** — derived, never stamped. Check the converse too: *does the
  projection hold the facts its own claim depends on?* One shipped vector reported a program effective
  two months in the future as live, because `effective_date` and the approval appeared in zero
  predicates.

## 13. A parser- or human-minted string as identity

- *For every identifier in this template, name its kind* (authoring spec §5.7). *Which values are
  hand-keyed, console-supplied, parsed out of a file, or concatenated from other fields?*
- A foreign coordinate (kind 4) is **provenance, never the key** and never authority. If you already
  mint a SAID over the thing's content, that is the identity. Also flag any `required` string with **no
  `pattern`** sitting beside a patterned sibling — its blank value is a silent no-op and its typo
  matches no row.

## 14. A boolean asserting an ordering

- *Is any boolean named `*_before_*`, `already_*`, `pre_*`/`post_*`, `*_yet` — or derived from
  `size(state.x) > 0` or an `exists` over state?*
- Ordering in KERI is an **edge**. A required edge from the later artifact to the earlier one makes the
  bad state unconstructable — you cannot form the credential without committing to the far node's SAID,
  and a dangling commitment fails `validate_edge` step 1. Then ask the harder question: *does the
  boolean's name claim more than its expression checks?*

## 15. An array attribute standing in for per-scope authorization

- *Does any admissibility or authorization check test membership in an array attribute —
  `exists(m, m == …)`, `contains`, `in`?*
- **An edge targets a credential, not an array element**, so the chain has nothing to discriminate
  against and you are forced to compare values, which `validate_edge` cannot do. One credential per
  authorized scope, `NI2I`, and the unauthorized case has no edge target. Ask also: *can the current
  shape express adding one scope, or exiting one scope while keeping the others?*

## 16. A derived flag frozen at ingest, or with no consumer

- *Is any derived value written once on upsert and never recomputed?* If the fact is an observation of
  someone else's artifact, it must be a **read-time as-of evaluation** — scopes move after issuance.
- *Which rule, precondition, invariant, `row_filter`, or notification reads this field?* If the answer
  is "none, but a human can see the column," it is decoration, and stale decoration at that. If the
  prose says a person must be alerted, **route it somewhere**.

## 17. Defending against a hazard the protocol eliminates

- *Does any rule, prose, or contract text in this template guard a threat that KERI/ACDC already
  removes?* Check each claim against the spec rather than against the framework's own docs.
- Worked case: the authoring spec once forbade conform-by-name from reaching an inbound ACDC's
  attributes, on the grounds that a counterparty's schema change could silently re-bind this role's
  log. ACDC requires a schema `$id` to be a bare SAID and the schema to be immutable, and every import
  pins `expected_schema_said` — so a changed schema **is a different SAID** and the import stops
  matching, loudly. **Specs are ground truth; when framework canon and the spec disagree, the canon is
  the defect.**

## 18. A commitment whose digest has the wrong scope

- *For every SAID this template commits to that was produced outside the system — a parse run, a
  manifest, an export — what exactly does that digest cover?* Does it cover the content someone will
  later need to re-derive, or only a **listing** of it?
- Register **finding 8**: `index_said` was a SAID over a parser index listing *filenames*, committing to
  no shard content. It looked like proof and was not. `program_manifest_said`, over the shard map, is
  the same crossing done right. **A workbench crossing with the wrong scope is worse than none, because
  it reads as proof.**
- And: *who stores that content, who serves it, and what happens when they stop?* A SAID proves
  integrity and gives no retrieval — anchor an unavailable document and you can prove you committed to
  something and never again prove what.

## Recording the review

After walking the checklist, add a paragraph to `metadata.json` `author_intent_notes`:

> Adversarial review performed 2026-MM-DD. Walked shape checks 11-18 and adversary checks 1-10. Identified concerns: [list]. Mitigations: [list]. Open risks: [list].
