# M16 — Local Filesystem Cache

**Spec ID:** WT-M16  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M15

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Avoid redundant Wikimedia requests while keeping cache behavior transparent and safe.

## In scope

- local filesystem cache
- cache keys for article pageviews, project pageviews, and resolution results
- TTL policy
- atomic writes
- corrupted-entry recovery
- cache provenance in output

## Cache location

Default:

```text
.cache/wikipedia/
├── article-pageviews/
├── project-pageviews/
└── resolution/
```

Allow override through environment variable or optional config without making it mandatory.

## Cache key

Use a canonical serialization of request-defining fields, then SHA-256.

Article pageview key includes at least:
- project
- article
- start
- end
- granularity
- access
- agent

Project pageview key includes equivalent project-level dimensions.

## TTL defaults

- historical data ending more than 2 complete months ago: 30 days
- data including one of the latest 2 complete months: 24 hours
- resolution metadata: 7 days

These values should be constants/configurable internals, not user-facing complexity in MVP.

## Safety

- atomic temp-file then rename
- JSON cache format
- corrupted cache entry is ignored and refetched
- never treat stale cache as fresh
- cache failure must not crash analysis if network is available

## Output provenance

Source metadata must state:

```json
"retrieval": "network"
```

or

```json
"retrieval": "cache"
```

## Acceptance criteria

- first call hits network
- identical second call hits cache
- stale entry refetches
- different parameters do not collide
- corrupted cache refetches
- cache can be disabled for tests
- output provenance records retrieval source

## Test plan

- cold cache
- warm cache
- stale cache
- key collision prevention
- corrupted JSON
- atomic-write behavior
- disabled cache

## Deliverables

- `cache.py`
- Wikimedia/resolver integration
- tests
- README note
