# M14 — Versioned JSON Report Schema

**Spec ID:** WT-M14  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M13

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Define a stable, versioned machine-readable `analysis.json` contract that contains enough information to reproduce, audit, and explain a research run.

## In scope

- output schema version
- run metadata
- normalized input config
- resolved articles/topic representation
- data-source metadata
- period
- per-language series summaries
- metrics
- quality checks
- anomalies
- confidence intervals
- comparison section
- warnings
- generated artifact paths

## Schema version

Start with:

```text
schema_version = "1.0.0"
```

Use semantic-versioning principles for future breaking/non-breaking changes.

## Required top-level shape

```json
{
  "schema_version": "1.0.0",
  "run": {},
  "input": {},
  "resolution": {},
  "sources": [],
  "period": {},
  "languages": {},
  "comparison": {},
  "quality": [],
  "warnings": [],
  "artifacts": {}
}
```

## Provenance requirements

For each external dataset record enough provenance to understand:
- Wikimedia endpoint family
- project
- article/title when applicable
- requested period
- fetch timestamp
- access/agent/granularity parameters
- whether value came from network or cache (after M16)

Do not embed huge raw API responses in `analysis.json`.

## Determinism

Given:
- same normalized config
- same input data
- same methodology version
- fixed bootstrap seed

all numeric analysis fields should be stable.

Run timestamps and filesystem paths may differ.

## Output location

Default:

```text
output/<run-slug>/analysis.json
```

Run slug should be filesystem-safe and deterministic enough to understand, e.g. date + topic + languages, while collisions are handled safely.

## Acceptance criteria

- JSON validates against internal Pydantic/output model.
- Required provenance is present.
- All earlier metrics are represented.
- File is UTF-8 and pretty-printed.
- Non-ASCII titles remain readable.
- Schema version is present.
- Tests detect accidental schema regressions.

## Test plan

- single-language article report
- topic report
- multi-language report
- warnings present
- unavailable CI
- unresolved language
- serialization round-trip

## Deliverables

- output models
- `references/output-schema.md`
- JSON writer/orchestrator integration
- tests
