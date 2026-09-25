"""M11 coverage for deterministic paired-month bootstrap intervals."""

from __future__ import annotations

from datetime import date
from math import isfinite

import pytest

from wiki_trends.confidence import compute_yoy_confidence_interval
from wiki_trends.models import ConfidenceIntervalStatus, MonthlyPageview, ObservationStatus


def test_repeated_runs_with_the_same_seed_are_identical() -> None:
    series = _two_year_series(
        previous_values=[100, 110, 90, 120, 80, 100, 95, 105, 100, 110, 90, 100],
        recent_values=[120, 100, 100, 150, 90, 130, 100, 110, 120, 100, 95, 140],
    )

    first = compute_yoy_confidence_interval(series, seed=73)
    second = compute_yoy_confidence_interval(series, seed=73)

    assert first == second
    assert first.status is ConfidenceIntervalStatus.AVAILABLE


@pytest.mark.parametrize(
    ("previous_monthly_views", "recent_monthly_views", "expected_growth"),
    [(100, 120, 20.0), (100, 80, -20.0), (100, 100, 0.0)],
)
def test_constant_growth_series_produces_exact_interval(
    previous_monthly_views: int,
    recent_monthly_views: int,
    expected_growth: float,
) -> None:
    result = compute_yoy_confidence_interval(
        _two_year_series([previous_monthly_views] * 12, [recent_monthly_views] * 12)
    )

    assert result.status is ConfidenceIntervalStatus.AVAILABLE
    assert result.metric == "yoy_growth_pct"
    assert result.method == "paired_month_bootstrap"
    assert result.level == 0.95
    assert result.iterations == 2_000
    assert result.seed == 42
    assert result.lower == pytest.approx(expected_growth)
    assert result.upper == pytest.approx(expected_growth)
    assert set(result.model_dump(mode="json")) == {
        "metric",
        "method",
        "level",
        "iterations",
        "seed",
        "lower",
        "upper",
        "status",
    }


def test_a_series_before_the_supported_two_year_calendar_range_is_unavailable() -> None:
    result = compute_yoy_confidence_interval([MonthlyPageview(month=date(1, 1, 1), views=100)])

    assert result.status is ConfidenceIntervalStatus.UNAVAILABLE


def test_volatile_series_has_a_wider_interval_than_a_stable_series() -> None:
    stable = compute_yoy_confidence_interval(_two_year_series([100] * 12, [120] * 12))
    volatile = compute_yoy_confidence_interval(
        _two_year_series(
            previous_values=[100, 180, 40, 200, 80, 140, 60, 220, 100, 160, 50, 190],
            recent_values=[140, 90, 180, 70, 200, 80, 170, 75, 150, 100, 210, 85],
        ),
    )

    assert stable.lower is not None and stable.upper is not None
    assert volatile.lower is not None and volatile.upper is not None
    assert (volatile.upper - volatile.lower) > (stable.upper - stable.lower)


def test_fewer_than_eight_valid_pairs_returns_unavailable_metadata() -> None:
    result = compute_yoy_confidence_interval(_two_year_series([100] * 7, [120] * 7))

    assert result.status is ConfidenceIntervalStatus.UNAVAILABLE
    assert result.lower is None
    assert result.upper is None
    assert result.iterations == 2_000
    assert result.level == 0.95
    assert result.seed == 42


def test_zero_resampled_baselines_are_skipped_without_division_by_zero() -> None:
    result = compute_yoy_confidence_interval(_two_year_series([0] * 11 + [100], [100] * 12))

    assert result.status is ConfidenceIntervalStatus.AVAILABLE
    assert result.lower is not None and isfinite(result.lower)
    assert result.upper is not None and isfinite(result.upper)


def test_all_zero_baseline_resamples_return_unavailable() -> None:
    result = compute_yoy_confidence_interval(_two_year_series([0] * 12, [100] * 12))

    assert result.status is ConfidenceIntervalStatus.UNAVAILABLE
    assert result.lower is None
    assert result.upper is None


def test_unknown_observations_are_excluded_from_pairs() -> None:
    series = _two_year_series([100] * 12, [120] * 12)
    series[0] = MonthlyPageview(month=series[0].month, status=ObservationStatus.UNKNOWN)
    series[13] = MonthlyPageview(month=series[13].month, status=ObservationStatus.UNKNOWN)
    series[2] = MonthlyPageview(month=series[2].month, status=ObservationStatus.UNKNOWN)
    series[14] = MonthlyPageview(month=series[14].month, status=ObservationStatus.UNKNOWN)
    series[4] = MonthlyPageview(month=series[4].month, status=ObservationStatus.UNKNOWN)
    series[16] = MonthlyPageview(month=series[16].month, status=ObservationStatus.UNKNOWN)
    series[6] = MonthlyPageview(month=series[6].month, status=ObservationStatus.UNKNOWN)
    series[18] = MonthlyPageview(month=series[18].month, status=ObservationStatus.UNKNOWN)
    series[8] = MonthlyPageview(month=series[8].month, status=ObservationStatus.UNKNOWN)

    result = compute_yoy_confidence_interval(series)

    assert result.status is ConfidenceIntervalStatus.UNAVAILABLE


@pytest.mark.parametrize(
    ("kwargs", "exception", "message"),
    [
        ({"iterations": 0}, ValueError, "iterations"),
        ({"confidence_level": 1.0}, ValueError, "confidence_level"),
        ({"seed": True}, TypeError, "seed"),
    ],
)
def test_invalid_bootstrap_options_fail_fast(
    kwargs: dict[str, int | float | bool],
    exception: type[Exception],
    message: str,
) -> None:
    with pytest.raises(exception, match=message):
        compute_yoy_confidence_interval(_two_year_series([100] * 12, [120] * 12), **kwargs)


def test_duplicate_calendar_months_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate monthly observation"):
        compute_yoy_confidence_interval(
            [
                MonthlyPageview(month=date(2024, 1, 1), views=100),
                MonthlyPageview(month=date(2024, 1, 1), views=100),
            ],
        )


def _two_year_series(previous_values: list[int], recent_values: list[int]) -> list[MonthlyPageview]:
    """Build two contiguous calendar years from explicit monthly view counts."""
    return [
        *[
            MonthlyPageview(month=date(2024, month, 1), views=views)
            for month, views in enumerate(previous_values, start=1)
        ],
        *[
            MonthlyPageview(month=date(2025, month, 1), views=views)
            for month, views in enumerate(recent_values, start=1)
        ],
    ]
