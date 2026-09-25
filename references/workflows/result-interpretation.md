# Result interpretation workflow

## Use when

The user asks what the analysis means, including growth or decline, trend
direction, reliability, language comparisons, or a concise summary of metrics.

## Process

1. Inspect statuses before reading numeric values. Check resolution, requested
   and available periods, quality checks, warnings, criteria, and comparison
   validity.
2. Use `yoy_metrics` only when its status is `available`. Preserve unavailable
   states such as `insufficient_data`, `zero_baseline`, and
   `non_comparable_periods`; do not turn them into zero or a directional claim.
3. Use `period_growth` only when the report records the explicit configured
   `comparison_period`. Describe that baseline as recorded.
4. Use `descriptive_trend` for statements about behavior inside the requested
   window. An endpoint change is descriptive and is not YoY growth. Use the
   exact ending streak only when `ending_streak.intervals` and its direction
   are available.
5. Never calculate percentages, averages, ratios, rankings, streak lengths, or
   custom comparisons from `pageviews[]`. Rounding a Python-produced value for
   display is allowed.
6. Preserve warnings and every non-passing quality status. Explain concrete
   checks instead of assigning a composite reliability score.
7. Do not attribute a spike, decline, or other pattern to an external event,
   seasonality, or cause unless the user asked for external research and the
   cited source supports it.
8. Describe results as attention to the named Wikipedia language edition.
   Do not infer country readership, market demand, sales, or purchase intent
   from edition pageviews.

## Output requirements

State only conclusions supported by fields in the current Python-generated
report. Distinguish standard YoY or explicit-baseline growth from descriptive
within-window change. Include material resolution, coverage, quality, and
comparison limitations.

## Related references

- [`output-schema.md`](../output-schema.md)
- [`methodology.md`](../methodology.md)
- [`criteria-and-thresholds.md`](criteria-and-thresholds.md)
