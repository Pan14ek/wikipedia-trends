---
name: wikipedia-trends
description: Analyze Wikipedia pageview trends across topics and language editions, create charts, and generate concise reports.
---

# Wikipedia Trends analysis skill

Use this skill when a user asks to analyze Wikipedia pageview interest by
article or topic, compare language editions, or create a JSON or PDF report.

## Workflow

1. Clarify the subject when it could identify unrelated concepts, such as
   “Java”. Ask which meaning the user intends before choosing article titles.
2. Collect the requested Wikipedia language editions, period, and granularity.
   Accept ISO start/end dates and treat boundaries as inclusive. “Last month”
   means the previous completed calendar month. Use daily buckets for partial
   calendar-month windows and monthly buckets for full calendar months unless
   the user explicitly requests another supported granularity. Use 24 complete
   months when no period is specified. If the requested end is not yet
   available, let the CLI report both requested and available windows.
3. If the user asks whether a topic meets a definition of “promising”, ask for
   measurable metrics and numeric thresholds. Do not invent a weighted score,
   forecast, or market-demand proxy. If growth is requested without a baseline,
   ask which comparison period to use before running the analysis.
4. For topic mode, ask for the source language of the phrase when more than
   one Wikipedia edition is requested and that language is not clear. The
   Python resolver owns semantic acceptance: use its structured resolved,
   rejected, ambiguous, and missing-sitelink outcomes. Do not validate weak
   candidates yourself or replace a resolver rejection with a direct match.
   If an explicit proxy is proposed, explain the missing direct mapping and
   name the proxy article; ask for approval before adding it as an article
   override. A proxy is measured as the selected article and cannot participate
   in a like-for-like topic comparison.
5. Create a JSON configuration matching `examples/` and the validated
   `AnalysisConfig` contract. For a follow-up, treat the previous
   `analysis.json` `input` as the current request state; change only fields the
   user clarified, and preserve the exact dates already recorded. Never
   silently re-resolve “last month” or another relative period to a newer
   window during a follow-up.
6. Run the project CLI for every analysis:

   ```bash
   python scripts/analyze.py --config <config.json> --output-dir <output-dir>
   ```

   If `python` is not available in the shell and the repository virtual
   environment exists, use `.venv/bin/python` with the same arguments.

   Direct Wikimedia API calls are not a substitute for the CLI workflow.
7. Before describing results, validate and inspect the CLI-produced
   `analysis.json`; verify that each requested/configured chart and PDF exists
   at the exact CLI-reported path, and that a requested PDF is readable. If an
   artifact is missing or invalid, report the failure instead of claiming it
   was created. Surface working paths for every artifact.
8. Preserve warnings, quality failures, unresolved languages, unavailable
   metrics, and comparison limitations in the response.

## Interpretation rules

- Never calculate or estimate metrics in prose. Use only the Python-generated
  `analysis.json`; quote unavailable values as unavailable.
- Report interest in a language edition of Wikipedia. Do not infer country
  demand from the language edition.
- Pageviews are attention signals. Never describe them as purchase intent,
  willingness to pay, or proof of market demand.
- Never invent canonical article titles. Use the resolver's selected article
  records; ask for clarification when resolution is ambiguous.
- Resolver decisions are the semantic boundary. A clarification or rejected
  candidate stays unresolved; never manually promote it based on prose
  reasoning. For example, a broader article about therapeutic fasting is not
  a direct match for intermittent fasting.
- When the user approves a proxy, identify it explicitly and limit every
  metric and conclusion to that selected article. Do not present proxy
  pageviews as a measurement of the original topic, and state that the
  cross-language comparison is not a like-for-like topic comparison.
- For follow-ups, change only the requested configuration fields, then rerun
  the CLI and report the newly generated artifacts.
- The report's requested period and available period are distinct. Describe
  the available window when data is truncated; do not fill unavailable days or
  months with estimated values.
- Treat each configured threshold independently using its recorded
  `met`/`not_met`/`not_evaluable` result. A non-evaluable threshold is not a
  failure or a pass.

## Relevance regression check

For multi-language topic mode, resolve the phrase once in its source language.
The resolver maps the resulting canonical Wikidata QIDs to each requested
edition through sitelinks. A missing sitelink remains unresolved; never search
that target edition for an approximate replacement. Report any explicit proxy
override as language-local article metrics and preserve its non-comparable
status in the response.
