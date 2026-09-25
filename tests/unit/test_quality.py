"""Unit coverage for M08 explicit data-quality checks."""

from __future__ import annotations

from datetime import date

import pytest

from wiki_trends.analytics import compute_yoy_metrics
from wiki_trends.models import (
    ArticleResolution,
    MissingLanguageEquivalent,
    MonthlyPageview,
    ObservationStatus,
    QualityCheck,
    QualityCheckId,
    QualityStatus,
    ResolutionMethod,
    ResolutionStatus,
    ResolvedArticle,
)
from wiki_trends.quality import evaluate_quality


@pytest.mark.parametrize(
    ("requested_months", "available_months", "expected_status"),
    [
        (20, 20, QualityStatus.PASS),
        (20, 19, QualityStatus.PASS),
        (20, 16, QualityStatus.WARNING),
        (20, 14, QualityStatus.FAIL),
    ],
)
def test_classifies_completeness_at_specified_thresholds(
    requested_months: int,
    available_months: int,
    expected_status: QualityStatus,
) -> None:
    report = evaluate_quality(
        _monthly_series(month_count=requested_months, available_months=available_months),
        _resolved_article(),
    )

    completeness = _check(report.checks, QualityCheckId.COMPLETENESS)

    assert completeness.status is expected_status
    assert completeness.details["available_months"] == available_months
    assert completeness.details["requested_months"] == requested_months


def test_passes_period_sufficiency_for_a_twenty_four_month_request() -> None:
    report = evaluate_quality(_twenty_four_month_series(24), _resolved_article())

    period = _check(report.checks, QualityCheckId.PERIOD_SUFFICIENCY)

    assert period.status is QualityStatus.PASS


def test_warns_for_a_valid_twelve_month_period_without_standard_yoy() -> None:
    report = evaluate_quality(_monthly_series(month_count=12), _resolved_article())

    period = _check(report.checks, QualityCheckId.PERIOD_SUFFICIENCY)

    assert period.status is QualityStatus.WARNING
    assert "cannot provide" in period.message


def test_fails_period_sufficiency_below_the_minimum_analysis_window() -> None:
    report = evaluate_quality(_monthly_series(month_count=11), _resolved_article())

    period = _check(report.checks, QualityCheckId.PERIOD_SUFFICIENCY)

    assert period.status is QualityStatus.FAIL
    assert "at least 12 months" in period.message


def test_fails_yoy_period_check_when_aligned_data_is_insufficient() -> None:
    series = _twenty_four_month_series(available_months=24)
    series[2] = MonthlyPageview(month=series[2].month, status=ObservationStatus.UNKNOWN)

    report = evaluate_quality(series, _resolved_article(), compute_yoy_metrics(series))

    period = _check(report.checks, QualityCheckId.PERIOD_SUFFICIENCY)
    assert period.status is QualityStatus.FAIL
    assert "cannot support a valid YoY comparison" in period.message


def test_reports_unresolved_language_as_a_resolution_failure() -> None:
    resolution = ArticleResolution(
        requested_title="Astronomy",
        source_language="en",
        status=ResolutionStatus.PARTIAL,
        articles=[_resolved_article().articles[0]],
        missing_languages=[
            MissingLanguageEquivalent(
                language="uk",
                project="uk.wikipedia",
                requested_title="Astronomy",
                reason="No linked article exists.",
            )
        ],
    )

    report = evaluate_quality(_twenty_four_month_series(24), resolution)

    resolution_check = _check(report.checks, QualityCheckId.ARTICLE_RESOLUTION)
    assert resolution_check.status is QualityStatus.FAIL
    assert resolution_check.details["missing_languages"] == ["uk"]


def test_reports_mixed_trend_changes_as_diagnostics_not_a_judgment() -> None:
    series = [
        MonthlyPageview(month=date(2025, 1, 1), views=100),
        MonthlyPageview(month=date(2025, 2, 1), views=110),
        MonthlyPageview(month=date(2025, 3, 1), views=90),
        MonthlyPageview(month=date(2025, 4, 1), views=90),
        MonthlyPageview(month=date(2025, 5, 1), views=120),
    ]

    report = evaluate_quality(series, _resolved_article())

    trend = _check(report.checks, QualityCheckId.TREND_CONSISTENCY)
    assert trend.status is QualityStatus.PASS
    assert trend.details["comparable_adjacent_month_pairs"] == 4
    assert trend.details["positive_month_over_month_changes"] == 2
    assert trend.details["positive_change_ratio"] == 0.5


def test_includes_not_evaluated_future_integration_points() -> None:
    report = evaluate_quality(_twenty_four_month_series(24), _resolved_article())

    assert _check(report.checks, QualityCheckId.SPIKE_SENSITIVITY).status is QualityStatus.NOT_EVALUATED
    assert _check(report.checks, QualityCheckId.COMPARISON_VALIDITY).status is QualityStatus.NOT_EVALUATED


def test_warns_when_removing_a_spike_flips_yoy_direction() -> None:
    baseline = [95, 100, 105] * 4
    series = [
        *[MonthlyPageview(month=date(2024, month, 1), views=views) for month, views in enumerate(baseline, start=1)],
        *[
            MonthlyPageview(month=date(2025, month, 1), views=2_000 if month == 12 else views)
            for month, views in enumerate(baseline, start=1)
        ],
    ]

    report = evaluate_quality(series, _resolved_article(), compute_yoy_metrics(series))

    spike_sensitivity = _check(report.checks, QualityCheckId.SPIKE_SENSITIVITY)
    assert spike_sensitivity.status is QualityStatus.WARNING
    assert spike_sensitivity.details["selected_anomaly_month"] == "2025-12"
    assert spike_sensitivity.details["direction_changed"] is True


def test_passes_spike_sensitivity_when_no_anomalies_are_detected() -> None:
    series = [
        MonthlyPageview(month=date(2024 + index // 12, index % 12 + 1, 1), views=95 + (index % 3) * 5)
        for index in range(24)
    ]

    report = evaluate_quality(series, _resolved_article(), compute_yoy_metrics(series))

    spike_sensitivity = _check(report.checks, QualityCheckId.SPIKE_SENSITIVITY)
    assert spike_sensitivity.status is QualityStatus.PASS
    assert spike_sensitivity.details["anomaly_count"] == 0


def test_uses_the_configured_spike_sensitivity_materiality_threshold() -> None:
    baseline = [95, 100, 105] * 4
    series = [
        *[MonthlyPageview(month=date(2024, month, 1), views=views) for month, views in enumerate(baseline, start=1)],
        *[
            MonthlyPageview(month=date(2025, month, 1), views=2_000 if month == 12 else 200)
            for month, _ in enumerate(baseline, start=1)
        ],
    ]

    report = evaluate_quality(
        series,
        _resolved_article(),
        compute_yoy_metrics(series),
        spike_sensitivity_threshold_pct=200,
    )

    spike_sensitivity = _check(report.checks, QualityCheckId.SPIKE_SENSITIVITY)
    assert spike_sensitivity.status is QualityStatus.PASS
    assert spike_sensitivity.details["materiality_threshold_percentage_points"] == 200


def test_rejects_an_invalid_spike_sensitivity_threshold() -> None:
    with pytest.raises(ValueError, match="finite non-negative"):
        evaluate_quality(_twenty_four_month_series(24), spike_sensitivity_threshold_pct=-1)


def test_rejects_duplicate_months_before_calculating_diagnostics() -> None:
    duplicate_month = date(2025, 1, 1)
    with pytest.raises(ValueError, match="at most one observation"):
        evaluate_quality(
            [
                MonthlyPageview(month=duplicate_month, views=1),
                MonthlyPageview(month=duplicate_month, views=2),
            ],
            _resolved_article(),
        )


def _check(checks: list[QualityCheck], check_id: QualityCheckId) -> QualityCheck:
    """Return one quality check by its stable identifier."""
    return next(check for check in checks if check.id is check_id)


def _twenty_four_month_series(available_months: int) -> list[MonthlyPageview]:
    """Create 24 requested months with a controlled number of known values."""
    return _monthly_series(month_count=24, available_months=available_months)


def _monthly_series(month_count: int, available_months: int | None = None) -> list[MonthlyPageview]:
    """Create consecutive observations, making trailing months unknown when requested."""
    known_months = month_count if available_months is None else available_months
    return [
        MonthlyPageview(month=date(2024 + index // 12, index % 12 + 1, 1), views=100)
        if index < known_months
        else MonthlyPageview(month=date(2024 + index // 12, index % 12 + 1, 1), status=ObservationStatus.UNKNOWN)
        for index in range(month_count)
    ]


def _resolved_article() -> ArticleResolution:
    """Build a canonical M04 resolution outcome for one English article."""
    return ArticleResolution(
        requested_title="Astronomy",
        source_language="en",
        status=ResolutionStatus.RESOLVED,
        articles=[
            ResolvedArticle(
                language="en",
                project="en.wikipedia",
                requested_title="Astronomy",
                canonical_title="Astronomy",
                page_id=123,
                url="https://en.wikipedia.org/wiki/Astronomy",
                resolution_method=ResolutionMethod.INPUT_ARTICLE,
            )
        ],
    )
