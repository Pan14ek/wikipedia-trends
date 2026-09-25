# M21 — SKILL Orchestration and Workflow References

**Spec ID:** WT-M21  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Implemented — awaiting WT-M18 revalidation
**Depends on:** WT-M20  
**Revalidation after completion:** WT-M18 agent evaluation

## SDD rule

This document is the source of truth for the Agent Skill instruction-architecture refactor after WT-M20.

The implementation agent must:

- preserve the current WT-M01–WT-M20 runtime behavior;
- refactor agent instructions without changing Python analytics, resolution, schemas, or CLI behavior;
- keep `SKILL.md` as the compact orchestration/router layer;
- move workflow-specific procedures into `references/workflows/`;
- use progressive disclosure: load only the workflow references required for the current request;
- treat the current Python resolver as the semantic authority for topic acceptance;
- preserve the WT-M20 direct/proxy comparison boundary;
- avoid duplicating full methodology or schema documentation into workflow files;
- avoid speculative features or future behavior not present in the repository.

WT-M21 is a documentation and agent-orchestration milestone. It is not a runtime feature milestone.

---

## Context

The repository now implements WT-M20 topic correctness remediation.

Current runtime behavior includes:

- deterministic semantic evidence for topic candidates;
- source-language topic discovery;
- MediaWiki search rank used only after semantic acceptance;
- structured candidate evidence and rejection reasons;
- canonical source concept sets based on Wikidata QIDs;
- cross-language topic mapping through Wikidata sitelinks;
- no approximate target-language fallback search for missing sitelinks;
- explicit proxy overrides with `comparison_equivalent = false` when QID sets differ;
- strict topic aggregation: if any selected article is `UNKNOWN`, the topic bucket is `UNKNOWN`;
- one project-wide denominator per language edition for normalized topic interest;
- report schema `2.1.0`;
- frozen exact dates in report input for safe follow-up analysis.

The current `SKILL.md` has been updated for WT-M20 but remains a mostly linear instruction document. It mixes:

- skill activation;
- request clarification;
- period selection;
- topic resolution;
- proxy handling;
- follow-up state;
- CLI execution;
- artifact verification;
- interpretation rules.

That structure works for the current feature set but will become increasingly difficult to extend.

WT-M21 restructures the skill into an orchestration layer plus reusable workflow references.

---

# 1. Goal

Create an Agent Skill instruction architecture in which:

```text
SKILL.md
    ↓
identify request type
    ↓
select only relevant workflows
    ↓
apply global invariants
    ↓
build validated config
    ↓
run project CLI
    ↓
interpret validated output
```

Detailed operational procedures live under:

```text
references/workflows/
```

The resulting skill must be easier for a fast/inexpensive model to navigate and easier to extend with future workflows.

---

# 2. Design principles

## 2.1 SKILL.md is the router

`SKILL.md` should answer:

- When should this skill activate?
- When should it not activate?
- What rules always apply?
- What information must be known before analysis?
- Which workflow references should be loaded?
- How is the CLI invoked?
- When must the agent stop?
- What must be validated before responding?
- What information must be returned to the user?

It should not contain full domain methodology.

## 2.2 Workflow references are operational

A workflow file answers:

> How should the agent handle this specific type of request?

It should contain:

- inputs;
- preconditions;
- process;
- stop conditions;
- output requirements;
- links to schema/methodology references.

## 2.3 Domain references remain authoritative

Keep the existing responsibility split:

```text
references/input-schema.md
→ configuration contract

references/output-schema.md
→ analysis.json contract

references/methodology.md
→ metric definitions, resolver methodology, quality rules, interpretation limits
```

Do not copy these documents into the workflows.

## 2.4 Python owns correctness-critical decisions

The agent must not replace Python logic with its own arithmetic or semantic acceptance.

Especially after WT-M20:

```text
resolver accepts/rejects topic candidate
→ agent consumes that decision
```

not:

```text
resolver rejects candidate
→ agent promotes it manually
```

---

# 3. Target repository structure

Add:

```text
references/
├── input-schema.md
├── methodology.md
├── output-schema.md
└── workflows/
    ├── article-analysis.md
    ├── topic-analysis.md
    ├── multi-language-comparison.md
    ├── period-selection.md
    ├── criteria-and-thresholds.md
    ├── follow-up-analysis.md
    ├── proxy-resolution.md
    └── artifact-validation.md
```

Keep workflow files small enough to load selectively.

Do not create workflow files that merely duplicate another workflow.

---

# 4. Target SKILL.md structure

Recommended structure:

```text
Frontmatter

# Wikipedia Trends

## Purpose
## When to Use
## When Not to Use
## Non-Negotiable Rules
## Preflight
## Choose a Workflow
## Run the Analysis
## Stop and Clarify
## Interpret the Result
## Output Contract
## References
```

Minor wording changes are acceptable. The responsibilities are mandatory.

---

# 5. Frontmatter

The description should be trigger-oriented.

It must mention the core user intents:

- Wikipedia pageview trend analysis;
- article/topic analysis;
- language-edition comparison;
- measurable criteria;
- reproducible JSON/PNG/PDF reports;
- follow-up analysis.

It should also prevent incorrect activation for general market research.

Recommended shape:

```yaml
---
name: wikipedia-trends
description: >
  Analyze Wikipedia pageview interest for an article or topic over time,
  compare Wikipedia language editions, evaluate explicit numeric criteria,
  and generate reproducible JSON, PNG, or one-page PDF reports. Use for
  Wikipedia pageview trend analysis and follow-up comparisons. Do not use
  Wikipedia pageviews as proof of market demand, country demand, willingness
  to pay, or purchase intent.
---
```

The final wording may be shorter, but must remain precise.

---

# 6. When to Use

Add explicit activation examples.

Use this skill when the user wants to:

- analyze attention to one Wikipedia article over time;
- analyze a broader topic represented by one or more Wikipedia articles;
- compare the same article/topic across Wikipedia language editions;
- inspect absolute pageviews, normalized interest, growth, anomalies, stability, or uncertainty;
- test explicit numeric thresholds supported by the config;
- produce a JSON report, chart, or PDF;
- refine or repeat a previous Wikipedia Trends analysis.

Do not make activation depend on the user knowing terms such as `normalized_interest` or `comparison_period`.

---

# 7. When Not to Use

Do not use this skill as the primary method to:

- estimate total addressable market;
- estimate revenue;
- infer country demand solely from language-edition traffic;
- estimate willingness to pay;
- estimate purchase intent;
- forecast future popularity;
- answer general web-trend questions whose requested source is not Wikipedia pageviews.

For mixed requests, the skill may provide the Wikipedia evidence component while explicitly limiting what that evidence supports.

---

# 8. Non-Negotiable Rules

Keep this section compact and global.

At minimum:

1. Use the project CLI for every analysis.
2. Never replace the CLI with direct Wikimedia API calls.
3. Never calculate or estimate metrics manually in prose.
4. Never invent canonical Wikipedia titles.
5. Never silently choose between materially different concepts.
6. In topic mode, treat the resolver as the semantic authority.
7. Never manually promote a rejected topic candidate to a direct match.
8. Never search a target language for an approximate replacement when the resolver reports a missing canonical sitelink.
9. Never treat `UNKNOWN` as zero.
10. Never present a non-equivalent proxy as a like-for-like comparison.
11. Never infer country demand from a Wikipedia language edition.
12. Never describe pageviews as purchase intent, willingness to pay, or proof of market demand.
13. Never invent a numeric threshold or explicit comparison baseline.
14. On follow-up requests, change only the fields the user requested.
15. Never claim an artifact was created until it has been validated.

Do not duplicate long explanations here.

---

# 9. Preflight

Before creating a config, identify the minimum information required for the request.

Check:

```text
subject known?
article vs topic mode known or safely inferable?
requested Wikipedia language edition(s) known?
source language known when required?
period known or safely defaultable?
granularity resolvable?
explicit criterion thresholds known?
comparison baseline known when a growth_pct threshold is requested?
proxy explicitly approved when required?
requested outputs known or safely defaultable?
```

## 9.1 Safe defaults

Current safe defaults include:

```text
period = 24 complete calendar months
criteria = enabled according to AnalysisConfig defaults
outputs = JSON + charts + PDF according to OutputConfig defaults
```

Do not ask questions for values that have a documented safe default unless the user's wording conflicts with the default.

## 9.2 Required clarification

Clarification is required when the runtime cannot safely infer the value.

Important cases:

- ambiguous article concept;
- multi-language request without a safe source language;
- resolver returns `REQUIRES_CLARIFICATION`;
- explicit growth threshold without a comparison period;
- unapproved proxy.

---

# 10. Choose a Workflow

Use a Markdown table.

Required routing section:

```md
## Choose a Workflow

Read only the workflow references required for the current request.

| User intent / situation | Workflow |
|---|---|
| Analyze one specific Wikipedia article | [`article-analysis.md`](references/workflows/article-analysis.md) |
| Analyze a broader topic represented by one or more articles | [`topic-analysis.md`](references/workflows/topic-analysis.md) |
| Compare multiple Wikipedia language editions | [`multi-language-comparison.md`](references/workflows/multi-language-comparison.md) |
| Use exact dates, relative periods, or choose granularity | [`period-selection.md`](references/workflows/period-selection.md) |
| Evaluate growth, thresholds, or explicit measurable criteria | [`criteria-and-thresholds.md`](references/workflows/criteria-and-thresholds.md) |
| Modify a previous analysis while preserving unchanged parameters | [`follow-up-analysis.md`](references/workflows/follow-up-analysis.md) |
| Handle a missing direct equivalent or user-approved proxy | [`proxy-resolution.md`](references/workflows/proxy-resolution.md) |
| Validate JSON, charts, and PDF before returning results | [`artifact-validation.md`](references/workflows/artifact-validation.md) |
```

Immediately after:

```text
A request may require more than one workflow. Apply all relevant workflows
together. Do not read unrelated workflow references.
```

---

# 11. Workflow file contract

Every workflow should use the same basic shape:

```md
# <Workflow Name>

## Use When
## Inputs
## Preconditions
## Process
## Stop Conditions
## Output Requirements
## Related References
```

A section may be omitted only if genuinely irrelevant.

Workflow files must be:

- operational;
- concise;
- deterministic where possible;
- explicit about stop conditions;
- linked to schemas/methodology rather than duplicating them;
- compatible with multiple tool-capable agent runtimes.

---

# 12. article-analysis.md

## Purpose

Handle `query.mode = "article"`.

## Required behavior

The workflow must state:

- use concrete article mode when the user refers to one Wikipedia concept/page;
- one requested language can infer its own `source_language`;
- multi-language article analysis requires an explicit/safe source language;
- the resolver may return:
  - `resolved`;
  - `partial`;
  - `requires_clarification`;
- `partial` means some requested language equivalents are missing;
- resolved languages may still be analyzed while missing editions remain explicit;
- never invent a missing equivalent;
- disambiguation requires clarification;
- cross-language equivalents come from structured Wikipedia/Wikidata linkage, not LLM title translation.

## Composition

When multiple editions are requested, also use:

```text
multi-language-comparison.md
```

When custom time semantics are requested, also use:

```text
period-selection.md
```

---

# 13. topic-analysis.md

This workflow must reflect the implemented WT-M20 behavior, not the older M12 behavior.

## Source language

For topic mode:

- one requested language may infer source language from that edition;
- multi-language topic analysis requires the topic phrase's source language;
- never assume English silently.

## Resolver authority

The workflow must state:

```text
The Python resolver owns semantic candidate acceptance.
```

The agent may explain resolver evidence, but must not override it.

## Resolver flow

The workflow should describe the operational flow at a high level:

```text
source-language search
→ deterministic semantic evidence
→ accepted source concepts
→ canonical Wikidata QIDs
→ target-language sitelinks
```

Do not reproduce the entire 0.80 semantic methodology; link to `methodology.md`.

## Structured outcomes

Handle:

```text
resolved
requires_clarification
```

Topic mode does not use `partial` for a single `TopicResolution`.

For clarification, inspect the structured reason and stop before analysis for that unresolved representation.

Important currently supported reasons include:

```text
disambiguation_page
ambiguous_topic_candidates
insufficient_semantic_evidence
missing_canonical_sitelink
override_not_article
no_valid_topic_candidates
```

The workflow does not need to hard-code every possible future reason, but should explain these current categories.

## Candidate evidence

`analysis.json` schema 2.1.0 may contain:

- accepted/rejected candidate evidence;
- search rank;
- exact title/label/alias signals;
- token coverage;
- metadata languages;
- canonical concept QIDs.

Use this evidence for explanation/audit only.

Do not re-score or re-decide candidate acceptance in the agent.

## Cross-language mapping

For target editions:

- use resolver-produced Wikidata sitelinks;
- do not manually search for an approximate replacement;
- missing sitelink remains unresolved unless the user explicitly approves a proxy.

## Topic aggregation

The agent must not calculate the topic aggregate itself.

Interpret Python output with the WT-M20 rule:

```text
any component UNKNOWN
→ topic bucket UNKNOWN
```

The detailed rule belongs in `methodology.md`.

---

# 14. multi-language-comparison.md

## Use when

Any request includes 2–20 Wikipedia language editions.

## Required behavior

The workflow must distinguish:

```text
language-local analysis
```

from:

```text
valid direct cross-language comparison
```

A language may have language-local metrics even when it cannot participate in a like-for-like comparison.

## Comparison equivalence

For topic mode, direct comparison requires:

```text
comparison_equivalent = true
```

A proxy with a different QID set is:

```text
resolved locally
but
not direct-comparison equivalent
```

The agent must preserve that distinction.

## Comparison result

Read:

- `comparison.comparable`;
- `comparison.normalized_comparable`;
- `comparison.effective_period`;
- comparison warnings;
- comparison validity quality check.

Do not invent a direct comparison when `comparable = false`.

## Normalized interest

When available, normalized interest is a scale-aware comparison across language editions.

Do not reinterpret it as country demand.

For topic mode, WT-M20 already guarantees one project-wide denominator per language edition. The agent should consume the result, not recalculate it.

## No winner

Do not generate a synthetic "best market" score.

The agent may explain measurable trade-offs only according to user-provided criteria.

---

# 15. period-selection.md

Document the actual WT-M19 contract.

## Default

No period supplied:

```text
24 complete calendar months
monthly granularity
```

## Explicit dates

`start` and `end` are inclusive.

Both must be supplied together.

## Granularity

Default inference:

```text
full calendar-month range
→ monthly

partial calendar-month range
→ daily
```

Explicit granularity may be used only when valid for the period contract.

## Relative wording

For:

```text
last month
```

resolve to the previous completed calendar month before creating the config.

## Availability

The report distinguishes:

```text
requested_period
period / available period
```

The agent must describe truncation when the latest requested buckets are unavailable.

Never fill unavailable buckets.

## Follow-ups

Once a relative period has been resolved and written to `analysis.json.input`, preserve those exact dates during follow-ups unless the user explicitly changes the period.

---

# 16. criteria-and-thresholds.md

This workflow must clearly distinguish two concepts that are easy for an agent to confuse.

## 16.1 Standard YoY analysis

`criteria.growth = true` enables the existing growth analysis.

For monthly data, Python may produce calendar-aligned YoY metrics when sufficient data exists.

This does **not** require `comparison_period`.

Do not ask for an explicit baseline merely because normal YoY output is enabled.

## 16.2 Explicit `growth_pct` threshold

A threshold such as:

```json
{
  "metric": "growth_pct",
  "operator": "gte",
  "threshold": 10
}
```

requires an explicit:

```text
comparison_period
```

The baseline must:

- use matching granularity;
- contain the same number of buckets;
- end before the main period begins.

If the user asks whether growth exceeds a threshold but has not defined the baseline, ask for clarification.

## Other supported threshold metrics

Current metrics:

```text
growth_pct
normalized_interest_mean
completeness_ratio
```

Operators:

```text
gt
gte
lt
lte
```

## Interpretation

Each criterion is independent:

```text
met
not_met
not_evaluable
```

`not_evaluable` is neither pass nor fail.

Never create a composite opportunity score.

---

# 17. follow-up-analysis.md

Use the previous report as state.

## Source of truth

Read:

```text
analysis.json.input
```

The input contains the resolved/frozen exact period.

## Rules

For follow-ups:

- change only requested fields;
- preserve all unrelated fields;
- preserve exact dates unless period is explicitly changed;
- rerun the CLI;
- use the new run's outputs;
- never edit old results manually.

Examples:

```text
"add Ukrainian Wikipedia"
"change the period to 36 months"
"JSON only"
"disable PDF"
"add a normalized-interest threshold"
```

If a change introduces a new requirement, load the corresponding workflow too.

Example:

```text
"add Ukrainian Wikipedia"
→ follow-up-analysis
→ multi-language-comparison
```

---

# 18. proxy-resolution.md

Use only when a direct topic representation is unavailable or the user explicitly proposes an alternative article set.

## Direct mapping first

A missing canonical sitelink is not permission to search for a replacement automatically.

## Approval

Before adding a non-equivalent article override:

1. explain which direct mapping is unavailable;
2. identify the proposed proxy article(s);
3. explain that the proxy measures those articles only;
4. ask for explicit approval.

## After approval

Use `query.article_overrides`.

Python resolves the override and compares its QID set with the canonical source concept set.

Possible result:

```text
comparison_equivalent = true
```

or:

```text
comparison_equivalent = false
```

If false:

- language-local metrics may be shown;
- direct comparison must remain invalid/excluded;
- the response must label the result as proxy evidence;
- never describe proxy pageviews as direct measurement of the original topic.

The agent must not decide QID equivalence itself.

---

# 19. artifact-validation.md

This workflow is mandatory before returning completed analysis artifacts.

## Requested outputs

Current configurable artifacts:

```text
JSON
PNG chart(s)
one-page PDF
```

## Validation

If JSON is enabled:

- verify the CLI-produced `analysis.json` exists;
- parse it;
- confirm schema version is supported (`2.1.0` currently);
- read metrics, warnings, resolution, comparison, and artifact paths from the report.

If charts are enabled:

- verify every reported PNG path exists.

If PDF is enabled:

- verify the reported PDF exists;
- verify it is readable;
- do not claim success from a path string alone.

## JSON-disabled runs

Do not assume `analysis.json` exists when `output.json = false`.

If the user explicitly disables JSON:

- validate only artifacts actually configured/generated;
- do not invent metrics that are not available through a validated machine-readable result;
- if a detailed numeric interpretation is required, prefer keeping JSON enabled as the audit artifact unless the user explicitly forbids generating it.

Do not silently override an explicit request not to generate JSON.

## Failure

If any requested artifact is missing or invalid:

- report that failure;
- do not claim it was generated successfully.

---

# 20. Run the Analysis

Keep the canonical command in `SKILL.md`:

```bash
python scripts/analyze.py --config <config.json> --output-dir <output-dir>
```

If `python` is unavailable and the repository virtual environment exists:

```bash
.venv/bin/python scripts/analyze.py --config <config.json> --output-dir <output-dir>
```

Direct Wikimedia API calls are not an alternative execution path.

---

# 21. Stop and Clarify

Create a concise global stop-condition section.

The agent must stop before pretending analysis can proceed when:

| Condition | Action |
|---|---|
| Article/topic meaning is materially ambiguous | Ask the user which concept they mean |
| Multi-language request lacks a safe source language | Ask for the source language |
| Resolver returns `REQUIRES_CLARIFICATION` | Explain the structured reason and ask for the required clarification |
| Topic mapping lacks a canonical sitelink | Keep it unresolved; use proxy workflow only with approval |
| Explicit `growth_pct` threshold lacks baseline | Ask for comparison period |
| Proposed proxy lacks approval | Ask before adding override |
| CLI fails | Report the CLI failure; do not reconstruct metrics manually |
| Requested artifact is missing/invalid | Report artifact failure |

Do not convert resolver uncertainty into agent certainty.

---

# 22. Interpret the Result

Keep global interpretation boundaries in `SKILL.md`.

At minimum:

- numbers come from the Python-generated report;
- Wikipedia language edition is not the same as a country;
- pageviews measure attention, not unique people;
- topic sums can include overlapping readers;
- pageviews do not prove purchase intent or willingness to pay;
- requested and available periods are distinct;
- unresolved mappings remain unresolved;
- proxy evidence remains proxy evidence;
- `not_evaluable` remains not evaluable;
- warnings and failed quality checks must not be hidden.

Detailed metric definitions belong in `methodology.md`.

---

# 23. Output Contract

For a successful analysis, the agent should return a concise user-facing summary containing:

1. what was analyzed;
2. query mode if relevant to interpretation;
3. Wikipedia edition(s);
4. effective/requested period as relevant;
5. the Python-generated findings that answer the user's question;
6. material quality/comparison/resolution warnings;
7. proxy caveats if applicable;
8. working artifact paths for requested outputs.

Do not impose a rigid sentence template.

The objective is consistent content, not identical prose.

---

# 24. Reference loading table

Add a compact reference table to `SKILL.md`.

Example:

```md
## References

| Need | Reference |
|---|---|
| Build or modify analysis config | [`input-schema.md`](references/input-schema.md) |
| Read or validate `analysis.json` | [`output-schema.md`](references/output-schema.md) |
| Explain metrics, resolution, normalization, quality, anomalies, confidence intervals, or limitations | [`methodology.md`](references/methodology.md) |
```

Workflow files may link directly to these references.

---

# 25. Workflow composition examples

Use these cases as documentation acceptance tests.

## Case A — simple article

User:

```text
Analyze astronomy interest in Ukrainian Wikipedia for the last 24 months.
```

Expected workflows:

```text
article-analysis
period-selection
artifact-validation
```

## Case B — multi-language topic

User:

```text
Compare learning English across Polish, Czech, and Ukrainian Wikipedia.
```

Expected workflows:

```text
topic-analysis
multi-language-comparison
period-selection
artifact-validation
```

Topic workflow must use the resolver's canonical source concept/QID mapping behavior.

## Case C — ambiguous topic

User:

```text
Analyze Java in English and Ukrainian Wikipedia.
```

Expected:

```text
article-analysis or topic-analysis depending user intent
→ resolver/ambiguity handling
→ stop and clarify
```

Do not silently choose programming language, island, or another sense.

## Case D — standard YoY question

User:

```text
How has interest changed year over year?
```

Expected:

```text
relevant article/topic workflow
period-selection
artifact-validation
```

Do not ask for `comparison_period` solely for standard monthly YoY analysis.

## Case E — explicit growth threshold

User:

```text
Is growth at least 15% compared with the previous period?
```

Expected:

```text
criteria-and-thresholds
period-selection
```

If the baseline is not unambiguously defined, clarify it.

## Case F — proxy

User:

```text
There is no Czech equivalent. Use "X" as a proxy.
```

Expected:

```text
proxy-resolution
multi-language-comparison
artifact-validation
```

Python determines whether the override is QID-equivalent.

## Case G — follow-up

User:

```text
Add Ukrainian Wikipedia to the previous analysis.
```

Expected:

```text
follow-up-analysis
multi-language-comparison
artifact-validation
```

Preserve previous exact dates and all unrelated settings.

## Case H — PDF-only request

User:

```text
Generate the PDF report only.
```

Expected:

```text
relevant analysis workflow
artifact-validation
```

Respect explicit output configuration. Do not assume a JSON file exists when JSON is disabled.

---

# 26. Current runtime facts that workflows must preserve

WT-M21 workflow documentation must match the current repository.

At minimum:

```text
report schema version = 2.1.0
methodology version = 2.1
languages = 1..20
topic candidate search = max 5
topic selected concepts = max 3
article overrides = 1..3 titles per language
period.months = 1..120, default 24
explicit date boundaries = inclusive
daily latest available day = yesterday
current partial month excluded from monthly collection
```

Do not duplicate these values unnecessarily in `SKILL.md`; place them in workflow/schema references where operationally relevant.

---

# 27. Documentation consistency requirements

Before completion verify:

- every workflow link from `SKILL.md` resolves;
- every workflow file uses repository-relative links;
- no workflow still describes pre-WT-M20 independent per-language topic search;
- no workflow tells the LLM to make its own semantic relevance decision;
- no workflow tells the agent to search an approximate replacement for a missing sitelink;
- proxy behavior matches `comparison_equivalent`;
- period behavior matches `input-schema.md`;
- output behavior matches report schema `2.1.0`;
- standard YoY and explicit `growth_pct` baseline semantics are not conflated;
- follow-up behavior uses `analysis.json.input`;
- artifact validation handles `output.json = false`;
- methodology remains the source for formulas and interpretation details.

---

# 28. Files expected to change

Primary:

```text
SKILL.md

references/workflows/article-analysis.md
references/workflows/topic-analysis.md
references/workflows/multi-language-comparison.md
references/workflows/period-selection.md
references/workflows/criteria-and-thresholds.md
references/workflows/follow-up-analysis.md
references/workflows/proxy-resolution.md
references/workflows/artifact-validation.md
```

SDD documentation:

```text
docs/sdd/M21-skill-orchestration-workflow-references.md
docs/sdd/INDEX.md
docs/sdd/STATUS.md      # if introduced/used
```

Optional consistency edits only if needed:

```text
README.md
references/input-schema.md
references/output-schema.md
references/methodology.md
docs/sdd/00-SDD-README.md
```

Do not modify Python runtime code as part of WT-M21 unless a documentation review proves the documented current behavior is impossible and the user explicitly expands the milestone.

---

# 29. Implementation order

Recommended order:

```text
1. Inventory every rule in the current SKILL.md
2. Classify each rule:
   - global invariant
   - workflow-specific instruction
   - schema detail
   - methodology detail
3. Create references/workflows/
4. Write workflow files against current WT-M20 behavior
5. Rewrite SKILL.md as the router
6. Verify every old rule is preserved or intentionally relocated
7. Validate all links
8. Run representative workflow-routing cases A–H
9. Run repository regression checks
```

Do not rewrite `SKILL.md` first and hope to reconstruct lost instructions later.

---

# 30. Verification

Runtime regression checks:

```bash
python -m pytest
ruff check .
mypy
git diff --check
```

Use repository-configured equivalents if necessary.

Documentation checks:

- manually follow routing cases A–H;
- inspect every relative link;
- search for stale pre-WT-M20 phrases such as independent target-language topic search;
- verify no workflow tells the agent to override resolver semantic decisions;
- verify all current `SKILL.md` safety rules remain represented.

WT-M21 does not require a new live Wikimedia run.

---

# 31. Acceptance criteria

WT-M21 is accepted when:

- `SKILL.md` is primarily an orchestration/router document;
- the frontmatter clearly describes skill activation;
- `When to Use` and `When Not to Use` are explicit;
- global rules are consolidated;
- preflight is explicit;
- workflow routing uses a Markdown table;
- the agent is instructed to load only relevant workflows;
- all eight workflow references exist;
- workflows share a consistent operational shape;
- topic workflow reflects implemented WT-M20 resolver authority;
- multi-language workflow respects `comparison_equivalent`;
- proxy workflow delegates QID equivalence to Python;
- period workflow reflects WT-M19 exact/daily/monthly behavior;
- criteria workflow distinguishes standard YoY from explicit `growth_pct` thresholds;
- follow-up workflow preserves frozen exact dates;
- artifact workflow handles JSON-enabled and JSON-disabled runs correctly;
- `SKILL.md` does not duplicate full methodology/schema content;
- no runtime behavior is changed;
- all regression checks pass.

---

# 32. Relationship to WT-M18

After WT-M21 is complete, rerun the inexpensive-model evaluation defined by WT-M18 against the current skill architecture.

The evaluation should verify not only numerical correctness but also instruction routing:

- the model selects the correct workflow(s);
- it does not load unrelated workflow documents unnecessarily;
- it obeys resolver clarification;
- it does not manually promote rejected candidates;
- it preserves follow-up state;
- it validates requested artifacts;
- it respects proxy/non-comparable results.

Keep raw evaluation evidence local under ignored `evaluation/`.

Only the final SDD status/result needs to be recorded in the repository.

---

# Definition of Done

WT-M21 is done when a tool-capable agent can open `SKILL.md`, determine whether Wikipedia Trends applies, load only the workflow references needed for the request, obey the current WT-M20 semantic-resolution boundary, build and run the current CLI configuration safely, validate the requested outputs, and explain the result without requiring a monolithic instruction file.
