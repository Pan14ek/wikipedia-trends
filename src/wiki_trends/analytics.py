"""Pure, deterministic calculations for monthly Wikipedia pageview series."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from statistics import median

from wiki_trends.models import (
    AbsoluteMetrics,
    AbsoluteMetricsStatus,
    DescriptiveTrend,
    DescriptiveTrendStatus,
    EndingTrendStreak,
    EndpointChangeStatus,
    Granularity,
    MonthlyPageview,
    ObservationStatus,
    TrendPoint,
    TrendStreakDirection,
    WindowDirection,
    YoYMetrics,
    YoYStatus,
)

__all__ = [
    "aggregate_topic_pageviews",
    "compute_absolute_metrics",
    "compute_descriptive_trend",
    "compute_yoy_metrics",
]

_YOY_WINDOW_MONTHS = 12
_DESCRIPTIVE_TREND_NOTE = "Descriptive window trend only; this is not a YoY growth metric."


def compute_descriptive_trend(monthly_pageviews: Sequence[MonthlyPageview]) -> DescriptiveTrend:
    """Summarize deterministic within-window trend evidence without imputing data.

    Adjacency requires consecutive calendar buckets at the declared granularity.
    Unknown values and missing calendar buckets break both comparisons and
    ending streaks. Equal extrema select the earliest timestamp.

    Args:
        monthly_pageviews: Requested observations in any order, with at most
            one observation per calendar bucket.

    Returns:
        A typed summary whose endpoint change is explicitly distinct from YoY.

    Raises:
        ValueError: If duplicate timestamps or mixed granularities are supplied.
    """
    observations = sorted(monthly_pageviews, key=lambda observation: observation.timestamp)
    timestamps = [observation.timestamp for observation in observations]
    if len(timestamps) != len(set(timestamps)):
        raise ValueError("descriptive trend requires unique pageview timestamps")
    granularities = {observation.granularity for observation in observations}
    if len(granularities) > 1:
        raise ValueError("descriptive trend observations must use one granularity")
    if not observations:
        return DescriptiveTrend(
            status=DescriptiveTrendStatus.INSUFFICIENT_DATA,
            direction=WindowDirection.UNKNOWN,
            endpoint_change_status=EndpointChangeStatus.INSUFFICIENT_DATA,
            comparable_adjacent_pairs=0,
            positive_adjacent_changes=0,
            negative_adjacent_changes=0,
            unchanged_adjacent_changes=0,
            ending_streak=EndingTrendStreak(direction=TrendStreakDirection.NONE, intervals=0),
            notes=[_DESCRIPTIVE_TREND_NOTE],
        )

    known = [observation for observation in observations if _is_known_observation(observation)]
    first_observation, last_observation = observations[0], observations[-1]
    first = TrendPoint(timestamp=first_observation.timestamp, views=first_observation.views)
    last = TrendPoint(timestamp=last_observation.timestamp, views=last_observation.views)
    if (
        first_observation.views is None
        or last_observation.views is None
        or not _is_known_observation(first_observation)
        or not _is_known_observation(last_observation)
    ):
        direction = WindowDirection.UNKNOWN
        endpoint_status = EndpointChangeStatus.INSUFFICIENT_DATA
        endpoint_change_pct = None
    else:
        direction = _window_direction(first_observation.views, last_observation.views)
        if first_observation.views == 0:
            endpoint_status = EndpointChangeStatus.ZERO_BASELINE
            endpoint_change_pct = None
        else:
            endpoint_status = EndpointChangeStatus.AVAILABLE
            endpoint_change_pct = ((last_observation.views / first_observation.views) - 1) * 100

    adjacent_changes = [
        (previous, current, current.views - previous.views)
        for previous, current in zip(observations, observations[1:], strict=False)
        if _are_adjacent(previous, current)
        and _is_known_observation(previous)
        and _is_known_observation(current)
        and previous.views is not None
        and current.views is not None
    ]
    positive = sum(change > 0 for _, _, change in adjacent_changes)
    negative = sum(change < 0 for _, _, change in adjacent_changes)
    unchanged = len(adjacent_changes) - positive - negative
    ending_streak = _ending_streak(observations, adjacent_changes)
    peak_observation = (
        min(known, key=lambda observation: (-int(observation.views or 0), observation.timestamp)) if known else None
    )
    trough_observation = (
        min(known, key=lambda observation: (int(observation.views or 0), observation.timestamp)) if known else None
    )

    return DescriptiveTrend(
        status=DescriptiveTrendStatus.AVAILABLE,
        first=first,
        last=last,
        direction=direction,
        endpoint_change_status=endpoint_status,
        endpoint_change_pct=endpoint_change_pct,
        comparable_adjacent_pairs=len(adjacent_changes),
        positive_adjacent_changes=positive,
        negative_adjacent_changes=negative,
        unchanged_adjacent_changes=unchanged,
        ending_streak=ending_streak,
        peak=(
            TrendPoint(timestamp=peak_observation.timestamp, views=peak_observation.views) if peak_observation else None
        ),
        trough=(
            TrendPoint(timestamp=trough_observation.timestamp, views=trough_observation.views)
            if trough_observation
            else None
        ),
        notes=[_DESCRIPTIVE_TREND_NOTE],
    )


def _is_known_observation(observation: MonthlyPageview) -> bool:
    """Return whether an observation contains a real or explicit zero value."""
    return observation.status is not ObservationStatus.UNKNOWN and observation.views is not None


def _window_direction(first: int, last: int) -> WindowDirection:
    """Classify the relationship between known requested boundaries."""
    if last > first:
        return WindowDirection.HIGHER_AT_END
    if last < first:
        return WindowDirection.LOWER_AT_END
    return WindowDirection.UNCHANGED


def _are_adjacent(previous: MonthlyPageview, current: MonthlyPageview) -> bool:
    """Return whether two observations occupy consecutive calendar buckets."""
    if previous.granularity is Granularity.DAILY and current.granularity is Granularity.DAILY:
        return current.timestamp - previous.timestamp == timedelta(days=1)
    return (
        current.timestamp.year * 12 + current.timestamp.month
        == previous.timestamp.year * 12 + previous.timestamp.month + 1
    )


def _ending_streak(
    observations: Sequence[MonthlyPageview],
    adjacent_changes: Sequence[tuple[MonthlyPageview, MonthlyPageview, int]],
) -> EndingTrendStreak:
    """Return the same-direction known comparisons ending at the last bucket."""
    if len(observations) < 2:
        return EndingTrendStreak(direction=TrendStreakDirection.NONE, intervals=0)
    by_edge = {(previous.timestamp, current.timestamp): change for previous, current, change in adjacent_changes}
    final_change = by_edge.get((observations[-2].timestamp, observations[-1].timestamp))
    if final_change is None:
        return EndingTrendStreak(direction=TrendStreakDirection.NONE, intervals=0)
    direction = (
        TrendStreakDirection.INCREASE
        if final_change > 0
        else TrendStreakDirection.DECREASE
        if final_change < 0
        else TrendStreakDirection.UNCHANGED
    )
    expected_sign = (final_change > 0) - (final_change < 0)
    intervals = 1
    start_index = len(observations) - 2
    for index in range(len(observations) - 3, -1, -1):
        change = by_edge.get((observations[index].timestamp, observations[index + 1].timestamp))
        if change is None or (change > 0) - (change < 0) != expected_sign:
            break
        intervals += 1
        start_index = index
    return EndingTrendStreak(
        direction=direction,
        intervals=intervals,
        start=observations[start_index].timestamp,
        end=observations[-1].timestamp,
    )


def aggregate_topic_pageviews(article_series: Sequence[Sequence[MonthlyPageview]]) -> list[MonthlyPageview]:
    """Sum complete selected-article buckets into a transparent topic series.

    A bucket is unknown if any selected article is missing or unknown. Known
    values are summed only when every selected article contributes.

    Args:
        article_series: Monthly pageview observations for one to three selected
            topic articles.

    Returns:
        Calendar-sorted topic observations without mutating input sequences.

    Raises:
        ValueError: If no article series are supplied or one contains a
            duplicate calendar month.
    """
    if not article_series:
        raise ValueError("'article_series' must contain at least one selected article series")
    if len(article_series) > 3:
        raise ValueError("'article_series' must contain no more than three selected article series")
    granularities = {item.granularity for series in article_series for item in series}
    if len(granularities) > 1:
        raise ValueError("topic article series must use the same granularity")
    granularity = next(iter(granularities), None)

    indexed_series = [
        _index_by_month(series, f"article_series[{index}]") for index, series in enumerate(article_series)
    ]
    months = sorted({month for series in indexed_series for month in series})
    return [_aggregate_topic_month(month, indexed_series, granularity) for month in months]


def _aggregate_topic_month(
    month: date,
    indexed_series: Sequence[dict[date, MonthlyPageview]],
    granularity: Granularity | None,
) -> MonthlyPageview:
    """Aggregate one calendar month from the available article observations."""
    observations = [series.get(month) for series in indexed_series]
    if any(
        observation is None or observation.status is ObservationStatus.UNKNOWN or observation.views is None
        for observation in observations
    ):
        return MonthlyPageview(
            month=month,
            granularity=granularity or Granularity.MONTHLY,
            status=ObservationStatus.UNKNOWN,
        )
    known_observations = [observation for observation in observations if observation is not None]
    status = (
        ObservationStatus.ZERO_INFERRED
        if all(observation.status is ObservationStatus.ZERO_INFERRED for observation in known_observations)
        else ObservationStatus.OBSERVED
    )
    return MonthlyPageview(
        month=month,
        granularity=granularity or Granularity.MONTHLY,
        views=sum(observation.views or 0 for observation in known_observations),
        status=status,
    )


def compute_absolute_metrics(monthly_pageviews: Sequence[MonthlyPageview]) -> AbsoluteMetrics:
    """Compute baseline metrics without imputing or mutating the input series.

    ``UNKNOWN`` observations do not contribute to numeric aggregates, while
    observed and zero-inferred values both contribute their supplied count.

    Args:
        monthly_pageviews: Requested monthly observations in any sequence form.

    Returns:
        Aggregate metrics and coverage counts. The result has
        ``insufficient_data`` status when the series has no numeric values.
    """
    requested_months = len(monthly_pageviews)
    observed_values = [
        observation.views
        for observation in monthly_pageviews
        if observation.status is not ObservationStatus.UNKNOWN and observation.views is not None
    ]
    observed_months = len(observed_values)
    completeness_ratio = observed_months / requested_months if requested_months else 0.0

    if not observed_values:
        return AbsoluteMetrics(
            status=AbsoluteMetricsStatus.INSUFFICIENT_DATA,
            observed_months=0,
            requested_months=requested_months,
            completeness_ratio=completeness_ratio,
        )

    return AbsoluteMetrics(
        status=AbsoluteMetricsStatus.AVAILABLE,
        total_views=sum(observed_values),
        mean_monthly_views=sum(observed_values) / observed_months,
        median_monthly_views=median(observed_values),
        min_monthly_views=min(observed_values),
        max_monthly_views=max(observed_values),
        observed_months=observed_months,
        requested_months=requested_months,
        completeness_ratio=completeness_ratio,
    )


def compute_yoy_metrics(monthly_pageviews: Sequence[MonthlyPageview]) -> YoYMetrics:
    """Calculate calendar-aligned growth for the most recent two-year window.

    The most recent supplied month anchors the recent 12-calendar-month
    window; the preceding 12 calendar months form the baseline. Observations
    older than those 24 months are intentionally ignored. Each window needs
    at least ten known months, and known month positions must match across
    the two years before totals are compared.

    Args:
        monthly_pageviews: Monthly observations in any order. Every month may
            appear only once; unknown observations represent missing data.

    Returns:
        A result whose status explains whether a non-misleading YoY comparison
        was possible.

    Raises:
        ValueError: If the input contains duplicate calendar-month observations.
    """
    observations_by_month = _index_by_month(monthly_pageviews, "monthly_pageviews")
    if any(item.granularity.value != "monthly" for item in monthly_pageviews):
        return _unavailable_yoy(YoYStatus.INSUFFICIENT_DATA, "Calendar YoY is only defined for monthly observations.")
    if not observations_by_month:
        return _unavailable_yoy(
            YoYStatus.INSUFFICIENT_DATA,
            "YoY requires two calendar-aligned 12-month windows; no observations were supplied.",
        )

    latest_month = max(observations_by_month)
    window_months = _two_year_window_ending_at(latest_month)
    if window_months is None:
        return _unavailable_yoy(
            YoYStatus.INSUFFICIENT_DATA,
            "YoY requires two calendar-aligned 12-month windows within the supported calendar range.",
        )

    previous_months, recent_months = window_months
    previous_values = _known_values_for_months(observations_by_month, previous_months)
    recent_values = _known_values_for_months(observations_by_month, recent_months)

    if len(previous_values) < 10 or len(recent_values) < 10:
        return _unavailable_yoy(
            YoYStatus.INSUFFICIENT_DATA,
            "Each YoY window requires at least 10 observed or inferred-zero months.",
        )

    if tuple(previous_values) != tuple(recent_values):
        return _unavailable_yoy(
            YoYStatus.NON_COMPARABLE_PERIODS,
            "Missing month positions differ between the previous and recent YoY windows.",
        )

    previous_total = sum(previous_values.values())
    recent_total = sum(recent_values.values())
    if previous_total == 0:
        return YoYMetrics(
            previous_total=previous_total,
            recent_total=recent_total,
            status=YoYStatus.ZERO_BASELINE,
            notes=["YoY growth is undefined because the previous 12-month total is zero."],
        )

    growth_pct = ((recent_total / previous_total) - 1) * 100
    return YoYMetrics(
        previous_total=previous_total,
        recent_total=recent_total,
        growth_pct=growth_pct,
        mean_growth_pct=growth_pct,
        status=YoYStatus.AVAILABLE,
    )


def _index_by_month(
    monthly_pageviews: Sequence[MonthlyPageview],
    series_name: str,
) -> dict[date, MonthlyPageview]:
    """Index observations by calendar month while rejecting ambiguous duplicates."""
    observations_by_month: dict[date, MonthlyPageview] = {}
    for observation in monthly_pageviews:
        if observation.month in observations_by_month:
            raise ValueError(f"'{series_name}' contains duplicate month {observation.month.isoformat()}")
        observations_by_month[observation.month] = observation
    return observations_by_month


def _two_year_window_ending_at(latest_month: date) -> tuple[tuple[date, ...], tuple[date, ...]] | None:
    """Return the previous and recent calendar windows ending at ``latest_month``."""
    latest_index = latest_month.year * 12 + latest_month.month - 1
    earliest_index = latest_index - ((2 * _YOY_WINDOW_MONTHS) - 1)
    if earliest_index < 12:
        return None

    all_months = tuple(_month_from_index(index) for index in range(earliest_index, latest_index + 1))
    return all_months[:_YOY_WINDOW_MONTHS], all_months[_YOY_WINDOW_MONTHS:]


def _month_from_index(month_index: int) -> date:
    """Convert a zero-based Gregorian month index to a canonical month date."""
    return date(month_index // 12, month_index % 12 + 1, 1)


def _known_values_for_months(
    observations_by_month: dict[date, MonthlyPageview],
    months: Sequence[date],
) -> dict[int, int]:
    """Return known values keyed by their month position in one YoY window."""
    return {
        position: observation.views
        for position, month in enumerate(months)
        if (observation := observations_by_month.get(month)) is not None
        and observation.status is not ObservationStatus.UNKNOWN
        and observation.views is not None
    }


def _unavailable_yoy(status: YoYStatus, note: str) -> YoYMetrics:
    """Construct one explicitly explained unavailable YoY result."""
    return YoYMetrics(status=status, notes=[note])
