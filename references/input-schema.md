# Input schema

The current JSON input contract accepts both legacy month counts and explicit
inclusive date windows. Unknown fields are rejected
at every level.

```json
{
  "query": {"mode": "article", "value": "Astronomy", "source_language": "en"},
  "languages": ["uk"],
  "period": {"months": 24, "granularity": "monthly"},
  "criteria": {
    "growth": true,
    "normalized_interest": true,
    "stability": true,
    "anomalies": true,
    "confidence_intervals": true
  },
  "output": {"json": true, "charts": true, "pdf": true}
}
```

`query.mode` is either `article` or `topic`; `query.value` is a non-empty
trimmed string. `query.source_language` is optional and is used by M04 article
resolution. It is required when resolving an article into multiple language
editions, since the resolver must not guess which language edition owns a title.
For one requested language it is inferred from that language. For
`query.mode = "topic"`, `query.article_overrides` can replace MediaWiki search
selection for reviewed languages. It is an optional object keyed by a language
included in `languages`; each key supplies one to three unique, non-empty
article titles:

```json
{
  "query": {
    "mode": "topic",
    "value": "learning English",
    "article_overrides": {
      "en": ["English language", "English grammar"]
    }
  },
  "languages": ["en"]
}
```

Article overrides are rejected for article mode. `languages` contains one to
20 unique lowercase codes.
Legacy `period.months` accepts 1 through 120 and defaults to 24 complete
months. Alternatively, specify ISO `start` and `end` dates (both inclusive):

```json
{
  "period": {"start": "2026-08-01", "end": "2026-08-07"},
  "comparison_period": {
    "start": "2026-07-25", "end": "2026-07-31", "granularity": "daily"
  },
  "thresholds": [
    {"name": "traffic floor", "metric": "normalized_interest_mean", "operator": "gte", "threshold": 25}
  ]
}
```

Partial calendar-month date windows default to `daily`; full calendar-month
windows default to `monthly`. Set `granularity` to override that inference.
`months` cannot be combined with explicit dates. “Last month” is resolved by
the agent to the previous complete calendar month before config creation.
Monthly metrics use monthly buckets. Exact date windows require full-day
boundaries for monthly granularity. Growth thresholds require an explicit,
equal-length `comparison_period` of matching granularity that ends before the
analysis window. Thresholds support `growth_pct`, `normalized_interest_mean`,
and `completeness_ratio`, with `gt`, `gte`, `lt`, or `lte` operators.

The `period`, `criteria`, and `output` objects can be omitted; their defaults
are shown above.

Legacy month counts resolve to the latest N complete calendar months. Daily
requests are capped at yesterday if the final requested day is not yet
complete, and the output records requested and available dates separately. A
valid configuration can be checked with:

```bash
python scripts/analyze.py --config examples/astronomy-uk.json
```
