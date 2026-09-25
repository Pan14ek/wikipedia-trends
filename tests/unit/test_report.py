"""Regression coverage for the versioned M14 JSON report contract."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from wiki_trends.analytics import compute_absolute_metrics, compute_yoy_metrics
from wiki_trends.config import AnalysisConfig
from wiki_trends.models import (
    ArticleResolution,
    ConfidenceInterval,
    ConfidenceIntervalStatus,
    MonthlyPageview,
    ObservationStatus,
    ResolutionStatus,
)
from wiki_trends.report import (
    ANALYSIS_REPORT_SCHEMA_VERSION,
    AnalysisReport,
    DataSourceMetadata,
    LanguageReport,
    ReportArtifacts,
    ReportPeriod,
    ReportResolution,
    ReportRun,
    create_run_slug,
    write_analysis_report,
)


def _config(mode: str = "article", languages: list[str] | None = None) -> AnalysisConfig:
    return AnalysisConfig.model_validate(
        {
            "query": {"mode": mode, "value": "Kyiv"},
            "languages": languages or ["en"],
            "output": {"json": True, "charts": False, "pdf": False},
        }
    )


def _article_resolution() -> ArticleResolution:
    return ArticleResolution(
        requested_title="Kyiv",
        source_language="en",
        status=ResolutionStatus.REQUIRES_CLARIFICATION,
        clarification={"language": "en", "title": "Kyiv", "reason": "Fixture intentionally unresolved."},
    )


def _report(languages: list[str] | None = None) -> AnalysisReport:
    config = _config(languages=languages)
    period = ReportPeriod(start=date(2024, 1, 1), end=date(2024, 12, 1))
    pageviews = [MonthlyPageview(month=date(2024, 1, 1), views=123)]
    language_reports = {
        language: LanguageReport(
            pageviews=pageviews if language == "en" else [],
            absolute_metrics=compute_absolute_metrics(pageviews) if language == "en" else None,
            yoy_metrics=compute_yoy_metrics(pageviews) if language == "en" else None,
            warnings=[] if language == "en" else ["No resolved equivalent is available."],
        )
        for language in config.languages
    }
    return AnalysisReport(
        run=ReportRun(
            slug="202401-202412-kyiv-en",
            generated_at=datetime(2026, 9, 25, tzinfo=UTC),
            methodology_version="1.0",
        ),
        input=config,
        resolution=ReportResolution(article=_article_resolution()),
        sources=[
            DataSourceMetadata(
                endpoint_family="wikimedia-pageviews-per-article",
                project="en.wikipedia",
                article_title="Kyiv",
                requested_period=period,
                fetched_at=datetime(2026, 9, 25, tzinfo=UTC),
                access="all-access",
                agent="user",
            )
        ],
        period=period,
        languages=language_reports,
        warnings=["The fixture has fewer than 12 requested observations."],
        artifacts=ReportArtifacts(charts=["trend.png"]),
    )


def test_writer_emits_pretty_utf8_validated_single_article_report(tmp_path: Path) -> None:
    output_path = write_analysis_report(_report(), tmp_path)

    text = output_path.read_text(encoding="utf-8")
    parsed = AnalysisReport.model_validate(json.loads(text))

    assert text.startswith("{\n  ")
    assert parsed.schema_version == ANALYSIS_REPORT_SCHEMA_VERSION
    assert parsed.artifacts.analysis_json == str(output_path)
    assert parsed.sources[0].endpoint_family == "wikimedia-pageviews-per-article"


def test_writer_avoids_colliding_run_directories(tmp_path: Path) -> None:
    first = write_analysis_report(_report(), tmp_path)
    second = write_analysis_report(_report(), tmp_path)

    assert first.parent.name == "202401-202412-kyiv-en"
    assert second.parent.name == "202401-202412-kyiv-en-1"


def test_report_represents_unresolved_language_and_unavailable_confidence_interval() -> None:
    report = _report(languages=["en", "uk"])
    report.languages["en"].confidence_interval = ConfidenceInterval(
        level=0.95,
        iterations=1_000,
        seed=7,
        status=ConfidenceIntervalStatus.UNAVAILABLE,
    )

    assert report.languages["uk"].pageviews == []
    assert report.languages["uk"].warnings == ["No resolved equivalent is available."]
    assert report.languages["en"].confidence_interval.status is ConfidenceIntervalStatus.UNAVAILABLE


def test_topic_mode_and_default_slug_are_supported() -> None:
    config = _config(mode="topic", languages=["en", "uk"])
    period = ReportPeriod(start=date(2024, 1, 1), end=date(2024, 12, 1))

    assert create_run_slug(period, config) == "202401-202412-kyiv-en-uk"


def test_report_rejects_missing_language_section() -> None:
    report = _report()
    with pytest.raises(ValidationError, match="configured languages"):
        AnalysisReport.model_validate({**report.model_dump(by_alias=True), "languages": {}})


def test_unknown_observations_remain_explicit_in_report() -> None:
    report = _report()
    report.languages["en"].pageviews = [
        MonthlyPageview(month=date(2024, 1, 1), views=None, status=ObservationStatus.UNKNOWN)
    ]

    assert report.languages["en"].pageviews[0].views is None
