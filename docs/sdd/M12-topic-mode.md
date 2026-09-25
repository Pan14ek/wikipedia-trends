# M12 — Topic Mode

**Spec ID:** WT-M12  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M11

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Support a broader user topic represented by a small, transparent set of relevant Wikipedia articles rather than exactly one page.

## In scope

For `query.mode = topic`:

- discover candidate Wikipedia pages
- rank candidates deterministically
- select up to 3 articles per language
- expose selected articles and resolution provenance
- allow config override with explicit article titles
- aggregate pageviews across selected articles with clear caveats

## Non-goal

Do not attempt semantic web-scale topic modeling or LLM-based hidden article selection inside Python.

## Candidate discovery

Use MediaWiki search for the topic phrase.

Recommended flow:
1. request top 5 search results per language
2. resolve redirects/canonical titles
3. exclude disambiguation/list pages when detectable
4. compute reproducible relevance from:
   - search rank
   - exact/partial title token overlap
5. select up to 3 highest-ranked valid pages

The agent may provide an explicit article override when human/agent review identifies a better representation.

## Aggregation

For each month:

```text
topic_views = sum(available selected article views)
```

But output must include:
- selected article list
- per-article series
- aggregated series
- warning that the sum is article views, not unique users and may include repeat/overlapping readers

## Topic resolution output

```json
{
  "topic_resolution": {
    "requested_topic": "learning English",
    "language": "pl",
    "selected_articles": [...],
    "candidate_count": 5,
    "selection_method": "mediawiki_search_rank_plus_title_overlap"
  }
}
```

## Ambiguity

If search results represent materially different concepts with no clear dominant interpretation, return a structured clarification-required status instead of proceeding.

## Acceptance criteria

- Topic mode returns 1..3 selected pages per valid language.
- Selected pages are visible in output.
- Aggregated views equal sum of selected pageviews per month.
- Explicit article override is supported.
- Ambiguous topic can request clarification.
- No hidden LLM-only selection occurs in Python.
- Article mode remains unchanged.

## Test plan

- topic with one obvious result
- topic with 3 relevant results
- disambiguation page exclusion
- ambiguous topic
- explicit override
- missing page in one month
- aggregation arithmetic

## Deliverables

- topic-mode logic in `article_resolver.py`
- config/model extension for overrides
- tests
- methodology update
