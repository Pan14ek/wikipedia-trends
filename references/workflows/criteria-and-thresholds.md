# Criteria and Thresholds

## Use When

The user asks about growth, explicit numeric thresholds, or measurable
criteria.

## Inputs

- User-specified metric, numeric threshold, and supported operator.
- An explicit baseline period when a `growth_pct` threshold is requested.

## Preconditions

- Do not invent a threshold, composite score, or baseline.
- A standard monthly YoY request is distinct from a `growth_pct` threshold.

## Process

1. For ordinary monthly YoY analysis, `criteria.growth = true` enables
   calendar-aligned YoY output when data permits. It does not require
   `comparison_period`; do not ask for a baseline only because standard YoY was
   requested.
2. An explicit `growth_pct` threshold requires `comparison_period`. The
   baseline must use matching granularity and bucket count and end before the
   main period starts. Clarify if the user's intended baseline is not clear.
3. Supported threshold metrics are `growth_pct`,
   `normalized_interest_mean`, and `completeness_ratio`; supported operators
   are `gt`, `gte`, `lt`, and `lte`. Read the input contract before building
   the config.
4. Report each criterion independently as `met`, `not_met`, or
   `not_evaluable`. Do not treat `not_evaluable` as pass/fail.

## Stop Conditions

- Stop for clarification if an explicit growth threshold has no unambiguous
  equal-length comparison period.
- Do not substitute a generated or inferred threshold.

## Output Requirements

Return the Python-recorded criterion outcomes and relevant warnings without
combining them into an opportunity score.

## Related References

- [Input schema](../input-schema.md)
- [Output schema](../output-schema.md)
- [Methodology](../methodology.md)
