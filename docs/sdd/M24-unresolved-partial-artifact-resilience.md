# M24 — Unresolved and Partial Artifact Resilience

**Spec ID:** WT-M24  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M23  
**Precedes:** WT-M18.1 revalidation  
**Primary risk addressed:** valid semantic resolution limitations becoming generic artifact/runtime failures

## SDD rule

This document is the source of truth for artifact behavior when one or more
requested Wikipedia editions cannot produce an analyzable pageview series.

The implementation agent must:

- preserve explicit unresolved/partial semantic state;
- prevent chart rendering from turning an expected resolution limitation into
  a generic CLI analysis failure;
- preserve all requested language entries in machine-readable reports;
- generate presentation artifacts only from actual analyzable series;
- never synthesize zero-valued data for unresolved editions;
- keep direct comparison invalid when requested editions are unresolved or
  non-equivalent;
- preserve WT-M22 CLI protocol unless this spec explicitly requires otherwise;
- avoid placeholder trend data or misleading charts.

---

# 1. Context

The current pipeline already models unresolved data explicitly.

When no article is available for a requested language, it can produce:

```python
language_series[language] = []
```

and later construct a language report with:

```text
pageviews = []
absolute_metrics = null
warnings = [...]
```

The comparison layer can also represent:

```text
resolved = false
comparison.comparable = false
```

This is correct semantically.

However, presentation generation currently uses the entire `language_series`
mapping whenever charts or PDF are enabled.

For a multi-language request, the pipeline calls the comparison chart renderer.
The chart renderer rejects any language whose series is empty.

Conceptually:

```text
resolver correctly reports one requested edition as unresolved
    ↓
pipeline stores []
    ↓
comparison correctly becomes non-comparable
    ↓
chart renderer receives unresolved empty series
    ↓
ValueError
    ↓
CLI exit 1
```

The result is that a presentation-layer invariant hides the useful semantic
resolution result.

This is especially dangerous for inexpensive agents because the CLI now tells
them that exit `1` is a runtime/analysis failure. They can lose the actual
reason that the comparison could not be completed.

WT-M24 separates:

```text
semantic result completeness
```

from:

```text
presentation artifact availability
```

---

# 2. Goal

A request with unresolved/partial language mappings should produce the most
useful valid result possible.

Desired behavior:

```text
some requested languages unresolved
    ↓
preserve all language statuses in report
    ↓
collect metrics only for resolved languages
    ↓
direct comparison remains invalid where required
    ↓
render charts only from non-empty analyzable series
    ↓
generate requested PDF when a usable chart exists
    ↓
CLI completes successfully
```

An unresolved edition must not become:

```text
0 views
```

and must not be silently omitted from:

```text
resolution
languages
comparison warnings
```

---

# 3. Terminology

## 3.1 Requested language

Any edition listed in:

```text
config.languages
```

## 3.2 Analyzable language

A requested edition for which resolver output produced one or more valid
articles and the pipeline collected a non-empty pageview series.

Operationally:

```text
bool(language_series[language]) is true
```

for the current pipeline.

## 3.3 Unresolved language

A requested edition that cannot safely proceed to pageview collection because
no direct equivalent or approved usable representation exists.

It remains present in the report.

## 3.4 Presentation series

The subset of:

```text
language_series
```

that is safe to render as a trend chart.

Presentation series must never include empty unresolved placeholders.

---

# 4. Behavioral matrix

## 4.1 All requested languages analyzable

No behavioral change.

Example:

```text
languages = [pl, cs]
resolved = [pl, cs]
```

Expected:

```text
normal comparison
requested charts
requested PDF
requested JSON
```

## 4.2 Multi-language request with some unresolved editions

Example:

```text
requested = [pl, cs, uk]
analyzable = [pl, cs]
unresolved = [uk]
```

Expected:

```text
analysis.json.languages contains pl, cs, uk
uk has no fabricated pageviews
uk warning explains unresolved state
comparison.comparable = false
comparison warnings mention unresolved uk
chart input contains pl + cs only
PDF may be generated from the valid pl/cs presentation chart
CLI exit = 0
```

The chart title/legend may contain only the rendered analyzable editions, but
the JSON/PDF reliability text must preserve the fact that `uk` was requested
and unresolved.

## 4.3 Multi-language request with exactly one analyzable edition

Example:

```text
requested = [pl, cs, uk]
analyzable = [pl]
unresolved = [cs, uk]
```

Do not call:

```text
render_comparison_charts(...)
```

because it requires two or more non-empty series.

Render a normal single-series chart for `pl`.

Expected:

```text
chart = pl trend only
report still lists pl/cs/uk
comparison.comparable = false
PDF may use pl chart
CLI exit = 0
```

Do not relabel the result as if the original request were only Polish.

## 4.4 Zero analyzable editions

Example:

```text
requested = [pl, cs, uk]
analyzable = []
```

This is usually a clarification/resolution outcome.

Expected baseline behavior:

```text
do not call trend chart renderers
do not fabricate a no-data trend line
preserve structured resolution state
```

If JSON output is enabled:

```text
analysis.json must still be written
CLI should complete without a chart-rendering exception
charts = []
```

The report must include an explicit warning equivalent to:

```text
No requested language produced an analyzable pageview series; trend charts
were not generated.
```

PDF behavior is defined in section 8.

---

# 5. Presentation-series selection

Before chart/PDF generation, derive:

```python
presentation_series = {
    language: series
    for language, series in language_series.items()
    if series
}
```

The exact implementation may use a helper, but the semantics are mandatory.

Do not mutate `language_series` itself.

Why:

```text
language_series
→ analytical/report state for every requested edition

presentation_series
→ renderable subset only
```

This separation prevents unresolved editions from disappearing from the
machine-readable report.

---

# 6. Chart generation rules

## 6.1 More than one analyzable series

Use:

```text
render_comparison_charts(presentation_series, ...)
```

Existing 2–6 / 7–20 behavior remains unchanged.

## 6.2 Exactly one analyzable series

Use:

```text
render_trend_chart(...)
```

even if the original request listed multiple languages.

The chart is a language-local artifact, not a valid direct comparison.

The report/comparison warnings must make that distinction clear.

## 6.3 Zero analyzable series

Do not call chart rendering.

Return:

```text
charts = []
```

Do not create:

- blank PNGs;
- zero lines;
- fake zero observations;
- placeholder “trend” charts.

If charts were requested, record an explicit report warning that chart output
was skipped because no analyzable series existed.

This is a semantic skip, not a file-generation crash.

---

# 7. JSON report ordering and resilience

A machine-readable report is the primary audit artifact when enabled.

Artifact generation order must not allow an expected presentation limitation
to prevent `analysis.json` from being produced.

Implementation may either:

### Option A — condition presentation before rendering

Determine presentation feasibility before render calls and only call valid
renderers.

or:

### Option B — write/rewrite report safely

Build the report, render valid optional artifacts, update artifact paths, then
write final JSON.

The final `analysis.json` must contain correct artifact paths.

Do not write a stale report that claims artifacts were generated when they
were skipped.

For default:

```json
"output": {
  "json": true,
  "charts": true,
  "pdf": true
}
```

an unresolved/partial result must still leave the agent with a usable
`analysis.json`.

---

# 8. PDF behavior

The current PDF implementation requires a PNG chart.

WT-M24 distinguishes two cases.

## 8.1 At least one analyzable series

If PDF is requested and at least one presentation chart can be generated:

```text
generate PDF normally
```

If `output.charts = false` and `output.pdf = true`, the implementation may
generate an internal chart for PDF rendering exactly as WT-M22 allows.

That internal chart remains absent from user-facing:

```text
charts[]
```

unless chart output was explicitly enabled.

## 8.2 Zero analyzable series

Do not pass an invalid or missing chart into the existing PDF renderer.

For WT-M24, the minimum required behavior is:

```text
skip PDF generation
pdf = null
```

and add a report warning equivalent to:

```text
PDF was not generated because no analyzable pageview series was available
for the chart-based report layout.
```

Do not convert this into an accidental `ValueError` from `_resolve_chart_path`.

A future milestone may introduce a dedicated resolution-only PDF layout. That
is not required here.

## 8.3 JSON-disabled zero-series request

If:

```text
output.json = false
```

and zero analyzable series make every requested presentation artifact
impossible, do not fail inside chart/PDF rendering.

The CLI may complete with empty/null artifact paths, but application stderr
must remain free of a fake rendering exception.

Agent documentation must state that no numeric interpretation is possible
without a generated machine-readable report.

No CLI schema-version change is required by WT-M24.

---

# 9. Report warnings

Add deterministic report-level warnings for skipped presentation artifacts.

Recommended forms:

```text
No requested language produced an analyzable pageview series; requested chart
output was not generated.
```

and when applicable:

```text
PDF output was not generated because the current one-page PDF layout requires
at least one analyzable trend series.
```

Warnings must:

- be concise;
- explain the semantic cause;
- not imply a filesystem failure;
- not imply zero pageviews;
- remain available in `analysis.json`.

Do not duplicate dozens of equivalent warnings.

Language-local resolver warnings and comparison warnings remain authoritative
for which edition failed and why.

---

# 10. Comparison behavior

Do not change `compare_languages()` validity rules.

An unresolved requested edition must still cause:

```text
comparison.comparable = false
```

even when the chart contains only resolved editions.

The chart is visualization of available local evidence.

It is not proof that the original full requested comparison became valid.

Preserve:

```text
comparison.normalized_comparable
comparison.effective_period
comparison.warnings
comparison.comparison_validity
```

as currently defined.

---

# 11. Artifact-validation workflow change

Update:

```text
references/workflows/artifact-validation.md
```

so a weak model distinguishes:

```text
requested artifact failed unexpectedly
```

from:

```text
requested presentation artifact intentionally unavailable because there is no
analyzable series
```

Rules:

1. Inspect `analysis.json` when available before declaring skipped chart/PDF a
   generation bug.
2. If the report contains the explicit WT-M24 semantic-skip warning and the
   corresponding CLI path is `[]`/`null`, report the limitation to the user.
3. Do not claim the artifact exists.
4. Do not rerun the CLI repeatedly trying to force a chart.
5. If the report says analyzable series existed but the requested artifact is
   missing, treat it as an actual artifact failure.

This rule is important for inexpensive models.

---

# 12. SKILL/CLI documentation

Keep `SKILL.md` compact.

No large orchestration change is required.

`references/cli.md` should gain one short success-path note:

```text
A successful run may intentionally return no chart/PDF when resolution leaves
no analyzable series. Inspect analysis.json warnings before treating empty
artifact paths as a runtime failure.
```

Do not rewrite WT-M22 lifecycle.

---

# 13. Tests

## 13.1 Partial article mapping with two analyzable languages

Create a deterministic pipeline test:

```text
requested = [pl, cs, uk]
resolved = [pl, cs]
missing = [uk]
outputs = JSON + charts + PDF
```

Assert:

```text
run succeeds
analysis_json exists
charts exist
PDF exists
report.languages keys == {pl, cs, uk}
report.languages.uk.pageviews == []
report.languages.uk.absolute_metrics == null
comparison.comparable == false
comparison warnings mention uk
chart renderer never receives uk empty series
```

## 13.2 Partial topic mapping

Create a deterministic topic test where a canonical source QID lacks one
target sitelink.

Assert the same resilience semantics.

This is especially important because missing canonical sitelinks are an
intentional WT-M20 state.

## 13.3 Exactly one analyzable series in multi-language request

Example:

```text
requested = [pl, cs, uk]
resolved = [pl]
```

Assert:

```text
single-series chart generated
no comparison-chart validation error
comparison.comparable == false
PDF generated from the usable chart when requested
```

## 13.4 Zero analyzable series, JSON enabled

Use a structured clarification result.

Assert:

```text
exit/run does not fail during chart generation
analysis.json exists
charts == []
pdf == null
report contains resolver clarification
report warnings explain skipped presentation output
no pageview requests occur
```

## 13.5 Zero analyzable series, JSON-only

Assert:

```text
analysis.json exists
charts == []
pdf == null
```

and no rendering functions are called.

## 13.6 PDF-only with at least one analyzable series

Preserve WT-M22 behavior:

```text
output.json = false
output.charts = false
output.pdf = true
```

Assert:

```text
internal chart may be generated
CLI user-facing charts == []
PDF exists
```

WT-M24 must not regress this case.

## 13.7 More than six analyzable languages plus unresolved language

Example:

```text
8 requested
7 analyzable
1 unresolved
```

Assert:

```text
7 actual per-language PNGs
no empty-series renderer failure
unresolved edition preserved in report
comparison invalid
no nonexistent base chart path
```

---

# 14. Quality/report consistency

WT-M24 does not require redesigning M08 quality models.

However, do not remove existing warnings or comparison-validity evidence.

If implementation work exposes a clearly isolated defect where unresolved
language reports have no quality information even though the current
methodology promises a full quality set, record it as a follow-up issue rather
than silently expanding WT-M24 unless the fix is trivial and fully covered.

The primary acceptance target is artifact resilience.

---

# 15. Out of scope

Do not:

- fabricate zero observations for unresolved languages;
- create fake blank trend charts;
- mark a partial comparison comparable;
- search target languages for approximate replacements;
- automatically apply proxies;
- redesign the PDF layout into a new report product;
- change normalized-interest methodology;
- change report schema `2.1.0`;
- change CLI schema `1.0.0`;
- add new metrics;
- hide unresolved editions from JSON;
- silently drop requested languages from `comparison.languages`.

---

# 16. Expected implementation surface

Primary runtime:

```text
src/wiki_trends/pipeline.py
```

Potential small presentation guard changes:

```text
src/wiki_trends/charts.py
src/wiki_trends/report.py
```

but prefer fixing orchestration before weakening renderer preconditions.

Documentation:

```text
references/cli.md
references/workflows/artifact-validation.md
```

Potential methodology clarification:

```text
references/output-schema.md
```

Tests:

```text
tests/e2e/test_cli_scenarios.py
tests/unit/test_charts.py
tests/unit/test_pdf_report.py
```

or dedicated pipeline tests if clearer.

---

# 17. Preferred implementation design

Prefer:

```text
keep renderers strict
+
filter/select valid presentation input in pipeline
```

over:

```text
make renderers silently accept empty series
```

Why:

- chart functions retain useful invariants;
- orchestration owns whether a chart is meaningful;
- empty analytical state stays explicit;
- accidental empty-series calls remain detectable in other code.

---

# 18. Verification

Run:

```bash
python -m pytest
ruff check .
mypy
git diff --check
```

Re-run all WT-M22 CLI contract tests.

No live network call is required for acceptance.

---

# 19. Acceptance criteria

WT-M24 is accepted when:

- unresolved/partial requested editions remain present in the report;
- no unresolved edition is converted to zero;
- chart rendering receives only analyzable series;
- 2+ analyzable series use comparison charts;
- exactly 1 analyzable series uses a single trend chart;
- 0 analyzable series does not invoke trend renderers;
- JSON output can still be produced for structured clarification/unresolved
  results;
- PDF generation remains functional whenever at least one usable chart exists;
- zero-series PDF requests are skipped intentionally with an explicit warning
  rather than crashing;
- direct comparison remains invalid when required;
- default-output partial runs return useful artifacts instead of exit `1`;
- WT-M22 optional-artifact semantics remain valid;
- full tests/lint/typecheck pass.

---

# Definition of Done

Expected semantic limitations such as a missing sitelink or clarification state
remain visible as structured results and warnings, while the presentation layer
generates only the artifacts that are meaningful for the available data.

A missing language equivalent must no longer be able to turn a valid
machine-readable analysis result into a generic chart-rendering failure.
