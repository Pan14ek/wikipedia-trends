# M08 — Data Quality and Reliability Checks

**Spec ID:** WT-M08  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M07

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Return explicit, explainable quality checks instead of a synthetic confidence score.

## In scope

Implement structured checks for:

1. data completeness
2. period sufficiency
3. article resolution quality
4. trend consistency
5. spike sensitivity placeholder/integration point
6. comparison validity placeholder/integration point

At this stage anomaly logic is not yet implemented, so spike sensitivity may return `not_evaluated` until M10.

## Status model

Use:

- `pass`
- `warning`
- `fail`
- `not_evaluated`

Each check must include:
- `id`
- `status`
- `message`
- `details`

## Completeness thresholds

For a 24-month request:

- >= 90% available: `pass`
- >= 75% and < 90%: `warning`
- < 75%: `fail`

Generalize by ratio for other allowed periods.

## Period sufficiency

- 24+ months: pass for YoY-oriented analysis
- 12–23 months: warning if YoY cannot satisfy the method
- insufficient aligned data: fail for metrics that require it, without necessarily failing all analysis

## Article resolution quality

Examples:
- exact/canonical structured resolution: pass
- search fallback or uncertain mapping: warning
- unresolved article: fail for that language

## Trend consistency

Provide diagnostics, not judgment. Suggested initial measure:
- ratio of positive month-over-month changes among comparable adjacent observed months
- monotonicity is not required for a trend to be valid

## Acceptance criteria

- Quality report always exists for a completed analysis.
- No numeric “confidence score” is emitted.
- Every warning/fail has a human-readable reason.
- Thresholds are unit tested.
- A partial data series can complete with warnings when allowed.
- Fatal insufficiency is distinguishable from non-fatal warning.

## Test plan

- 100%, 95%, 80%, 70% completeness
- unresolved article
- insufficient period
- mixed positive/negative months
- placeholder `not_evaluated` fields

## Deliverables

- `quality.py`
- result models
- tests
- methodology thresholds
