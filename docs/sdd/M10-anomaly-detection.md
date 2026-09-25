# M10 — Anomaly Detection

**Spec ID:** WT-M10  
**Project:** Wikipedia Trends Agent Skill  
**Method:** Specification-Driven Development (SDD)  
**Status:** Ready for implementation  
**Depends on:** WT-M09

## SDD rule

This document is the source of truth for this implementation step. The coding agent must implement only the scope described here, preserve behavior accepted by previous specs, and avoid speculative work from later specs. If this spec conflicts with an already accepted earlier spec, stop and report the conflict instead of silently changing behavior.

## Goal

Detect unusual monthly spikes or drops using a robust statistical rule suitable for small, heavy-tailed pageview series.

## In scope

- robust z-score based on median absolute deviation (MAD)
- anomaly records
- spike-sensitivity quality check integration
- handling constant/near-constant series

## Primary method

For each observed monthly value `x_i`:

```text
robust_z = 0.6745 * (x_i - median) / MAD
```

Flag as anomaly when:

```text
abs(robust_z) > 3.5
```

## Fallback behavior

If `MAD == 0`:
- do not divide by zero
- use an IQR-based fallback if meaningful
- otherwise return no statistical anomalies and record method limitation

## Output

```json
{
  "anomalies": [
    {
      "month": "2026-03",
      "views": 18421,
      "direction": "high",
      "score": 4.7,
      "method": "robust_z_mad"
    }
  ]
}
```

## Spike sensitivity check

A trend should receive a warning if removing the single largest anomalous month materially changes YoY direction or changes YoY magnitude by more than a configurable threshold.

Default materiality threshold: 10 percentage points.

This is a diagnostic warning, not an automatic rejection.

## Acceptance criteria

- Clear spike is detected.
- Constant series does not fail.
- One extreme low value can be detected.
- Unknown months are excluded.
- Anomaly removal sensitivity is tested.
- Quality report integrates spike-sensitivity status.

## Test plan

- no anomaly
- one high anomaly
- one low anomaly
- MAD zero
- unknown points
- YoY direction flips when spike removed

## Deliverables

- `anomalies.py`
- quality integration
- tests
