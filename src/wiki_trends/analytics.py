"""Pure, deterministic calculations for monthly Wikipedia pageview series."""

from __future__ import annotations

from collections.abc import Sequence
from statistics import median

from wiki_trends.models import AbsoluteMetrics, AbsoluteMetricsStatus, MonthlyPageview, ObservationStatus

__all__ = ["compute_absolute_metrics"]


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
