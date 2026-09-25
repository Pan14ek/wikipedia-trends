"""Pure normalized-interest calculations for monthly Wikipedia pageview series."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from statistics import median

from wiki_trends.models import (
    MonthlyPageview,
    NormalizedInterest,
    NormalizedInterestPoint,
    ObservationStatus,
)

__all__ = ["compute_normalized_interest"]

_PER_MILLION: int = 1_000_000


def compute_normalized_interest(
    article_pageviews: Sequence[MonthlyPageview],
    project_pageviews: Sequence[MonthlyPageview],
) -> NormalizedInterest:
    """Normalize article pageviews against aligned project traffic.

    A point is known only when both series provide a numeric value for the
    same calendar month and the project denominator is positive. Unknown or
    zero project totals are never interpolated or divided by. The input series
    are not modified, so absolute metrics remain independently available.

    Args:
        article_pageviews: Monthly observations for one resolved article.
        project_pageviews: Monthly aggregate observations for its project.

    Returns:
        Monthly article views per 1,000,000 project views, with an arithmetic
        mean and median across known normalized months when any exist.

    Raises:
        ValueError: If either series includes a calendar month more than once.
    """
    articles_by_month = _index_by_month(article_pageviews, "article_pageviews")
    projects_by_month = _index_by_month(project_pageviews, "project_pageviews")

    monthly = [
        _normalize_month(month, articles_by_month.get(month), projects_by_month.get(month))
        for month in sorted(articles_by_month.keys() | projects_by_month.keys())
    ]
    known_values = [point.value for point in monthly if point.value is not None]
    if not known_values:
        return NormalizedInterest(monthly=monthly)

    return NormalizedInterest(
        monthly=monthly,
        mean=sum(known_values) / len(known_values),
        median=median(known_values),
    )


def _index_by_month(
    observations: Sequence[MonthlyPageview],
    series_name: str,
) -> dict[date, MonthlyPageview]:
    """Index one series while rejecting ambiguous duplicate months."""
    observations_by_month: dict[date, MonthlyPageview] = {}
    for observation in observations:
        if observation.month in observations_by_month:
            raise ValueError(f"'{series_name}' contains duplicate month {observation.month.isoformat()}")
        observations_by_month[observation.month] = observation
    return observations_by_month


def _normalize_month(
    month: date,
    article: MonthlyPageview | None,
    project: MonthlyPageview | None,
) -> NormalizedInterestPoint:
    """Calculate one month only when the numerator and denominator align."""
    if (
        article is None
        or project is None
        or article.status is ObservationStatus.UNKNOWN
        or project.status is ObservationStatus.UNKNOWN
        or article.views is None
        or project.views is None
        or project.views == 0
    ):
        return NormalizedInterestPoint(month=month, status=ObservationStatus.UNKNOWN)

    return NormalizedInterestPoint(
        month=month,
        value=(article.views / project.views) * _PER_MILLION,
    )
