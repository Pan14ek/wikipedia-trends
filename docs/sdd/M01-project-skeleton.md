# M01 — Project Skeleton

**Spec ID:** WT-M01  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** None

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Create a minimal, installable, testable Agent Skill project skeleton without implementing Wikimedia API access or analytics.

## In scope

- Create the agreed directory structure.
- Add `SKILL.md` skeleton with valid Agent Skills frontmatter.
- Add `README.md`.
- Add `pyproject.toml` for Python 3.12+.
- Configure package layout under `src/wiki_trends`.
- Add `scripts/analyze.py` as the executable entry point.
- Add `pytest`.
- Add placeholder reference documents and example directory.
- Add basic lint/type-friendly project configuration if lightweight.
- Add one smoke test proving imports and CLI startup work.

## Out of scope

- Network calls.
- Real config schema.
- Analytics.
- Charts.
- PDF generation.
- Cache.
- Topic/article resolution logic.

## Required files

```text
SKILL.md
README.md
pyproject.toml
scripts/analyze.py
src/wiki_trends/__init__.py
src/wiki_trends/cli.py
src/wiki_trends/config.py
src/wiki_trends/models.py
references/methodology.md
references/input-schema.md
references/output-schema.md
tests/unit/test_smoke.py
```

## SKILL.md minimum contract

Frontmatter must contain at least:

```yaml
---
name: wikipedia-trends
description: Analyze Wikipedia pageview trends across topics and language editions, create charts, and generate concise reports.
---
```

Body should state that the skill will eventually invoke `scripts/analyze.py --config <file>` and must not invent numeric results.

## CLI behavior

For this step only:

```bash
python scripts/analyze.py --help
```

must succeed.

Running without required args may return a usage error. No real analysis is required.

## Dependency management

Use `pyproject.toml` as the canonical dependency definition. Prefer `uv` for lockfile generation, but the project must also be installable with standard Python tooling.

## Acceptance criteria

- `python -m pytest` passes.
- `python scripts/analyze.py --help` exits with code 0.
- `python -c "import wiki_trends"` works in the configured environment.
- All project-owned code is inside the skill directory.
- No network, analytics, chart, PDF, or cache implementation is introduced.

## Test plan

- Smoke import test.
- CLI `--help` smoke test.
- Optional packaging/install smoke test.

## Deliverables

- Project skeleton committed.
- Short implementation note listing created files and commands used to validate them.
