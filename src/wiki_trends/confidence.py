"""Deterministic bootstrap confidence intervals for YoY growth."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from math import floor
from random import Random

from wiki_trends.models import ConfidenceInterval, ConfidenceIntervalStatus, MonthlyPageview, ObservationStatus

__all__ = ["compute_yoy_confidence_interval"]

_DEFAULT_ITERATIONS = 2_000
_DEFAULT_CONFIDENCE_LEVEL = 0.95
_DEFAULT_RANDOM_SEED = 42
_MINIMUM_VALID_PAIRS = 8
_MONTHS_PER_YEAR = 12
_EARLIEST_SUPPORTED_MONTH_INDEX = _MONTHS_PER_YEAR


def compute_yoy_confidence_interval(
    monthly_pageviews: Sequence[MonthlyPageview],
    *,
    iterations: int = _DEFAULT_ITERATIONS,
    confidence_level: float = _DEFAULT_CONFIDENCE_LEVEL,
    seed: int = _DEFAULT_RANDOM_SEED,
) -> ConfidenceInterval:
    """Estimate percentile bootstrap bounds for calendar-aligned YoY growth.

    The latest supplied month anchors a recent 12-month window. Its preceding
    12 months form the baseline, and a pair is eligible only when both matching
    month positions have known pageview values. Resampling occurs over those
    paired positions, preserving the relationship between each prior/recent
    month. Resamples with a zero baseline have undefined YoY and are excluded.

    Args:
        monthly_pageviews: Monthly observations in any order, with at most one
            observation per calendar month.
        iterations: Number of bootstrap resampling attempts. Defaults to 2,000.
        confidence_level: Central interval coverage between zero and one.
            Defaults to 0.95.
        seed: Seed for the module-local pseudo-random generator. Defaults to 42.

    Returns:
        Confidence interval metadata and percentile bounds, or an explicit
        unavailable result when there are too few valid pairs or no resample
        has a positive baseline.

    Raises:
        ValueError: If observations contain duplicate months or an option is
            outside its supported range.
        TypeError: If an option has an invalid runtime type.
    """
    _validate_options(iterations, confidence_level, seed)
    paired_values = _calendar_aligned_pairs(monthly_pageviews)
    if len(paired_values) < _MINIMUM_VALID_PAIRS:
        return _unavailable_interval(iterations, confidence_level, seed)

    bootstrap_growth_rates = _bootstrap_growth_rates(paired_values, iterations, seed)
    if not bootstrap_growth_rates:
        return _unavailable_interval(iterations, confidence_level, seed)

    tail_probability = (1 - confidence_level) / 2
    return ConfidenceInterval(
        level=confidence_level,
        iterations=iterations,
        seed=seed,
        lower=_percentile(bootstrap_growth_rates, tail_probability),
        upper=_percentile(bootstrap_growth_rates, 1 - tail_probability),
        status=ConfidenceIntervalStatus.AVAILABLE,
    )


def _validate_options(iterations: int, confidence_level: float, seed: int) -> None:
    """Fail early when bootstrap options cannot produce a defined interval."""
    if isinstance(iterations, bool) or not isinstance(iterations, int):
        raise TypeError("'iterations' must be an integer")
    if iterations <= 0:
        raise ValueError("'iterations' must be greater than zero")
    if isinstance(confidence_level, bool) or not isinstance(confidence_level, (int, float)):
        raise TypeError("'confidence_level' must be a number")
    if not 0 < confidence_level < 1:
        raise ValueError("'confidence_level' must be greater than zero and less than one")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("'seed' must be an integer")


def _calendar_aligned_pairs(monthly_pageviews: Sequence[MonthlyPageview]) -> list[tuple[int, int]]:
    """Return known matching positions from the latest previous/recent years."""
    observations_by_month: dict[date, MonthlyPageview] = {}
    for observation in monthly_pageviews:
        if observation.month in observations_by_month:
            raise ValueError(f"duplicate monthly observation for {observation.month.isoformat()}")
        observations_by_month[observation.month] = observation

    if not observations_by_month:
        return []

    latest_month = max(observations_by_month)
    latest_month_index = (latest_month.year * _MONTHS_PER_YEAR) + latest_month.month - 1
    earliest_required_month_index = latest_month_index - ((2 * _MONTHS_PER_YEAR) - 1)
    if earliest_required_month_index < _EARLIEST_SUPPORTED_MONTH_INDEX:
        return []
    recent_months = tuple(_shift_month(latest_month, -offset) for offset in range(_MONTHS_PER_YEAR - 1, -1, -1))
    return [
        (previous.views, recent.views)
        for recent_month in recent_months
        if (recent := observations_by_month.get(recent_month)) is not None
        and (previous := observations_by_month.get(_shift_month(recent_month, -_MONTHS_PER_YEAR))) is not None
        and recent.status is not ObservationStatus.UNKNOWN
        and previous.status is not ObservationStatus.UNKNOWN
        and recent.views is not None
        and previous.views is not None
    ]


def _shift_month(month: date, months: int) -> date:
    """Move a canonical month by an integer number of calendar months."""
    month_index = month.year * _MONTHS_PER_YEAR + (month.month - 1) + months
    return date(month_index // _MONTHS_PER_YEAR, month_index % _MONTHS_PER_YEAR + 1, 1)


def _bootstrap_growth_rates(paired_values: Sequence[tuple[int, int]], iterations: int, seed: int) -> list[float]:
    """Resample paired months and retain YoY values with positive baselines."""
    random_generator = Random(seed)
    pair_count = len(paired_values)
    growth_rates: list[float] = []
    for _ in range(iterations):
        sampled_pairs = [paired_values[random_generator.randrange(pair_count)] for _ in range(pair_count)]
        previous_total = sum(previous for previous, _ in sampled_pairs)
        if previous_total == 0:
            continue
        recent_total = sum(recent for _, recent in sampled_pairs)
        growth_rates.append(((recent_total / previous_total) - 1) * 100)
    return growth_rates


def _percentile(values: Sequence[float], probability: float) -> float:
    """Return a linearly interpolated percentile from non-empty numeric values."""
    ordered_values = sorted(values)
    index = (len(ordered_values) - 1) * probability
    lower_index = floor(index)
    upper_index = min(lower_index + 1, len(ordered_values) - 1)
    weight = index - lower_index
    return ordered_values[lower_index] + ((ordered_values[upper_index] - ordered_values[lower_index]) * weight)


def _unavailable_interval(iterations: int, confidence_level: float, seed: int) -> ConfidenceInterval:
    """Construct M11 metadata when bootstrap bounds cannot be responsibly shown."""
    return ConfidenceInterval(
        level=confidence_level,
        iterations=iterations,
        seed=seed,
        status=ConfidenceIntervalStatus.UNAVAILABLE,
    )
