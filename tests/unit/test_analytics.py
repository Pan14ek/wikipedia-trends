"""Hand-calculated unit coverage for M05 absolute pageview metrics."""

from __future__ import annotations

from datetime import date

import pytest

from wiki_trends.analytics import compute_absolute_metrics
from wiki_trends.models import AbsoluteMetricsStatus, MonthlyPageview, ObservationStatus


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
