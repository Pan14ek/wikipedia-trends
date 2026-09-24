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

This is the M01 project skeleton. It provides package layout, documentation,
and CLI startup only. Wikimedia access, configuration validation, analytics,
charts, reports, and caching are intentionally not implemented yet.
