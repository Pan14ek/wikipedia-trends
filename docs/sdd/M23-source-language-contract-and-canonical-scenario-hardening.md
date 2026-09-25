# M23 — Source-Language Contract and Canonical Scenario Hardening

**Spec ID:** WT-M23  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M22.1  
**Precedes:** WT-M24 and WT-M18.1 revalidation  
**Primary risk addressed:** fast/inexpensive agents building semantically wrong configs

## SDD rule

This document is the source of truth for source-language semantics after WT-M20–WT-M22.

The implementation agent must:

- preserve existing article/topic resolution methodology unless this specification explicitly changes configuration validation or documentation;
- make `source_language` mean one thing everywhere;
- ensure canonical user scenarios exercise the real source-language contract rather than bypassing it through mocks;
- classify a missing source language for a multi-language request as a configuration failure before network resolution starts;
- preserve the ability to use a source language that is not one of the requested output editions;
- avoid agent-generated translations of canonical article titles;
- avoid broad unrelated refactors.

---

# 1. Context

The current repository has a mismatch between:

- user-facing prompts;
- documentation;
- example configs;
- deterministic E2E configs;
- resolver behavior.

The resolver already has the important capability:

```text
query.value
+
query.source_language
→ canonical source concept
→ structured mapping to requested target Wikipedia editions
```

However, several current examples/tests encode the source language as though it were the requested target edition.

Examples of the problematic pattern include the conceptual equivalent of:

```json
{
  "query": {
    "mode": "article",
    "value": "Astronomy"
  },
  "languages": ["uk"]
}
```

For a one-language request, runtime inference currently makes:

```text
source_language = uk
```

which means the resolver searches for the literal English string `Astronomy` in Ukrainian Wikipedia.

Likewise, a multi-language request such as:

```json
{
  "query": {
    "mode": "article",
    "value": "Intermittent fasting",
    "source_language": "pl"
  },
  "languages": ["pl", "cs"]
}
```

says that the English phrase `Intermittent fasting` should be interpreted as a Polish source title.

A mocked pipeline may still pass because resolver behavior is replaced by a test double. A real inexpensive agent using the live resolver can therefore fail even when the E2E test appears green.

A second mismatch exists at the CLI boundary.

`AnalysisConfig` currently accepts a multi-language config with no `source_language`. The resolver rejects it later. Because configuration loading already succeeded, the CLI classifies this as:

```text
exit 1
analysis_error
```

instead of the intended:

```text
exit 2
configuration_error
```

This conflicts with the agent recovery contract introduced by WT-M22.

WT-M23 fixes both problems.

---

# 2. Goal

Make the following contract obvious and enforceable:

```text
source_language
= the Wikipedia language in which query.value is interpreted/resolved

languages
= the Wikipedia language editions whose metrics the user wants
```

These concepts are independent.

The source language:

- may equal one of the target languages;
- may differ from every target language;
- does not have to appear in `languages`.

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

means:

```text
Interpret "Astronomy" in English Wikipedia
→ resolve the canonical concept
→ map that concept to Ukrainian Wikipedia
→ analyze Ukrainian Wikipedia only
```

It does **not** request English Wikipedia metrics.

---

# 3. Definitions

## 3.1 Query value language

The language in which the string:

```text
query.value
```

is intended to be interpreted.

Examples:

```text
"Astronomy"              → en
"Intermittent fasting"   → en
"learning English"       → en
"Астрономія"             → uk
"Přerušovaný půst"       → cs
```

The agent may identify an obvious phrase language from the user's request.

It must not guess when the language is materially ambiguous.

## 3.2 Source language

`query.source_language` identifies the Wikipedia edition in which the source title/topic phrase is resolved.

It is a semantic input, not an output-selection field.

## 3.3 Target languages

`languages` identifies the editions for which the user wants pageview analysis.

These are output/analysis editions.

---

# 4. Normative source-language rules

## 4.1 Multi-language analysis

For both:

```text
query.mode = article
query.mode = topic
```

when:

```text
len(languages) > 1
```

`query.source_language` is required.

The config layer must reject a missing value before any resolver/network work.

Required failure class:

```text
configuration validation
→ CLI exit 2
→ error_type = configuration_error
```

Do not defer this validation to `ArticleResolver.resolve()`.

The resolver may retain its defensive validation for direct callers.

## 4.2 Single-language analysis

For a one-language request, runtime inference remains supported for backward compatibility:

```text
source_language absent
+
languages = ["uk"]
→ resolver may infer source_language = "uk"
```

However, the agent-facing rule is stricter:

> Omit `source_language` only when `query.value` is intentionally expressed for the same Wikipedia edition being analyzed.

If the query phrase is English but the requested edition is Ukrainian:

```text
"Astronomy"
languages = ["uk"]
```

the agent should explicitly set:

```text
source_language = "en"
```

The agent must not rely on single-language inference in this case.

## 4.3 Source language may be outside target languages

This is valid:

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

Validation must not require:

```text
source_language ∈ languages
```

Do not fetch source-language pageviews unless the source language is also listed in `languages`.

## 4.4 Do not translate titles manually

The agent must not transform:

```text
Astronomy
```

into:

```text
Астрономія
Astronomia
Astronomie
```

and submit those as independent direct targets.

The intended flow is:

```text
source phrase/title
→ source-language resolver
→ canonical page/QID
→ Wikidata sitelink / structured language link
→ target edition
```

Topic mode retains the stronger WT-M20 rule:

```text
source topic discovery once
→ canonical source QIDs
→ target sitelinks
```

No target-language approximate search is introduced by WT-M23.

---

# 5. Configuration validation change

Implement the cross-field rule in `AnalysisConfig`.

Conceptual validation:

```python
if len(self.languages) > 1 and self.query.source_language is None:
    raise ValueError(
        "query.source_language is required when analyzing multiple Wikipedia language editions"
    )
```

Exact wording may differ but must clearly identify:

```text
query.source_language
multiple language editions
```

Do not implement this only for topic mode.

It applies to:

```text
article
topic
```

Do not enforce source-target membership.

The validation must happen during:

```text
load_config(...)
```

so the CLI catches it in the existing configuration-error branch.

---

# 6. CLI behavior

Given:

```json
{
  "query": {
    "mode": "topic",
    "value": "learning English"
  },
  "languages": ["pl", "cs", "uk"]
}
```

the expected CLI behavior is:

```text
no resolver/network request
exit code = 2
stderr = structured CLI error JSON
error_type = configuration_error
```

The error must not become:

```text
exit 1
analysis_error
```

This is important because WT-M22 teaches agents:

```text
exit 2 → inspect/fix configuration
exit 1 → runtime/analysis failure
```

WT-M23 must keep that protocol true.

---

# 7. Canonical product scenarios

Normalize the three original product scenarios so they exercise the real contract.

## Scenario A — Astronomy in Ukrainian Wikipedia

User intent:

```text
Analyze whether interest in astronomy is growing in Ukrainian Wikipedia
and expose reliability checks.
```

Canonical config semantics:

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

Expected resolution flow:

```text
enwiki "Astronomy"
→ canonical concept
→ ukwiki sitelink "Астрономія"
→ collect uk.wikipedia pageviews
```

English Wikipedia metrics are not requested.

## Scenario B — Intermittent fasting in Polish vs Czech Wikipedia

User intent:

```text
Compare interest in intermittent fasting in Polish and Czech Wikipedia
over the last 24 complete months.
```

Canonical article-mode config:

```json
{
  "query": {
    "mode": "article",
    "value": "Intermittent fasting",
    "source_language": "en"
  },
  "languages": ["pl", "cs"]
}
```

Expected flow:

```text
enwiki canonical concept
→ structured mappings to plwiki + cswiki
→ collect only requested target editions
```

Do not use:

```text
source_language = pl
```

with an English `query.value`.

## Scenario C — Learning English topic comparison

User intent:

```text
Compare interest in learning English across Polish, Czech, and Ukrainian
Wikipedia.
```

Canonical config:

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

Expected flow:

```text
English source topic discovery
→ deterministic semantic acceptance
→ canonical QID set
→ pl/cs/uk sitelinks
→ target-edition analysis
```

This scenario must exercise WT-M20 rather than bypassing topic resolution with a fake per-language selection.

---

# 8. Documentation changes

Update the source-language explanation consistently.

## 8.1 `SKILL.md`

Preflight must make the distinction explicit.

Recommended compact rule:

```text
`query.source_language` is the language in which the supplied article title or
topic phrase should be resolved. It is independent of the requested `languages`
and may be outside them. For multi-language analysis it is required. For a
single target edition, omit it only when the supplied phrase/title is already
in that edition's language.
```

Do not turn `SKILL.md` into a long methodology document.

## 8.2 `references/input-schema.md`

Add at least one example where:

```text
source_language != target language
```

Use the astronomy example.

Explicitly state:

```text
source_language does not need to appear in languages
```

## 8.3 `references/workflows/article-analysis.md`

Replace any rule equivalent to:

```text
Use the requested language as source_language for a one-language request.
```

with:

```text
Use the language of the supplied source title/concept phrase.
For a one-language request, target-language inference is safe only when the
supplied title is intentionally in that target language.
```

## 8.4 `references/workflows/topic-analysis.md`

Make the same source-phrase distinction explicit.

For multi-language topics:

```text
source language must be known before config creation
```

If the user writes an obviously English topic phrase such as `learning English`,
the agent may set `source_language = "en"` without asking a redundant question.

If it cannot safely determine the phrase language, clarify.

## 8.5 README

Keep the public explanation concise.

The README should contain one clear sentence/example showing:

```text
source language can differ from analyzed editions
```

Deep rules remain in `input-schema.md` and workflows.

---

# 9. Example config change

Update:

```text
examples/astronomy-uk.json
```

from implicit Ukrainian source interpretation to explicit English source resolution:

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

Preserve existing period, criteria, and output fields.

This example is user-facing and must not teach the wrong semantic pattern.

---

# 10. Test changes

## 10.1 Config validation

Add tests proving:

### Valid

```text
article:
source_language = en
languages = [uk]

topic:
source_language = en
languages = [pl, cs, uk]

article:
source_language = en
languages = [pl, cs]
```

### Invalid

```text
article:
source_language absent
languages = [pl, cs]

topic:
source_language absent
languages = [pl, cs, uk]
```

### Important valid boundary

This must remain valid:

```text
source_language = en
languages = [uk]
```

Do not add a membership validator that rejects it.

## 10.2 CLI classification

Test an invalid multi-language config with no source language.

Assertions:

```text
exit code == 2
stderr parses as JSON
status == "error"
error_type == "configuration_error"
message mentions source_language
```

Assert the resolver/pipeline is not called.

## 10.3 Canonical E2E config tests

Correct the existing canonical test configs.

At minimum:

```text
Astronomy:
value = Astronomy
source_language = en
languages = [uk]

Intermittent fasting:
value = Intermittent fasting
source_language = en
languages = [pl, cs]

Learning English:
value = learning English
source_language = en
languages = [pl, cs, uk]
```

Do not let a test double hide an invalid source-language configuration.

## 10.4 Resolver integration regression

Add mocked resolver coverage where the source edition is not included in the
requested output editions.

Example:

```text
source_language = en
languages = [uk]
```

The mocked HTTP sequence should prove:

```text
enwiki source lookup occurs
Wikidata/sitelink mapping occurs
ukwiki target lookup occurs
```

and that the resolved article belongs to:

```text
uk.wikipedia
```

## 10.5 Topic canonical regression

Use the existing semantic regression fixture where applicable.

For `learning English`:

```text
source_language = en
canonical QID = Q130192
```

For `intermittent fasting` topic regression, preserve:

```text
canonical QID = Q1666254
```

WT-M23 must not weaken WT-M20 semantic gates.

---

# 11. Repository-wide config audit

Search for valid-looking multi-language configs in:

```text
README.md
SKILL.md
references/
examples/
docs/sdd/
tests/
```

Classify matches:

```text
historical spec example
current normative documentation
runtime test fixture
user-facing example
```

Do not rewrite old historical text merely because it describes a superseded
milestone.

Do update active documentation/tests that teach or depend on the current
contract.

Especially inspect configs containing:

```text
"languages": [ ... more than one ... ]
```

without:

```text
"source_language"
```

Some current tests that only exercise config parsing will need intentional
updates because they will become invalid under the new contract.

---

# 12. Agent preflight behavior

The cheap-model path should be mechanically understandable.

Recommended decision table:

| Situation | Agent behavior |
|---|---|
| One target edition; title/topic phrase clearly in that edition's language | source may be omitted/inferred |
| One target edition; phrase is clearly in another language | set explicit source language |
| Multiple target editions; source phrase language is clear | set explicit source language |
| Multiple target editions; source phrase language is unclear | ask user |
| Source language is not a requested target | allowed |
| Target title differs from source phrase | let resolver map it; do not translate manually |

---

# 13. Out of scope

Do not:

- add automatic language-detection ML;
- add external translation services;
- translate titles with an LLM;
- change topic semantic thresholds;
- change Wikidata identity rules;
- add fuzzy target-language search;
- require source language to be one of the target editions;
- change analytics metrics;
- change report schema;
- change CLI schema version;
- redesign follow-up state.

A future language detector may be considered separately if agent evaluation
shows phrase-language identification is a recurring problem.

---

# 14. Expected implementation surface

Likely runtime changes:

```text
src/wiki_trends/config.py
```

Potential defensive behavior remains in:

```text
src/wiki_trends/article_resolver.py
```

but large resolver changes are not expected.

Documentation:

```text
SKILL.md
README.md
references/input-schema.md
references/workflows/article-analysis.md
references/workflows/topic-analysis.md
```

Examples:

```text
examples/astronomy-uk.json
```

Tests:

```text
tests/unit/test_config.py
tests/unit/test_cli.py
tests/integration/test_article_resolver.py
tests/e2e/test_cli_scenarios.py
```

plus any other current config fixture that becomes invalid.

---

# 15. Verification

Run:

```bash
python -m pytest
ruff check .
mypy
git diff --check
```

Also run:

```bash
python scripts/analyze.py --help
```

No live Wikimedia request is required for acceptance.

Optional live smoke after tests:

```text
Astronomy / en source / uk target
```

may be used manually, but live network behavior is not deterministic CI evidence.

---

# 16. Acceptance criteria

WT-M23 is accepted when all of the following are true.

## Contract

- `source_language` is documented as the language of `query.value`.
- `languages` is documented as the requested metric/output editions.
- source language may be outside target languages.
- active docs do not imply that a one-target request must use that target as the source when the phrase is in another language.

## Validation

- every multi-language config requires `query.source_language`;
- this applies to article and topic mode;
- missing multi-language source fails before resolver/network work;
- CLI returns exit `2` / `configuration_error`;
- source-target membership is not required.

## Canonical scenarios

- astronomy uses English source → Ukrainian target;
- intermittent fasting uses English source → Polish/Czech targets;
- learning English uses English source → Polish/Czech/Ukrainian targets;
- mocked tests do not hide invalid source-language semantics.

## Regression safety

- WT-M20 semantic selection remains unchanged;
- target-language approximate search is still forbidden;
- no manual title translation is introduced;
- report schema remains `2.1.0`;
- CLI schema remains `1.0.0`;
- full test/lint/typecheck suite passes.

---

# Definition of Done

A fast/inexpensive agent can read the current documentation and correctly
distinguish:

```text
the language of the phrase it is resolving
```

from:

```text
the Wikipedia editions the user wants analyzed
```

and a malformed multi-language config is rejected as a configuration error
before any analysis work begins.
