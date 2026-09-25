"""Robust, deterministic anomaly detection for monthly pageview series."""

from __future__ import annotations

from collections.abc import Sequence
from statistics import median

from wiki_trends.models import (
    AnomalyDetection,
    AnomalyDetectionMethod,
    AnomalyDirection,
    AnomalyRecord,
    MonthlyPageview,
    ObservationStatus,
)

__all__ = ["detect_anomalies"]

_ROBUST_Z_SCALE = 0.6745
_ROBUST_Z_THRESHOLD = 3.5
_IQR_FENCE_MULTIPLIER = 1.5


def detect_anomalies(monthly_pageviews: Sequence[MonthlyPageview]) -> AnomalyDetection:
    """Detect unusual observed months without imputing or changing the series.

    Scores use the median absolute deviation (MAD), which is less influenced
    by a spike than mean-and-standard-deviation approaches. When MAD is zero,
    an IQR fence is used only when its spread is positive. Unknown observations
    are excluded from both methods.

    Args:
        monthly_pageviews: Monthly observations in any order, with no duplicate
            calendar months.

    Returns:
        Typed anomaly records, or an explicit method limitation when a stable
        statistical spread cannot be calculated.

    Raises:
        ValueError: If the input contains duplicate calendar-month observations.
    """
    _validate_unique_months(monthly_pageviews)
    observed_pageviews = _observed_pageviews(monthly_pageviews)
    values = [views for _, views in observed_pageviews]
    if not values:
        return AnomalyDetection(
            observed_months=0,
            limitation="Anomaly detection requires at least one observed monthly value.",
        )

    center = median(values)
    median_absolute_deviation = median([abs(value - center) for value in values])
    if median_absolute_deviation > 0:
        return _detect_with_mad(observed_pageviews, center, median_absolute_deviation)

    return _detect_with_iqr_fallback(observed_pageviews, values)


def _observed_pageviews(monthly_pageviews: Sequence[MonthlyPageview]) -> list[tuple[MonthlyPageview, int]]:
    """Return only numeric observations, preserving their source months."""
    return [
        (observation, observation.views)
        for observation in monthly_pageviews
        if observation.status is not ObservationStatus.UNKNOWN and observation.views is not None
    ]


def _detect_with_mad(
    observed_pageviews: Sequence[tuple[MonthlyPageview, int]],
    center: float,
    median_absolute_deviation: float,
) -> AnomalyDetection:
    """Apply the specified robust-z rule when MAD provides a valid denominator."""
    records: list[AnomalyRecord] = []
    for observation, views in observed_pageviews:
        score = _ROBUST_Z_SCALE * (views - center) / median_absolute_deviation
        if abs(score) > _ROBUST_Z_THRESHOLD:
            records.append(_anomaly_record(observation, score, AnomalyDetectionMethod.ROBUST_Z_MAD))
    return AnomalyDetection(
        anomalies=records,
        observed_months=len(observed_pageviews),
        method=AnomalyDetectionMethod.ROBUST_Z_MAD,
    )


def _detect_with_iqr_fallback(
    observed_pageviews: Sequence[tuple[MonthlyPageview, int]],
    values: Sequence[int],
) -> AnomalyDetection:
    """Apply Tukey IQR fences when a zero MAD still leaves useful spread."""
    first_quartile, third_quartile = _quartiles(values)
    interquartile_range = third_quartile - first_quartile
    if interquartile_range <= 0:
        return AnomalyDetection(
            observed_months=len(observed_pageviews),
            limitation=(
                "MAD and IQR are zero, so anomaly detection cannot distinguish a statistical outlier "
                "from a constant or near-constant series."
            ),
        )

    lower_fence = first_quartile - (_IQR_FENCE_MULTIPLIER * interquartile_range)
    upper_fence = third_quartile + (_IQR_FENCE_MULTIPLIER * interquartile_range)
    center = median(values)
    records = [
        _anomaly_record(
            observation,
            (views - center) / interquartile_range,
            AnomalyDetectionMethod.IQR_FALLBACK,
        )
        for observation, views in observed_pageviews
        if views < lower_fence or views > upper_fence
    ]
    return AnomalyDetection(
        anomalies=records,
        observed_months=len(observed_pageviews),
        method=AnomalyDetectionMethod.IQR_FALLBACK,
    )


def _anomaly_record(
    observation: MonthlyPageview,
    score: float,
    method: AnomalyDetectionMethod,
) -> AnomalyRecord:
    """Convert one numeric observation and score into the public record shape."""
    if observation.views is None:
        raise ValueError("anomaly records require a known pageview count")
    return AnomalyRecord(
        month=observation.month.strftime("%Y-%m"),
        views=observation.views,
        direction=AnomalyDirection.HIGH if score > 0 else AnomalyDirection.LOW,
        score=score,
        method=method,
    )


def _quartiles(values: Sequence[int]) -> tuple[float, float]:
    """Return median-of-halves quartiles without external numerical packages."""
    sorted_values = sorted(values)
    middle = len(sorted_values) // 2
    if len(sorted_values) % 2 == 0:
        lower_half = sorted_values[:middle]
        upper_half = sorted_values[middle:]
    else:
        lower_half = sorted_values[:middle]
        upper_half = sorted_values[middle + 1 :]

    if not lower_half or not upper_half:
        return 0.0, 0.0
    return float(median(lower_half)), float(median(upper_half))


def _validate_unique_months(monthly_pageviews: Sequence[MonthlyPageview]) -> None:
    """Reject ambiguous observations before calculating statistical diagnostics."""
    months = [observation.month for observation in monthly_pageviews]
    if len(months) != len(set(months)):
        raise ValueError("anomaly detection requires at most one observation per calendar month")
