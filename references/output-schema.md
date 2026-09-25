# Output schema

WT-M20 updates the versioned machine-readable report contract. Every JSON report
has `schema_version: "2.1.0"` and validates against
`wiki_trends.report.AnalysisReport` before it is written.

## Top-level contract

```json
{
  "schema_version": "2.1.0",
  "run": {},
  "input": {},
  "resolution": {},
  "sources": [],
  "period": {},
  "requested_period": {},
  "comparison_period": null,
  "criteria": [],
  "languages": {},
  "comparison": null,
  "quality": [],
  "warnings": [],
  "artifacts": {}
}
```

`input` is the resolved `AnalysisConfig` supplied to the run. Relative periods
are frozen into exact dates, so follow-up requests can preserve the original
window. `requested_period` records the full intended inclusive dates;
`period` records the actually available inclusive dates. Both include their
granularity. `comparison_period` is the explicit baseline when configured.
Pageview and normalized-interest series are timestamped daily or monthly.
Threshold definitions appear in `criteria`, and every language reports an
independent `criterion_evaluations` list with `met`, `not_met`, or
`not_evaluable` status. `resolution`
contains exactly one article-resolution outcome or a list of topic resolutions.
Topic resolution records source language, canonical concept QIDs, whether an
override is QID-equivalent for direct comparison, and typed candidate evidence
with acceptance or rejection reasons and metadata fallback languages.
`languages` is keyed by the requested language codes and
contains the pageview series, available metrics, quality checks, anomalies,
confidence interval, and limitations for each edition. `comparison` contains
the M13 output when a multi-language comparison was performed; otherwise it is
`null` rather than a synthetic comparison.

Each `sources` record captures the endpoint family, project, applicable title,
requested period, fetch timestamp, access, agent, granularity, and whether the
evidence came from the network or cache. Raw external API responses are not
included.

## Serialization

`write_analysis_report()` writes UTF-8 JSON with indentation, stable key order,
and unescaped non-ASCII text. Its default destination is
`output/<run-slug>/analysis.json`; an existing run directory receives a numeric
suffix instead of being overwritten. Slugs use a readable period, normalized
topic, and language sequence. For a fixed normalized configuration, input data,
methodology, and random seed, all numeric result fields are deterministic;
timestamps and filesystem paths are intentionally run-specific.
