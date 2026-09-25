# Wikipedia Trends Agent Skill

An Agent Skill for reproducible analysis of Wikipedia pageview trends across
topics and language editions.

## Development setup

Requires Python 3.12 or newer.

```bash
python -m pip install -e ".[dev]"
python -m pytest
python scripts/analyze.py --help
```

## Current scope

The CLI assembles article or topic analyses across up to 20 Wikipedia
language editions. It supports legacy complete-month windows and inclusive
ISO-date windows, using daily buckets for partial months and monthly buckets
for complete months by default. Reports distinguish requested from available
coverage, preserve unknown observations, evaluate user-defined numeric
thresholds independently, and emit schema-v2 JSON with optional charts and a
one-page A4 PDF.

## Run an analysis

```bash
python scripts/analyze.py --config analysis.json --output-dir output
```

The command writes a versioned JSON report, PNG trend chart, and one-page PDF.
The default test suite uses mocked HTTP only. A live run is optional and uses
Wikimedia endpoints and the local cache; do not treat live network results as
deterministic CI evidence.

Wikimedia pageviews and public resolution results use a local cache by default
at `.cache/wikipedia`. Set `WIKIPEDIA_TRENDS_CACHE_DIR` to choose another
location. Cache entries are a convenience only: stale or corrupted entries are
ignored and live requests remain authoritative.
