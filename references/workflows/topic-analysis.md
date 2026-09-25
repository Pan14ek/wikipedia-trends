# Topic Analysis

## Use When

The user wants a broader topic represented by one or more Wikipedia articles
(`query.mode = "topic"`).

## Inputs

- Topic phrase and requested language editions.
- Source language when more than one edition is requested.
- Any explicitly approved article overrides and requested analysis options.

## Preconditions

- For a single edition, its language may be inferred as the source language.
- For multiple editions, the topic phrase's source language must be known; do
  not silently assume English.

## Process

1. Run the project CLI and consume its structured resolver decisions. Python's
   resolver is the semantic authority; candidate evidence is for explanation
   and audit, not agent re-scoring.
2. Follow the current flow: source-language search, deterministic semantic
   evidence, accepted source concepts, canonical Wikidata QIDs, and target
   language sitelinks. See methodology for details.
3. Handle `resolved` and `requires_clarification` results. For an unresolved
   representation, read the structured reason and stop analysis for it. Common
   reasons include disambiguation, ambiguous candidates, insufficient
   semantic evidence, missing canonical sitelink, invalid override, and no
   valid candidates.
4. Treat accepted/rejected candidate evidence, search rank, exact title/label/
   alias signals, token coverage, metadata languages, and canonical QIDs as
   recorded audit evidence only. Never manually accept a rejected candidate.
5. Map target editions using resolver-produced Wikidata sitelinks. A missing
   sitelink stays unresolved; do not run approximate target-language search.
6. Do not aggregate article series or calculate normalized interest yourself.
   Consume Python output; if any selected component is `UNKNOWN`, that topic
   bucket is `UNKNOWN`.
7. For two or more editions, also use
   [`multi-language-comparison.md`](multi-language-comparison.md). For custom
   periods or granularity, also use
   [`period-selection.md`](period-selection.md). For a missing direct mapping
   or proposed alternative, also use [`proxy-resolution.md`](proxy-resolution.md).

## Stop Conditions

- Stop for a `requires_clarification` result and explain its structured reason.
- Never replace a resolver rejection or missing sitelink with an agent-selected
  direct match.
- Proxy overrides require the separate proxy workflow and user approval.

## Output Requirements

Report the resolver's topic status, canonical source concepts and mapping
limitations. Preserve unknown topic buckets and proxy status from Python.

## Related References

- [CLI execution](../cli.md)
- [Input schema](../input-schema.md)
- [Output schema](../output-schema.md)
- [Methodology](../methodology.md)
