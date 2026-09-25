# Wikipedia Trends Agent Skill

A reproducible Agent Skill for analyzing Wikipedia pageview trends across articles, topics, and language editions.

Wikipedia Trends resolves Wikipedia concepts, collects Wikimedia Pageviews data, computes transparent trend metrics, compares Wikipedia language editions, and can produce machine-readable JSON, PNG charts, and one-page PDF reports.

It is designed for questions such as:

> “How has interest in astronomy changed in Ukrainian Wikipedia?”

> “Compare interest in intermittent fasting in Polish and Czech Wikipedia over the last two years.”

> “Compare interest in learning English across Polish, Czech, and Ukrainian Wikipedia.”

> “Does this topic meet my minimum growth or normalized-interest threshold?”

The skill combines agent orchestration with a deterministic Python analysis engine. The agent decides what analysis the user is asking for; Python owns concept resolution, data retrieval, calculations, validation, and report generation.

---

## Table of contents

- [What Wikipedia Trends does](#what-wikipedia-trends-does)
- [What it does not tell you](#what-it-does-not-tell-you)
- [How it works](#how-it-works)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Example questions](#example-questions)
- [Analysis modes](#analysis-modes)
- [Metrics](#metrics)
- [Multi-language comparison](#multi-language-comparison)
- [Topic resolution](#topic-resolution)
- [Criteria and thresholds](#criteria-and-thresholds)
- [Output artifacts](#output-artifacts)
- [CLI](#cli)
- [Configuration](#configuration)
- [Understanding the results](#understanding-the-results)
- [Follow-up analyses](#follow-up-analyses)
- [Data source and cache](#data-source-and-cache)
- [Project architecture](#project-architecture)
- [Repository structure](#repository-structure)
- [Development](#development)
- [Testing](#testing)
- [Specification-driven development](#specification-driven-development)
- [Limitations](#limitations)

---

## What Wikipedia Trends does

Wikipedia Trends turns a natural-language research question into a reproducible Wikipedia pageview analysis.

It can:

- analyze one Wikipedia article over time;
- analyze a broader topic represented by one or more Wikipedia articles;
- compare the same concept across Wikipedia language editions;
- measure absolute pageview attention;
- calculate year-over-year growth;
- normalize article or topic attention relative to total traffic in each Wikipedia edition;
- detect unusual spikes;
- calculate bootstrap confidence intervals for supported growth analysis;
- evaluate explicit numeric thresholds;
- distinguish requested data windows from actually available data;
- preserve missing or unknown observations instead of silently converting them to zero;
- generate JSON, PNG, and PDF artifacts;
- preserve the exact resolved configuration so a later follow-up can modify the previous analysis reproducibly.

Wikipedia Trends currently supports up to **20 Wikipedia language editions** in one analysis.

---

## What it does not tell you

Wikipedia pageviews are an **attention signal**.

They are useful for studying how often Wikipedia content is viewed, how that attention changes over time, and how relative attention differs between Wikipedia editions.

They are not a direct measurement of:

- market size;
- revenue opportunity;
- purchase intent;
- willingness to pay;
- number of unique people;
- country-level demand;
- future popularity.

A Wikipedia language edition is also not the same thing as a country.

For example, traffic to Polish Wikipedia measures activity in the Polish-language Wikipedia project. It should not automatically be interpreted as demand from people physically located in Poland.

Wikipedia Trends deliberately keeps these distinctions visible in its reports.

---

## How it works

At a high level:

```text
User request
    │
    ▼
SKILL.md
    │
    ├── determine whether the skill applies
    ├── run preflight checks
    └── select relevant workflows
            │
            ▼
references/workflows/*
            │
            ▼
Build AnalysisConfig
            │
            ▼
Wikipedia Trends CLI
            │
            ├── Wikipedia / Wikidata resolution
            ├── Wikimedia Pageviews collection
            ├── deterministic Python analytics
            └── report generation
                    │
                    ▼
        analysis.json / PNG / PDF
                    │
                    ▼
           artifact validation
                    │
                    ▼
              user response
```

The separation is intentional.

The **agent** handles request interpretation, workflow selection, clarification, and explanation.

The **Python implementation** owns correctness-critical operations such as:

- article and topic resolution;
- Wikidata concept mapping;
- pageview collection;
- aggregation;
- normalization;
- growth calculations;
- anomaly detection;
- confidence intervals;
- threshold evaluation;
- cross-language comparison;
- report generation.

The agent must not recreate these calculations manually.

---

## Installation

### Install as an Agent Skill

If you use an Agent Skills-compatible installer:

```bash
npx skills add Pan14ek/wikipedia-trends
```

The skill is centered around `SKILL.md`, with additional workflow and methodology references under `references/`.

Once installed, ask your agent a Wikipedia trend question in natural language.

For example:

```text
Compare interest in intermittent fasting in Polish and Czech Wikipedia
over the last two years.
```

The agent should select the appropriate workflow, build the analysis configuration, execute the project CLI, inspect the generated report, and return the validated result.

### Clone for local development or direct CLI use

```bash
git clone https://github.com/Pan14ek/wikipedia-trends.git
cd wikipedia-trends
```

Wikipedia Trends requires **Python 3.12 or newer**.

Install the project and development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Then verify the CLI:

```bash
python scripts/analyze.py --help
```

---

## Quick start

### Using an AI agent

After installing the skill, you can ask:

```text
Analyze astronomy interest in Ukrainian Wikipedia over the last 24 months.
```

The skill will determine the required configuration and run the analysis through the project CLI.

A request may involve several workflows. For example:

```text
Compare learning English across Polish, Czech, and Ukrainian Wikipedia
over the last two years.
```

may involve:

```text
topic analysis
+
multi-language comparison
+
period selection
+
artifact validation
```

The user does not need to know those internal workflow names.

### Using the CLI directly

An example configuration already exists at:

```text
examples/astronomy-uk.json
```

Run it with:

```bash
python scripts/analyze.py \
  --config examples/astronomy-uk.json \
  --output-dir output
```

A successful CLI run prints one machine-readable JSON object:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": "output/.../analysis.json",
  "charts": [
    "output/.../trend.png"
  ],
  "pdf": "output/.../report.pdf"
}
```

Disabled outputs are represented explicitly:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": null,
  "charts": [],
  "pdf": null
}
```

See [`references/cli.md`](references/cli.md) for the complete execution contract.

---

## Example questions

### Single article

```text
Show me the Wikipedia pageview trend for astronomy in Ukrainian Wikipedia.
```

### Multiple language editions

```text
Compare intermittent fasting in Polish and Czech Wikipedia over the last
24 months.
```

### Topic analysis

```text
Analyze interest in learning English in Polish, Czech, and Ukrainian Wikipedia.
```

### Growth

```text
How has interest changed year over year?
```

### Explicit criteria

```text
Check whether normalized interest is at least 150 pageviews per million
Wikipedia pageviews.
```

### Exact period

```text
Analyze this topic between 2026-01-01 and 2026-08-31.
```

### Follow-up

After an existing analysis:

```text
Add Ukrainian Wikipedia to the previous comparison.
```

or:

```text
Keep everything else the same, but use the last 36 months.
```

---

## Analysis modes

Wikipedia Trends supports two query modes.

### Article mode

Use article mode when the subject corresponds to one specific Wikipedia concept or article.

Example:

```json
{
  "query": {
    "mode": "article",
    "value": "Astronomy",
    "source_language": "en"
  },
  "languages": ["en", "uk"]
}
```

The resolver identifies the canonical source article and maps equivalent articles to requested language editions through structured Wikipedia and Wikidata links.

It does not rely on LLM-generated title translations.

If the requested title is ambiguous, the analysis can return a structured clarification state instead of silently selecting a meaning.

### Topic mode

Use topic mode when the request describes a broader subject that may be represented by one or more Wikipedia articles.

Example:

```json
{
  "query": {
    "mode": "topic",
    "value": "learning English",
    "source_language": "en"
  },
  "languages": ["en", "pl", "cs", "uk"]
}
```

Topic mode performs semantic candidate selection in the source-language Wikipedia and establishes a canonical concept set using Wikidata identities.

The selected concepts are then mapped to other Wikipedia editions using Wikidata sitelinks.

The resolver deliberately prefers an unresolved result over silently selecting a weak semantic match.

---

## Metrics

Wikipedia Trends keeps different measurements separate instead of collapsing them into one synthetic score.

### Absolute pageviews

Basic traffic measurements are calculated from known observations, including period totals and summary statistics.

Missing observations are not silently treated as zero.

### Year-over-year growth

For supported monthly analyses, Wikipedia Trends compares calendar-aligned periods.

The primary YoY calculation is:

```text
YoY % = ((recent period / previous period) - 1) × 100
```

Insufficient or structurally non-comparable data produces an explicit unavailable status rather than a fabricated percentage.

### Normalized interest

Absolute pageviews are difficult to compare directly across Wikipedia editions because the projects have different total traffic.

Wikipedia Trends can normalize topic or article traffic against total traffic in its own Wikipedia edition:

```text
normalized interest =
article or topic pageviews
────────────────────────── × 1,000,000
total project pageviews
```

The result is expressed as:

```text
pageviews per 1,000,000 Wikipedia project pageviews
```

This provides a scale-aware signal for comparing relative attention across language editions.

It is still not country-level market demand.

### Anomaly detection

Wikipedia Trends can detect unusual traffic spikes using robust statistical methods.

Anomalies are reported separately so one large event does not silently distort the interpretation of the longer-term trend.

### Confidence intervals

For supported monthly YoY analysis, Wikipedia Trends can calculate a deterministic bootstrap interval around the observed growth estimate.

The interval describes uncertainty in the observed Wikipedia pageview series under the implemented bootstrap procedure.

It is not uncertainty about market demand.

### Quality checks

Reports include explicit quality checks rather than a hidden confidence score.

Quality information can cover areas such as:

- completeness;
- period sufficiency;
- article resolution;
- trend consistency;
- spike sensitivity;
- comparison validity.

Checks are reported with explicit statuses such as:

```text
pass
warning
fail
not_evaluated
```

---

## Multi-language comparison

Wikipedia Trends can compare between **2 and 20 Wikipedia language editions**.

A valid cross-language comparison requires more than simply having traffic numbers for several pages.

The system tracks whether:

- the requested concept resolved in each language;
- the compared concepts are equivalent;
- sufficient shared observations exist;
- the available periods overlap correctly;
- normalized values are available when requested.

Language-local metrics may still exist even when a direct comparison is invalid.

For example:

```text
Czech edition:
local metrics available

but

comparison_equivalent = false
```

means those metrics can be discussed locally, but they must not be included in a like-for-like comparison with the canonical topic.

Wikipedia Trends does not emit a synthetic “best market” ranking.

---

## Topic resolution

Topic resolution is one of the most correctness-sensitive parts of the project.

The current topic-mode flow is:

```text
topic phrase
    ↓
source-language Wikipedia search
    ↓
deterministic semantic evidence
    ↓
accepted canonical source concept(s)
    ↓
Wikidata QIDs
    ↓
target-language sitelinks
```

MediaWiki search rank is used for discovery and deterministic ordering, but a highly ranked result is not automatically considered semantically relevant.

Candidate evidence can include:

- canonical article title;
- Wikidata label;
- Wikidata aliases;
- Wikidata description;
- token coverage;
- source language;
- fallback metadata language;
- Wikidata QID.

If evidence is insufficient or materially ambiguous, the resolver returns a structured clarification state.

### Missing equivalents

If a canonical concept has no corresponding sitelink in one requested Wikipedia edition, Wikipedia Trends does not automatically search that edition for a “similar enough” replacement.

The mapping stays unresolved.

### Proxies

A user may explicitly approve another article as a proxy.

When this happens, the selected proxy is resolved and its Wikidata concept set is compared with the canonical source concept set.

If:

```text
comparison_equivalent = false
```

the proxy can still have language-local metrics, but it cannot be presented as a direct like-for-like measurement of the original topic.

---

## Criteria and thresholds

Wikipedia Trends can evaluate explicit numeric criteria.

Supported threshold metrics currently include:

```text
growth_pct
normalized_interest_mean
completeness_ratio
```

Supported operators:

```text
gt
gte
lt
lte
```

Example:

```json
{
  "thresholds": [
    {
      "name": "normalized interest floor",
      "metric": "normalized_interest_mean",
      "operator": "gte",
      "threshold": 150
    }
  ]
}
```

Each criterion is evaluated independently as:

```text
met
not_met
not_evaluable
```

`not_evaluable` is not treated as either success or failure.

Wikipedia Trends does not combine individual criteria into a hidden opportunity score.

### Growth thresholds

There is an important distinction between standard YoY analysis and an explicit growth threshold.

Normal monthly YoY analysis can be enabled with:

```json
{
  "criteria": {
    "growth": true
  }
}
```

An explicit `growth_pct` threshold requires an explicit comparison period with matching granularity and length.

The system does not invent that baseline.

---

## Output artifacts

Each output type is independently configurable.

```json
{
  "output": {
    "json": true,
    "charts": true,
    "pdf": true
  }
}
```

### JSON report

The machine-readable report currently uses:

```text
schema_version: 2.1.0
```

A report contains information such as:

```text
input
resolution
sources
requested_period
period
comparison_period
criteria
languages
comparison
quality
warnings
artifacts
```

The report's `input` contains the resolved configuration used for the run, including exact dates. This makes later follow-up analysis reproducible.

See [`references/output-schema.md`](references/output-schema.md).

### PNG charts

For multi-language analysis:

```text
2–6 languages
→ one shared comparison chart

7–20 languages
→ separate per-language charts
```

Unknown observations appear as gaps rather than artificial zero values.

### PDF report

Wikipedia Trends can generate a one-page A4 PDF containing a compact shareable summary.

The PDF is intentionally bounded. Detailed machine-readable results and warnings remain available in `analysis.json` when JSON output is enabled.

---

## CLI

The CLI is the supported execution path for an analysis.

```bash
python scripts/analyze.py \
  --config <config.json> \
  --output-dir <output-dir>
```

### Arguments

| Argument | Description |
|---|---|
| `--config <FILE>` | Path to a JSON `AnalysisConfig`. Required. |
| `--output-dir <DIR>` | Root directory for generated artifacts. |
| `--help` | Display CLI usage without running an analysis. |

Agents are instructed to always pass `--output-dir` explicitly so the current run's artifact location is unambiguous.

### Exit codes

| Exit code | Meaning |
|---|---|
| `0` | The pipeline completed. |
| `1` | Analysis/runtime failure. |
| `2` | Configuration or CLI usage failure. |

An exit code of `0` does **not** mean that the requested concept necessarily resolved successfully or that a direct comparison is valid.

The generated report may still contain:

```text
requires_clarification
comparison.comparable = false
not_evaluable
quality warnings
unresolved language mappings
truncated data availability
```

This distinction is important for agent reliability.

### CLI protocol

Successful runs expose a machine-readable protocol:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": "...",
  "charts": ["..."],
  "pdf": "..."
}
```

Application-controlled configuration and analysis failures are emitted as structured JSON on `stderr`.

For the full execution lifecycle, recovery rules, path handling, and artifact semantics, see:

[`references/cli.md`](references/cli.md)

---

## Configuration

A complete example:

```json
{
  "query": {
    "mode": "article",
    "value": "Astronomy",
    "source_language": "en"
  },
  "languages": ["uk"],
  "period": {
    "months": 24,
    "granularity": "monthly"
  },
  "criteria": {
    "growth": true,
    "normalized_interest": true,
    "stability": true,
    "anomalies": true,
    "confidence_intervals": true
  },
  "output": {
    "json": true,
    "charts": true,
    "pdf": true
  }
}
```

The following sections can be omitted when their defaults are appropriate:

```text
period
criteria
output
```

The default analysis period is the latest **24 complete calendar months**.

### Exact dates

Exact inclusive date windows are also supported:

```json
{
  "period": {
    "start": "2026-08-01",
    "end": "2026-08-31"
  }
}
```

Partial calendar-month windows default to daily granularity.

Full calendar-month windows default to monthly granularity.

### Source language

A one-language request can infer its source language from that edition.

Multi-language requests require a source language because Wikipedia Trends must know which edition owns the source title or topic phrase.

It does not silently assume English.

For the complete configuration contract, see:

[`references/input-schema.md`](references/input-schema.md)

---

## Understanding the results

### Requested period vs available period

The report distinguishes:

```text
requested_period
```

from:

```text
period
```

The first is what was requested.

The second is what was actually available from the data source.

Wikipedia Trends does not fill unavailable recent observations with estimated values.

### Unknown is not zero

Missing observations are represented explicitly.

```text
UNKNOWN
≠
0 pageviews
```

This distinction is preserved through downstream calculations.

For a topic consisting of multiple selected articles, a topic bucket becomes unknown if any required component is unknown.

### Pageviews are not unique readers

Wikipedia pageviews count page visits, not unique users.

When a topic is represented by several articles, a person may visit more than one selected article. Summed topic pageviews can therefore contain overlapping audiences.

### Language edition is not country

Metrics always refer to a Wikipedia language edition.

They should not automatically be converted into statements such as:

```text
“Poland has more demand than Czechia.”
```

without separate evidence.

### Proxy evidence

A proxy measures the selected proxy article or article set.

It is not silently presented as measurement of the original topic.

---

## Follow-up analyses

Wikipedia Trends supports reproducible follow-up requests.

For example, after:

```text
Compare intermittent fasting in Polish and Czech Wikipedia over the last
24 months.
```

you can ask:

```text
Add Ukrainian Wikipedia.
```

The agent should use the previous report's:

```text
analysis.json.input
```

as the current configuration state.

Only explicitly requested fields are changed.

Importantly, relative periods are already frozen to exact dates in the previous report. A follow-up therefore does not silently move “the last 24 months” to a different calendar window unless the user asks to change the period.

---

## Data source and cache

Wikipedia Trends uses public Wikimedia services for resolution and pageview data, including:

- Wikipedia / MediaWiki;
- Wikidata;
- Wikimedia Analytics Pageviews.

Pageview analysis uses Wikimedia's standard human-reader metric:

```text
access = all-access
agent = user
```

### Local cache

Successful raw Pageviews responses and validated public resolution data are cached locally by default under:

```text
.cache/wikipedia
```

Set:

```bash
WIKIPEDIA_TRENDS_CACHE_DIR=/custom/path
```

to use another cache location.

The cache is an optimization, not an authoritative source.

Stale, corrupted, malformed, or unusable cache entries are ignored and can be replaced by live data.

Reports record whether relevant evidence came from:

```text
network
```

or:

```text
cache
```

---

## Project architecture

Wikipedia Trends separates orchestration from deterministic analysis.

```text
┌─────────────────────────────────────┐
│              SKILL.md               │
│ activation, routing, global rules   │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│        references/workflows/        │
│ article / topic / comparison / ...  │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│             AnalysisConfig          │
│       references/input-schema.md    │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│          scripts/analyze.py         │
│              CLI 1.0.0              │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│          src/wiki_trends/           │
│ resolver / collection / analytics   │
│ comparison / quality / reporting    │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ JSON report / PNG charts / PDF      │
└─────────────────────────────────────┘
```

The main design principle is:

> The agent decides what workflow to run. Python owns calculations and correctness-critical runtime decisions.

---

## Repository structure

```text
wikipedia-trends/
├── SKILL.md
├── README.md
├── pyproject.toml
│
├── references/
│   ├── cli.md
│   ├── input-schema.md
│   ├── output-schema.md
│   ├── methodology.md
│   │
│   └── workflows/
│       ├── article-analysis.md
│       ├── topic-analysis.md
│       ├── multi-language-comparison.md
│       ├── period-selection.md
│       ├── criteria-and-thresholds.md
│       ├── follow-up-analysis.md
│       ├── proxy-resolution.md
│       └── artifact-validation.md
│
├── scripts/
│   └── analyze.py
│
├── src/
│   └── wiki_trends/
│
├── examples/
│   └── astronomy-uk.json
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
│
└── docs/
    └── sdd/
```

### Documentation responsibilities

| File | Purpose |
|---|---|
| `SKILL.md` | Agent activation, orchestration, invariants, and workflow routing |
| `references/cli.md` | Agent-facing execution lifecycle and CLI contract |
| `references/input-schema.md` | Valid analysis configuration |
| `references/output-schema.md` | Machine-readable JSON report contract |
| `references/methodology.md` | Metric definitions, resolution rules, and methodological limits |
| `references/workflows/*` | Request-specific operational workflows |
| `docs/sdd/*` | Specification-driven development history and milestone contracts |

---

## Development

Requires:

```text
Python >= 3.12
```

Runtime dependencies include:

```text
httpx
matplotlib
pydantic
reportlab
```

Development dependencies include:

```text
pytest
mypy
ruff
pypdf
```

Install:

```bash
python -m pip install -e ".[dev]"
```

Run CLI help:

```bash
python scripts/analyze.py --help
```

---

## Testing

Run the test suite:

```bash
python -m pytest
```

Lint:

```bash
ruff check .
```

Type checking:

```bash
mypy
```

Check whitespace errors:

```bash
git diff --check
```

The default automated suite uses mocked HTTP for deterministic tests.

A live Wikimedia run is useful as a smoke test but should not be treated as deterministic CI evidence because external data and network conditions can change.

The test suite includes coverage for:

- configuration validation;
- Wikimedia pageview collection;
- article resolution;
- topic semantic resolution;
- aggregation;
- normalization;
- growth;
- anomalies;
- confidence intervals;
- quality checks;
- charts;
- PDF generation;
- CLI protocol;
- multi-language comparisons;
- multi-chart output;
- end-to-end scenarios.

---

## Specification-driven development

Wikipedia Trends is developed using Specification-Driven Development.

Milestone specifications live under:

```text
docs/sdd/
```

The project was built incrementally through specifications covering areas such as:

```text
project skeleton
configuration
Wikimedia client
article resolution
metrics
quality
normalization
anomalies
confidence intervals
topic mode
multi-language comparison
reporting
cache
E2E scenarios
agent evaluation
flexible periods
topic correctness remediation
skill orchestration
agent-friendly CLI execution
```

See:

[`docs/sdd/INDEX.md`](docs/sdd/INDEX.md)

for the current specification index.

---

## Limitations

Wikipedia Trends intentionally keeps its scope narrow.

Current limitations include:

- Wikipedia pageviews are an attention signal, not a market-demand measurement;
- language editions cannot be equated directly with countries;
- topic totals may contain overlapping readers across selected articles;
- semantic resolution is deliberately conservative and may ask for clarification instead of forcing a weak match;
- not every Wikipedia concept exists in every language edition;
- proxy articles may provide local evidence without being valid for direct comparison;
- recent Wikimedia data can be incomplete or unavailable;
- the project does not currently forecast future popularity;
- the project does not estimate purchase intent, willingness to pay, revenue, or total addressable market.

These constraints are intentional. The goal is reproducible evidence with explicit limitations rather than an opaque recommendation score.

---

## Further reference

For agent orchestration:

[`SKILL.md`](SKILL.md)

For CLI execution:

[`references/cli.md`](references/cli.md)

For configuration:

[`references/input-schema.md`](references/input-schema.md)

For report structure:

[`references/output-schema.md`](references/output-schema.md)

For methodology:

[`references/methodology.md`](references/methodology.md)

For development specifications:

[`docs/sdd/INDEX.md`](docs/sdd/INDEX.md)