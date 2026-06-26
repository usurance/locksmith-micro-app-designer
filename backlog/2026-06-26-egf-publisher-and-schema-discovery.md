# Backlog seed — Schema/ACDC publishing & EGF discovery (the "Micro-App EGF Publisher")

> **Status:** Backlog seed — *for a later brainstorming pass* (likely a separate Claude Code instance). Not designed yet. Captured 2026-06-26.
> **Relation to current work:** This is the **publish/discovery** side of the EGF acceptable-SAID set referenced in the data-driven-microapp-build spec (`docs/superpowers/specs/2026-06-25-data-driven-microapp-build-design.md` §5.1). That spec *consumes* an EGF acceptable-SAID set; this item is about how a micro-app's schemas get **out there** to *be* in an EGF in the first place. Mostly **plugin-world + a global-utility service** — adjacent to, not inside, the loader build.

## The idea (founder's framing)

When a micro-app is **loaded / set up / deployed**, its ACDCs — specifically its **schemas** (the novel concepts it mints) — should be **published** so they are *universally discoverable and resolvable* (via OOBI). Then anyone can find them and pull them into their own **EGF** (Ecosystem Governance Framework). A single micro-app's published schemas/endpoints are effectively a **reusable *component* of an EGF** that *any* EGF can incorporate.

The open question is **where do they get published**, and by what service.

## How KERI publishes/resolves schemas today (grounded — confirm + extend)

- A schema is published by **serving its JSON at an OOBI URL** (e.g. `https://<host>/oobi/<schemaSAID>`) with `Content-Type: application/schema+json`.
- Resolution is **trustless**: a resolver fetches the URL, builds a `Schemer`, and verifies the content's SAID equals the requested SAID — so the host need only be *available*, never *trusted*. (keripy: `src/keri/app/oobiing.py:554` pins the resolved `Schemer` into `db.schema` by SAID; `src/keri/core/scheming.py` — `Schemer` / `CacheResolver` / `JSONSchema`.)
- **Prior art / the canonical "publisher":** GLEIF's **vLEI-server** is a schema-hosting server that serves vLEI schemas by SAID over OOBI. The "Micro-App EGF Publisher" is the same shape, generalized.
- **Two distinct OOBIs — don't conflate:** (a) the **schema OOBI** (publish the schema JSON, trustless via SAID) — the focus here; (b) the micro-app **Service-AID's own AID OOBI** (reachability/endpoints, published via witnesses + `loc`/`end` reply messages) — related, separate.
- **Research pointers for the next pass:** `keria` (agent server — how its agents resolve/host schema OOBIs) and `signify` (client resolution); the `keri.host` infra (S3/CloudFront/Route53 already in play for releases) as a hosting substrate.

## Proposed shape (to brainstorm, not decided)

- A **"Micro-App EGF Publisher" service** — plausibly itself a **Service-AID / global-utility micro-app** — that, on micro-app load/setup, **publishes the micro-app's schemas** (and possibly an EGF-component declaration: the acceptable-SAID set it contributes, the Service-AID OOBI, governance metadata) at OOBI-resolvable endpoints.
- **Default = `keri.host`** (founder-owned; intended to become a foundation): every Micro-App Designer install publishes there by default — e.g. an `egf.keri.host` subdomain serving `/oobi/<said>`.
- **Overridable**: an install can point at a *different* publisher implementing the **same publisher interface**. Rationale: if *only* `keri.host` publishes globally, it bears all the storage (S3) and traffic; allowing self-hosted/alternate publishers distributes that. (Same "default global utility, overridable" pattern the framework uses elsewhere — cf. the update appcast / federation-vs-demo-witness toggles.)

## The plugin-setup abstraction (explicitly OUT of scope for the loader build)

From the Locksmith perspective, installing the **Micro-App Designer plugin** would require a one-time **setup** that configures two directions:
- **Pull-in:** OOBIs of EGFs the user wants to *consume* (to resolve imported schema SAIDs and assemble an acceptable-SAID set).
- **Push-to:** a **publisher** to *emit* this install's own schemas/EGF-components to (default `keri.host`, overridable).

This abstraction layer lives in the **plugin world**, not the loader. It overlaps this work only via the **Service-AID** seam (the publisher may be one) and the **EGF acceptable-SAID set** (§5.1) it feeds.

## Open questions (for the brainstorm)

1. **What exactly gets published?** Schema JSON only, or also: an EGF-component doc (the acceptable-SAID set this micro-app contributes), the Service-AID's AID OOBI, governance/rules, the SAID lockfile?
2. **Publisher as a Service-AID?** Is the publisher itself a micro-app (publish/resolve commands), and if so does it self-host the publish-on-load step (chicken-and-egg with its own bootstrap)?
3. **Trust & curation.** Resolution is trustless (SAID-verified), but *which* schemas an EGF *accepts* is governance — how does adoption-as-trust (§5.1) surface here? Does a publisher rank/curate by adoption?
4. **Storage/cost & federation.** Who pays for hosting? How does the override (alternate publishers) keep discovery global without a single chokepoint? Mirror/replication?
5. **Naming/addressing.** `egf.keri.host/oobi/<said>`? A registry index? How do consumers *discover* publishers (an OOBI of OOBIs)?
6. **Lifecycle.** Publish-on-load only, or also on schema evolution (a new SAID → publish the new one; old stays resolvable)? Unpublish/deprecation?

## Scope note

Out of scope for the current data-driven-microapp-build (loader / command Service-AID / CLIs / integration test). Bring this back as its own brainstorm → spec once the loader and a first template exist, so the publisher has something concrete to publish.
