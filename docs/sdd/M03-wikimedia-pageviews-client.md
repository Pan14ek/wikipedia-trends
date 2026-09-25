# M03 — Wikimedia Pageviews Client

**Spec ID:** WT-M03  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M02

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Implement a reliable HTTP client that fetches monthly article pageviews from Wikimedia without performing analytics.

## In scope

- Wikimedia Pageviews API client.
- Monthly article pageviews.
- URL/title encoding.
- Request identification via User-Agent.
- Timeouts.
- bounded retries for transient failures.
- handling 200, 404, 429, 5xx, and timeout.
- conversion into `MonthlyPageview` records.
- deterministic test doubles / mocked integration tests.

## Out of scope

- project-wide pageviews for normalization (M09).
- cache (M16).
- article discovery/resolution (M04).
- metrics.

## Client interface

Recommended:

```python
class WikimediaPageviewsClient:
    def get_article_pageviews(
        self,
        project: str,
        article: str,
        start_month: str,
        end_month: str
    ) -> list[MonthlyPageview]:
        ...
```

`project` example: `uk.wikipedia`.

## API behavior

Use the official Wikimedia Analytics Pageviews endpoint for per-article metrics with:

- all access methods unless a later config requires otherwise
- user agents appropriate for measuring human+bot traffic only if chosen explicitly; default should follow the standard “user” agent metric for article interest
- monthly granularity

Document the exact chosen API dimensions in `methodology.md`.

## Missing periods

Do not silently turn missing API values into zero.

Returned series must cover the requested month range. For months absent from the response, create `UNKNOWN` observations unless the API semantics conclusively support inferred zero for that case.

## Retry policy

Default:
- timeout: 10 seconds
- max attempts: 3
- exponential backoff
- respect `Retry-After` on 429 when present

Tests must not sleep for real; inject a retry/sleep strategy.

## Error model

Introduce explicit exceptions such as:

```python
WikimediaError
WikimediaRateLimitError
WikimediaUnavailableError
WikimediaNotFoundError
```

Do not leak raw `httpx` exceptions to the CLI.

## Acceptance criteria

- Correct endpoint is generated for a known article.
- 200 response maps to monthly points.
- Missing months become explicit `UNKNOWN`.
- 429 is retried within policy, then surfaced clearly.
- 5xx is retried within policy.
- timeout is handled.
- 404 behavior is explicit and tested.
- User-Agent is always sent.
- No analytics is implemented.

## Test plan

Mocked integration tests for:
- successful 24-month response
- article title with spaces/slashes/non-ASCII
- missing month
- 404
- 429 then success
- repeated 429
- 500 then success
- timeout

## Deliverables

- `wikipedia_client.py`
- API fixtures
- integration tests
- methodology note describing endpoint parameters
