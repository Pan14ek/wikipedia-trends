"""Pure aggregation coverage for M12 topic mode."""

from __future__ import annotations

from datetime import date

import pytest

from wiki_trends.analytics import aggregate_topic_pageviews
from wiki_trends.models import MonthlyPageview, ObservationStatus


def test_topic_aggregation_sums_available_article_views_without_mutating_inputs() -> None:
    first_article = [
        MonthlyPageview(month=date(2026, 1, 1), views=10),
        MonthlyPageview(month=date(2026, 2, 1), status=ObservationStatus.UNKNOWN),
        MonthlyPageview(month=date(2026, 3, 1), status=ObservationStatus.UNKNOWN),
    ]
    second_article = [
        MonthlyPageview(month=date(2026, 1, 1), views=20),
        MonthlyPageview(month=date(2026, 2, 1), views=30),
        MonthlyPageview(month=date(2026, 3, 1), status=ObservationStatus.UNKNOWN),
    ]
    original_first = [observation.model_copy(deep=True) for observation in first_article]
    original_second = [observation.model_copy(deep=True) for observation in second_article]

    aggregated = aggregate_topic_pageviews([first_article, second_article])

    assert [(item.month, item.views, item.status) for item in aggregated] == [
        (date(2026, 1, 1), 30, ObservationStatus.OBSERVED),
        (date(2026, 2, 1), 30, ObservationStatus.OBSERVED),
        (date(2026, 3, 1), None, ObservationStatus.UNKNOWN),
    ]
    assert first_article == original_first
    assert second_article == original_second


def test_topic_aggregation_rejects_empty_and_duplicate_article_series() -> None:
    with pytest.raises(ValueError, match="at least one"):
        aggregate_topic_pageviews([])

    duplicate_month = [
        MonthlyPageview(month=date(2026, 1, 1), views=10),
        MonthlyPageview(month=date(2026, 1, 1), views=20),
    ]
    with pytest.raises(ValueError, match=r"article_series\[0\].*duplicate month"):
        aggregate_topic_pageviews([duplicate_month])

    with pytest.raises(ValueError, match="no more than three"):
        aggregate_topic_pageviews([[MonthlyPageview(month=date(2026, 1, 1), views=index)] for index in range(4)])
