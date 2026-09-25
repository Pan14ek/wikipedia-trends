# Output schema

M14 defines the versioned machine-readable report contract. Every JSON report
has `schema_version: "1.0.0"` and validates against
`wiki_trends.report.AnalysisReport` before it is written.

## Top-level contract

```json
{
  "schema_version": "1.0.0",
  "run": {},
  "input": {},
  "resolution": {},
  "sources": [],
  "period": {},
  "languages": {},
  "comparison": null,
  "quality": [],
  "warnings": [],
  "artifacts": {}
}
```

`input` is the normalized `AnalysisConfig` supplied to the run. `resolution`
contains exactly one article-resolution outcome or a list of language-local
topic resolutions. `languages` is keyed by the requested language codes and
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
