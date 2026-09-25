"""Pure aggregation coverage for WT-M20 topic completeness semantics."""

from __future__ import annotations

from datetime import date

import pytest

from wiki_trends.analytics import aggregate_topic_pageviews
from wiki_trends.models import Granularity, MonthlyPageview, ObservationStatus


def test_unknown_component_makes_topic_bucket_unknown_without_mutating_inputs() -> None:
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
        (date(2026, 2, 1), None, ObservationStatus.UNKNOWN),
        (date(2026, 3, 1), None, ObservationStatus.UNKNOWN),
    ]
    assert first_article == original_first
    assert second_article == original_second


def test_complete_topic_buckets_sum_and_preserve_zero_inferred_semantics() -> None:
    observed = [MonthlyPageview(month=date(2026, 1, 1), views=10)]
    inferred = [MonthlyPageview(month=date(2026, 1, 1), views=0, status=ObservationStatus.ZERO_INFERRED)]

    mixed = aggregate_topic_pageviews([observed, inferred])[0]
    assert (mixed.views, mixed.status) == (10, ObservationStatus.OBSERVED)

    all_inferred = aggregate_topic_pageviews([inferred, inferred])[0]
    assert (all_inferred.views, all_inferred.status) == (0, ObservationStatus.ZERO_INFERRED)


@pytest.mark.parametrize("granularity", [Granularity.DAILY, Granularity.MONTHLY])
def test_unknown_component_makes_daily_and_monthly_topic_buckets_unknown(granularity: Granularity) -> None:
    bucket = date(2026, 1, 1)
    first = [MonthlyPageview(month=bucket, granularity=granularity, views=5)]
    second = [MonthlyPageview(month=bucket, granularity=granularity, status=ObservationStatus.UNKNOWN)]

    result = aggregate_topic_pageviews([first, second])

    assert len(result) == 1
    assert result[0].views is None
    assert result[0].status is ObservationStatus.UNKNOWN


def test_missing_article_bucket_is_unknown_in_the_topic_aggregate() -> None:
    first = [MonthlyPageview(month=date(2026, 1, 1), views=5), MonthlyPageview(month=date(2026, 2, 1), views=8)]
    second = [MonthlyPageview(month=date(2026, 1, 1), views=7)]

    result = aggregate_topic_pageviews([first, second])

    assert [(item.views, item.status) for item in result] == [
        (12, ObservationStatus.OBSERVED),
        (None, ObservationStatus.UNKNOWN),
    ]


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
