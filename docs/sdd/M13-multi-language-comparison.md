# M13 — Multi-Language Comparison

**Spec ID:** WT-M13  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M12

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Compare one article/topic across multiple Wikipedia language editions while preventing invalid comparisons caused by mismatched periods or missing data.

## In scope

- analyze 2..20 languages in one run
- align month windows
- compare absolute and normalized metrics
- language-specific warnings
- shared-comparison validity checks
- multi-series chart support

## Comparison rules

- Use the same requested calendar window for all languages.
- A language may continue with warnings if its own completeness permits.
- For direct comparative metrics, use only periods that are valid for every compared language.
- Do not compare one language over 24 months against another over 18 months without making the effective shared period explicit.

## Comparison output

Recommended:

```json
{
  "comparison": {
    "languages": ["pl", "cs"],
    "effective_period": {
      "start": "2024-09",
      "end": "2026-08"
    },
    "comparable": true,
    "warnings": [],
    "metrics_by_language": {...}
  }
}
```

## No overall winner

The Python layer must not emit a “best market” or synthetic opportunity score. It may expose measurable facts such as:
- higher YoY
- higher normalized interest
- more stable series

The agent can explain trade-offs according to user-provided criteria.

## Multi-language chart

Extend chart rendering:
- one line per language
- legend required
- unknown points remain gaps
- title includes topic/article and period
- avoid overcrowding; if > 6 languages, optionally generate a normalized chart plus per-language charts rather than an unreadable single chart

## Acceptance criteria

- 2-language comparison works.
- 3+ language comparison works.
- Missing language equivalent is handled with warning/fail for that language.
- Comparison validity check is explicit.
- Shared period is recorded.
- Multi-language PNG is generated.
- No opaque “winner score” is introduced.

## Test plan

- 2 complete languages
- one language with 1 missing month
- one unresolved language article
- mismatched valid periods
- 7-language chart fallback behavior

## Deliverables

- comparison orchestration
- chart extension
- quality integration
- tests
