# M09 — Normalized Interest

**Spec ID:** WT-M09  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M08

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Enable fairer comparison across Wikipedia language editions by normalizing article pageviews against total project traffic.

## In scope

- Extend Wikimedia client with project-level monthly pageviews.
- Compute normalized interest per month.
- Compute period summary of normalized interest.
- Preserve both absolute and normalized metrics.

## Formula

```text
normalized_interest = article_views / project_views * 1_000_000
```

Unit:

`article pageviews per 1,000,000 project pageviews`

## Data alignment

A normalized monthly point is valid only when article and project values are available for the same month and project total > 0.

Do not interpolate missing project totals.

## Client interface extension

Recommended:

```python
get_project_pageviews(
    project: str,
    start_month: str,
    end_month: str
) -> list[MonthlyPageview]
```

If the Wikimedia aggregate endpoint returns daily values, aggregate them to calendar months deterministically inside the client/data layer before normalization.

## Output

```json
{
  "normalized_interest": {
    "unit": "views_per_1m_project_views",
    "monthly": [...],
    "mean": 42.1,
    "median": 39.8
  }
}
```

## Acceptance criteria

- Formula matches hand-calculated fixtures.
- Missing denominator month produces unknown normalized value.
- Zero denominator never causes division-by-zero.
- Absolute metrics remain available.
- Project and article month alignment is tested.
- Methodology explicitly warns that normalization does not convert language traffic into country-level market demand.

## Test plan

- constant denominator
- changing denominator
- missing denominator month
- zero denominator
- non-overlapping month ranges

## Deliverables

- `normalization.py`
- client extension
- tests
- methodology update
