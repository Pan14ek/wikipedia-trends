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

Implemented milestones cover configuration validation, Wikimedia article and
project pageview collection, article resolution, absolute and YoY metrics,
charts, data-quality diagnostics, normalized interest, and robust anomaly
detection, bootstrap YoY confidence intervals, and transparent topic-mode
article selection and aggregation, multi-language comparison, and comparison
charts, and a versioned JSON report contract. The CLI remains an M02 validation
placeholder; assembled analyses and caching remain out of scope until later
milestones. A structured report can also be rendered as a one-page A4 PDF from
its existing metrics and chart, without recalculation.
