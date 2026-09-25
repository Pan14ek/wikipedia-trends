# Multi-Language Comparison

## Use When

The request includes two or more Wikipedia language editions.

## Inputs

- Requested language codes.
- Resolved article/topic mapping and source language where required.
- User's comparison question and selected period.

## Preconditions

- Do not equate language-local analysis with a valid direct comparison.
- Topic mode must use the resolver's source concept and QID/sitelink mapping.

## Process

1. Inspect `comparison.comparable`, `comparison.normalized_comparable`,
   `comparison.effective_period`, comparison warnings, and comparison-validity
   quality status in the report.
2. Explain language-local metrics even when available, while clearly stating
   when a direct comparison is invalid or excluded.
3. In topic mode, preserve `comparison_equivalent`. If false, the proxy may
   have language-local metrics but cannot join like-for-like comparison.
4. Consume normalized interest from Python; do not recalculate it. In topic
   mode Python uses one project-wide denominator per language edition.
5. Do not create a synthetic best-market score. Explain only trade-offs tied
   to user-provided criteria.

## Stop Conditions

- Do not invent a direct comparison if `comparable = false`.
- Keep unresolved editions, excluded periods, and proxy exclusions explicit.

## Output Requirements

Distinguish edition-local findings from direct comparison findings. Describe
the effective shared period and material warnings when present. Normalized
interest is not country demand.

## Related References

- [Output schema](../output-schema.md)
- [Methodology](../methodology.md)
- [Proxy resolution](proxy-resolution.md)
