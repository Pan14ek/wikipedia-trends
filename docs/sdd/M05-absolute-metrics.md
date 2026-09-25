# M05 — Absolute Pageview Metrics

**Spec ID:** WT-M05  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M04

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Compute deterministic baseline metrics from a monthly pageview series.

## In scope

Implement:

- total observed views
- mean monthly views
- median monthly views
- observed month count
- requested month count
- completeness ratio
- min/max monthly views
- raw monthly series preservation

## Input

A sequence of `MonthlyPageview` records covering the requested period.

## Missing-data rules

- `UNKNOWN` values are excluded from numeric aggregates.
- `ZERO_INFERRED` values count as zero.
- Always report both observed and requested month counts.
- Do not impute unknown data in this spec.

## Output model

Recommended:

```json
{
  "absolute_metrics": {
    "total_views": 123456,
    "mean_monthly_views": 5144.0,
    "median_monthly_views": 4821.0,
    "min_monthly_views": 2100,
    "max_monthly_views": 11900,
    "observed_months": 24,
    "requested_months": 24,
    "completeness_ratio": 1.0
  }
}
```

## Numeric behavior

- Integer counts remain integers where natural.
- Means/medians may be floats.
- Define rounding only at presentation time; preserve full precision in internal models.

## Acceptance criteria

- Correct metrics for complete series.
- Correct metrics when unknown months exist.
- All-zero series works.
- Empty observed series returns an explicit “insufficient data” state instead of divide-by-zero.
- Raw series is not mutated.
- Unit tests use hand-calculated fixtures.

## Test plan

Fixtures:
- simple 3-month series
- 24-month constant series
- series with unknown month
- all zeros
- all unknown

## Deliverables

- `analytics.py`
- result models
- unit tests
