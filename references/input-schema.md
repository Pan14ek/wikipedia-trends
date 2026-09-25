# Input schema

M02 defines the version-one JSON input contract. Unknown fields are rejected
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
For one requested language it is inferred from that language. `languages`
contains one to 20 unique lowercase codes.
`period.months` is an integer from 12 through 120 and defaults to 24.
Only monthly granularity is supported. The `period`, `criteria`, and `output`
objects can be omitted; their defaults are shown above.

The period is the latest N complete calendar months. The current, incomplete
month is excluded. A valid configuration can be checked with:

```bash
python scripts/analyze.py --config examples/astronomy-uk.json
```
