"""Hand-calculated unit coverage for M05 absolute pageview metrics."""

from __future__ import annotations

from datetime import date

import pytest

from wiki_trends.analytics import compute_absolute_metrics, compute_yoy_metrics
from wiki_trends.models import AbsoluteMetricsStatus, MonthlyPageview, ObservationStatus, YoYStatus


@pytest.fixture
def simple_three_month_series() -> list[MonthlyPageview]:
    """Provide a complete series with hand-calculated, varied counts."""
    return [
        MonthlyPageview(month=date(2026, 1, 1), views=2),
        MonthlyPageview(month=date(2026, 2, 1), views=4),
        MonthlyPageview(month=date(2026, 3, 1), views=9),
    ]


@pytest.fixture
def constant_twenty_four_month_series() -> list[MonthlyPageview]:
    """Provide a two-year series with one constant monthly count."""
    return [MonthlyPageview(month=date(2024 + index // 12, index % 12 + 1, 1), views=100) for index in range(24)]


@pytest.fixture
def series_with_unknown_month() -> list[MonthlyPageview]:
    """Provide known, unknown, and inferred-zero observations."""
    return [
        MonthlyPageview(month=date(2026, 1, 1), views=10),
        MonthlyPageview(month=date(2026, 2, 1), status=ObservationStatus.UNKNOWN),
        MonthlyPageview(month=date(2026, 3, 1), views=0, status=ObservationStatus.ZERO_INFERRED),
    ]


def test_computes_hand_calculated_metrics_for_complete_series(simple_three_month_series: list[MonthlyPageview]) -> None:
    metrics = compute_absolute_metrics(simple_three_month_series)

    assert metrics.status is AbsoluteMetricsStatus.AVAILABLE
    assert metrics.total_views == 15
    assert metrics.mean_monthly_views == 5.0
    assert metrics.median_monthly_views == 4.0
    assert metrics.min_monthly_views == 2
    assert metrics.max_monthly_views == 9
    assert metrics.observed_months == 3
    assert metrics.requested_months == 3
    assert metrics.completeness_ratio == 1.0


def test_computes_metrics_for_a_constant_twenty_four_month_series(
    constant_twenty_four_month_series: list[MonthlyPageview],
) -> None:
    metrics = compute_absolute_metrics(constant_twenty_four_month_series)

    assert metrics.total_views == 2400
    assert metrics.mean_monthly_views == 100.0
    assert metrics.median_monthly_views == 100.0
    assert metrics.min_monthly_views == 100
    assert metrics.max_monthly_views == 100
    assert metrics.observed_months == 24
    assert metrics.requested_months == 24
    assert metrics.completeness_ratio == 1.0


def test_unknown_observations_are_excluded_and_zero_inferred_is_counted(
    series_with_unknown_month: list[MonthlyPageview],
) -> None:
    metrics = compute_absolute_metrics(series_with_unknown_month)

    assert metrics.status is AbsoluteMetricsStatus.AVAILABLE
    assert metrics.total_views == 10
    assert metrics.mean_monthly_views == 5.0
    assert metrics.median_monthly_views == 5.0
    assert metrics.min_monthly_views == 0
    assert metrics.max_monthly_views == 10
    assert metrics.observed_months == 2
    assert metrics.requested_months == 3
    assert metrics.completeness_ratio == pytest.approx(2 / 3)


def test_all_zero_series_has_available_zero_metrics() -> None:
    metrics = compute_absolute_metrics(
        [
            MonthlyPageview(month=date(2026, 1, 1), views=0),
            MonthlyPageview(month=date(2026, 2, 1), views=0),
            MonthlyPageview(month=date(2026, 3, 1), views=0),
        ],
    )

    assert metrics.status is AbsoluteMetricsStatus.AVAILABLE
    assert metrics.total_views == 0
    assert metrics.mean_monthly_views == 0.0
    assert metrics.median_monthly_views == 0.0
    assert metrics.min_monthly_views == 0
    assert metrics.max_monthly_views == 0
    assert metrics.observed_months == 3
    assert metrics.requested_months == 3
    assert metrics.completeness_ratio == 1.0


def test_all_unknown_series_returns_explicit_insufficient_data_without_mutation() -> None:
    series = [
        MonthlyPageview(month=date(2026, 1, 1), status=ObservationStatus.UNKNOWN),
        MonthlyPageview(month=date(2026, 2, 1), status=ObservationStatus.UNKNOWN),
        MonthlyPageview(month=date(2026, 3, 1), status=ObservationStatus.UNKNOWN),
    ]
    original_series = [observation.model_copy(deep=True) for observation in series]

    metrics = compute_absolute_metrics(series)

    assert metrics.status is AbsoluteMetricsStatus.INSUFFICIENT_DATA
    assert metrics.total_views is None
    assert metrics.mean_monthly_views is None
    assert metrics.median_monthly_views is None
    assert metrics.min_monthly_views is None
    assert metrics.max_monthly_views is None
    assert metrics.observed_months == 0
    assert metrics.requested_months == 3
    assert metrics.completeness_ratio == 0.0
    assert series == original_series


def test_computes_positive_yoy_growth_for_two_complete_calendar_years() -> None:
    metrics = compute_yoy_metrics(_two_year_series(previous_monthly_views=100, recent_monthly_views=120))

    assert metrics.status is YoYStatus.AVAILABLE
    assert metrics.previous_total == 1200
    assert metrics.recent_total == 1440
    assert metrics.growth_pct == pytest.approx(20.0)
    assert metrics.mean_growth_pct == pytest.approx(20.0)
    assert metrics.notes == []


def test_computes_negative_yoy_growth_for_two_complete_calendar_years() -> None:
    metrics = compute_yoy_metrics(_two_year_series(previous_monthly_views=100, recent_monthly_views=80))

    assert metrics.status is YoYStatus.AVAILABLE
    assert metrics.growth_pct == pytest.approx(-20.0)


def test_computes_zero_yoy_growth_for_unchanged_series() -> None:
    metrics = compute_yoy_metrics(_two_year_series(previous_monthly_views=100, recent_monthly_views=100))

    assert metrics.status is YoYStatus.AVAILABLE
    assert metrics.growth_pct == 0.0


def test_reports_zero_baseline_without_an_infinite_growth_percentage() -> None:
    metrics = compute_yoy_metrics(_two_year_series(previous_monthly_views=0, recent_monthly_views=100))

    assert metrics.status is YoYStatus.ZERO_BASELINE
    assert metrics.previous_total == 0
    assert metrics.recent_total == 1200
    assert metrics.growth_pct is None
    assert metrics.notes


def test_allows_one_missing_month_when_the_same_position_is_missing_in_both_years() -> None:
    series = _two_year_series(previous_monthly_views=100, recent_monthly_views=120)
    series[2] = MonthlyPageview(month=series[2].month, status=ObservationStatus.UNKNOWN)
    series[14] = MonthlyPageview(month=series[14].month, status=ObservationStatus.UNKNOWN)

    metrics = compute_yoy_metrics(series)

    assert metrics.status is YoYStatus.AVAILABLE
    assert metrics.previous_total == 1100
    assert metrics.recent_total == 1320
    assert metrics.growth_pct == pytest.approx(20.0)


def test_reports_non_comparable_periods_when_missing_positions_do_not_match() -> None:
    series = _two_year_series(previous_monthly_views=100, recent_monthly_views=120)
    series[2] = MonthlyPageview(month=series[2].month, status=ObservationStatus.UNKNOWN)

    metrics = compute_yoy_metrics(series)

    assert metrics.status is YoYStatus.NON_COMPARABLE_PERIODS
    assert metrics.previous_total is None
    assert metrics.recent_total is None
    assert metrics.notes


def test_reports_insufficient_data_when_each_paired_window_has_fewer_than_ten_known_months() -> None:
    series = _two_year_series(previous_monthly_views=100, recent_monthly_views=120)
    for index in (0, 1, 2, 12, 13, 14):
        series[index] = MonthlyPageview(month=series[index].month, status=ObservationStatus.UNKNOWN)

    metrics = compute_yoy_metrics(series)

    assert metrics.status is YoYStatus.INSUFFICIENT_DATA
    assert metrics.previous_total is None
    assert metrics.recent_total is None
    assert metrics.notes


def test_uses_the_most_recent_two_year_window_when_more_than_twenty_four_months_are_supplied() -> None:
    older_year = _year_of_monthly_pageviews(year=2023, views=1)
    previous_year = _year_of_monthly_pageviews(year=2024, views=100)
    recent_year = _year_of_monthly_pageviews(year=2025, views=120)

    metrics = compute_yoy_metrics([*older_year, *previous_year, *recent_year])

    assert metrics.status is YoYStatus.AVAILABLE
    assert metrics.previous_total == 1200
    assert metrics.recent_total == 1440
    assert metrics.growth_pct == pytest.approx(20.0)


def _two_year_series(previous_monthly_views: int, recent_monthly_views: int) -> list[MonthlyPageview]:
    """Build a deterministic 2024/2025 series for YoY unit tests."""
    return [
        *_year_of_monthly_pageviews(year=2024, views=previous_monthly_views),
        *_year_of_monthly_pageviews(year=2025, views=recent_monthly_views),
    ]


def _year_of_monthly_pageviews(year: int, views: int) -> list[MonthlyPageview]:
    """Build all monthly observations for one calendar year at one view count."""
    return [MonthlyPageview(month=date(year, month, 1), views=views) for month in range(1, 13)]
