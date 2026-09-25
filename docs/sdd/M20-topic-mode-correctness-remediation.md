# M20 — Topic Mode Correctness Remediation

**Spec ID:** WT-M20  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M19  
**Remediates:** WT-M09, WT-M12, WT-M13  
**Revalidation required after completion:** WT-M18

## SDD rule

This document is the source of truth for this remediation step.

The implementation agent must:

- implement only the scope defined by WT-M20;
- preserve accepted behavior from WT-M01 through WT-M19 unless this specification explicitly supersedes it;
- treat the correctness rules in this document as stronger than conflicting WT-M09, WT-M12, or WT-M13 behavior;
- avoid speculative features such as embeddings, LLM-based scoring, forecasting, or external data sources;
- stop and report any conflict that is not explicitly resolved by this specification.

WT-M20 is a correctness milestone, not a feature-expansion milestone.

## Context and problem statement

Agent evaluation and repository review exposed correctness failures in topic mode.

The current topic resolver performs MediaWiki search independently in every requested language and ranks candidates using search rank plus title-token overlap. Search rank is therefore allowed to contribute directly to relevance. A high-ranked MediaWiki result can be selected even when it has little or no semantic relationship to the requested topic.

This produced invalid topic selections for canonical scenarios such as:

- `learning English`;
- `intermittent fasting`.

The downstream pipeline can then successfully fetch pageviews, calculate metrics, draw charts, and generate a PDF for articles that do not represent the requested subject. This is a critical correctness failure because technically valid output can describe the wrong concept.

A second critical issue exists in normalized topic interest. When a topic is represented by multiple articles from the same Wikipedia language edition, the current pipeline fetches the same project-wide traffic once per selected article and aggregates those project totals. This multiplies the denominator by the number of selected topic articles and understates normalized interest.

A directly coupled aggregation issue also exists: if one selected topic article is `UNKNOWN` for a bucket while another article has data, the current topic aggregate can be marked `OBSERVED`. That makes a partial topic measurement look complete.

WT-M20 fixes these correctness failures before further feature work.

## Goal

Make topic-mode analysis conservative, reproducible, semantically auditable, and safe for inexpensive tool-capable agents.

After WT-M20:

1. MediaWiki search rank is used only for candidate discovery and deterministic tie-breaking, never as sufficient evidence of semantic relevance.
2. Topic candidates must pass deterministic semantic evidence gates in Python before they can be selected.
3. Multi-language topic analysis resolves a canonical source concept set once and maps the same concepts to target Wikipedia editions through Wikidata sitelinks.
4. The resolver must not independently search target languages for approximate replacements when a canonical equivalent is missing.
5. Topic aggregation must not silently treat partial article coverage as a complete observation.
6. Normalized topic interest must divide the aggregated topic numerator by exactly one project-traffic series per language edition.
7. Weak, ambiguous, or missing semantic mappings must prevent silent analysis and must be surfaced explicitly to the agent.
8. Canonical regression scenarios must prevent recurrence of the failures discovered during WT-M18.

## In scope

### Topic resolution

- source-language topic discovery;
- deterministic semantic evidence collection;
- hard relevance gates;
- candidate rejection;
- ambiguity handling;
- canonical concept identity through Wikidata QIDs;
- cross-language concept mapping through Wikidata sitelinks;
- explicit handling of missing direct equivalents;
- existing explicit article overrides;
- proxy/non-equivalent comparison safeguards.

### Topic analytics

- strict topic-bucket completeness semantics;
- corrected normalized-interest denominator;
- deduplicated project-level data retrieval and provenance;
- prevention of downstream analysis for unresolved direct topic mappings.

### Agent behavior and documentation

- update `SKILL.md` so the agent consumes resolver decisions instead of performing semantic validation as the primary correctness mechanism;
- update methodology documentation;
- update relevant input/output documentation if public contracts change;
- add regression tests for canonical failure cases.

## Out of scope

WT-M20 must not add:

- embeddings;
- sentence-transformer models;
- LLM-based relevance scoring inside Python;
- external web search as a resolver;
- Google Trends, Reddit, YouTube, or commercial market data;
- topic forecasting;
- market-demand prediction;
- synthetic opportunity scores;
- new chart types unrelated to correctness;
- new report formats;
- a general ontology or web-scale topic-modeling system.

False negatives are preferable to false positives in this milestone. When deterministic evidence is insufficient, the system must request clarification rather than guess.

# 1. Compatibility and superseded behavior

WT-M20 intentionally supersedes the following earlier behavior.

## WT-M12 candidate discovery

WT-M12 allowed topic selection from:

```text
MediaWiki search rank + exact/partial title token overlap
```

This is replaced by:

```text
candidate discovery
    ↓
canonical metadata lookup
    ↓
semantic evidence collection
    ↓
hard acceptance/rejection gate
    ↓
ranking among accepted candidates only
```

Search rank alone must never cause a candidate to be accepted.

## WT-M12 cross-language discovery

Language-local independent topic search is no longer the default for a multi-language topic comparison.

A canonical source concept set is resolved once, then mapped to requested languages by structured Wikidata identity.

## WT-M12 aggregation

The previous rule:

```text
topic_views = sum(available selected article views)
```

is replaced by strict bucket completeness defined in section 10.

## WT-M09 normalization

For topic mode, the denominator is one project-wide traffic series per Wikipedia language edition, not one project-wide series per selected article.

## Article mode

`query.mode = article` behavior from WT-M04 must remain unchanged except for shared internal refactoring that does not alter its public behavior.

# 2. Topic source-language contract

Topic discovery needs one language in which the requested phrase is interpreted.

`query.source_language` is the canonical discovery language for topic mode.

## Rules

### Single-language topic analysis

If:

```text
languages = ["uk"]
```

and `query.source_language` is absent, the resolver may infer:

```text
source_language = "uk"
```

### Multi-language topic analysis

If more than one language is requested, the resolver must not guess the source language.

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

If a multi-language topic request reaches the resolver without `source_language`, it must stop before topic search and return or raise an actionable structured error indicating that the topic source language is required.

It must not:

- use the first target language silently;
- assume English silently;
- independently submit the same phrase to every language edition.

## Agent rule

`SKILL.md` must instruct the agent to clarify or provide the language of the topic phrase before invoking multi-language topic analysis when it cannot be determined safely.

# 3. Source candidate discovery

Topic candidate discovery occurs only in the source Wikipedia edition.

## Search boundary

Use MediaWiki Search with the existing bounded search size:

```text
top 5 results
```

The result list is a candidate-discovery mechanism only.

For each search result:

1. resolve redirects to the canonical page;
2. discard missing pages;
3. detect and exclude list pages when reliably detectable;
4. detect disambiguation pages;
5. obtain Wikidata QID when available;
6. fetch deterministic semantic metadata for the candidate.

## Disambiguation rule

If the normalized requested topic directly corresponds to a disambiguation page, the resolver must return `REQUIRES_CLARIFICATION`.

It must not skip the disambiguation result and silently choose one of its meanings.

# 4. Semantic evidence

Semantic relevance must be based on deterministic, inspectable evidence.

For each source candidate, collect when available:

- requested topic;
- canonical Wikipedia title;
- MediaWiki search rank;
- Wikidata QID;
- Wikidata label in the source language;
- Wikidata aliases in the source language;
- Wikidata description in the source language.

English fallback metadata may be used only when the source-language Wikidata field is absent. The fallback must be explicit in internal evidence/provenance.

No LLM call is allowed for candidate acceptance.

## Text normalization

All lexical comparisons must use one deterministic normalization function.

At minimum:

1. Unicode NFKC normalization;
2. `casefold()`;
3. replace `_` with whitespace;
4. normalize punctuation to whitespace;
5. collapse repeated whitespace;
6. tokenize consistently with Unicode-aware tokenization;
7. remove empty tokens.

Do not add large language-specific stemming/lemmatization dependencies in WT-M20.

## Evidence fields

The implementation should expose an internal typed evidence model equivalent to:

```python
TopicCandidateEvidence(
    canonical_title=...,
    wikidata_id=...,
    search_rank=...,
    exact_title_match=...,
    exact_label_match=...,
    exact_alias_match=...,
    query_token_coverage=...,
    lexical_anchor=...,
    decision=...,
    reason=...,
)
```

The exact class name may differ, but the evidence must be testable without parsing prose.

# 5. Hard relevance gate

Candidate acceptance and candidate ranking are separate operations.

## Direct semantic match

A candidate is a strong direct match if any of the following is true:

```text
normalized query == normalized canonical title
normalized query == normalized Wikidata label
normalized query == any normalized Wikidata alias
```

A strong direct match passes the relevance gate unless the page is a disambiguation/list page.

## Token-coverage semantic match

When there is no exact title/label/alias match, compute:

```text
query_token_coverage =
    number of unique normalized query tokens found in candidate semantic text
    /
    number of unique normalized query tokens
```

Candidate semantic text consists of:

```text
canonical title
+ Wikidata label
+ Wikidata aliases
+ Wikidata description
```

The default minimum coverage is:

```text
0.80
```

Additionally, at least one query token must occur in:

```text
canonical title
OR Wikidata label
OR Wikidata alias
```

A candidate must not pass only because all overlap comes from the description.

## Rejection

A candidate is rejected when:

- it is a list/disambiguation page for selection purposes;
- it has no lexical anchor;
- `query_token_coverage < 0.80` and no exact title/label/alias match exists;
- semantic metadata is too incomplete to satisfy a direct-match rule;
- it is otherwise not safe to identify as the requested topic.

Example:

```text
requested topic: learning English
candidate: Da Vinci
title/label/alias match: false
query-token coverage: insufficient
decision: rejected
reason: insufficient_semantic_evidence
```

## Search rank

Search rank:

- may be stored as provenance;
- may be used as a final deterministic tie-breaker among already accepted candidates;
- must not add relevance points;
- must not turn a rejected candidate into an accepted candidate.

This invariant is mandatory.

# 6. Candidate ordering and ambiguity

After rejection, rank only accepted candidates.

Recommended deterministic ordering:

1. exact normalized title match;
2. exact Wikidata label match;
3. exact Wikidata alias match;
4. higher query-token coverage;
5. lower MediaWiki search rank;
6. canonical title as stable final tie-breaker.

Select no more than three source concepts.

## Clarification cases

Return `REQUIRES_CLARIFICATION` without starting pageview collection when:

- the requested topic resolves to a disambiguation page;
- multiple accepted candidates represent materially different explicit parenthetical senses with no safe dominant interpretation;
- no candidate passes the relevance gate but one or more weak candidates are available for the user to inspect;
- multi-language topic analysis lacks a source language;
- a required canonical cross-language mapping is unavailable and no explicit approved override exists.

The resolver must provide an actionable reason such as:

```text
disambiguation_page
source_language_required
ambiguous_topic_candidates
insufficient_semantic_evidence
missing_canonical_sitelink
```

If current public models cannot represent a new reason without structural changes, extend the existing reason field rather than putting the decision only in log text.

# 7. Canonical topic concepts

The selected source candidates define the canonical topic concept set.

For multi-language topic comparison, every selected source concept must have a Wikidata QID.

Example conceptual structure:

```text
requested topic
    ↓
source candidate A → QID-A
source candidate B → QID-B
    ↓
canonical concept set = [QID-A, QID-B]
```

A candidate without a QID may still be used for a single-language topic analysis if it passes the relevance gate.

A candidate without a QID must not be used as a canonical concept for automatic cross-language mapping.

# 8. Cross-language mapping

For each selected source QID, resolve the requested target edition through Wikidata sitelinks.

Example:

```text
QID-A
├── plwiki → article A-pl
├── cswiki → article A-cs
└── ukwiki → article A-uk
```

## Required invariants

For automatic direct comparison:

- every target language must represent the same canonical source concept set;
- each target article must correspond to the expected QID;
- target-language search must not be used to replace a missing sitelink with an approximately similar article;
- selected concept order must remain deterministic;
- target article provenance must identify Wikidata/sitelink resolution.

## Missing direct equivalent

If any canonical concept lacks a required target-language sitelink, the language must not silently continue as a direct equivalent.

The resolver must surface:

```text
REQUIRES_CLARIFICATION
reason = missing_canonical_sitelink
```

for that language representation, or an equivalent structured unresolved outcome supported by the public model.

No pageviews for that missing direct representation may be included in the direct cross-language comparison.

# 9. Explicit article overrides and proxies

Existing `query.article_overrides` support must remain available.

An explicit override is a reviewed representation, not automatic proof of semantic equivalence.

## Direct override

If the resolved override article QID set equals the canonical source concept QID set, it may participate as a direct mapping.

## Proxy override

If an override uses a different QID set:

- language-local metrics may be generated for the explicitly selected proxy;
- the output must clearly identify that the selection came from `EXPLICIT_ARTICLE_OVERRIDE`;
- the direct multi-language topic comparison must treat that language as non-equivalent/non-comparable;
- the report must warn that proxy pageviews measure the selected article, not the original topic;
- proxy data must not be silently presented as a like-for-like topic comparison.

`SKILL.md` must instruct the agent to request user approval before supplying a proxy override.

Python remains responsible for detecting QID mismatch and preventing a false like-for-like comparison.

# 10. Strict topic aggregation semantics

Topic aggregation must distinguish a complete aggregate from a partial aggregate.

For one timestamp/bucket with selected articles `A..N`:

## Complete known bucket

If every selected article is known (`OBSERVED` or `ZERO_INFERRED`):

```text
topic_views = sum(all selected article views)
```

Status:

- `ZERO_INFERRED` only if every selected article is `ZERO_INFERRED`;
- otherwise `OBSERVED`.

## Incomplete bucket

If any selected article is `UNKNOWN`:

```text
topic views = null
status = UNKNOWN
```

Do not sum the known subset and label it `OBSERVED`.

Example:

```text
A = UNKNOWN
B = 300
C = 200

old behavior:
topic = 500 OBSERVED    ❌

WT-M20 behavior:
topic = null UNKNOWN    ✅
```

This rule applies to daily and monthly topic observations.

## Rationale

The configured topic is defined by the complete selected article set. A partial sum is not the same measurement and must not enter totals, YoY, normalized interest, anomaly detection, or confidence intervals as if complete.

# 11. Correct normalized-interest denominator

For one language edition:

```text
topic numerator =
    sum of all selected topic articles for each complete known bucket
```

The denominator is:

```text
ONE project-wide pageview series for that language edition
```

Formula remains:

```text
normalized_interest =
    aggregated_topic_views
    /
    project_views
    *
    1_000_000
```

## Forbidden behavior

For three topic articles from `en.wikipedia`:

```text
project_total
+ project_total
+ project_total
```

must never be used as the denominator.

## Required retrieval behavior

The pipeline must fetch or read from cache project pageviews once per unique:

```text
(project, requested period, granularity, access, agent)
```

within one analysis run.

Example:

```text
3 selected articles in pl.wikipedia
→ 3 per-article series
→ 1 aggregated topic series
→ 1 pl.wikipedia project series
→ 1 normalized-interest calculation
```

## Provenance

`analysis.json.sources` must contain one project-level source entry per unique project-period-granularity request, not one duplicate entry per selected article.

Article-level provenance remains one entry per selected article request.

# 12. Pipeline safeguards

The pipeline must not rely on the agent to repair invalid resolver output.

## Before data collection

For topic mode:

- if direct topic resolution for a language requires clarification, do not fetch pageviews for that unresolved direct representation;
- do not fabricate or translate a replacement title;
- do not independently search another target-language candidate as fallback.

## Comparison

A language can participate in direct topic comparison only when:

- its selected articles are resolved;
- its canonical QID set matches the source concept set;
- it is not a non-equivalent proxy;
- existing completeness/shared-period rules also pass.

A proxy may still receive language-local analysis, but the direct cross-language comparison must mark it non-comparable.

# 13. Agent contract changes

`SKILL.md` must no longer make the LLM the primary semantic validator.

Replace the current effective flow:

```text
resolver selects candidate
    ↓
agent decides whether resolver was semantically correct
```

with:

```text
resolver validates semantic evidence
    ↓
resolver returns safe status
    ↓
agent communicates the status
```

## Required agent behavior

### Resolved

If the resolver returns a direct resolved mapping:

```text
continue to CLI analysis
```

### Requires clarification

If the resolver reports ambiguity, weak evidence, missing source language, or missing canonical mapping:

```text
ask the user for clarification
```

Do not choose a candidate manually.

### Proxy

If a proxy is proposed:

1. explain which direct representation is unavailable;
2. name the proposed proxy article;
3. ask the user for approval;
4. only after approval, rerun with the explicit override;
5. preserve the proxy warning and non-comparable status.

The agent must never convert a resolver rejection into a direct match by reasoning in prose.

# 14. Data-model guidance

Prefer the smallest model changes that make the decisions inspectable and testable.

At minimum, the implementation needs typed representation for semantic evidence and a structured reason for rejected/clarification outcomes.

A possible internal shape is:

```python
class TopicCandidateDecision(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class TopicCandidateEvidence(BaseModel):
    canonical_title: str
    wikidata_id: str | None
    search_rank: int
    exact_title_match: bool
    exact_label_match: bool
    exact_alias_match: bool
    query_token_coverage: float
    lexical_anchor: bool
    decision: TopicCandidateDecision
    reason: str
```

This exact API is not mandatory.

The following properties are mandatory:

- deterministic fields;
- no free-form LLM score;
- rejection reason is machine-readable;
- tests can inspect why a candidate passed or failed.

Do not introduce an opaque scalar “semantic confidence score”.

# 15. Report and methodology requirements

Update `references/methodology.md` to document:

- source-language topic resolution;
- candidate search versus acceptance;
- semantic evidence used;
- `0.80` query-token coverage gate;
- search rank as tie-breaker only;
- canonical QID concept set;
- Wikidata sitelink mapping;
- missing-sitelink behavior;
- proxy semantics;
- strict topic aggregation;
- one-project-series normalized denominator;
- language-edition interest is not country demand;
- topic pageviews are not unique users or purchase intent.

Update output documentation if serialized resolution metadata changes.

If the public `analysis.json` contract changes structurally, update the report schema version according to the project's versioning convention. Do not silently change a versioned public schema.

# 16. Testing requirements

All new correctness tests must be deterministic and must not depend on live Wikimedia traffic in CI.

Use mocked MediaWiki/Wikidata/Pageviews responses or stable local fixtures.

## Unit tests — semantic normalization

Cover:

- Unicode normalization;
- case folding;
- punctuation/whitespace normalization;
- exact title match;
- exact label match;
- exact alias match;
- token coverage;
- lexical-anchor requirement;
- rejection below threshold;
- rank does not override rejection.

## Unit tests — topic aggregation

Cover:

```text
all articles observed
observed + zero_inferred
all zero_inferred
one unknown + one observed
one unknown + zero_inferred
daily buckets
monthly buckets
```

The critical regression assertion is:

```text
any selected article UNKNOWN
→ aggregate UNKNOWN
```

## Integration tests — topic resolver

Use mocked MediaWiki and Wikidata responses for:

### Direct topic

```text
Astronomy-like unambiguous topic
→ direct accepted candidate
```

### Irrelevant rank-1 result

```text
requested topic = learning English
rank-1 unrelated candidate
→ rejected even though search rank is 1
```

### Broad/weak candidate

```text
requested topic = intermittent fasting
candidate represents a broader/different fasting concept
→ must not be accepted solely because "fasting" overlaps
```

### Ambiguous topic

```text
Java-like ambiguous topic
→ REQUIRES_CLARIFICATION
→ no pageview collection
```

### Cross-language mapping

```text
source QID
→ target sitelinks
→ same QID set in every directly comparable language
```

### Missing sitelink

```text
source concept lacks one requested target edition
→ no target-language fallback search
→ clarification/unresolved outcome
```

### Explicit override

Cover both:

- QID-equivalent direct override;
- different-QID proxy override.

## Pipeline tests — normalized denominator

Create a deterministic fixture:

```text
article A = 100
article B = 200
article C = 300
project traffic = 1_000_000
```

Expected:

```text
aggregated topic views = 600
normalized interest = 600 views per 1M project views
```

The test must additionally assert that project pageviews are requested once for the language, not three times.

## Provenance test

For a three-article topic in one language:

```text
3 article source entries
1 project source entry
```

must be produced for one period/granularity.

## Regression tests for canonical product scenarios

Add deterministic regression coverage for the original scenarios relevant to topic correctness:

- intermittent fasting — Polish/Czech;
- learning English — selected language editions;
- astronomy article mode remains unchanged.

Fixtures must encode reviewed source concepts and QIDs at fixture-creation time.

Do not assert against unstable live MediaWiki search ordering in normal CI.

# 17. End-to-end behavior

At least one mocked E2E path must exercise the real resolver boundary rather than replacing it with a pre-resolved `TopicResolution`.

The E2E test must prove:

```text
config
→ source topic discovery
→ relevance gate
→ canonical QIDs
→ target sitelinks
→ article pageviews
→ strict aggregation
→ one project denominator
→ normalized metrics
→ JSON
→ PNG
→ PDF
```

A second negative E2E path must prove:

```text
weak/ambiguous topic
→ clarification
→ no downstream pageview analysis
```

The test does not need live network access.

# 18. Performance and network constraints

WT-M20 must keep resolver work bounded.

For a default topic request:

- source MediaWiki search remains limited to 5 candidates;
- metadata lookups must be bounded to those candidates;
- repeated Wikidata entities should not be fetched unnecessarily within one resolution run;
- existing filesystem cache may be reused;
- no unbounded crawl or recursive link traversal is allowed.

Correctness takes priority over minimizing a small number of deterministic metadata requests.

# 19. Logging and failure behavior

Logs may include:

- source language;
- candidate count;
- accepted candidate count;
- rejected candidate count;
- rejection reason codes;
- canonical QID count;
- missing target sitelink languages.

Logs must not be the only place where a correctness decision exists.

Anything the pipeline needs to prevent invalid analysis must be represented in typed runtime state.

# 20. Acceptance criteria

WT-M20 is accepted only when all of the following are true.

### Semantic correctness

- MediaWiki search rank cannot make an otherwise irrelevant candidate valid.
- Candidates with insufficient semantic evidence are rejected.
- `learning English` regression fixtures cannot select known unrelated pages.
- broader/different `intermittent fasting` candidates cannot pass on one shared token alone.
- ambiguous topics stop before pageview collection.
- multi-language topic discovery uses one source concept set.
- target languages are mapped through the same canonical QIDs.
- missing sitelinks do not trigger approximate target-language search.

### Aggregation correctness

- any unknown component makes the aggregated topic bucket unknown;
- complete known article sets sum exactly;
- zero-inferred semantics remain explicit.

### Normalization correctness

- one project denominator is used per language edition;
- a three-article topic does not triple the denominator;
- normalized-interest fixture arithmetic matches the expected hand calculation;
- project source provenance is not duplicated per article.

### Comparison safety

- only QID-equivalent direct mappings participate in like-for-like comparison;
- proxy mismatches cannot be presented as directly comparable;
- proxy warnings remain visible.

### Regression safety

- article mode behavior remains intact;
- WT-M19 daily/monthly period behavior remains intact;
- all existing tests pass after intentional expectation updates;
- Ruff passes;
- strict mypy passes;
- `git diff --check` passes;
- new resolver, aggregation, normalization, and E2E regression tests pass.

### Agent contract

- `SKILL.md` consumes resolver decisions;
- the agent is not responsible for inventing a semantic pass/fail decision;
- clarification and proxy approval flows are explicit.

# 21. Required files likely to change

Expected implementation surface:

```text
src/wiki_trends/article_resolver.py
src/wiki_trends/models.py
src/wiki_trends/analytics.py
src/wiki_trends/pipeline.py
src/wiki_trends/comparison.py
SKILL.md
references/methodology.md
references/input-schema.md
references/output-schema.md
tests/integration/test_article_resolver.py
tests/unit/test_topic_mode.py
tests/unit/test_normalization.py
tests/e2e/test_cli_scenarios.py
tests/fixtures/...
```

Avoid unrelated refactors.

# 22. Recommended implementation order

Implement WT-M20 in this order:

```text
1. Add deterministic semantic normalization/evidence helpers
2. Separate candidate discovery from candidate acceptance
3. Add hard relevance rejection
4. Resolve canonical source QID concept set
5. Replace independent target-language search with QID sitelink mapping
6. Add missing-equivalent / proxy safeguards
7. Fix strict topic aggregation semantics
8. Fix one-project-series normalized denominator
9. Deduplicate project provenance
10. Update SKILL.md and methodology
11. Add regression and negative tests
12. Run the complete verification suite
```

Do not start with report/UI changes before the resolver and numeric correctness are fixed.

# 23. Verification commands

At minimum run:

```bash
python -m pytest
ruff check .
mypy
git diff --check
```

Use the repository's configured command variants if they differ.

A live Wikimedia smoke test is optional and must not replace deterministic mocked acceptance tests.

# 24. Post-M20 revalidation

WT-M20 implementation does not by itself mark WT-M18 as accepted.

After WT-M20 is accepted:

1. rerun the inexpensive tool-capable agent evaluation defined by WT-M18;
2. include at minimum the three canonical product scenarios and the ambiguous-topic case;
3. verify that the agent follows resolver clarification instead of selecting weak candidates itself;
4. verify that reported normalized topic interest matches Python output;
5. keep evaluation prompts, transcripts, matrices, and generated artifacts local under ignored `evaluation/`;
6. record only the milestone/status outcome in SDD status documentation.

MVP readiness is restored only when the WT-M18 acceptance gate passes after this remediation.

# Definition of Done

WT-M20 is done when topic mode cannot silently produce a valid-looking report for a semantically invalid topic representation, topic normalization uses the correct denominator, incomplete topic buckets are not treated as complete observations, and deterministic regression tests prove those guarantees without relying on LLM judgment.
