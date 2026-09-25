"""Hand-calculated M13 comparison and shared-validity coverage."""

from __future__ import annotations

from datetime import date

from wiki_trends.comparison import compare_languages
from wiki_trends.models import Granularity, LanguageComparisonInput, MonthlyPageview, ObservationStatus, QualityStatus
from wiki_trends.normalization import compute_normalized_interest
from wiki_trends.quality import evaluate_quality


def test_compares_two_complete_languages_with_shared_absolute_and_normalized_metrics() -> None:
    english = _input("en", _series(date(2024, 1, 1), 24, 100))
    ukrainian = _input("uk", _series(date(2024, 1, 1), 24, 200))

    result = compare_languages([english, ukrainian])

    assert result.comparable is True
    assert result.normalized_comparable is True
    assert result.effective_period is not None
    assert result.effective_period.start == date(2024, 1, 1)
    assert result.effective_period.end == date(2025, 12, 1)
    assert result.metrics_by_language["en"].absolute_metrics is not None
    assert result.metrics_by_language["en"].absolute_metrics.total_views == 2_400
    assert result.metrics_by_language["uk"].absolute_metrics is not None
    assert result.metrics_by_language["uk"].absolute_metrics.total_views == 4_800
    assert result.comparison_validity.status is QualityStatus.PASS
    assert "winner" not in result.model_dump()


def test_compares_three_languages_using_the_same_shared_period() -> None:
    result = compare_languages(
        [
            _input("en", _series(date(2024, 1, 1), 24, 100)),
            _input("pl", _series(date(2024, 1, 1), 24, 150)),
            _input("cs", _series(date(2024, 1, 1), 24, 200)),
        ]
    )

    assert result.comparable is True
    assert result.languages == ["en", "pl", "cs"]
    assert set(result.metrics_by_language) == {"en", "pl", "cs"}


def test_non_equivalent_proxy_cannot_be_reported_as_directly_comparable() -> None:
    source = _input("en", _series(date(2024, 1, 1), 24, 100))
    proxy = _input("uk", _series(date(2024, 1, 1), 24, 200)).model_copy(update={"comparison_equivalent": False})

    result = compare_languages([source, proxy])

    assert result.comparable is False
    assert result.normalized_comparable is False
    assert result.comparison_validity.status is QualityStatus.FAIL
    assert any("Proxy article mappings" in warning for warning in result.warnings)
    assert result.metrics_by_language["uk"].absolute_metrics is None


def test_daily_comparison_accepts_short_exact_shared_window() -> None:
    days = [date(2026, 8, day) for day in range(1, 8)]
    result = compare_languages(
        [
            _input("en", [MonthlyPageview(month=day, granularity=Granularity.DAILY, views=100) for day in days]),
            _input("uk", [MonthlyPageview(month=day, granularity=Granularity.DAILY, views=200) for day in days]),
        ]
    )

    assert result.comparable is True
    assert result.effective_period is not None
    assert result.effective_period.granularity is Granularity.DAILY
    assert result.effective_period.start == days[0]
    assert result.effective_period.end == days[-1]


def test_missing_month_is_excluded_from_direct_metrics_with_a_warning() -> None:
    english_series = _series(date(2024, 1, 1), 24, 100)
    ukrainian_series = _series(date(2024, 1, 1), 24, 200)
    ukrainian_series[5] = MonthlyPageview(month=date(2024, 6, 1), status=ObservationStatus.UNKNOWN)

    result = compare_languages([_input("en", english_series), _input("uk", ukrainian_series)])

    assert result.comparable is True
    assert result.comparison_validity.status is QualityStatus.WARNING
    assert result.metrics_by_language["en"].absolute_metrics is not None
    assert result.metrics_by_language["en"].absolute_metrics.total_views == 2_300
    assert any("1 shared calendar month" in warning for warning in result.warnings)


def test_unresolved_language_is_explicitly_non_comparable() -> None:
    result = compare_languages(
        [
            _input("en", _series(date(2024, 1, 1), 24, 100)),
            LanguageComparisonInput(language="uk", resolved=False, resolution_reason="no_linked_article"),
        ]
    )

    assert result.comparable is False
    assert result.comparison_validity.status is QualityStatus.FAIL
    assert result.metrics_by_language["uk"].absolute_metrics is None
    assert "unresolved" in result.metrics_by_language["uk"].warnings[0]


def test_mismatched_requested_windows_use_an_explicit_eighteen_month_intersection() -> None:
    result = compare_languages(
        [
            _input("en", _series(date(2024, 1, 1), 24, 100)),
            _input("uk", _series(date(2024, 7, 1), 18, 200)),
        ]
    )

    assert result.comparable is True
    assert result.effective_period is not None
    assert result.effective_period.start == date(2024, 7, 1)
    assert result.effective_period.end == date(2025, 12, 1)
    assert result.metrics_by_language["en"].absolute_metrics is not None
    assert result.metrics_by_language["en"].absolute_metrics.requested_months == 18
    assert any("windows differ" in warning for warning in result.warnings)


def test_comparison_validity_integrates_with_the_existing_quality_report() -> None:
    english = _input("en", _series(date(2024, 1, 1), 24, 100))
    ukrainian = _input("uk", _series(date(2024, 1, 1), 24, 200))
    comparison = compare_languages([english, ukrainian])

    report = evaluate_quality(english.pageviews, comparison_validity=comparison.comparison_validity)

    comparison_check = next(check for check in report.checks if check.id.value == "comparison_validity")
    assert comparison_check == comparison.comparison_validity


def _input(language: str, series: list[MonthlyPageview]) -> LanguageComparisonInput:
    """Build a complete comparison input with aligned normalized interest."""
    project_series = [
        MonthlyPageview(month=observation.month, granularity=observation.granularity, views=1_000)
        for observation in series
    ]
    return LanguageComparisonInput(
        language=language,
        pageviews=series,
        normalized_interest=compute_normalized_interest(series, project_series),
    )


def _series(start: date, month_count: int, views: int) -> list[MonthlyPageview]:
    """Build a consecutive calendar-month series with a constant value."""
    start_index = start.year * 12 + start.month - 1
    return [
        MonthlyPageview(
            month=date((start_index + offset) // 12, (start_index + offset) % 12 + 1, 1),
            views=views,
        )
        for offset in range(month_count)
    ]
