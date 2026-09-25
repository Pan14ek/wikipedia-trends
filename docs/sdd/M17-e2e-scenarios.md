# M17 — End-to-End MVP Scenarios

**Spec ID:** WT-M17  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M16

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Prove the entire skill pipeline works from JSON config to generated JSON, PNG, and PDF for the three required product scenarios.

## In scope

Automated E2E coverage for:

### Scenario A — Intermittent fasting
Compare interest in intermittent fasting in Polish and Czech Wikipedia over the last 24 complete months.

Expected outputs:
- analysis.json
- comparison chart PNG
- one-page PDF

### Scenario B — Astronomy
Analyze whether interest in astronomy is growing in Ukrainian Wikipedia and expose reliability checks.

Expected outputs:
- analysis.json
- trend chart PNG
- one-page PDF
- YoY
- CI
- quality checks
- anomaly diagnostics

### Scenario C — Learning English
Use topic mode to compare interest in learning English across a selected set of language editions.

Default fixture languages for deterministic test:
- pl
- cs
- uk

Expected outputs:
- transparent topic resolution
- per-language selected articles
- comparison metrics
- chart
- one-page PDF

## Test strategy

Maintain two layers:

1. deterministic E2E with mocked/recorded Wikimedia responses
2. optional live smoke test against Wikimedia, excluded from default CI to avoid network flakiness

## CLI contract

Tests must invoke the same CLI an agent will use:

```bash
python scripts/analyze.py --config <fixture.json>
```

## Assertions

For each scenario:
- exit code 0
- `analysis.json` exists
- schema version valid
- expected languages present
- metrics are numeric or explicitly unavailable
- quality checks present
- PNG exists and non-empty
- PDF exists, valid, one page
- no invented article titles beyond resolver output
- warnings appear where fixture expects them

## Regression artifacts

Do not assert exact binary equality for PNG/PDF. Assert semantic/structural properties.

## Acceptance criteria

- All three mocked E2E scenarios pass in CI.
- Optional live smoke instructions are documented.
- End-to-end runtime is reasonable for a coding-agent workflow.
- No manual edit is required between config input and final artifacts.

## Deliverables

- `tests/e2e/`
- fixture configs
- mocked/recorded API fixtures
- optional live smoke script/instructions
