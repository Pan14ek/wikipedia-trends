---
name: wikipedia-trends
description: Analyze Wikipedia pageview trends across topics and language editions, create charts, and generate concise reports.
---

# Wikipedia Trends

This skill will eventually invoke `scripts/analyze.py --config <file>` to run
Wikipedia-trend analyses. It must not invent numeric results: all reported
figures must come from implemented, reproducible calculations.

The current project stage provides typed, reproducible components for
configuration validation, article resolution, Wikimedia pageviews, metrics,
charts, quality diagnostics, normalization, and anomaly detection. The CLI
does not yet compose those components into a complete analysis run.
