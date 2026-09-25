# M11 — Bootstrap Confidence Intervals

**Spec ID:** WT-M11  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M10

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Estimate uncertainty around YoY growth caused by month-to-month variation without presenting the interval as market-demand certainty.

## In scope

- percentile bootstrap confidence interval for YoY
- deterministic random seed
- explicit method metadata
- insufficiency rules
- methodology warning

## Method

Use calendar-aligned month pairs from previous and recent year.

For each bootstrap iteration:
1. sample paired month indices with replacement
2. sum selected previous-year values
3. sum selected recent-year values
4. calculate YoY from the resampled sums
5. collect result

Defaults:
- iterations: 2000
- confidence level: 95%
- random seed: 42

Use percentile bounds 2.5% and 97.5%.

## Pairing rule

Only paired months with valid values on both sides are eligible.

Minimum default number of valid month pairs: 8.

If fewer than 8 valid pairs exist, interval is `unavailable`.

## Output

```json
{
  "confidence_interval": {
    "metric": "yoy_growth_pct",
    "method": "paired_month_bootstrap",
    "level": 0.95,
    "iterations": 2000,
    "seed": 42,
    "lower": 7.2,
    "upper": 28.4,
    "status": "available"
  }
}
```

## Interpretation requirement

`methodology.md` must state:

This interval quantifies variability in the observed monthly series under the chosen bootstrap procedure. It is not a confidence interval for total market demand, willingness to pay, or causal product opportunity.

## Acceptance criteria

- Deterministic result for a fixed seed.
- Positive, negative, and zero-growth fixtures work.
- Fewer than 8 valid pairs returns unavailable.
- Zero resampled baseline is handled safely.
- CI metadata is present.
- No claim of market-level probability is emitted by Python.

## Test plan

- deterministic repeated runs
- stable series gives narrow interval
- volatile series gives wider interval
- insufficient pairs
- zero baseline cases

## Deliverables

- `confidence.py`
- unit tests
- methodology update
