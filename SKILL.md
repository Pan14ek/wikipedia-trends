---
name: wikipedia-trends
description: >
  Analyze Wikipedia pageview interest for an article or topic over time,
  compare Wikipedia language editions, evaluate explicit numeric criteria,
  and generate reproducible JSON, PNG, or one-page PDF reports. Use for
  Wikipedia pageview trend analysis and follow-up comparisons. Do not use
  Wikipedia pageviews as proof of market demand, country demand, willingness
  to pay, or purchase intent.
---

# Wikipedia Trends

## Purpose

Use the project CLI to analyze Wikipedia pageview attention over time and
produce the requested report artifacts. Python owns resolution, calculations,
and report data; the agent routes the request, builds a validated config,
interprets the recorded results, and explains their limits.

## When to Use

Use this skill when the user wants to analyze an article or broader topic,
compare Wikipedia language editions, inspect pageview metrics or explicit
numeric criteria, create JSON/charts/PDF, or refine a previous analysis.
Users do not need to know internal metric or config names.

## When Not to Use

Do not use Wikipedia pageviews as the primary method to estimate market size,
revenue, country demand, willingness to pay, purchase intent, or future
popularity. Do not use this skill for general web trends when the requested
source is not Wikipedia. For mixed requests, provide only the Wikipedia
evidence component and state what it can support.

## Non-Negotiable Rules

- Run every analysis through the project CLI; direct Wikimedia API calls are
  not an alternate analysis path.
- Every analytical number in a user-facing answer must already exist in the
  current Python-generated report. Never derive percentages, averages, ratios,
  rankings, streak lengths, or other metrics from raw observations. Rounding a
  report value for presentation is allowed.
- Use `descriptive_trend` only for within-window direction and endpoint
  changes. Those changes are not YoY growth. Do not claim unavailable growth.
- Describe reliability through explicit quality, completeness, warning, and
  metric statuses; do not invent a composite reliability score or adjective.
- Never invent canonical article titles or silently choose between materially
  different concepts.
- In topic mode, Python's resolver is the semantic authority. Never promote a
  rejected candidate or decide QID equivalence yourself.
- For topic mappings, use canonical source concepts and Wikidata QID sitelinks.
  A missing canonical sitelink stays unresolved; do not search for an
  approximate target-language replacement.
- Never treat `UNKNOWN` as zero or hide unresolved languages, warnings, failed
  quality checks, unavailable metrics, or invalid comparisons.
- Keep a proxy's language-local metrics distinct from like-for-like evidence
  whenever `comparison_equivalent = false`; obtain explicit approval before
  adding a proposed proxy override.
- Do not infer country demand from a Wikipedia language edition or describe
  pageviews as unique people, purchase intent, willingness to pay, or proof of
  market demand.
- Do not invent a threshold or explicit comparison baseline. Standard monthly
  YoY analysis does not require `comparison_period`; an explicit `growth_pct`
  threshold does.
- If the user does not specify artifact preferences, omit the config `output`
  section so `AnalysisConfig` defaults apply. Follow-up analyses preserve the
  prior report's output configuration unless the user changes it.
- For follow-ups, change only explicitly requested fields and preserve the
  previous report's frozen dates unless the user changes the period.
- Validate requested/generated artifacts before claiming they exist.

## Preflight

Before creating a config, determine whether the subject, article/topic mode,
requested language editions, required source language, period and granularity,
explicit thresholds and any required baseline, proxy approval, and requested
outputs are known or safely defaultable. Apply documented defaults rather than
asking for values the user did not need to specify. Read
[`input-schema.md`](references/input-schema.md) when building or changing a
config.

`query.source_language` is the Wikipedia language in which the supplied article
title or topic phrase is resolved. It is independent of requested `languages`
and may be outside them. It is required for multiple target editions. For one
target edition, omit it only when the supplied title or phrase is intentionally
expressed for that edition; runtime inference is not safe for a phrase in a
different language.

## Choose a Workflow

Read only the workflow references relevant to the current request. A request
may require several workflows; apply them together and do not load unrelated
references.

| User intent / situation | Workflow |
|---|---|
| Analyze one specific Wikipedia article | [`article-analysis.md`](references/workflows/article-analysis.md) |
| Analyze a broader topic represented by one or more articles | [`topic-analysis.md`](references/workflows/topic-analysis.md) |
| Compare multiple Wikipedia language editions | [`multi-language-comparison.md`](references/workflows/multi-language-comparison.md) |
| Use exact dates, relative periods, or choose granularity | [`period-selection.md`](references/workflows/period-selection.md) |
| Evaluate growth, thresholds, or explicit measurable criteria | [`criteria-and-thresholds.md`](references/workflows/criteria-and-thresholds.md) |
| Modify a previous analysis while preserving unchanged parameters | [`follow-up-analysis.md`](references/workflows/follow-up-analysis.md) |
| Handle a missing direct equivalent or user-approved proxy | [`proxy-resolution.md`](references/workflows/proxy-resolution.md) |
| Validate JSON, charts, and PDF before returning results | [`artifact-validation.md`](references/workflows/artifact-validation.md) |
| Interpret growth, trends, quality, or comparisons | [`result-interpretation.md`](references/workflows/result-interpretation.md) |

## Run the Analysis

All analyses must use the project CLI. Before execution, follow
[`cli.md`](references/cli.md) for the complete config → CLI → report →
artifact-validation lifecycle. Build a config that matches the input contract
and run:

```bash
python3 <skill-root>/scripts/run.py \
  --config <config.json> \
  --output-dir <output-dir>
```

For installed Skills, use this launcher; it provisions a cached runtime outside
the Skill root and works when the installation is read-only. Do not install the
Skill itself in editable mode. For local development, `scripts/analyze.py`
remains the low-level CLI. Do not call Wikimedia APIs directly or calculate
results manually. Before returning a completed analysis, follow
[`artifact-validation.md`](references/workflows/artifact-validation.md).

## Stop and Clarify

Stop before running when a material concept is ambiguous, a required source
language is unknown, the resolver requires clarification, an explicit
`growth_pct` threshold lacks an unambiguous baseline, or a proposed proxy lacks
approval. Keep a missing canonical sitelink unresolved unless the user
explicitly approves using a proxy. Report CLI or artifact failures directly;
never replace missing evidence with agent judgment.

## Interpret the Result

Use recorded Python output and preserve its statuses. Requested and available
periods are distinct. A not-evaluable criterion is neither a pass nor a
failure. A language edition describes readership of that Wikipedia edition,
not a country. Pageviews count page visits, and topic sums may include repeated
or overlapping readers. Do not turn pageviews into demand, intent, a forecast,
or a composite opportunity score. Before interpreting results, follow
[`result-interpretation.md`](references/workflows/result-interpretation.md).
See [`methodology.md`](references/methodology.md) for metric definitions and
limits.

## Output Contract

Return a concise summary of the subject and mode, language edition(s),
requested/effective period as relevant, Python-generated findings, material
resolution/quality/comparison caveats, and verified paths for requested
artifacts. Follow the artifact workflow when JSON is disabled; do not assume
`analysis.json` exists.

## References

| Need | Reference |
|---|---|
| Build or modify an analysis config | [`input-schema.md`](references/input-schema.md) |
| Execute the analysis CLI and interpret its output | [`cli.md`](references/cli.md) |
| Read or validate `analysis.json` | [`output-schema.md`](references/output-schema.md) |
| Explain metrics, resolution, quality, or interpretation limits | [`methodology.md`](references/methodology.md) |
