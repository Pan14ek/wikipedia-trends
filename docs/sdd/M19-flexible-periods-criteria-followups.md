# M19 — Flexible Periods, Analysis Criteria, and Follow-up State

**Spec ID:** WT-M19
**Project:** Wikipedia Trends Agent Skill
**Method:** Specification-Driven Development (SDD)
**Status:** Implemented
**Depends on:** WT-M18

## Goal

Allow users to select topics, Wikipedia language editions, exact analysis
windows, and measurable numerical criteria; clarify assumptions over multiple
turns; and consistently produce auditable results through the project CLI.

## Implemented behavior

- Preserve legacy `period.months` configurations and their default of 24
  complete calendar months. Accept inclusive ISO `start` and `end` dates as an
  alternative. “Last month” is the previous completed calendar month.
- Support daily and monthly Pageviews observations. Partial-calendar-month
  requests default to daily; whole-calendar-month requests default to monthly.
  An explicit granularity is honored when valid. An incomplete recent tail is
  excluded from collection and reported as a separate available window.
- Keep missing observations explicitly unknown. Daily/monthly granularity is
  part of API cache identity and observation/report contracts.
- Accept independent numeric thresholds for existing measurable values:
  period growth, normalized-interest mean, and completeness ratio. Return
  `met`, `not_met`, or `not_evaluable`; do not synthesize a score or forecast.
- Require an explicit, equal-length, preceding baseline of matching
  granularity for growth-threshold evaluation. Incomplete current/baseline
  coverage makes growth not evaluable rather than silently aligning or
  imputing values.
- Emit `analysis.json` schema `2.0.0` with requested and available periods,
  granularity, comparison period, timestamped series, and criterion results.
  Old input configurations remain readable. Record the actual PDF path in
  `artifacts.pdf`.
- Persist a resolved relative window as exact dates in the report input so
  follow-ups can reuse it without silently moving the period. Update only the
  parameters clarified by the user.
- Require the agent workflow to invoke the project CLI for every analysis and
  verify every configured/requested artifact before reporting it. A weak or
  broader cross-language article remains unresolved until the user approves a
  proxy; approved proxy conclusions describe only the selected article.
- Keep evaluation prompts, transcripts, result matrices, and generated
  evaluation artifacts local. Ignore the complete `evaluation/` directory so
  each clone can maintain its own evaluation data.

## Verification

- Unit coverage includes legacy and exact-date configuration, inclusive date
  resolution, granularity, cache-key separation, daily observations,
  short-window quality/comparison behavior, and report serialization.
- Mocked end-to-end coverage exercises daily and monthly pipelines, explicit
  baselines, criteria, incomplete latest-period coverage, JSON/PNG/PDF paths,
  and a one-page PDF.
- At implementation completion: 145 tests passed; Ruff, strict mypy, and
  `git diff --check` passed. A separate live daily smoke generated valid JSON,
  PNG, and a one-page PDF. Fontconfig/Matplotlib emitted host cache-permission
  warnings but did not prevent artifact generation.
- GPT-5.5 agent evaluation was not run as part of this milestone. M19 agent
  scenarios are documented separately from each user's private evaluation
  evidence.

## Acceptance

The milestone is complete when exact and relative periods resolve
deterministically, API/client/cache/analytics preserve granularity, user
criteria and growth baselines are explicit, v2 reports retain follow-up state
and artifact paths, and the CLI and generated artifacts are covered by mocked
end-to-end verification.
