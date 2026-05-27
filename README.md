# locksmith-micro-app-designer

Two artifacts in one repo, both about authoring **micro-app templates** — the JSON contract that captures one role's slice of one use case in a KERI-native ecosystem.

| Artifact | Audience | How to use |
|---|---|---|
| **Locksmith wallet plugin** | An SME or developer editing templates inside their wallet | `pip install -e .` into Locksmith's venv, then install via Locksmith's Plugins page |
| **Claude Code marketplace plugin** (`micro-app-template-gen` skill) | An SME working with Claude Code to walk through template authoring conversationally | `claude plugin marketplace add <repo-url>` then `claude plugin install micro-app-template-gen@locksmith-micro-app-designer` |

Both paths produce the same artifact: `micro-app-template.json` + `metadata.json` + `schemas/*.json`, conforming to the spec at `docs/specs/2026-05-09-micro-app-template-authoring-and-data-model.md`.

## What's in the plugin (wallet-side)

The Locksmith plugin registers a "Micro App: Designer" sidebar entry with 10 editor pages, one per template primitive (overview, imports, exports, commands, aggregates, reactions, workflows, projections, rules, plus the templates browser). It's a direct-manipulation UI for editing the JSON template — fields, chips, swimlanes, state machines, JSON source view, live validation.

Beyond editing, the plugin is the **wallet-resident half of micro-app adoption**:

- **Schema/ACDC publication** — when you ingest a template, the SAIDs and ACDC schemas it declares can be published to a registry so others can verify against them
- **Runtime wiring** — bind each command/reaction in the template to a specific runtime endpoint (local Python callable, REST URL, mock)
- **Mock environment** — test projections and workflows locally before pointing at real runtimes

The plugin does NOT include the runtimes themselves. Compute runtimes (rating engines, claim adjudicators) and principal runtimes (autonomous agents like a venue check-in service) are deployed separately. The designer's wiring config tells the wallet how to reach them.

## What's in the marketplace (Claude Code side)

The `micro-app-template-gen` skill walks an SME through producing a valid `micro-app-template.json` artifact via a 10-step process. Asks one question at a time, saves after each step, runs an adversarial review checklist before commit, and saidifies + validates the result. Includes:

- 10-step process reference
- Question bank per step
- UEL/1.0 cheat sheet (the rule expression language)
- Naming conventions
- Adversarial review prompts
- Minimal-valid skeleton template
- Two worked examples (carrier-license-application, regulator-grants-carrier-license)

## Repo structure

```
.claude-plugin/                  Claude Code marketplace + plugin manifests
locksmith-plugin.toml            Locksmith wallet plugin manifest
pyproject.toml                   Python package metadata
src/locksmith_micro_app_designer/  Python plugin source (entry: DesignerPlugin)
  ├── plugin.py                  Plugin entry class
  ├── editors/                   10 page editors
  ├── widgets/                   Composable UI widgets
  └── template/                  Template canonical-JSON / saidify / validate library
skills/micro-app-template-gen/   Claude Code skill (distributed via marketplace)
scripts/                         CLI utilities (saidify, validate)
docs/specs/                      Normative artifact contract
tests/                           Library tests
```

## Status

Pre-1.0. Sourced from work in [locksmith](https://github.com/keri-foundation/locksmith)'s `feat/designer-plugin-spec` branch. Initial extract on 2026-05-26.

## License

MIT.
