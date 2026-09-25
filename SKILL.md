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
2. Collect the requested Wikipedia language editions and complete-month
   period. Use 24 months when no period is specified.
3. Create a JSON configuration matching `examples/` and the validated
   `AnalysisConfig` contract. Preserve unrelated settings when applying a
   follow-up change.
4. Run the Python implementation:

   ```bash
   python scripts/analyze.py --config <config.json> --output-dir <output-dir>
   ```

   If `python` is not available in the shell and the repository virtual
   environment exists, use `.venv/bin/python` with the same arguments.

5. Read the CLI's JSON paths and inspect `analysis.json` before describing
   numeric results. Surface the generated JSON, chart, and PDF requested by
   the user.
6. Preserve warnings, quality failures, unresolved languages, unavailable
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
- For follow-ups, change only the requested configuration fields, then rerun
  the CLI and report the newly generated artifacts.
