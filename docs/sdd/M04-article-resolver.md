# M04 — Article Resolver

**Spec ID:** WT-M04  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M03

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Resolve a concrete Wikipedia concept into canonical article identities for requested language editions without relying on LLM translation.

## In scope

For `query.mode = article`:

- validate that the requested page exists
- normalize redirects to canonical titles
- discover language equivalents using MediaWiki language links and/or Wikidata sitelinks
- return one `ResolvedArticle` per requested language where available
- record missing language equivalents explicitly
- expose provenance for how each title was resolved

## Out of scope

- broad-topic multi-article discovery (M12)
- pageview analysis
- ranking markets

## Resolution strategy

Preferred order:

1. Resolve the input article in a source/default language if obvious from config or explicit article identifier.
2. Follow redirects to canonical page.
3. Use language links / Wikidata sitelinks to map equivalent concepts into requested languages.
4. Never translate the title with an LLM as the primary resolution mechanism.
5. If no equivalent article exists for a language, return a structured missing result.

If source language cannot be inferred safely, require the config/agent to provide enough information rather than guessing.

## Model additions

Recommended:

```python
ResolvedArticle(
    language="uk",
    project="uk.wikipedia",
    requested_title="Astronomy",
    canonical_title="Астрономія",
    page_id=...,
    wikidata_id="Q333",
    url="...",
    resolution_method="wikidata_sitelink"
)
```

## Ambiguity

This module must not silently choose between materially different concepts. If search/disambiguation indicates ambiguity, return a structured “requires clarification” outcome.

## Acceptance criteria

- Exact page resolves.
- Redirect resolves to canonical title.
- Cross-language equivalent resolves through structured Wikipedia/Wikidata linkage.
- Missing language equivalent is represented without crashing.
- Ambiguous concept is not silently guessed.
- Resolver output includes provenance.
- No topic-mode aggregation exists yet.

## Test plan

Mocked tests for:
- exact article
- redirect
- 2-language sitelink mapping
- missing sitelink
- disambiguation/ambiguous result
- non-ASCII title

## Deliverables

- `article_resolver.py`
- model updates
- integration tests
- methodology documentation for resolution rules
