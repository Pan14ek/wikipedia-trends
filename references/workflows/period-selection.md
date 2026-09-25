# Period Selection

## Use When

The user supplies exact or relative dates, asks about a period, or selects
granularity.

## Inputs

- Requested start/end dates or a supported relative period.
- Any explicit granularity.
- Existing frozen period from the previous report for follow-ups.

## Preconditions

- Do not ask for a period when the documented default is suitable.
- Exact `start` and `end` boundaries are inclusive and must be supplied
  together.

## Process

1. With no period, use the latest 24 complete calendar months at monthly
   granularity.
2. Resolve “last month” to the previous complete calendar month before config
   creation. Resolve other supported relative wording to exact dates once.
3. Infer monthly granularity for full calendar-month ranges and daily for
   partial-month ranges, unless the user specifies a valid supported choice.
4. Keep requested and available periods distinct. Daily availability ends at
   yesterday; monthly collection excludes the current partial month.
5. On follow-ups, preserve the exact dates frozen in `analysis.json.input`
   unless the user explicitly changes the period.

## Stop Conditions

- Clarify an invalid or materially ambiguous date range rather than silently
  changing it.
- Never fill unavailable buckets or describe the requested window as fully
  observed when it was truncated.

## Output Requirements

Report the available window when it differs materially from the requested
window. Preserve both periods as reported.

## Related References

- [Input schema](../input-schema.md)
- [Output schema](../output-schema.md)
- [Methodology](../methodology.md)
