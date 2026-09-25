# M06 — Year-over-Year Growth

**Spec ID:** WT-M06  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M05

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Compute YoY growth for the default 24-month analysis window in a way that respects full-month alignment.

## In scope

- previous 12-month total
- recent 12-month total
- YoY growth percentage
- optional mean-based equivalent for diagnostics
- availability/validity state
- reasons when YoY cannot be computed

## Formula

Primary metric:

```text
YoY % = ((recent_12_total / previous_12_total) - 1) * 100
```

Use only calendar-aligned complete months.

## Validity rules

YoY is valid only when:
- there are at least 12 months in each comparison window
- baseline total is greater than zero
- missing data does not invalidate comparability

Default completeness requirement for YoY:
- each 12-month window must have at least 10 observed/inferred-zero months
- if months are missing, calculate only when the same calendar-month positions are available in both years; otherwise mark as unavailable

Do not silently compare 12 months with 10 months.

## Output

```json
{
  "yoy": {
    "previous_total": 100000,
    "recent_total": 118000,
    "growth_pct": 18.0,
    "status": "available",
    "notes": []
  }
}
```

Possible statuses:
- `available`
- `insufficient_data`
- `zero_baseline`
- `non_comparable_periods`

## Acceptance criteria

- Correct positive, negative, and zero growth.
- Zero baseline handled explicitly.
- Missing/non-comparable months prevent misleading YoY.
- Period boundaries are deterministic.
- Existing absolute metrics remain unchanged.

## Test plan

- +20% fixture
- -20% fixture
- no change
- zero baseline
- one missing paired month
- too many missing months
- more than 24 months: use configured recent window consistently

## Deliverables

- YoY logic in `analytics.py`
- unit tests
- methodology formula
