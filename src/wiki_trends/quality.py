"""Explicit, deterministic data-quality checks for Wikipedia pageview analyses."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from math import isfinite

from wiki_trends.analytics import compute_yoy_metrics
from wiki_trends.anomalies import detect_anomalies
from wiki_trends.models import (
    AnomalyDetection,
    AnomalyRecord,
    ArticleResolution,
    Granularity,
    MonthlyPageview,
    ObservationStatus,
    QualityCheck,
    QualityCheckId,
    QualityDetailValue,
    QualityReport,
    QualityStatus,
    ResolutionStatus,
    YoYMetrics,
    YoYStatus,
)

__all__ = ["evaluate_quality"]

_COMPLETENESS_PASS_THRESHOLD = 0.90
_COMPLETENESS_WARNING_THRESHOLD = 0.75
_YOY_SUFFICIENT_MONTHS = 24
_MINIMUM_ANALYSIS_MONTHS = 12


def evaluate_quality(
    monthly_pageviews: Sequence[MonthlyPageview],
    article_resolution: ArticleResolution | None = None,
    yoy_metrics: YoYMetrics | None = None,
    anomaly_detection: AnomalyDetection | None = None,
    spike_sensitivity_threshold_pct: float = 10.0,
    comparison_validity: QualityCheck | None = None,
) -> QualityReport:
    """Evaluate the six M08 quality checks without changing supplied analysis data.

    Args:
        monthly_pageviews: Requested monthly observations. Each calendar month
            must occur at most once.
        article_resolution: Structured article-resolution outcome, when the
            caller has performed M04 resolution.
        yoy_metrics: Calendar-aligned YoY outcome, when the caller has
            performed M06 growth calculation.
        anomaly_detection: Existing M10 detection result. If omitted, the
            detector runs against ``monthly_pageviews``.
        spike_sensitivity_threshold_pct: Minimum absolute YoY difference in
            percentage points that is material. Defaults to 10.
        comparison_validity: M13's shared-comparison quality finding, when a
            multi-language comparison has been performed.

    Returns:
        A report containing each check exactly once. A ``fail`` is local to
        its check; callers can distinguish it from a non-fatal ``warning``.

    Raises:
        ValueError: If the supplied observations include the same month twice
            or the materiality threshold is invalid.
    """
    _validate_unique_months(monthly_pageviews)
    _validate_spike_sensitivity_threshold(spike_sensitivity_threshold_pct)
    _validate_comparison_validity(comparison_validity)
    detection = anomaly_detection or detect_anomalies(monthly_pageviews)
    return QualityReport(
        checks=[
            _evaluate_completeness(monthly_pageviews),
            _evaluate_period_sufficiency(monthly_pageviews, yoy_metrics),
            _evaluate_article_resolution(article_resolution),
            _evaluate_trend_consistency(monthly_pageviews),
            _evaluate_spike_sensitivity(
                monthly_pageviews,
                yoy_metrics or compute_yoy_metrics(monthly_pageviews),
                detection,
                spike_sensitivity_threshold_pct,
            ),
            comparison_validity
            or _not_evaluated_check(
                QualityCheckId.COMPARISON_VALIDITY,
                "Comparison validity was not supplied, so multi-language comparison has not been evaluated.",
                "M13 multi-language comparison result not supplied",
            ),
        ]
    )


def _evaluate_completeness(monthly_pageviews: Sequence[MonthlyPageview]) -> QualityCheck:
    """Classify coverage with the M08 90% and 75% thresholds."""
    requested_months = len(monthly_pageviews)
    available_months = sum(observation.status is not ObservationStatus.UNKNOWN for observation in monthly_pageviews)
    completeness_ratio = available_months / requested_months if requested_months else 0.0
    details: dict[str, QualityDetailValue] = {
        "available_months": available_months,
        "requested_months": requested_months,
        "completeness_ratio": completeness_ratio,
    }

    if completeness_ratio >= _COMPLETENESS_PASS_THRESHOLD:
        return QualityCheck(
            id=QualityCheckId.COMPLETENESS,
            status=QualityStatus.PASS,
            message=f"Data completeness is {completeness_ratio:.0%} ({available_months}/{requested_months} months available).",
            details=details,
        )
    if completeness_ratio >= _COMPLETENESS_WARNING_THRESHOLD:
        return QualityCheck(
            id=QualityCheckId.COMPLETENESS,
            status=QualityStatus.WARNING,
            message=(
                f"Data completeness is {completeness_ratio:.0%} ({available_months}/{requested_months} months available), "
                "below the 90% preferred threshold."
            ),
            details=details,
        )
    return QualityCheck(
        id=QualityCheckId.COMPLETENESS,
        status=QualityStatus.FAIL,
        message=(
            f"Data completeness is {completeness_ratio:.0%} ({available_months}/{requested_months} months available), "
            "below the 75% minimum threshold."
        ),
        details=details,
    )


def _evaluate_period_sufficiency(
    monthly_pageviews: Sequence[MonthlyPageview],
    yoy_metrics: YoYMetrics | None,
) -> QualityCheck:
    """Report whether the requested period and computed YoY data are sufficient."""
    requested_months = len(monthly_pageviews)
    if monthly_pageviews and monthly_pageviews[0].granularity is Granularity.DAILY:
        return _not_evaluated_check(
            QualityCheckId.PERIOD_SUFFICIENCY,
            "Monthly YoY sufficiency rules do not apply to a daily date window.",
            "daily series uses a user-selected comparison period when growth is requested",
        )
    details: dict[str, QualityDetailValue] = {
        "requested_months": requested_months,
        "yoy_status": yoy_metrics.status.value if yoy_metrics else "not_supplied",
    }
    if requested_months < _MINIMUM_ANALYSIS_MONTHS:
        return QualityCheck(
            id=QualityCheckId.PERIOD_SUFFICIENCY,
            status=QualityStatus.FAIL,
            message=(
                f"Only {requested_months} months were requested; at least {_MINIMUM_ANALYSIS_MONTHS} months are required "
                "for the supported analysis period."
            ),
            details=details,
        )
    if requested_months < _YOY_SUFFICIENT_MONTHS:
        return QualityCheck(
            id=QualityCheckId.PERIOD_SUFFICIENCY,
            status=QualityStatus.WARNING,
            message=(
                f"The {requested_months}-month period is valid for absolute metrics but cannot provide the "
                "standard 24-month YoY comparison."
            ),
            details=details,
        )
    if yoy_metrics is not None and yoy_metrics.status in {
        YoYStatus.INSUFFICIENT_DATA,
        YoYStatus.NON_COMPARABLE_PERIODS,
    }:
        return QualityCheck(
            id=QualityCheckId.PERIOD_SUFFICIENCY,
            status=QualityStatus.FAIL,
            message=(
                "The requested period is long enough, but its observed months cannot support a valid "
                f"YoY comparison: {yoy_metrics.notes[0]}"
            ),
            details=details,
        )
    return QualityCheck(
        id=QualityCheckId.PERIOD_SUFFICIENCY,
        status=QualityStatus.PASS,
        message=f"The {requested_months}-month period is sufficient for a calendar-aligned YoY analysis.",
        details=details,
    )


def _evaluate_article_resolution(article_resolution: ArticleResolution | None) -> QualityCheck:
    """Explain whether structured article resolution is usable for this analysis."""
    if article_resolution is None:
        return _not_evaluated_check(
            QualityCheckId.ARTICLE_RESOLUTION,
            "Article resolution was not supplied, so resolution quality has not been evaluated.",
            "M04 article resolution result not supplied",
        )

    missing_languages = [missing.language for missing in article_resolution.missing_languages]
    details: dict[str, QualityDetailValue] = {
        "resolution_status": article_resolution.status.value,
        "resolved_languages": [article.language for article in article_resolution.articles],
        "missing_languages": missing_languages,
        "resolution_methods": [article.resolution_method.value for article in article_resolution.articles],
    }
    if article_resolution.status is ResolutionStatus.RESOLVED:
        return QualityCheck(
            id=QualityCheckId.ARTICLE_RESOLUTION,
            status=QualityStatus.PASS,
            message="All requested language editions were resolved through canonical structured mappings.",
            details=details,
        )
    if article_resolution.status is ResolutionStatus.PARTIAL:
        return QualityCheck(
            id=QualityCheckId.ARTICLE_RESOLUTION,
            status=QualityStatus.FAIL,
            message=f"Article resolution failed for requested language editions: {', '.join(missing_languages)}.",
            details=details,
        )
    return QualityCheck(
        id=QualityCheckId.ARTICLE_RESOLUTION,
        status=QualityStatus.FAIL,
        message="Article resolution requires clarification before pageview collection can be valid.",
        details=details,
    )


def _evaluate_trend_consistency(monthly_pageviews: Sequence[MonthlyPageview]) -> QualityCheck:
    """Calculate positive month-over-month changes without treating volatility as failure."""
    sorted_observations = sorted(monthly_pageviews, key=lambda observation: observation.month)
    known_pairs: list[tuple[int, int]] = []
    for previous, current in zip(sorted_observations, sorted_observations[1:], strict=False):
        if not _are_adjacent(previous, current):
            continue
        if previous.status is ObservationStatus.UNKNOWN or current.status is ObservationStatus.UNKNOWN:
            continue
        if previous.views is None or current.views is None:
            continue
        known_pairs.append((previous.views, current.views))
    comparable_pairs = len(known_pairs)
    if comparable_pairs == 0:
        return QualityCheck(
            id=QualityCheckId.TREND_CONSISTENCY,
            status=QualityStatus.NOT_EVALUATED,
            message="Trend consistency could not be evaluated because there are no comparable adjacent observed months.",
            details={"comparable_adjacent_month_pairs": 0, "positive_change_ratio": None},
        )

    positive_changes = sum(current_views > previous_views for previous_views, current_views in known_pairs)
    positive_change_ratio = positive_changes / comparable_pairs
    return QualityCheck(
        id=QualityCheckId.TREND_CONSISTENCY,
        status=QualityStatus.PASS,
        message=(
            "Trend consistency is diagnostic only: "
            f"{positive_changes}/{comparable_pairs} comparable adjacent-month changes were positive."
        ),
        details={
            "comparable_adjacent_month_pairs": comparable_pairs,
            "positive_month_over_month_changes": positive_changes,
            "positive_change_ratio": positive_change_ratio,
        },
    )


def _evaluate_spike_sensitivity(
    monthly_pageviews: Sequence[MonthlyPageview],
    yoy_metrics: YoYMetrics,
    anomaly_detection: AnomalyDetection,
    materiality_threshold_pct: float,
) -> QualityCheck:
    """Assess whether the largest detected anomaly materially drives YoY growth."""
    base_details: dict[str, QualityDetailValue] = {
        "anomaly_count": len(anomaly_detection.anomalies),
        "observed_months": anomaly_detection.observed_months,
        "detection_method": anomaly_detection.method.value if anomaly_detection.method else None,
        "materiality_threshold_percentage_points": materiality_threshold_pct,
    }
    if monthly_pageviews and monthly_pageviews[0].granularity is Granularity.DAILY:
        return _not_evaluated_check(
            QualityCheckId.SPIKE_SENSITIVITY,
            "YoY spike sensitivity is only defined for monthly observations.",
            "daily series has no calendar-aligned YoY metric",
        )
    if anomaly_detection.limitation is not None:
        return QualityCheck(
            id=QualityCheckId.SPIKE_SENSITIVITY,
            status=QualityStatus.NOT_EVALUATED,
            message=f"Spike sensitivity could not be evaluated: {anomaly_detection.limitation}",
            details={**base_details, "method_limitation": anomaly_detection.limitation},
        )
    if not anomaly_detection.anomalies:
        return QualityCheck(
            id=QualityCheckId.SPIKE_SENSITIVITY,
            status=QualityStatus.PASS,
            message="No statistical anomalies were detected, so no single-month spike materially drives YoY.",
            details=base_details,
        )
    if yoy_metrics.status is not YoYStatus.AVAILABLE or yoy_metrics.growth_pct is None:
        return QualityCheck(
            id=QualityCheckId.SPIKE_SENSITIVITY,
            status=QualityStatus.NOT_EVALUATED,
            message="Spike sensitivity requires an available YoY growth percentage.",
            details={**base_details, "yoy_status": yoy_metrics.status.value},
        )

    selected_anomaly = max(anomaly_detection.anomalies, key=lambda anomaly: (anomaly.views, abs(anomaly.score)))
    sensitivity_yoy = compute_yoy_metrics(_series_without_anomaly_contribution(monthly_pageviews, selected_anomaly))
    if sensitivity_yoy.status is not YoYStatus.AVAILABLE or sensitivity_yoy.growth_pct is None:
        return QualityCheck(
            id=QualityCheckId.SPIKE_SENSITIVITY,
            status=QualityStatus.NOT_EVALUATED,
            message="Spike sensitivity could not calculate YoY after removing the largest anomalous contribution.",
            details={
                **base_details,
                "selected_anomaly_month": selected_anomaly.month,
                "selected_anomaly_views": selected_anomaly.views,
                "sensitivity_yoy_status": sensitivity_yoy.status.value,
            },
        )

    percentage_point_change = sensitivity_yoy.growth_pct - yoy_metrics.growth_pct
    direction_changed = _direction(sensitivity_yoy.growth_pct) != _direction(yoy_metrics.growth_pct)
    details: dict[str, QualityDetailValue] = {
        **base_details,
        "selected_anomaly_month": selected_anomaly.month,
        "selected_anomaly_views": selected_anomaly.views,
        "selected_anomaly_score": selected_anomaly.score,
        "baseline_yoy_growth_pct": yoy_metrics.growth_pct,
        "yoy_without_largest_anomaly_pct": sensitivity_yoy.growth_pct,
        "yoy_change_percentage_points": percentage_point_change,
        "direction_changed": direction_changed,
    }
    if direction_changed or abs(percentage_point_change) > materiality_threshold_pct:
        return QualityCheck(
            id=QualityCheckId.SPIKE_SENSITIVITY,
            status=QualityStatus.WARNING,
            message=(
                "Removing the largest anomalous monthly contribution materially changes YoY "
                "and should be considered when interpreting the trend."
            ),
            details=details,
        )
    return QualityCheck(
        id=QualityCheckId.SPIKE_SENSITIVITY,
        status=QualityStatus.PASS,
        message="Removing the largest anomalous monthly contribution does not materially change YoY.",
        details=details,
    )


def _series_without_anomaly_contribution(
    monthly_pageviews: Sequence[MonthlyPageview],
    anomaly: AnomalyRecord,
) -> list[MonthlyPageview]:
    """Return a counterfactual series whose selected anomaly contributes zero views."""
    return [
        MonthlyPageview(
            month=observation.month,
            views=0,
            status=ObservationStatus.ZERO_INFERRED,
        )
        if observation.month.strftime("%Y-%m") == anomaly.month
        else observation
        for observation in monthly_pageviews
    ]


def _direction(growth_pct: float) -> int:
    """Map a YoY percentage to a comparable directional sign."""
    return (growth_pct > 0) - (growth_pct < 0)


def _validate_spike_sensitivity_threshold(threshold_pct: float) -> None:
    """Reject non-finite and negative materiality thresholds at the API boundary."""
    if not isfinite(threshold_pct) or threshold_pct < 0:
        raise ValueError("spike_sensitivity_threshold_pct must be a finite non-negative percentage")


def _validate_comparison_validity(comparison_validity: QualityCheck | None) -> None:
    """Reject a mismatched quality check at the M13 integration boundary."""
    if comparison_validity is not None and comparison_validity.id is not QualityCheckId.COMPARISON_VALIDITY:
        raise ValueError("comparison_validity must use the comparison_validity check ID")


def _not_evaluated_check(check_id: QualityCheckId, message: str, dependency: str) -> QualityCheck:
    """Create a named future-milestone integration point."""
    return QualityCheck(
        id=check_id,
        status=QualityStatus.NOT_EVALUATED,
        message=message,
        details={"dependency": dependency},
    )


def _validate_unique_months(monthly_pageviews: Sequence[MonthlyPageview]) -> None:
    """Reject duplicate month identifiers before they can corrupt diagnostics."""
    months = [observation.month for observation in monthly_pageviews]
    if len(months) != len(set(months)):
        raise ValueError("quality checks require at most one observation per calendar month")


def _are_adjacent(previous: MonthlyPageview, current: MonthlyPageview) -> bool:
    """Return whether two observations are adjacent at their declared resolution."""
    if previous.granularity is Granularity.DAILY and current.granularity is Granularity.DAILY:
        return current.month - previous.month == timedelta(days=1)
    return current.month.year * 12 + current.month.month == previous.month.year * 12 + previous.month.month + 1
