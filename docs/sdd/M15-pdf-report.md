# M15 — One-Page PDF Report

**Spec ID:** WT-M15  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M14

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Generate a concise, shareable one-page PDF from the already computed analysis result.

## In scope

- A4 one-page PDF
- summary heading and scope
- one main chart
- key metrics table
- quality/reliability notes
- limitations
- source/methodology footer

## Library

Use `reportlab` by default to maximize portability across agent platforms and avoid browser/system-library dependencies.

## Source of truth

The PDF must render from the structured analysis result. It must not independently recalculate metrics.

## Layout

Recommended sections:

1. Title: topic/article + languages
2. Analysis period
3. Executive summary data bullets
4. Trend chart
5. Key metrics table
6. Reliability / warnings
7. Limitations
8. Wikimedia source + methodology version + generated date

## Content rules

- Do not claim pageviews equal demand or willingness to pay.
- For language comparisons, say “interest in the [language]-language Wikipedia edition”, not “interest in country X”, unless country data exists.
- If data quality has warnings, they must appear in PDF.
- If comparison is invalid, PDF should say so rather than hiding the issue.

## One-page requirement

Normal MVP scenarios must fit on one A4 page.

If content overflows:
- prioritize key metrics
- truncate detailed warning text safely
- keep full details in `analysis.json`
- never silently create a multi-page report for the normal MVP path

## Acceptance criteria

- Valid PDF file is generated.
- File has exactly one page for MVP fixtures.
- Core title, period, and metrics text are present.
- Main PNG chart is embedded.
- Warnings appear when applicable.
- Report generation works in headless CI.
- Metrics in PDF match JSON.

## Test plan

- PDF signature
- page count == 1
- text extraction smoke assertions for title/period
- warning fixture
- Unicode content
- multi-language fixture

## Deliverables

- `report.py`
- report layout asset if needed
- tests
