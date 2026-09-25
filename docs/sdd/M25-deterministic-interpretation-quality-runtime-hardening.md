# M25 — Deterministic Interpretation, Quality Propagation, and Installed-Skill Runtime Hardening

**Spec ID:** WT-M25  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Draft — requires approval before implementation  
**Depends on:** WT-M20, WT-M21, WT-M22, WT-M22.1, WT-M23, WT-M24  
**Triggered by:** post-WT-M24 cross-model exploratory evaluation using the Nintendo Switch 2 scenario  
**Precedes:** fresh WT-M18.1 revalidation on a new frozen commit  
**Primary risks addressed:** agent-created analytics outside Python, unsupported narrative trend claims, incomplete quality propagation, and fragile execution from read-only Skills Manager installations

## SDD rule

This specification defines remediation prompted by observed agent behavior after WT-M20–WT-M24.

It is intentionally broader than a documentation-only change because the observed failures have three different causes:

1. the report does not expose enough deterministic descriptive trend evidence for a 12-month window when YoY is unavailable;
2. the pipeline does not propagate already-known resolution/comparison state into all applicable quality checks;
3. the installed Skill does not expose one robust, writable, dependency-aware launcher, causing agents to improvise environment recovery.

Implementation must not begin until this specification is approved.

WT-M18.1 is not considered completed by the exploratory Nintendo Switch 2 runs. After WT-M25 is implemented and verified, WT-M18.1 must be rerun from a new frozen commit.

---

# 1. Evidence that triggered WT-M25

Two independent model runs were performed with the same natural-language task:

```text
Проаналізуй інтерес до Nintendo Switch 2 у Wikipedia за останні 12 повних місяців.
Покажи основні метрики, динаміку інтересу та поясни, чи можна говорити про
зростання або спад уваги до теми.

Також коротко поясни, наскільки надійним є цей висновок і які є обмеження
даних. Не прирівнюй Wikipedia pageviews до продажів, популярності консолі на
ринку або наміру купити її.
```

Both successful analyses resolved the English Wikipedia article `Nintendo Switch 2`,
used the same 12 complete months (2025-09 through 2026-08), and produced the same
underlying pageview data.

Observed monthly values:

```text
2025-09  128863
2025-10  117568
2025-11  120937
2025-12  135545
2026-01  115543
2026-02  104737
2026-03  137994
2026-04  112784
2026-05  104997
2026-06  108090
2026-07   90074
2026-08   87467
```

The generated report correctly recorded:

```text
total_views = 1,364,599
completeness = 12/12 = 100%
yoy_metrics.status = insufficient_data
yoy_metrics.growth_pct = null
period_growth = null
confidence_interval.status = unavailable
positive adjacent changes = 4/11
anomalies = []
```

The exploratory runs then exposed the following problems.

---

# 2. Problem statement

## 2.1 P1 — Agent-created analytics escaped Python authority

One evaluated model correctly read `yoy_metrics.status = insufficient_data`, but
then independently calculated and presented new percentages:

```text
first month → last month: about -32.1%
second half → first half: about -11.3%
last three months → first three months: about -22.2%
```

The arithmetic was numerically correct, but these metrics were not present in
`analysis.json`.

This violates the core architecture:

```text
Python owns calculations.
Agent owns routing, inspection, and explanation.
```

The problem is not limited to fabricated arithmetic. Even correct arithmetic is
a contract violation when the model invents a new metric definition.

### Required correction

The agent must never create a numeric analytical metric from raw pageview
observations.

If a descriptive number is useful for normal user language, Python must compute
and expose it under a stable, named, documented field.

---

## 2.2 P2 — Narrative trend claims were not machine-verifiable

Another evaluated model avoided custom percentages but stated that pageviews
fell for four consecutive months after the March 2026 peak.

The actual series is:

```text
Mar 137994
Apr 112784  ↓
May 104997  ↓
Jun 108090  ↑
Jul  90074  ↓
Aug  87467  ↓
```

Therefore a four-month uninterrupted decline did not occur.

The model produced a plausible prose pattern by visually reasoning over raw
monthly values instead of using a deterministic report field.

### Required correction

The report must expose the descriptive trend facts that an agent is allowed to
state, including endpoint direction and consecutive ending streaks.

The agent must not infer a streak, turning point, percentage, or trend duration
from raw observations if Python does not expose that derived fact.

---

## 2.3 P3 — Article-resolution quality contradicted the resolution object

Both runs recorded a structured successful resolution:

```text
status = resolved
canonical article = Nintendo Switch 2
project = en.wikipedia
Wikidata QID = Q122761124
```

At the same time, the language-level quality report stated:

```text
article_resolution.status = not_evaluated
Article resolution was not supplied...
```

The current pipeline calls conceptually:

```python
evaluate_quality(series, yoy_metrics=yoy)
```

without supplying the already-computed `ArticleResolution`.

This is a pipeline propagation defect.

### Required correction

For article mode, applicable language-level quality checks must receive the
structured resolver result already held by the pipeline.

A resolved article must not be reported as `article_resolution = not_evaluated`.

---

## 2.4 P4 — Multi-language comparison validity is computed after language quality

The current pipeline builds each `LanguageReport.quality` before it computes the
multi-language `comparison`.

Therefore `evaluate_quality(...)` cannot receive M13's
`comparison_validity` result during initial language-report construction.

For single-language analyses, `comparison_validity = not_evaluated` is correct.
For a real multi-language analysis, however, language quality should reflect the
already-known M13 comparison-validity result.

### Required correction

Pipeline ordering must make comparison validity available before the final
language quality reports are frozen, or quality must be deterministically
reconciled after comparison construction.

---

## 2.5 P5 — Installed-Skill runtime execution is fragile

The Skills Manager / Codex-installed Skill was readable, but a model encountered:

```text
python                         → command not found
python3                        → pydantic missing
bundled Codex Python           → httpx missing
pip install -e <skill-root>    → failed on write-protected egg-info
```

The model eventually succeeded by:

```text
creating a writable local venv
installing dependencies there
setting PYTHONPATH to <skill-root>/src
setting writable cache/config paths
running scripts/analyze.py
```

This recovery demonstrated agent capability, but it should not be necessary for
normal Skill use.

The current documentation says to use the Python environment already configured
for the Skill, but a Skills Manager installation does not guarantee that such an
environment exists.

### Required correction

The repository must provide one supported, read-only-install-safe launcher that:

```text
does not modify the installed Skill directory
uses a writable runtime/cache directory
ensures runtime dependencies are available
sets a writable Matplotlib config/cache location
preserves the WT-M22 CLI stdout/stderr/exit-code contract
```

Agents must not need to improvise `pip`, `PYTHONPATH`, or interpreter fallback
sequences.

---

## 2.6 P6 — Agent output choices can drift from documented defaults

The same user request produced different artifact choices:

```text
run A: JSON only
run B: JSON + chart
```

The current `AnalysisConfig` defaults are:

```json
{
  "output": {
    "json": true,
    "charts": true,
    "pdf": true
  }
}
```

The user did not request artifact suppression.

### Required correction

The Skill must state clearly:

```text
If the user does not specify output artifact preferences, omit `output` from the
config and let AnalysisConfig defaults apply.
```

An agent may explicitly change output flags only when:

- the user requests or rejects a particular artifact; or
- a documented workflow requires a different setting.

This removes unnecessary model-specific config variation.

---

# 3. Goals

WT-M25 must make this lifecycle reliable:

```text
user asks a natural trend question
    ↓
agent builds config without inventing semantics
    ↓
one documented installed-skill launcher executes Python
    ↓
Python returns deterministic metrics + descriptive trend evidence
    ↓
quality checks reflect already-known resolver/comparison state
    ↓
agent reports only Python-produced numerical findings
    ↓
agent may paraphrase deterministic status fields
    ↓
no manual analytics or unsupported sequence claims
```

The implementation must specifically prevent recurrence of:

```text
custom 32.1 / 11.3 / 22.2 calculations outside Python
"four months in a row" when the series contains an intervening increase
resolved article + article_resolution not_evaluated contradiction
ad-hoc dependency installation into or around the Skill directory
silent output-default overrides
```

---

# 4. Non-goals

WT-M25 does not:

- change Wikimedia APIs;
- change raw pageview collection semantics;
- change M20 topic semantic selection rules;
- change M23 source-language semantics;
- turn Wikipedia attention into sales, demand, or purchase intent;
- create an opaque reliability/confidence score;
- create an "opportunity score";
- introduce linear-regression forecasting;
- infer causality for spikes or declines;
- make a 12-month window equivalent to YoY;
- allow the agent to calculate missing metrics manually;
- require a specific LLM vendor;
- vendor compiled Python binaries into the Skill.

---

# 5. Terminology

## 5.1 Growth

Within Wikipedia Trends, the word **growth** refers only to a supported
Python-produced growth metric:

```text
yoy_metrics.growth_pct
```

or:

```text
period_growth.growth_pct
```

when an explicit comparison period is supplied.

A descriptive first-to-last change inside one analysis window is not called
YoY growth.

---

## 5.2 Descriptive window trend

A deterministic summary of how the observed series behaves inside the requested
window.

It is descriptive evidence only.

It must not be presented as:

- YoY growth;
- market growth;
- future growth;
- causal evidence.

---

## 5.3 Agent-created analytics

Any numerical analytical value produced by the LLM from lower-level values
instead of copied from a Python-generated report field.

Examples:

```text
(last / first - 1) * 100
mean(last 3) / mean(first 3)
second half vs first half
ratio between arbitrary peaks
custom trend score
```

These are forbidden unless the Python report explicitly exposes the metric.

---

# 6. Deterministic descriptive trend model

## 6.1 New domain model

Add a typed Python-produced descriptive trend object.

Recommended model names:

```python
DescriptiveTrend
DescriptiveTrendStatus
WindowDirection
EndpointChangeStatus
TrendStreakDirection
```

The exact class names may vary if repository naming conventions require it, but
the serialized field contract below is normative.

Each `LanguageReport` gains:

```json
"descriptive_trend": {
  "status": "available",
  "first": {
    "timestamp": "2025-09-01",
    "views": 128863
  },
  "last": {
    "timestamp": "2026-08-01",
    "views": 87467
  },
  "direction": "lower_at_end",
  "endpoint_change_status": "available",
  "endpoint_change_pct": -32.12403870777493,
  "comparable_adjacent_pairs": 11,
  "positive_adjacent_changes": 4,
  "negative_adjacent_changes": 7,
  "unchanged_adjacent_changes": 0,
  "ending_streak": {
    "direction": "decrease",
    "intervals": 2,
    "start": "2026-06-01",
    "end": "2026-08-01"
  },
  "peak": {
    "timestamp": "2026-03-01",
    "views": 137994
  },
  "trough": {
    "timestamp": "2026-08-01",
    "views": 87467
  },
  "notes": [
    "Descriptive window trend only; this is not a YoY growth metric."
  ]
}
```

For the Nintendo fixture above, these values are normative.

---

## 6.2 Endpoint-change semantics

`endpoint_change_pct` is calculated only by Python:

```text
((last_requested_bucket_views / first_requested_bucket_views) - 1) * 100
```

It is available only when:

- the first requested bucket is known;
- the last requested bucket is known;
- the first requested value is greater than zero.

If the first requested bucket is zero:

```text
endpoint_change_status = zero_baseline
endpoint_change_pct = null
```

If either requested boundary is `UNKNOWN`:

```text
endpoint_change_status = insufficient_data
endpoint_change_pct = null
direction = unknown
```

Do not silently substitute the first or last *known* bucket for a missing
requested boundary.

---

## 6.3 Direction semantics

When both requested boundary buckets are known:

```text
last > first  → higher_at_end
last < first  → lower_at_end
last == first → unchanged
```

This is a descriptive endpoint direction.

It must not be serialized as `growth_direction`.

---

## 6.4 Adjacent-change semantics

Adjacent comparisons are valid only for actual adjacent calendar buckets.

An `UNKNOWN` bucket breaks adjacency.

For monthly data:

```text
Jan known
Feb UNKNOWN
Mar known
```

must not create a Jan→Mar adjacent comparison.

The report records:

```text
comparable_adjacent_pairs
positive_adjacent_changes
negative_adjacent_changes
unchanged_adjacent_changes
```

These values become the canonical source for the existing
`trend_consistency` quality check.

The quality check must not independently recalculate a different count.

---

## 6.5 Ending streak semantics

`ending_streak` describes only the uninterrupted adjacent transitions ending at
the final requested bucket.

Example:

```text
May 104997
Jun 108090  ↑
Jul  90074  ↓
Aug  87467  ↓
```

produces:

```json
{
  "direction": "decrease",
  "intervals": 2,
  "start": "2026-06-01",
  "end": "2026-08-01"
}
```

It does not produce a four-month decline.

An `UNKNOWN` value breaks a streak.

If fewer than two known adjacent ending buckets exist:

```text
direction = none
intervals = 0
```

---

## 6.6 Peak and trough

Peak/trough are deterministic descriptive values from known observations.

Ties must be resolved deterministically:

```text
use the earliest timestamp among equal maxima/minima
```

They do not imply causality or trend direction.

---

## 6.7 Daily granularity

The same object may be produced for daily analysis.

Adjacency means consecutive calendar days.

Field names must remain granularity-neutral (`timestamp`, not `month`).

---

# 7. Report schema impact

## 7.1 Report schema version

Adding `descriptive_trend` is a report-schema change.

Bump:

```text
analysis report schema: 2.1.0 → 2.2.0
```

The CLI protocol remains:

```text
cli_schema_version = 1.0.0
```

unless implementation discovers an unavoidable protocol incompatibility, in
which case the implementation must stop and request a spec amendment.

---

## 7.2 Backward compatibility

Do not rename or remove existing report fields.

Existing consumers must continue to find:

```text
absolute_metrics
yoy_metrics
period_growth
normalized_interest
anomalies
confidence_interval
quality
warnings
```

`descriptive_trend` is additive.

---

# 8. Interpretation contract for agents

## 8.1 Numeric authority rule

Add an explicit high-priority rule to `SKILL.md`:

```text
Every analytical number in the user-facing answer must already exist in the
current Python-generated report. Do not derive percentages, averages, ratios,
rankings, streak lengths, or other metrics from raw observations.
```

Copying/rounding a Python-produced number for presentation is allowed.

Example:

```text
report: -32.12403870777493
answer: -32.1%
```

is allowed.

Computing `-32.1%` from first/last pageviews is not allowed.

---

## 8.2 Growth wording rule

When:

```text
yoy_metrics.status != available
```

and:

```text
period_growth is null or not available
```

the agent must not claim:

```text
"growth was X%"
"it declined by X% over the year"
"annual growth is negative"
```

It may say:

```text
Standard YoY growth is unavailable.
```

If `descriptive_trend.endpoint_change_status = available`, it may additionally
say:

```text
The analysis window ended X% lower/higher than it began.
```

and must distinguish that statement from YoY.

---

## 8.3 Sequence/streak wording rule

An agent may state:

```text
"views declined for N consecutive intervals"
```

only when the exact `N` and direction are present in
`descriptive_trend.ending_streak` or another explicit Python-produced field.

Do not infer streaks by eyeballing `pageviews[]`.

---

## 8.4 Reliability wording rule

Do not invent a composite adjective or score such as:

```text
high confidence
moderately reliable
7/10 reliability
```

unless a future explicit report field defines that exact scale.

Instead summarize concrete checks:

```text
completeness = pass
period_sufficiency = warning
anomalies = none
YoY = insufficient_data
confidence interval = unavailable
article resolution = pass
```

Natural-language synthesis is allowed, for example:

```text
The data are complete for the requested window, but the window is too short for
the standard YoY comparison.
```

This is not a numeric or categorical reliability score.

---

## 8.5 Causal wording rule

Do not explain a spike or decline using release events, news, seasonality, or
other causes unless those causes come from an explicitly requested external
source.

Within the Wikipedia Trends-only workflow:

```text
"the March spike may have been caused by X"
```

must not be presented as an analytical finding.

---

## 8.6 Language-edition boundary remains mandatory

Continue to require:

```text
English Wikipedia
Ukrainian Wikipedia
Japanese Wikipedia
```

rather than:

```text
English people
Ukrainians
Japanese people
country demand
market demand
```

unless separate evidence supports the broader statement.

---

# 9. New result-interpretation workflow

Create:

```text
references/workflows/result-interpretation.md
```

`SKILL.md` should remain compact and route to this file after a successful CLI
run when the user asks for:

- growth/decline;
- trend direction;
- reliability;
- comparison conclusions;
- a concise interpretation of metrics.

The workflow must define:

```text
1. inspect statuses before values;
2. use yoy_metrics only when available;
3. use period_growth only with the explicit configured baseline;
4. use descriptive_trend for within-window descriptive statements;
5. never calculate a metric from pageviews[];
6. preserve quality/warning statuses;
7. preserve Wikipedia-edition interpretation boundaries;
8. avoid causal explanations not present in the report.
```

`references/cli.md` Step 9 must link to this workflow.

---

# 10. Quality propagation remediation

## 10.1 Article mode

The pipeline already owns `article_resolution` before pageview collection.

For every analyzable article-mode language report, call quality evaluation with
the applicable structured resolution result.

The following state is forbidden:

```text
resolution.article.status = resolved
AND
language.quality.article_resolution.status = not_evaluated
```

for an analyzed article language.

---

## 10.2 Language-scoped article-resolution quality

A multi-language `ArticleResolution` may be `partial`.

Quality must be scoped to the current language.

Example:

```text
requested = [pl, cs, uk]
resolved = [pl, cs]
missing = [uk]
```

Required semantics for analyzable languages:

```text
pl.article_resolution = pass
cs.article_resolution = pass
```

The global `partial` result must not automatically make the successfully
resolved `pl` and `cs` language-local resolution check fail.

For `uk`, the unresolved state remains explicit in:

```text
resolution
language warnings
comparison warnings
comparison.comparable = false
```

If WT-M25 implementation adds quality checks to unresolved language reports,
all non-applicable checks must be `not_evaluated`, not fabricated failures.
That extension is optional; do not block WT-M25 on it.

---

## 10.3 Topic mode

WT-M25 does not redefine the M08 `article_resolution` check into a generic topic
resolution check.

For topic mode, preserve current semantics unless an existing test proves a
regression.

A future spec may introduce a separate topic-resolution quality check.

---

## 10.4 Comparison validity propagation

Reorder or reconcile pipeline construction so that a multi-language analysis
passes:

```text
comparison.comparison_validity
```

into each applicable analyzable language's quality report.

Required:

```text
single-language analysis
→ comparison_validity = not_evaluated

multi-language analysis
→ comparison_validity equals M13 result
```

Do not compute comparison validity twice with separate logic.

M13 remains the semantic authority.

---

## 10.5 Anomaly detection propagation

The pipeline currently computes anomalies for the report and quality evaluation
can recompute them independently.

Compute the anomaly result once per language and pass the same object to:

```text
LanguageReport.anomalies
evaluate_quality(... anomaly_detection=...)
```

This prevents drift between report fields and quality findings.

---

## 10.6 Trend consistency propagation

`trend_consistency` must consume the deterministic `descriptive_trend` adjacent
change counts rather than independently deriving another version of the same
metric.

There must be exactly one Python implementation of adjacency semantics.

---

# 11. Installed-Skill runtime launcher

## 11.1 New supported entry point

Add a standard-library bootstrap launcher:

```text
scripts/run.py
```

Agent-facing documentation must prefer:

```bash
python3 <skill-root>/scripts/run.py \
  --config <config.json> \
  --output-dir <output-dir>
```

The implementation may also accept a Python 3.12+ absolute interpreter path.

`scripts/analyze.py` remains the low-level CLI and development entry point.

---

## 11.2 Read-only Skill root

`run.py` must never write into:

```text
<skill-root>/
```

including:

```text
src/*.egg-info
.venv
Matplotlib caches
pip caches
generated configs
generated analysis artifacts
```

This is required for Skills Manager installations that expose the Skill as
read-only.

---

## 11.3 Writable runtime directory

Resolution order:

```text
WIKIPEDIA_TRENDS_RUNTIME_DIR
→ platform-appropriate user cache directory
```

Recommended Unix fallback:

```text
${XDG_CACHE_HOME:-~/.cache}/wikipedia-trends/
```

Recommended macOS fallback may use the normal user cache location if the
implementation already has a safe helper.

Do not use the project output directory for dependency installation.

---

## 11.4 Dependency bootstrap

Add a checked-in runtime dependency lock/export suitable for pip installation,
for example:

```text
requirements-runtime.lock
```

Generate it from the repository's existing `uv.lock`.

The exact generation command must be documented and reproducible.

`run.py` must:

```text
1. verify Python >= 3.12;
2. derive a runtime fingerprint from Python major/minor + dependency lock hash;
3. reuse an existing cached runtime when the fingerprint matches;
4. otherwise create a venv under the writable runtime directory;
5. install runtime dependencies into that venv;
6. run scripts/analyze.py with <skill-root>/src available on sys.path/PYTHONPATH;
7. use writable MPLCONFIGDIR and XDG_CACHE_HOME equivalents;
8. propagate analyze.py's final exit code.
```

The Skill package itself does not need to be installed editable.

This specifically avoids the observed write-protected `egg-info` failure.

---

## 11.5 Stdout/stderr contract

Bootstrap/setup diagnostics go to stderr only.

On a successful analysis, stdout visible to the agent must still be exactly the
WT-M22 CLI success JSON emitted by the analysis CLI.

The launcher must not prepend:

```text
creating venv...
installing...
starting...
```

to stdout.

Controlled bootstrap failures must:

- exit non-zero;
- explain the concrete failure on stderr;
- never emit a fake CLI success object.

Do not change `cli_schema_version` for bootstrap implementation alone.

---

## 11.6 Offline/cache behavior

If the matching runtime cache already exists:

```text
no dependency network access is required
```

If dependencies are missing and installation requires network access but the
network is unavailable:

```text
fail explicitly
```

Do not fall back to direct Wikimedia calls, manual calculations, or a different
analysis implementation.

---

# 12. Config-minimization and output-default rule

Update `SKILL.md` / `input-schema.md` guidance:

```text
Do not explicitly populate default-valued config sections unless the user or a
workflow requires a non-default value.
```

In particular:

```text
If the user does not specify JSON/chart/PDF preferences, omit `output`.
```

This allows `OutputConfig` to apply its stable defaults and prevents model-to-model
artifact drift.

Follow-ups must preserve the previous report's frozen output config unless the
user explicitly changes it.

---

# 13. Files expected to change

At minimum, implementation is expected to inspect/change:

```text
SKILL.md
references/cli.md
references/input-schema.md
references/output-schema.md
references/methodology.md
references/workflows/result-interpretation.md          NEW

src/wiki_trends/models.py
src/wiki_trends/analytics.py
src/wiki_trends/quality.py
src/wiki_trends/pipeline.py
src/wiki_trends/report.py
src/wiki_trends/config.py                              only if needed

scripts/run.py                                         NEW
scripts/analyze.py                                     only if needed
requirements-runtime.lock                             NEW

tests/...                                              unit + pipeline + CLI/bootstrap + E2E
README.md
docs/sdd/INDEX.md
docs/sdd/M25-deterministic-interpretation-quality-runtime-hardening.md
```

Do not perform unrelated refactors.

---

# 14. Unit test requirements

## 14.1 Descriptive trend — Nintendo fixture

Given the normative Nintendo series from section 1:

Expected:

```text
status = available
first = 2025-09-01 / 128863
last = 2026-08-01 / 87467
direction = lower_at_end
endpoint_change_pct ≈ -32.12403870777493
positive_adjacent_changes = 4
negative_adjacent_changes = 7
unchanged_adjacent_changes = 0
comparable_adjacent_pairs = 11
ending_streak.direction = decrease
ending_streak.intervals = 2
ending_streak.start = 2026-06-01
ending_streak.end = 2026-08-01
peak = 2026-03-01 / 137994
trough = 2026-08-01 / 87467
```

The test must explicitly guard against:

```text
ending_streak.intervals == 4
```

---

## 14.2 Unknown bucket breaks adjacency

Example:

```text
Jan observed
Feb UNKNOWN
Mar observed
Apr observed
```

Expected:

```text
Jan→Mar is not an adjacent comparison
Feb breaks any active streak
Mar→Apr is one valid adjacent comparison
```

---

## 14.3 Missing requested boundary

If the first or last requested bucket is `UNKNOWN`:

```text
endpoint_change_status = insufficient_data
endpoint_change_pct = null
direction = unknown
```

---

## 14.4 Zero endpoint baseline

If:

```text
first = 0
last > 0
```

Expected:

```text
direction = higher_at_end
endpoint_change_status = zero_baseline
endpoint_change_pct = null
```

Do not emit infinity.

---

## 14.5 Peak/trough tie determinism

When multiple known buckets share the maximum/minimum:

```text
earliest timestamp wins
```

---

# 15. Quality regression tests

## 15.1 Single resolved article

Given:

```text
resolution.status = resolved
language = en
series non-empty
```

Expected:

```text
article_resolution.status = pass
```

The old `not_evaluated` result is a regression.

---

## 15.2 Partial multi-language article resolution

Given:

```text
requested = [pl, cs, uk]
resolved = [pl, cs]
missing = [uk]
```

Expected:

```text
pl language quality: article_resolution = pass
cs language quality: article_resolution = pass
comparison.comparable = false
comparison.comparison_validity != not_evaluated
```

The missing `uk` state must remain explicit and must not become zero.

---

## 15.3 Multi-language comparison quality

For a valid comparable two-language scenario:

```text
comparison.comparison_validity = pass
```

and analyzable language reports must not show:

```text
comparison_validity = not_evaluated
```

---

## 15.4 Single-language comparison quality

For one language:

```text
comparison = null
comparison_validity = not_evaluated
```

This remains correct.

---

## 15.5 Shared anomaly object

A mocked anomaly detector must prove that the same computed anomaly semantics
feed both:

```text
LanguageReport.anomalies
spike_sensitivity quality evaluation
```

Do not maintain two independent detection paths.

---

# 16. Bootstrap/runtime tests

Tests must not depend on real internet access.

Mock subprocess/package installation where appropriate.

Required cases:

```text
Python < 3.12
→ clear non-zero bootstrap failure

read-only skill root
→ launcher does not attempt to write there

runtime cache missing
→ writable venv/cache path selected

runtime cache fingerprint matches
→ dependency installation skipped

runtime cache fingerprint differs
→ new/rebuilt runtime selected

analysis exit 0
→ launcher exits 0

analysis exit 1
→ launcher exits 1

analysis exit 2
→ launcher exits 2

bootstrap logs
→ stderr only

successful analysis
→ stdout remains exactly one CLI JSON object
```

A test must specifically simulate the condition that previously caused:

```text
Cannot update time stamp of directory 'src/wikipedia_trends.egg-info'
```

and prove that the new launcher does not attempt editable installation into the
Skill source.

---

# 17. End-to-end regression scenario

Add a deterministic E2E fixture equivalent to the Nintendo 12-month case.

The test does not need live Wikimedia data.

It must verify the report contains:

```text
schema_version = 2.2.0
resolution.article.status = resolved
article_resolution quality = pass
yoy_metrics.status = insufficient_data
period_growth = null
descriptive_trend.direction = lower_at_end
descriptive_trend.endpoint_change_pct ≈ -32.1240
descriptive_trend.ending_streak.intervals = 2
completeness = 100%
```

If charts/PDF are enabled by default, verify the expected default artifacts
according to current OutputConfig behavior.

---

# 18. Agent-level post-implementation verification

After deterministic tests pass, repeat the exact Nintendo prompt in independent
fresh sessions on at least:

```text
Model A — GPT-6 Luna High
Model B — GPT-5.5
```

Use the same frozen commit and same installed Skill snapshot.

Do not provide implementation hints.

Expected behavior for both:

```text
Skill activates
→ supported launcher is used
→ no ad-hoc pip/PYTHONPATH recovery
→ analysis.json is inspected
→ YoY insufficient_data is preserved
→ no custom arithmetic is performed
→ any -32.1% statement comes from descriptive_trend.endpoint_change_pct
→ no "four consecutive months" claim unless report says so
→ quality reports article resolution = pass
→ reliability is described through explicit checks, not an invented score
→ Wikipedia pageviews are not mapped to sales or purchase intent
```

A model may omit the endpoint percentage and simply state that the period ended
lower than it began.

It must not calculate any additional ratios.

---

# 19. Relationship to WT-M18.1

The current exploratory evaluations are remediation evidence, not the final
WT-M18.1 acceptance run.

Required sequence:

```text
WT-M25 spec approved
    ↓
WT-M25 implemented
    ↓
deterministic verification passes
    ↓
WT-M25 marked VERIFIED
    ↓
freeze a new repository commit
    ↓
reset WT-M18.1 evaluation evidence
    ↓
rerun C1/C2/C3 + R1–R8 + diagnostics
    ↓
produce model-specific summaries
    ↓
MVP READY / MVP NOT READY
```

Do not mix pre-M25 model scores with post-M25 WT-M18.1 scores.

---

# 20. Acceptance criteria

WT-M25 is complete only when all of the following are true:

1. Python exposes deterministic descriptive window trend evidence.
2. Endpoint change is Python-produced and explicitly distinguished from YoY.
3. Consecutive streak claims have a deterministic Python field.
4. `trend_consistency` uses the same adjacency semantics as descriptive trend.
5. Agents are explicitly prohibited from deriving analytical numbers from raw observations.
6. Agents are explicitly prohibited from deriving streaks from raw observations.
7. A resolved article no longer yields `article_resolution = not_evaluated`.
8. Resolved languages in a partial multi-language article result receive language-local resolution PASS.
9. Multi-language quality receives M13 comparison validity.
10. Single-language comparison validity remains `not_evaluated`.
11. Anomaly detection is not independently recomputed along divergent report/quality paths.
12. A read-only installed Skill can execute through one documented launcher without modifying the Skill root.
13. The launcher preserves WT-M22 exit code and stdout/stderr semantics.
14. Runtime dependency setup is cached in a writable location.
15. Matplotlib uses a writable configuration/cache location when launched through the supported runner.
16. Agents do not override output defaults when the user gave no artifact preference.
17. Report schema documentation is updated to 2.2.0.
18. README, SKILL.md, methodology, CLI, and output-schema documentation agree.
19. Unit, pipeline, CLI/bootstrap, and E2E tests pass.
20. Ruff passes.
21. mypy passes.
22. `git diff --check` passes.
23. The Nintendo regression scenario produces the normative trend result.
24. Fresh GPT-6 Luna High and GPT-5.5 smoke runs no longer reproduce the targeted manual-analytics or false-streak failures.
25. A new frozen commit is recorded before formal WT-M18.1 revalidation.

---

# 21. Verification commands

Use the repository's configured environment.

At minimum:

```bash
python -m pytest
ruff check .
mypy
git diff --check
```

Also verify:

```bash
python3 scripts/run.py --help
```

or the final approved bootstrap-help equivalent.

For a read-only-install smoke test, use a temporary copy or fixture whose Skill
source permissions prevent writes, while runtime/output/cache directories remain
writable.

Do not use a live Wikimedia request as the only evidence for runtime correctness.

---

# 22. Expected documentation updates

## SKILL.md

Add:

- numeric authority rule;
- descriptive trend vs growth distinction;
- reliability wording rule;
- output-default rule;
- supported installed-skill launcher.

## references/cli.md

Update lifecycle to use the supported launcher for installed Skill execution.

Retain `scripts/analyze.py` as the low-level CLI contract.

Link to `result-interpretation.md` before the response step.

## references/methodology.md

Document:

- descriptive window trend;
- endpoint-change semantics;
- streak semantics;
- distinction from YoY and explicit-baseline growth.

## references/output-schema.md

Document `descriptive_trend` and report schema 2.2.0.

## references/input-schema.md

Clarify that omitted output settings use defaults and agents should not restate
defaults unless required.

## README.md

Document installed-Skill execution without assuming a writable repository-local
`.venv`.

---

# 23. Suggested implementation order

```text
1. models + deterministic descriptive trend
2. unit tests for descriptive trend
3. quality propagation refactor
4. quality regression tests
5. report schema 2.2.0
6. pipeline integration
7. Nintendo deterministic E2E fixture
8. installed-skill bootstrap launcher
9. bootstrap tests
10. SKILL.md interpretation rules
11. result-interpretation workflow
12. CLI/input/output/methodology docs
13. README
14. full verification
15. fresh two-model Nintendo smoke
16. mark M25 VERIFIED
17. freeze commit and rerun WT-M18.1
```

---

# 24. Implementation constraints

The implementation agent must not:

- weaken resolver safety to make a test pass;
- reclassify unavailable YoY as zero or negative;
- turn endpoint change into `yoy_metrics.growth_pct`;
- add a hidden LLM calculation path;
- call Wikimedia directly from the agent as a fallback;
- write dependencies into a read-only Skill installation;
- silently swallow bootstrap failures;
- change CLI success semantics without a spec amendment;
- create an opaque reliability score;
- create a market/opportunity recommendation field;
- alter M20 topic equivalence rules;
- alter M23 source-language rules;
- remove M24 unresolved/partial artifact resilience.

---

# 25. Implementation handoff

The coding agent should treat this file as the normative WT-M25 contract.

Before coding:

```text
1. inspect current M18.1, M20–M24 specs;
2. inspect models.py, analytics.py, quality.py, pipeline.py, report.py, cli.py;
3. inspect current tests around M06, M08, M10, M14, M22, M24;
4. summarize the planned file-level changes;
5. identify any conflict between this spec and existing public contracts;
6. stop for approval if a conflict requires changing this specification.
```

During implementation:

```text
implement in small coherent steps
→ run targeted tests after each step
→ keep CLI schema 1.0.0
→ bump report schema to 2.2.0
→ avoid unrelated cleanup/refactoring
```

Before completion:

```text
run full tests
run Ruff
run mypy
run git diff --check
show the final changed-file list
show the Nintendo regression result
show read-only runtime-launcher evidence
```

Do not mark WT-M25 VERIFIED solely because tests pass.

WT-M25 becomes VERIFIED only after the deterministic verification and the
targeted fresh-model smoke defined in this specification are complete.
