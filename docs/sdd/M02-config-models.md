# M02 — Config and Domain Models

**Spec ID:** WT-M02  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M01

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Define the stable input contract for analysis requests and the foundational domain models used by later specs.

## In scope

Implement Pydantic models for:

- query
- languages
- period
- criteria
- output options
- analysis config
- monthly pageview point
- resolved article identity

## Input contract

Example:

```json
{
  "query": {
    "mode": "article",
    "value": "Astronomy"
  },
  "languages": ["uk"],
  "period": {
    "months": 24,
    "granularity": "monthly"
  },
  "criteria": {
    "growth": true,
    "normalized_interest": true,
    "stability": true,
    "anomalies": true,
    "confidence_intervals": true
  },
  "output": {
    "json": true,
    "charts": true,
    "pdf": true
  }
}
```

## Validation rules

- `query.mode`: `article | topic`.
- `query.value`: non-empty trimmed string.
- `languages`: 1..20 unique lowercase language codes.
- `period.months`: integer 12..120, default 24.
- `period.granularity`: MVP supports only `monthly`.
- Criteria fields default to `true`.
- Output fields default to `true`.
- Unknown top-level fields should be rejected.
- Duplicate languages must be deduplicated or rejected consistently; prefer rejection with a clear message.
- Invalid config must produce a non-zero CLI exit code and a readable error.

## Defaults

If omitted:

```json
{
  "period": {"months": 24, "granularity": "monthly"},
  "criteria": {
    "growth": true,
    "normalized_interest": true,
    "stability": true,
    "anomalies": true,
    "confidence_intervals": true
  },
  "output": {"json": true, "charts": true, "pdf": true}
}
```

## Date semantics

The requested period always means the latest N complete calendar months. The current incomplete month is excluded.

Expose a helper that returns `[start_month, end_month]` from `months` and an injectable reference date for deterministic testing.

## Required models

At minimum:

```python
AnalysisConfig
QueryConfig
PeriodConfig
CriteriaConfig
OutputConfig
MonthlyPageview
ResolvedArticle
```

`MonthlyPageview` must distinguish a known observation from missing/unknown data.

Recommended shape:

```python
class ObservationStatus(str, Enum):
    OBSERVED = "observed"
    ZERO_INFERRED = "zero_inferred"
    UNKNOWN = "unknown"
```

## CLI behavior

```bash
python scripts/analyze.py --config examples/astronomy-uk.json
```

must parse and validate config, then print a structured placeholder result or validation summary. Real network work is not required yet.

## Acceptance criteria

- Valid configs load successfully.
- Invalid query modes fail.
- Empty query values fail.
- Unsupported granularity fails.
- Invalid month range fails.
- Duplicate languages fail with a useful message.
- Date range uses complete months only.
- Tests cover defaults and validation edge cases.
- Existing M01 behavior remains intact.

## Test plan

Unit tests for:
- minimal valid config
- fully specified config
- default application
- invalid mode
- invalid months
- empty languages
- duplicate languages
- complete-month calculation

## Deliverables

- `src/wiki_trends/config.py`
- model additions in `models.py`
- `examples/astronomy-uk.json`
- tests
- updated `references/input-schema.md`
