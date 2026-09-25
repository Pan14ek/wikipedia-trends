# M07 — PNG Trend Charts

**Spec ID:** WT-M07  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M06

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Generate readable, deterministic PNG charts from analysis data without embedding business conclusions in the graphic.

## In scope

- monthly trend line chart
- one series for a single-language analysis
- output path management
- clear title, axes, legend when needed
- explicit markers/gaps for unknown data
- file validation

## Out of scope

- multi-language comparison styling (extended in M13)
- PDF layout
- interactive charts

## Chart requirements

- Use `matplotlib`.
- X axis: month.
- Y axis: pageviews.
- Unknown values must not be plotted as zero.
- Do not smooth by default.
- Avoid misleading truncated axes; default y-axis begins at zero unless a documented reason exists.
- Include source label in metadata/caption data, not necessarily as visually dense chart text.
- Use a headless backend suitable for CI.

## API

Recommended:

```python
def render_trend_chart(
    series: list[MonthlyPageview],
    title: str,
    output_path: Path
) -> Path:
    ...
```

## File behavior

- Create parent directories if needed.
- Overwrite only the file assigned to the current run.
- Return the final path.
- Validate that the file exists and is non-empty.

## Acceptance criteria

- Complete series produces valid PNG.
- Unknown month produces a visible gap, not zero.
- Non-ASCII title renders safely.
- Headless CI run succeeds.
- Chart generation is deterministic enough for structural tests; avoid brittle pixel-perfect assertions.

## Test plan

- PNG file signature check
- non-empty file
- gap in input accepted
- no GUI dependency
- temporary-directory output

## Deliverables

- `charts.py`
- tests
- example generated chart excluded from source control unless intentionally kept as fixture
