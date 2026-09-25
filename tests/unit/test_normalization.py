"""Hand-calculated unit coverage for M09 normalized interest."""

from __future__ import annotations

from datetime import date

import pytest

from wiki_trends.analytics import compute_absolute_metrics
from wiki_trends.models import MonthlyPageview, ObservationStatus
from wiki_trends.normalization import compute_normalized_interest


def test_computes_constant_denominator_normalized_interest_and_summary() -> None:
    result = compute_normalized_interest(
        _series(2026, [10, 20, 30]),
        _series(2026, [100, 100, 100]),
    )

    assert result.unit == "views_per_1m_project_views"
    assert [point.value for point in result.monthly] == [100_000.0, 200_000.0, 300_000.0]
    assert result.mean == pytest.approx(200_000.0)
    assert result.median == pytest.approx(200_000.0)


def test_computes_changing_denominator_normalized_interest() -> None:
    result = compute_normalized_interest(
        _series(2026, [10, 10]),
        _series(2026, [100, 200]),
    )

    assert [point.value for point in result.monthly] == [100_000.0, 50_000.0]
    assert result.mean == pytest.approx(75_000.0)
    assert result.median == pytest.approx(75_000.0)


def test_missing_project_month_produces_unknown_normalized_value() -> None:
    project = _series(2026, [100, 100, 100])
    project[1] = MonthlyPageview(month=date(2026, 2, 1), status=ObservationStatus.UNKNOWN)

    result = compute_normalized_interest(_series(2026, [10, 20, 30]), project)

    assert [(point.month, point.value, point.status) for point in result.monthly] == [
        (date(2026, 1, 1), 100_000.0, ObservationStatus.OBSERVED),
        (date(2026, 2, 1), None, ObservationStatus.UNKNOWN),
        (date(2026, 3, 1), 300_000.0, ObservationStatus.OBSERVED),
    ]
    assert result.mean == pytest.approx(200_000.0)
    assert result.median == pytest.approx(200_000.0)


def test_zero_project_denominator_produces_unknown_without_dividing_by_zero() -> None:
    result = compute_normalized_interest(
        _series(2026, [10, 20]),
        _series(2026, [100, 0]),
    )

    assert result.monthly[1].value is None
    assert result.monthly[1].status is ObservationStatus.UNKNOWN
    assert result.mean == pytest.approx(100_000.0)
    assert result.median == pytest.approx(100_000.0)


def test_non_overlapping_month_ranges_remain_unknown_without_summary() -> None:
    result = compute_normalized_interest(
        _series(2026, [10, 20]),
        _series(2027, [100, 100]),
    )

    assert [point.month for point in result.monthly] == [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2027, 1, 1),
        date(2027, 2, 1),
    ]
    assert all(point.status is ObservationStatus.UNKNOWN for point in result.monthly)
    assert result.mean is None
    assert result.median is None


def test_rejects_duplicate_months_before_calculating_values() -> None:
    duplicate_month = date(2026, 1, 1)

    with pytest.raises(ValueError, match="article_pageviews.*duplicate month"):
        compute_normalized_interest(
            [
                MonthlyPageview(month=duplicate_month, views=10),
                MonthlyPageview(month=duplicate_month, views=20),
            ],
            _series(2026, [100]),
        )


def test_normalization_does_not_change_absolute_metrics() -> None:
    article = _series(2026, [10, 20])

    compute_normalized_interest(article, _series(2026, [100, 100]))

    absolute_metrics = compute_absolute_metrics(article)
    assert absolute_metrics.total_views == 30
    assert absolute_metrics.mean_monthly_views == pytest.approx(15.0)


def _series(year: int, views: list[int]) -> list[MonthlyPageview]:
    """Create a consecutive monthly pageview series for one test year."""
    return [MonthlyPageview(month=date(year, month, 1), views=value) for month, value in enumerate(views, start=1)]
