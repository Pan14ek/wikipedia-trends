# Wikipedia Trends — SDD Implementation Pack

This directory contains the implementation specifications for the Wikipedia Trends Agent Skill.

## Product goal

Build a self-contained Agent Skill that lets an AI agent analyze Wikipedia pageview trends, compare one topic across one or more Wikipedia language editions, generate charts, produce a one-page PDF report, and rerun the same research with changed parameters.

## MVP baseline decisions

- Python 3.12+
- Agent Skill directory contains all project-owned code and materials.
- CLI accepts a JSON config.
- Default analysis period: 24 complete calendar months.
- Granularity: monthly.
- Two query modes in MVP:
  - `article`
  - `topic`
- Supported outputs:
  - `analysis.json`
  - one or more PNG charts
  - one-page PDF
- Local filesystem cache.
- Metrics:
  - absolute pageviews
  - mean and median monthly views
  - YoY growth
  - normalized interest relative to total language-edition traffic
  - trend stability indicators
  - anomaly detection
  - bootstrap confidence interval for YoY
- Data quality is expressed through explicit checks with `pass`, `warning`, or `fail`; no synthetic “confidence score”.
- Missing data may be tolerated if comparison remains methodologically valid.
- MVP is complete only when the three original product scenarios work end-to-end and the result is validated on at least one inexpensive tool-capable agent model.

## Planned project structure

```text
wikipedia-trends/
├── SKILL.md
├── README.md
├── pyproject.toml
├── uv.lock
├── scripts/
│   └── analyze.py
├── src/
│   └── wiki_trends/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── models.py
│       ├── article_resolver.py
│       ├── wikipedia_client.py
│       ├── cache.py
│       ├── analytics.py
│       ├── normalization.py
│       ├── anomalies.py
│       ├── confidence.py
│       ├── quality.py
│       ├── charts.py
│       └── report.py
├── references/
│   ├── methodology.md
│   ├── input-schema.md
│   └── output-schema.md
├── assets/
│   └── report-template.md
├── examples/
└── tests/
    ├── fixtures/
    ├── unit/
    ├── integration/
    └── e2e/
```

## Global implementation conventions

- Prefer pure Python and portable libraries.
- Default package choices:
  - `pydantic>=2` for config/schema validation
  - `httpx` for HTTP
  - `matplotlib` for charts
  - `reportlab` for PDF generation
  - `pytest` for tests
- Keep deterministic behavior where possible.
- Network code must be isolated from analytics code.
- Numeric calculations must be performed by Python, not by the LLM.
- The CLI must return non-zero exit codes for invalid configs or failed analyses.
- JSON outputs must be machine-readable and versioned.
- Do not add a database, web UI, forecasting, Google Trends, Reddit/YouTube data, or distributed processing in MVP.

## Spec order

1. M01 — Project skeleton
2. M02 — Config + models
3. M03 — Wikimedia Pageviews client
4. M04 — Article resolver
5. M05 — Absolute metrics
6. M06 — YoY
7. M07 — Charts
8. M08 — Quality checks
9. M09 — Normalized interest
10. M10 — Anomaly detection
11. M11 — Confidence intervals
12. M12 — Topic mode
13. M13 — Multi-language comparison
14. M14 — JSON report schema
15. M15 — PDF
16. M16 — Cache
17. M17 — E2E scenarios
18. M18 — Agent evaluation

Each spec should be implemented and accepted before moving to the next one.
