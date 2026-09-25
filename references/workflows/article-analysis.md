# Article Analysis

## Use When

The user refers to one specific Wikipedia concept or page (`query.mode = "article"`).

## Inputs

- Article subject or requested page title.
- One or more requested Wikipedia language editions.
- Source language when more than one edition is requested.
- Period, granularity, and requested outputs when the user specifies them.

## Preconditions

- The article concept is clear enough to resolve.
- A multi-language request has an explicit or safely inferable source language.

## Process

1. Use the requested language as `source_language` for a one-language request.
2. For multiple languages, identify the source edition; do not translate or
   guess a canonical title in another language.
3. Run article resolution through the project CLI. The resolver uses structured
   Wikipedia/Wikidata links to map equivalents.
4. Interpret `resolved`, `partial`, and `requires_clarification` as recorded.
   `partial` means some requested editions have no linked equivalent; resolved
   editions may still have language-local analysis while missing editions stay
   explicit.
5. If multiple editions are requested, also use
   [`multi-language-comparison.md`](multi-language-comparison.md).
6. If custom dates, relative periods, or granularity are involved, also use
   [`period-selection.md`](period-selection.md).

## Stop Conditions

- A disambiguation result or materially ambiguous subject requires user
  clarification before selecting an article.
- Never invent a missing equivalent or suppress a missing language.

## Output Requirements

Name the canonical resolved article(s) and editions from the report. Preserve
partial or clarification status and any comparison limitations.

## Related References

- [CLI execution](../cli.md)
- [Input schema](../input-schema.md)
- [Output schema](../output-schema.md)
- [Methodology](../methodology.md)
