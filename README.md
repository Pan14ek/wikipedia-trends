# Wikipedia Trends Agent Skill

A reproducible Agent Skill for analyzing Wikipedia pageview trends across articles, topics, and language editions.

Wikipedia Trends turns natural-language research questions into deterministic Wikipedia analyses using Wikimedia data, structured Wikipedia/Wikidata resolution, transparent metrics, explicit quality checks, and reproducible JSON, PNG, and PDF artifacts.

The core design principle is simple:

> **The agent decides what analysis to run. Python owns calculations and correctness-critical decisions.**

---

## Case overview

The goal of this project was to build an Agent Skill that can answer questions about Wikipedia interest over time without relying on an LLM to manually search for pages, calculate metrics, or silently resolve ambiguous concepts.

A naive agent-based implementation creates several risks:

- the model may choose the wrong Wikipedia article;
- equivalent articles in different languages may represent different concepts;
- missing data may accidentally become zero;
- the model may calculate its own percentages or rankings;
- invalid comparisons may still be presented as valid;
- Wikipedia traffic may be incorrectly interpreted as country-level or market demand.

Wikipedia Trends addresses these risks by separating agent orchestration from deterministic analysis.

```text
Natural-language user request
        ↓
Agent Skill
        ↓
Validated AnalysisConfig
        ↓
Deterministic Python pipeline
        ↓
Wikipedia / Wikidata resolution
        ↓
Wikimedia Pageviews
        ↓
Metrics + quality checks
        ↓
Versioned report + artifacts
        ↓
Agent interpretation
```

The LLM is therefore not the analytical engine.

It is the orchestration and explanation layer around a reproducible Python system.

---

## Key design decisions

### 1. Python owns analytical calculations

The agent must not independently calculate:

- percentages;
- averages;
- ratios;
- trend values;
- rankings;
- streak lengths;
- growth metrics.

Every analytical number shown to the user must already exist in the Python-generated report.

This prevents different models from inventing different definitions of the same metric.

---

### 2. Cross-language identity uses Wikidata

Equivalent concepts across Wikipedia editions are resolved through structured Wikipedia and Wikidata relationships.

The system does not rely on LLM-generated translations such as:

```text
English title
→ model translation
→ guessed Czech article
```

Instead:

```text
source Wikipedia concept
→ Wikidata QID
→ target-language sitelink
```

---

### 3. Missing data is not zero

Wikipedia Trends distinguishes:

```text
OBSERVED
ZERO_INFERRED
UNKNOWN
```

An unknown observation is never silently converted to:

```text
0 pageviews
```

because doing so would change totals, growth calculations, and comparisons.

---

### 4. Topic resolution is intentionally conservative

For broader topics, the resolver prefers a false negative over a weak semantic match.

If the evidence is insufficient, the system can return:

```text
requires_clarification
```

instead of selecting an approximately related article.

---

### 5. Invalid comparisons remain invalid

A language-local analysis may still be useful even when a direct cross-language comparison is not valid.

For example:

```text
Polish Wikipedia
→ valid local metrics

Ukrainian Wikipedia
→ unresolved equivalent

comparison
→ comparable = false
```

The unresolved language is not silently removed.

---

### 6. Wikipedia language edition is not a country

Traffic to:

```text
pl.wikipedia
```

means traffic to Polish-language Wikipedia.

It does not automatically mean:

```text
demand in Poland
```

The same applies to all language editions.

---

### 7. Wikipedia attention is not market demand

Wikipedia pageviews can be useful as an attention signal.

They are not direct measurements of:

- sales;
- market size;
- purchase intent;
- willingness to pay;
- unique people;
- country-level demand;
- future popularity.

---

## What Wikipedia Trends can do

Wikipedia Trends can:

- analyze a specific Wikipedia article over time;
- analyze a broader topic represented by one or more articles;
- compare equivalent concepts across Wikipedia language editions;
- calculate absolute pageview metrics;
- calculate supported year-over-year growth;
- calculate deterministic within-window descriptive trends;
- normalize attention relative to total Wikipedia-edition traffic;
- detect unusual spikes;
- calculate bootstrap confidence intervals for supported growth analysis;
- evaluate explicit numerical thresholds;
- report explicit data-quality checks;
- preserve missing and unresolved observations;
- generate JSON reports;
- generate PNG trend charts;
- generate one-page PDF reports;
- continue previous analyses without silently changing unrelated parameters.

Up to **20 Wikipedia language editions** can be requested in one analysis.

---

## Example questions

### Single article

```text
How has interest in astronomy changed in Ukrainian Wikipedia?
```

### Multi-language comparison

```text
Compare interest in intermittent fasting in Polish and Czech Wikipedia
over the last 24 complete months.
```

### Topic analysis

```text
Compare interest in learning English across Polish, Czech, and
Ukrainian Wikipedia.
```

### Reliability-aware analysis

```text
Analyze interest in Nintendo Switch 2 over the last 12 complete months.
Show the main metrics, explain the trend, and tell me how reliable the
conclusion is.
```

### Explicit threshold

```text
Check whether normalized interest is at least 25 pageviews per
1 million Wikipedia pageviews.
```

### Follow-up analysis

```text
Add Ukrainian Wikipedia to the previous comparison.
```

or:

```text
Keep everything else the same, but use 36 months.
```

---

## How it works

The Agent Skill uses progressive workflow selection.

```text
User request
    │
    ▼
SKILL.md
    │
    ├── determine whether the Skill applies
    ├── inspect required inputs
    └── choose relevant workflows
            │
            ▼
references/workflows/*
            │
            ▼
AnalysisConfig
            │
            ▼
scripts/run.py
installed-Skill runtime bootstrap
            │
            ▼
scripts/analyze.py
CLI contract
            │
            ▼
src/wiki_trends/
            │
            ├── resolution
            ├── data collection
            ├── analytics
            ├── normalization
            ├── quality checks
            ├── comparisons
            └── reporting
                    │
                    ▼
        analysis.json / PNG / PDF
                    │
                    ▼
        result interpretation
                    │
                    ▼
              user response
```

The separation is intentional.

### Agent responsibilities

The agent handles:

- interpreting the user request;
- selecting article or topic mode;
- choosing workflows;
- identifying source and target languages;
- building a valid configuration;
- asking for clarification when necessary;
- executing the Skill;
- reading generated results;
- explaining limitations.

### Python responsibilities

Python owns:

- article resolution;
- topic resolution;
- Wikidata identity mapping;
- Pageviews collection;
- aggregation;
- absolute metrics;
- growth calculations;
- descriptive trend calculations;
- normalized interest;
- anomaly detection;
- confidence intervals;
- threshold evaluation;
- data-quality checks;
- multi-language comparison;
- chart generation;
- PDF generation;
- versioned report generation.

---

## Installation

### Install as an Agent Skill

Using an Agent Skills-compatible installer:

```bash
npx skills add Pan14ek/wikipedia-trends
```

The installed Skill requires:

```text
Python >= 3.12
```

For installed Skills, execution goes through:

```text
scripts/run.py
```

The launcher creates or reuses a cached runtime outside the installed Skill directory.

This means the Skill can work even when its installation directory is read-only.

Runtime dependencies are pinned through:

```text
requirements-runtime.lock
```

and the launcher also redirects runtime caches such as Matplotlib configuration to writable user-cache locations.

After installation, the user can simply ask a natural-language question such as:

```text
Compare interest in intermittent fasting in Polish and Czech Wikipedia
over the last two years.
```

---

## Local development

Clone the repository:

```bash
git clone https://github.com/Pan14ek/wikipedia-trends.git
cd wikipedia-trends
```

Install development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Verify the low-level CLI:

```bash
python scripts/analyze.py --help
```

Or verify the installed-Skill launcher:

```bash
python3 scripts/run.py --help
```

---

## Quick start

An example configuration is available at:

```text
examples/astronomy-uk.json
```

Run it through the local development CLI:

```bash
python scripts/analyze.py \
  --config examples/astronomy-uk.json \
  --output-dir output
```

For installed-Skill execution:

```bash
python3 scripts/run.py \
  --config examples/astronomy-uk.json \
  --output-dir output
```

A successful analysis returns exactly one machine-readable CLI payload:

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

Disabled or unavailable outputs remain explicit:

```json
{
  "cli_schema_version": "1.0.0",
  "status": "success",
  "analysis_json": null,
  "charts": [],
  "pdf": null
}
```

CLI process success does not automatically mean that every requested semantic result is valid.

The generated report must still be inspected.

---

## Analysis modes

Wikipedia Trends supports two analysis modes.

### Article mode

Use article mode when the request refers to one specific Wikipedia concept.

Example:

```json
{
  "query": {
    "mode": "article",
    "value": "Astronomy",
    "source_language": "en"
  },
  "languages": ["uk"]
}
```

This means:

```text
resolve "Astronomy" in English Wikipedia
        ↓
identify its canonical concept
        ↓
map it to Ukrainian Wikipedia
        ↓
analyze Ukrainian Wikipedia
```

`source_language` identifies the Wikipedia edition in which the supplied phrase is interpreted.

It is independent from the editions listed in:

```text
languages
```

---

### Topic mode

Topic mode is used for a broader concept that may require multiple Wikipedia articles.

Example:

```json
{
  "query": {
    "mode": "topic",
    "value": "learning English",
    "source_language": "en"
  },
  "languages": ["pl", "cs", "uk"]
}
```

Topic resolution follows:

```text
topic phrase
    ↓
source-language Wikipedia search
    ↓
deterministic semantic evidence
    ↓
accepted canonical concepts
    ↓
Wikidata QIDs
    ↓
target-language sitelinks
```

Search rank alone is not sufficient evidence of semantic relevance.

---

## Source language vs target languages

These are intentionally separate concepts.

```text
source_language
=
the Wikipedia language in which query.value is interpreted

languages
=
the Wikipedia editions whose metrics should be analyzed
```

For example:

```json
{
  "query": {
    "mode": "article",
    "value": "Astronomy",
    "source_language": "en"
  },
  "languages": ["uk"]
}
```

does not request English Wikipedia metrics.

English is only the resolution source.

For multi-language requests, `source_language` is required.

---

## Metrics

Wikipedia Trends deliberately keeps measurements separate instead of combining them into one opaque score.

### Absolute pageviews

The system reports values such as:

- total pageviews;
- mean pageviews per bucket;
- median pageviews;
- maximum;
- minimum;
- completeness.

Missing values remain explicit.

---

### Year-over-year growth

For supported monthly analysis:

```text
YoY % =
((recent 12-month total / previous 12-month total) - 1) × 100
```

The latest two calendar-aligned 12-month windows are used.

If there is not enough comparable data:

```text
growth_pct = null
status = insufficient_data
```

The agent must not calculate its own replacement percentage.

---

### Descriptive window trend

A shorter analysis window may still contain useful descriptive trend evidence even when YoY cannot be calculated.

Python can report:

- first observation;
- last observation;
- endpoint direction;
- endpoint percentage change;
- positive adjacent changes;
- negative adjacent changes;
- unchanged adjacent changes;
- ending consecutive streak;
- peak;
- trough.

For example:

```text
direction = lower_at_end
endpoint_change_pct = -32.1%
ending_streak = decrease / 2 intervals
```

An endpoint change is a description of the selected analysis window.

It is **not YoY growth**.

The agent uses these generated fields directly and must not reconstruct them from raw pageviews.

---

### Normalized interest

Different Wikipedia editions have very different total traffic.

To make relative attention more comparable:

```text
normalized interest =
article or topic pageviews
────────────────────────── × 1,000,000
total project pageviews
```

Unit:

```text
pageviews per 1,000,000 project pageviews
```

This adjusts for Wikipedia-edition scale.

It does not transform Wikipedia readership into country-level demand.

---

### Anomaly detection

Wikipedia Trends uses robust statistical methods to detect unusual pageview observations.

Anomalies are reported separately from trend metrics.

They are not automatically interpreted as caused by:

- a product release;
- news;
- seasonality;
- marketing;
- external events.

Causal explanations require additional evidence.

---

### Confidence intervals

For supported monthly YoY analysis, Wikipedia Trends can calculate a deterministic paired bootstrap confidence interval.

The interval describes variation in the observed pageview series under the implemented statistical procedure.

It does not represent confidence about:

- market demand;
- sales;
- willingness to pay;
- product success.

---

## Quality checks

Instead of producing a hidden numerical confidence score, Wikipedia Trends reports explicit quality checks.

Current checks include:

```text
completeness
period_sufficiency
article_resolution
trend_consistency
spike_sensitivity
comparison_validity
```

Each check has one of:

```text
pass
warning
fail
not_evaluated
```

For example:

```text
completeness = pass
period_sufficiency = warning
article_resolution = pass
comparison_validity = not_evaluated
```

The agent describes these checks directly rather than converting them into an invented score such as:

```text
Reliability: 8/10
```

---

## Multi-language comparison

Wikipedia Trends supports comparisons across **2–20 Wikipedia language editions**.

A valid comparison requires more than simply having pageview values.

The system checks:

- whether every requested equivalent resolved;
- whether concepts are equivalent;
- local completeness;
- shared known periods;
- normalized-data availability where relevant;
- explicit comparison validity.

A comparison can therefore produce:

```text
local metrics = available
comparison.comparable = false
```

This is valid behavior.

Local evidence is preserved without pretending that a like-for-like comparison exists.

---

## Missing language equivalents

If the canonical Wikidata concept does not have a corresponding article in a requested edition:

```text
missing equivalent
→ unresolved
```

The system does not automatically search the target language for something “similar enough”.

It also does not create:

```text
0 pageviews
```

for the missing edition.

---

## Proxy articles

A user may explicitly approve an alternative article as a proxy.

The selected proxy still has its Wikidata identity checked.

If:

```text
comparison_equivalent = false
```

its local metrics may be reported, but it is excluded from a like-for-like comparison.

---

## Criteria and thresholds

Wikipedia Trends can evaluate explicit numerical criteria.

Supported threshold metrics include:

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
      "threshold": 25
    }
  ]
}
```

Possible states:

```text
met
not_met
not_evaluable
```

`not_evaluable` is neither success nor failure.

---

### Growth thresholds

A normal monthly YoY analysis does not require the user to manually provide a baseline.

However, an explicit threshold such as:

```text
Did this topic grow by at least 10%?
```

requires a clear comparison baseline.

The system must not invent that baseline.

---

## Output artifacts

Wikipedia Trends supports:

```text
JSON
PNG
PDF
```

The default output configuration enables all supported artifacts.

If the user does not specify output preferences, the agent should omit the `output` section and allow `AnalysisConfig` defaults to apply.

Example:

```json
{
  "output": {
    "json": true,
    "charts": true,
    "pdf": true
  }
}
```

---

### JSON report

The current report schema is:

```text
schema_version = 2.2.0
```

Major report sections include:

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

The exact resolved input is stored in the report so follow-up analyses can reproduce the previous state.

See:

[`references/output-schema.md`](references/output-schema.md)

---

### PNG charts

For multi-language analysis:

```text
2–6 analyzable languages
→ shared comparison chart

7–20 analyzable languages
→ separate per-language charts
```

Unknown observations are rendered as gaps rather than artificial zero values.

If only part of a multi-language request resolves, presentation artifacts may still be generated from valid analyzable series while the JSON report preserves the unresolved state.

---

### PDF

Wikipedia Trends can produce a compact one-page A4 PDF.

The PDF is intended as a shareable summary.

The JSON report remains the authoritative detailed machine-readable result.

---

## CLI

### Installed Skill

Use:

```bash
python3 <skill-root>/scripts/run.py \
  --config <config.json> \
  --output-dir <output-dir>
```

`scripts/run.py` is a bootstrap layer for installed Skills.

It:

- requires Python 3.12+;
- uses a writable runtime directory;
- reuses cached dependencies;
- does not install the project in editable mode;
- does not write to the Skill directory;
- provides writable cache locations;
- preserves the underlying CLI exit-code and stdout contract.

---

### Low-level development CLI

For a local development checkout:

```bash
python scripts/analyze.py \
  --config <config.json> \
  --output-dir <output-dir>
```

---

### Exit codes

| Exit code | Meaning |
|---|---|
| `0` | Pipeline execution completed |
| `1` | Analysis/runtime failure |
| `2` | Configuration or CLI usage failure |

Exit `0` means that execution completed.

It does **not** imply:

```text
every article resolved
every language resolved
comparison is valid
every criterion is evaluable
all quality checks passed
```

Those states are represented inside the report.

---

## Configuration

Example:

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
  }
}
```

When omitted, stable defaults are applied.

The following sections can normally be omitted when their defaults are appropriate:

```text
period
criteria
output
```

Default period:

```text
latest 24 complete calendar months
```

---

### Exact date windows

Exact inclusive dates are supported:

```json
{
  "period": {
    "start": "2026-08-01",
    "end": "2026-08-31"
  }
}
```

Full calendar-month windows default to monthly granularity.

Partial-month windows default to daily granularity.

---

## Understanding the results

### Requested period vs available period

Wikipedia Trends distinguishes:

```text
requested_period
```

from:

```text
period
```

The first represents what was requested.

The second represents what was actually available for analysis.

Unavailable observations are not fabricated.

---

### UNKNOWN is not zero

```text
UNKNOWN ≠ 0
```

This rule is preserved through aggregation, growth calculations, comparisons, and reports.

---

### Pageviews are not unique readers

Wikipedia Pageviews measures page visits.

A single person may generate multiple views.

Topic-mode aggregation may also include the same person viewing several selected articles.

---

### Language edition is not country

Statements such as:

```text
Polish Wikipedia has higher normalized interest.
```

may be supported.

Statements such as:

```text
People in Poland want this product more.
```

are not supported by Wikipedia pageviews alone.

---

### Descriptive trend is not growth

For a 12-month analysis:

```text
the period ended 32% lower than it began
```

may be a valid Python-produced descriptive endpoint result.

It must not become:

```text
YoY growth = -32%
```

unless the report actually contains a valid YoY metric.

---

## Follow-up analyses

A follow-up starts from the previous report's frozen configuration:

```text
analysis.json.input
```

Example initial request:

```text
Compare intermittent fasting in Polish and Czech Wikipedia
over the last 24 months.
```

Follow-up:

```text
Add Ukrainian Wikipedia.
```

Only the requested field changes.

Another follow-up:

```text
Keep everything else the same, but use 36 months.
```

The period changes, while unrelated configuration remains stable.

Relative date requests from the original analysis are already frozen to exact dates, so time does not silently shift between follow-ups.

---

## Data sources

Wikipedia Trends uses public Wikimedia services:

- MediaWiki;
- Wikidata;
- Wikimedia Analytics Pageviews API.

Pageview analysis uses:

```text
access = all-access
agent = user
```

This follows Wikimedia's standard human-reader Pageviews metric rather than bot traffic.

---

## Cache

Raw Pageviews responses and validated public resolution data can be cached locally.

Default analysis cache:

```text
.cache/wikipedia
```

Custom location:

```bash
WIKIPEDIA_TRENDS_CACHE_DIR=/custom/path
```

The installed runtime itself is cached separately from the Skill installation.

A cache entry is an optimization, not the authoritative analytical result.

Malformed or unusable cache data is not silently accepted.

---

## Project architecture

```text
┌───────────────────────────────────────┐
│               User                    │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│              SKILL.md                 │
│ activation / rules / routing          │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│       references/workflows/           │
│ request-specific workflows            │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│            AnalysisConfig             │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│            scripts/run.py             │
│ installed-Skill runtime bootstrap     │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│          scripts/analyze.py           │
│            CLI 1.0.0                  │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│          src/wiki_trends/             │
│                                       │
│ resolution                            │
│ collection                            │
│ analytics                             │
│ normalization                         │
│ quality                               │
│ comparison                            │
│ reporting                             │
└───────────────────┬───────────────────┘
                    │
                    ▼
┌───────────────────────────────────────┐
│ analysis.json / PNG / PDF             │
│ report schema 2.2.0                   │
└───────────────────────────────────────┘
```

---

## Repository structure

```text
wikipedia-trends/
├── README.md
├── SKILL.md
├── pyproject.toml
├── uv.lock
├── requirements-runtime.lock
│
├── scripts/
│   ├── run.py
│   └── analyze.py
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
│       ├── artifact-validation.md
│       └── result-interpretation.md
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
        ├── ...
        ├── M24-unresolved-partial-artifact-resilience.md
        ├── M25-deterministic-interpretation-quality-runtime-hardening.md
        └── M18.1-inexpensive-model-revalidation-after-remediation.md
```

---

## Documentation responsibilities

| File | Responsibility |
|---|---|
| `SKILL.md` | Agent activation, invariants, orchestration, workflow routing |
| `references/cli.md` | CLI lifecycle and execution contract |
| `references/input-schema.md` | Analysis configuration |
| `references/output-schema.md` | Versioned report schema |
| `references/methodology.md` | Metric and methodology definitions |
| `references/workflows/*` | Request-specific operational workflows |
| `docs/sdd/*` | Specification-driven development milestones |

---

## Testing and verification

Run the deterministic test suite:

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

Check whitespace and patch integrity:

```bash
git diff --check
```

The deterministic suite uses mocked HTTP where appropriate.

Live Wikimedia requests can be useful as smoke tests, but they are not used as the only evidence for correctness because external services and live traffic change over time.

Tests cover areas including:

- configuration validation;
- article resolution;
- topic resolution;
- Pageviews collection;
- missing-data semantics;
- absolute metrics;
- YoY;
- descriptive trends;
- normalization;
- anomalies;
- bootstrap intervals;
- quality propagation;
- multi-language comparison;
- partial resolution;
- charts;
- PDF generation;
- CLI protocol;
- installed-Skill runtime bootstrap;
- follow-up configuration;
- end-to-end scenarios.

---

## Specification-Driven Development

The project was built using Specification-Driven Development.

Each major milestone has a specification under:

```text
docs/sdd/
```

The development flow is:

```text
specification
    ↓
implementation
    ↓
verification
    ↓
next milestone
```

The specifications cover:

```text
project skeleton
configuration
Wikimedia collection
article resolution
metrics
charts
quality checks
normalization
anomaly detection
confidence intervals
topic mode
multi-language comparison
JSON reporting
PDF reporting
cache
E2E scenarios
agent evaluation
flexible periods
topic correctness remediation
Skill orchestration
CLI lifecycle
source-language semantics
partial-resolution resilience
deterministic interpretation
installed-Skill runtime hardening
```

See:

[`docs/sdd/INDEX.md`](docs/sdd/INDEX.md)

---

## Current project status

The core Wikipedia Trends implementation is complete.

Recent remediation work added:

- deterministic descriptive trend fields;
- stronger agent interpretation rules;
- quality-state propagation;
- an installed-Skill runtime launcher;
- read-only Skill installation support;
- runtime dependency locking;
- stronger cross-model safeguards against manual agent analytics.

The remaining project-level acceptance step is:

```text
WT-M18.1
Inexpensive-model revalidation
```

That evaluation is intended to validate the final Skill behavior on fresh model sessions after the latest remediation.

Pre-remediation exploratory model runs are treated as diagnostic evidence, not as final acceptance results.

---

## Known limitations

Wikipedia Trends intentionally keeps its scope narrow.

Current limitations include:

- Wikipedia pageviews are attention signals, not market-demand measurements;
- pageviews are not unique users;
- a Wikipedia language edition is not a country;
- topic aggregates may contain overlapping readers;
- semantic resolution is conservative and may require clarification;
- not every concept exists in every Wikipedia language edition;
- a proxy article may provide local evidence without being equivalent for direct comparison;
- 12 months are not sufficient for the standard two-window YoY analysis;
- recent or historical Wikimedia data can contain missing observations;
- Wikipedia Trends does not explain causal reasons for traffic changes;
- it does not forecast future popularity;
- it does not estimate revenue, sales, willingness to pay, purchase intent, or total addressable market;
- it does not produce an opaque opportunity or reliability score.

These constraints are deliberate.

The goal is reproducible evidence with explicit uncertainty and limitations rather than an unsupported recommendation.

---

## Further documentation

Agent orchestration:

[`SKILL.md`](SKILL.md)

CLI execution:

[`references/cli.md`](references/cli.md)

Configuration:

[`references/input-schema.md`](references/input-schema.md)

Report schema:

[`references/output-schema.md`](references/output-schema.md)

Methodology:

[`references/methodology.md`](references/methodology.md)

Specification index:

[`docs/sdd/INDEX.md`](docs/sdd/INDEX.md)

---

## License

MIT