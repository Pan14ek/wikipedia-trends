# Follow-Up Analysis

## Use When

The user modifies a previous analysis, such as adding an edition, changing a
period or output, or adding a criterion.

## Inputs

- Previous report's `analysis.json.input`.
- Fields explicitly changed by the user.
- Any additional inputs required by a newly requested workflow.

## Preconditions

- Use the previous report input as the configuration state; relative periods
  there are already frozen to exact dates.
- If the previous input is unavailable, ask for it or the missing configuration
  details rather than assuming unrelated settings.

## Process

1. Copy the prior input state and change only explicitly requested fields.
2. Preserve all unrelated settings and exact dates unless the user changes
   them. This includes the previous `output` configuration; do not reset
   artifact preferences during a follow-up unless the user requests that
   change.
3. Load workflows for new requirements. For example, adding an edition also
   requires [`multi-language-comparison.md`](multi-language-comparison.md).
4. Validate the updated config, rerun the CLI, and use only the new run's
   output artifacts. Never manually edit prior results.

## Stop Conditions

- Clarify when prior state is missing and cannot be reconstructed safely.
- Apply the relevant stop conditions for any newly added workflow.

## Output Requirements

Summarize the requested changes and findings from the new run. Link to verified
new artifacts; do not conflate them with the previous run.

## Related References

- [CLI execution](../cli.md)
- [Input schema](../input-schema.md)
- [Output schema](../output-schema.md)
- [Artifact validation](artifact-validation.md)
