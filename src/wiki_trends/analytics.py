"""Pure, deterministic calculations for monthly Wikipedia pageview series."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from statistics import median

from wiki_trends.models import (
    AbsoluteMetrics,
    AbsoluteMetricsStatus,
    Granularity,
    MonthlyPageview,
    ObservationStatus,
    YoYMetrics,
    YoYStatus,
)

__all__ = ["aggregate_topic_pageviews", "compute_absolute_metrics", "compute_yoy_metrics"]

_YOY_WINDOW_MONTHS = 12


def aggregate_topic_pageviews(article_series: Sequence[Sequence[MonthlyPageview]]) -> list[MonthlyPageview]:
    """Sum available article views into a transparent topic series.

    Each input sequence represents one selected article. A month is unknown
    only when every selected article is unavailable for that month. Otherwise
    its value is the sum of the available article views; callers must retain
    the per-article series because a partially available month is not a
    complete audience count.

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
    available_views = [
        observation.views
        for series in indexed_series
        if (observation := series.get(month)) is not None
        and observation.status is not ObservationStatus.UNKNOWN
        and observation.views is not None
    ]
    if not available_views:
        return MonthlyPageview(
            month=month,
            granularity=granularity or Granularity.MONTHLY,
            status=ObservationStatus.UNKNOWN,
        )
    return MonthlyPageview(month=month, granularity=granularity or Granularity.MONTHLY, views=sum(available_views))


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
