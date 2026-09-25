# M18 — Agent Evaluation on an Inexpensive Model

**Spec ID:** WT-M18  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M17

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Validate that a fast, inexpensive tool-capable AI model can correctly discover and use the skill without fabricating data or bypassing the Python implementation.

## In scope

- evaluation harness or documented repeatable procedure
- select at least one inexpensive tool-capable model after implementation
- run representative user prompts
- evaluate skill activation, tool usage, correctness, follow-ups, and artifact handling
- record failures and remediation notes

## Model selection

Do not hard-code a vendor in this spec. At evaluation time choose a currently available inexpensive model with:
- tool use
- filesystem/command execution or compatible agent environment
- enough context for `SKILL.md`

Record:
- model name/version
- platform
- date
- temperature/reasoning settings if relevant

## Evaluation prompts

At minimum:

1. single-language astronomy request
2. Polish vs Czech intermittent fasting
3. learning-English topic comparison
4. ambiguous topic such as “Java” that should trigger clarification
5. follow-up: “add Ukrainian Wikipedia”
6. request to change period from 24 to 36 months
7. request for JSON only
8. request for PDF report

## Evaluation dimensions

For each run record pass/fail:

- correct skill selected
- clarification asked when required
- correct JSON config created
- Python CLI actually invoked
- no manual/LLM arithmetic substituted for Python
- generated files surfaced to user
- numbers in prose match `analysis.json`
- warnings/limitations preserved
- follow-up changes only intended parameters
- no claim that Wikipedia pageviews equal purchase intent

## Success threshold

MVP agent evaluation passes when:
- all 3 canonical scenarios succeed end-to-end
- no fabricated numeric result occurs
- ambiguous-topic test does not silently choose a concept
- follow-up parameter-change test succeeds
- at least 80% of all evaluation cases pass on first attempt

Any failed canonical scenario blocks MVP completion.

## Evidence

Store:
- prompts
- model/platform metadata
- run logs or concise transcripts
- generated configs
- pass/fail matrix
- known issues

Suggested location:

```text
evaluation/
├── README.md
├── cases/
├── results/
└── summary.md
```

## Acceptance criteria

- Real inexpensive model is used.
- Results are reproducible enough to explain.
- Failures are documented, not hidden.
- Canonical three scenarios pass.
- Final summary explains how AI-generated implementation and agent behavior were verified.

## Deliverables

- evaluation assets
- summary report
- final MVP readiness decision
