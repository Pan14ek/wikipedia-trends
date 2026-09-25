"""Deterministic descriptive-window metrics required by WT-M25."""

from __future__ import annotations

from datetime import date

import pytest

from wiki_trends.analytics import compute_descriptive_trend, compute_yoy_metrics
from wiki_trends.models import (
    EndpointChangeStatus,
    Granularity,
    MonthlyPageview,
    ObservationStatus,
    TrendStreakDirection,
    WindowDirection,
    YoYStatus,
)

NINTENDO_VIEWS = [
    128_863,
    117_568,
    120_937,
    135_545,
    115_543,
    104_737,
    137_994,
    112_784,
    104_997,
    108_090,
    90_074,
    87_467,
]


def test_nintendo_switch_2_normative_descriptive_trend() -> None:
    """Keep the M25 regression values stable and distinct from YoY."""
    series = [
        MonthlyPageview(
            month=date((2025 * 12 + 8 + index) // 12, (2025 * 12 + 8 + index) % 12 + 1, 1),
            views=views,
        )
        for index, views in enumerate(NINTENDO_VIEWS)
    ]
    trend = compute_descriptive_trend(series)

    assert trend.status.value == "available"
    assert (trend.first.timestamp, trend.first.views) == (date(2025, 9, 1), 128_863)
    assert (trend.last.timestamp, trend.last.views) == (date(2026, 8, 1), 87_467)
    assert trend.direction is WindowDirection.LOWER_AT_END
    assert trend.endpoint_change_pct == pytest.approx(-32.12403870777493)
    assert trend.endpoint_change_status is EndpointChangeStatus.AVAILABLE
    assert trend.comparable_adjacent_pairs == 11
    assert trend.positive_adjacent_changes == 4
    assert trend.negative_adjacent_changes == 7
    assert trend.unchanged_adjacent_changes == 0
    assert trend.ending_streak.direction is TrendStreakDirection.DECREASE
    assert trend.ending_streak.intervals == 2
    assert trend.ending_streak.start == date(2026, 6, 1)
    assert trend.ending_streak.end == date(2026, 8, 1)
    assert (trend.peak.timestamp, trend.peak.views) == (date(2026, 3, 1), 137_994)
    assert (trend.trough.timestamp, trend.trough.views) == (date(2026, 8, 1), 87_467)
    assert trend.ending_streak.intervals != 4

    yoy = compute_yoy_metrics(series)
    assert yoy.status is YoYStatus.INSUFFICIENT_DATA
    assert yoy.growth_pct is None


def test_unknown_bucket_breaks_adjacency_and_streak() -> None:
    series = [
        MonthlyPageview(month=date(2026, 1, 1), views=10),
        MonthlyPageview(month=date(2026, 2, 1), status=ObservationStatus.UNKNOWN),
        MonthlyPageview(month=date(2026, 3, 1), views=20),
        MonthlyPageview(month=date(2026, 4, 1), views=25),
    ]

    trend = compute_descriptive_trend(series)

    assert trend.comparable_adjacent_pairs == 1
    assert trend.positive_adjacent_changes == 1
    assert trend.ending_streak.direction is TrendStreakDirection.INCREASE
    assert trend.ending_streak.intervals == 1
    assert trend.ending_streak.start == date(2026, 3, 1)


@pytest.mark.parametrize("unknown_index", [0, 2])
def test_unknown_requested_boundary_does_not_substitute_known_bucket(unknown_index: int) -> None:
    values = [100, 200, 300]
    series = [
        MonthlyPageview(month=date(2026, index + 1, 1), views=value)
        if index != unknown_index
        else MonthlyPageview(month=date(2026, index + 1, 1), status=ObservationStatus.UNKNOWN)
        for index, value in enumerate(values)
    ]

    trend = compute_descriptive_trend(series)

    assert trend.direction is WindowDirection.UNKNOWN
    assert trend.endpoint_change_status is EndpointChangeStatus.INSUFFICIENT_DATA
    assert trend.endpoint_change_pct is None
    assert trend.first.views is None if unknown_index == 0 else trend.last.views is None


def test_zero_endpoint_baseline_has_direction_without_percentage() -> None:
    trend = compute_descriptive_trend(
        [MonthlyPageview(month=date(2026, 1, 1), views=0), MonthlyPageview(month=date(2026, 2, 1), views=5)]
    )

    assert trend.direction is WindowDirection.HIGHER_AT_END
    assert trend.endpoint_change_status is EndpointChangeStatus.ZERO_BASELINE
    assert trend.endpoint_change_pct is None


def test_peak_and_trough_ties_choose_earliest_timestamp() -> None:
    trend = compute_descriptive_trend(
        [
            MonthlyPageview(month=date(2026, 1, 1), views=9),
            MonthlyPageview(month=date(2026, 2, 1), views=3),
            MonthlyPageview(month=date(2026, 3, 1), views=9),
            MonthlyPageview(month=date(2026, 4, 1), views=3),
        ]
    )

    assert trend.peak.timestamp == date(2026, 1, 1)
    assert trend.trough.timestamp == date(2026, 2, 1)


def test_daily_trend_requires_consecutive_calendar_days() -> None:
    series = [
        MonthlyPageview(month=date(2026, 8, 1), granularity=Granularity.DAILY, views=2),
        MonthlyPageview(month=date(2026, 8, 3), granularity=Granularity.DAILY, views=3),
    ]

    trend = compute_descriptive_trend(series)

    assert trend.comparable_adjacent_pairs == 0
    assert trend.ending_streak.intervals == 0
