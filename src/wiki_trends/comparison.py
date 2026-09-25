"""Pure, explicit alignment and comparison of Wikipedia language editions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from statistics import median

from wiki_trends.analytics import compute_absolute_metrics, compute_yoy_metrics
from wiki_trends.models import (
    ComparisonPeriod,
    Granularity,
    LanguageComparisonInput,
    LanguageComparisonMetrics,
    MonthlyPageview,
    MultiLanguageComparison,
    NormalizedInterest,
    ObservationStatus,
    QualityCheck,
    QualityCheckId,
    QualityDetailValue,
    QualityStatus,
)

__all__ = ["compare_languages"]

_COMPLETENESS_PASS_THRESHOLD = 0.90
_COMPLETENESS_MINIMUM_THRESHOLD = 0.75
_MINIMUM_SHARED_MONTHS = 12


def compare_languages(language_inputs: Sequence[LanguageComparisonInput]) -> MultiLanguageComparison:
    """Align language editions and calculate only metrics from shared valid months.

    The function is side-effect free. It does not decide a market winner or
    infer missing data: direct absolute metrics use the calendar months whose
    pageview values are known in every requested, resolved language. Normalized
    metrics use the further subset with known normalized values in every
    language.

    Args:
        language_inputs: Two to twenty language-specific pageview inputs.

    Returns:
        An explicit comparison result, including per-language warnings and the
        M08 comparison-validity quality check.

    Raises:
        ValueError: If the language count or language codes are invalid.
    """
    inputs = list(language_inputs)
    _validate_inputs(inputs)
    metrics_by_language = _initial_metrics(inputs)
    resolved_inputs = [item for item in inputs if item.resolved]
    warnings = _resolution_warnings(inputs)

    shared_months = _shared_available_months(resolved_inputs)
    requested_shared_months = _shared_requested_months(resolved_inputs)
    warnings.extend(_period_warnings(resolved_inputs, requested_shared_months, shared_months))
    granularity = _shared_granularity(resolved_inputs)
    minimum_shared = 12 if granularity is Granularity.MONTHLY else 1
    comparable = _is_comparable(inputs, metrics_by_language, shared_months, minimum_shared)
    normalized_months = _shared_normalized_months(resolved_inputs, shared_months)
    normalized_comparable = comparable and bool(normalized_months)
    if comparable and not normalized_comparable:
        warnings.append("Normalized interest is unavailable for at least one language in the effective shared period.")

    if shared_months:
        for item in resolved_inputs:
            metrics_by_language[item.language] = _calculated_metrics(item, shared_months, normalized_months)

    effective_period = _effective_period(shared_months, granularity)
    validity = _comparison_validity(
        inputs,
        comparable,
        effective_period,
        shared_months,
        warnings,
        minimum_shared,
    )
    return MultiLanguageComparison(
        languages=[item.language for item in inputs],
        effective_period=effective_period,
        comparable=comparable,
        normalized_comparable=normalized_comparable,
        warnings=warnings,
        metrics_by_language=metrics_by_language,
        comparison_validity=validity,
    )


def _validate_inputs(inputs: Sequence[LanguageComparisonInput]) -> None:
    """Validate the M13 language-count and uniqueness boundary."""
    if not 2 <= len(inputs) <= 20:
        raise ValueError("multi-language comparison requires two to twenty language inputs")
    languages = [item.language for item in inputs]
    if len(languages) != len(set(languages)):
        raise ValueError("multi-language comparison language codes must be unique")


def _initial_metrics(inputs: Sequence[LanguageComparisonInput]) -> dict[str, LanguageComparisonMetrics]:
    """Create local coverage diagnostics before shared-period calculation."""
    metrics: dict[str, LanguageComparisonMetrics] = {}
    for item in inputs:
        available_months = sum(_is_known(observation) for observation in item.pageviews)
        warnings = _language_warnings(item, available_months)
        if not warnings and item.resolved:
            warnings = ["No valid shared comparison period is available for direct metrics."]
        metrics[item.language] = LanguageComparisonMetrics(
            language=item.language,
            requested_months=len(item.pageviews),
            available_months=available_months,
            warnings=warnings,
        )
    return metrics


def _language_warnings(item: LanguageComparisonInput, available_months: int) -> list[str]:
    """Describe a language's own resolution and completeness caveats."""
    if not item.resolved:
        return [f"{item.language}: language equivalent is unresolved: {item.resolution_reason}"]
    requested_months = len(item.pageviews)
    if requested_months == 0:
        return [f"{item.language}: no pageview observations were supplied."]
    completeness_ratio = available_months / requested_months
    if completeness_ratio < _COMPLETENESS_MINIMUM_THRESHOLD:
        return [
            f"{item.language}: completeness is {completeness_ratio:.0%}, below the 75% minimum for direct comparison."
        ]
    if completeness_ratio < _COMPLETENESS_PASS_THRESHOLD:
        return [f"{item.language}: completeness is {completeness_ratio:.0%}, below the 90% preferred threshold."]
    return []


def _resolution_warnings(inputs: Sequence[LanguageComparisonInput]) -> list[str]:
    """Summarize language equivalents that prevent a full requested comparison."""
    unresolved_languages = [item.language for item in inputs if not item.resolved]
    if not unresolved_languages:
        return []
    return [f"Unresolved language equivalents prevent a full comparison: {', '.join(unresolved_languages)}."]


def _shared_requested_months(inputs: Sequence[LanguageComparisonInput]) -> set[date]:
    """Return calendar months represented in every resolved input series."""
    if not inputs or any(not item.pageviews for item in inputs):
        return set()
    requested_month_sets = [{observation.month for observation in item.pageviews} for item in inputs]
    return set.intersection(*requested_month_sets)


def _shared_available_months(inputs: Sequence[LanguageComparisonInput]) -> list[date]:
    """Return sorted calendar months with known pageviews in every language."""
    requested_shared_months = _shared_requested_months(inputs)
    pageviews_by_language = {
        item.language: {observation.month: observation for observation in item.pageviews} for item in inputs
    }
    return [
        month
        for month in sorted(requested_shared_months)
        if all(_is_known(pageviews_by_language[item.language][month]) for item in inputs)
    ]


def _period_warnings(
    inputs: Sequence[LanguageComparisonInput],
    requested_shared_months: set[date],
    shared_months: Sequence[date],
) -> list[str]:
    """Explain any period intersection or missing-data reduction."""
    if not inputs:
        return []
    calendar_month_counts = {len(item.pageviews) for item in inputs}
    calendar_bounds = {
        (
            min(observation.month for observation in item.pageviews),
            max(observation.month for observation in item.pageviews),
        )
        for item in inputs
        if item.pageviews
    }
    warnings: list[str] = []
    if len(calendar_month_counts) > 1 or len(calendar_bounds) > 1:
        warnings.append("Requested language windows differ; direct metrics use the explicit shared period only.")
    if requested_shared_months and len(shared_months) < len(requested_shared_months):
        warnings.append(
            f"{len(requested_shared_months) - len(shared_months)} shared calendar month(s) are excluded because at least "
            "one language has unknown pageviews."
        )
    return warnings


def _is_comparable(
    inputs: Sequence[LanguageComparisonInput],
    metrics_by_language: dict[str, LanguageComparisonMetrics],
    shared_months: Sequence[date],
    minimum_shared: int,
) -> bool:
    """Apply the explicit M13 direct-comparison validity rules."""
    if any(not item.resolved for item in inputs) or len(shared_months) < minimum_shared:
        return False
    return all(
        metrics.available_months / metrics.requested_months >= _COMPLETENESS_MINIMUM_THRESHOLD
        for metrics in metrics_by_language.values()
        if metrics.requested_months > 0
    )


def _shared_normalized_months(
    inputs: Sequence[LanguageComparisonInput],
    shared_pageview_months: Sequence[date],
) -> list[date]:
    """Return shared pageview months that also have known normalized values."""
    if not inputs or any(item.normalized_interest is None for item in inputs):
        return []
    normalized_by_language = {
        item.language: {point.month: point for point in item.normalized_interest.monthly}
        for item in inputs
        if item.normalized_interest is not None
    }
    return [
        month
        for month in shared_pageview_months
        if all(
            (point := normalized_by_language[item.language].get(month)) is not None and point.value is not None
            for item in inputs
        )
    ]


def _calculated_metrics(
    item: LanguageComparisonInput,
    shared_months: Sequence[date],
    normalized_months: Sequence[date],
) -> LanguageComparisonMetrics:
    """Calculate one language's metrics only from explicitly shared data."""
    pageviews_by_month = {observation.month: observation for observation in item.pageviews}
    shared_pageviews = [pageviews_by_month[month] for month in shared_months]
    normalized_interest = _aligned_normalized_interest(item.normalized_interest, normalized_months)
    return LanguageComparisonMetrics(
        language=item.language,
        absolute_metrics=compute_absolute_metrics(shared_pageviews),
        normalized_interest=normalized_interest,
        yoy_metrics=compute_yoy_metrics(shared_pageviews),
        requested_months=len(item.pageviews),
        available_months=sum(_is_known(observation) for observation in item.pageviews),
        warnings=_language_warnings(item, sum(_is_known(observation) for observation in item.pageviews)),
    )


def _aligned_normalized_interest(
    normalized_interest: NormalizedInterest | None,
    shared_months: Sequence[date],
) -> NormalizedInterest | None:
    """Recalculate a normalized summary from the language-shared month subset."""
    if normalized_interest is None or not shared_months:
        return None
    points_by_month = {point.month: point for point in normalized_interest.monthly}
    points = [points_by_month[month] for month in shared_months]
    values = [point.value for point in points if point.value is not None]
    if not values:
        return NormalizedInterest(monthly=points)
    return NormalizedInterest(monthly=points, mean=sum(values) / len(values), median=median(values))


def _effective_period(
    shared_months: Sequence[date],
    granularity: Granularity,
) -> ComparisonPeriod | None:
    """Expose the exact start and end bounds of shared known observations."""
    if not shared_months:
        return None
    return ComparisonPeriod(start=shared_months[0], end=shared_months[-1], granularity=granularity)


def _shared_granularity(inputs: Sequence[LanguageComparisonInput]) -> Granularity:
    """Read one common granularity and reject accidental mixed resolutions."""
    granularities = {observation.granularity for item in inputs for observation in item.pageviews}
    if len(granularities) > 1:
        raise ValueError("language comparison series must use the same granularity")
    return next(iter(granularities), Granularity.MONTHLY)


def _comparison_validity(
    inputs: Sequence[LanguageComparisonInput],
    comparable: bool,
    effective_period: ComparisonPeriod | None,
    shared_months: Sequence[date],
    warnings: Sequence[str],
    minimum_shared: int,
) -> QualityCheck:
    """Translate comparison validity into the stable M08 quality-check shape."""
    details: dict[str, QualityDetailValue] = {
        "requested_languages": [item.language for item in inputs],
        "resolved_languages": [item.language for item in inputs if item.resolved],
        "shared_available_months": len(shared_months),
        "minimum_shared_periods": minimum_shared,
        "effective_period_start": effective_period.start.isoformat() if effective_period else None,
        "effective_period_end": effective_period.end.isoformat() if effective_period else None,
    }
    if not comparable:
        return QualityCheck(
            id=QualityCheckId.COMPARISON_VALIDITY,
            status=QualityStatus.FAIL,
            message=f"Direct comparison is invalid until every language resolves and at least {minimum_shared} shared known buckets exist.",
            details=details,
        )
    if warnings:
        return QualityCheck(
            id=QualityCheckId.COMPARISON_VALIDITY,
            status=QualityStatus.WARNING,
            message="Direct comparison uses the recorded shared period and includes interpretation warnings.",
            details=details,
        )
    return QualityCheck(
        id=QualityCheckId.COMPARISON_VALIDITY,
        status=QualityStatus.PASS,
        message="All languages share a complete, valid direct-comparison period.",
        details=details,
    )


def _is_known(observation: MonthlyPageview) -> bool:
    """Return whether an observation safely contributes a numeric pageview value."""
    return observation.status is not ObservationStatus.UNKNOWN and observation.views is not None
