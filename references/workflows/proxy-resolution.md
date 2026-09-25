# Proxy Resolution

## Use When

A direct topic representation is unavailable or the user proposes an alternate
article set.

## Inputs

- The missing direct mapping and resolver evidence.
- Proposed proxy article title(s), when applicable.
- Explicit user approval before adding a proxy override.

## Preconditions

- A missing canonical sitelink is not permission to search for a replacement.
- Do not add a non-equivalent override without explicit approval.

## Process

1. Explain which direct mapping is unavailable and identify the proposed
   article(s). State that any proxy measures those selected article(s) only.
2. Ask for approval before adding the override. After approval, configure it
   under `query.article_overrides` and run the project CLI.
3. Let Python compare the override QID set with the canonical source concept
   set. Never determine equivalence yourself.
4. If `comparison_equivalent = false`, retain language-local metrics as proxy
   evidence, exclude that edition from direct comparison, and label it clearly.

## Stop Conditions

- Without approval, do not configure or run the proposed proxy.
- A different QID set must not be described as a direct measurement of the
  original topic or included in like-for-like comparison.

## Output Requirements

State the proxy article(s), what they measure, and whether Python marked them
comparison-equivalent. Preserve the direct-comparison limitation.

## Related References

- [Input schema](../input-schema.md)
- [Output schema](../output-schema.md)
- [Methodology](../methodology.md)
- [Multi-language comparison](multi-language-comparison.md)
