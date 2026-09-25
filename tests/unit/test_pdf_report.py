"""End-to-end tests for the bounded M15 PDF presentation layer."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pypdf import PdfReader

from wiki_trends.analytics import compute_absolute_metrics, compute_yoy_metrics
from wiki_trends.charts import render_multi_language_trend_chart, render_trend_chart
from wiki_trends.config import AnalysisConfig
from wiki_trends.models import ArticleResolution, MonthlyPageview, ResolutionStatus
from wiki_trends.report import (
    AnalysisReport,
    DataSourceMetadata,
    LanguageReport,
    ReportPeriod,
    ReportResolution,
    ReportRun,
    write_pdf_report,
)


def _config(languages: list[str]) -> AnalysisConfig:
    return AnalysisConfig.model_validate(
        {
            "query": {"mode": "article", "value": "Київ", "source_language": "uk"},
            "languages": languages,
            "output": {"json": True, "charts": True, "pdf": True},
        }
    )


def _report(languages: list[str]) -> AnalysisReport:
    config = _config(languages)
    period = ReportPeriod(start=date(2024, 1, 1), end=date(2024, 12, 1))
    pageviews = [
        MonthlyPageview(month=date(2024, 1, 1), views=1_200),
        MonthlyPageview(month=date(2024, 2, 1), views=1_500),
    ]
    return AnalysisReport(
        run=ReportRun(
            slug="202401-202412-kyiv-en-uk",
            generated_at=datetime(2026, 9, 25, tzinfo=UTC),
            methodology_version="1.0",
        ),
        input=config,
        resolution=ReportResolution(
            article=ArticleResolution(
                requested_title="Київ",
                source_language="uk",
                status=ResolutionStatus.REQUIRES_CLARIFICATION,
                clarification={"language": "uk", "title": "Київ", "reason": "Fixture resolution state."},
            )
        ),
        sources=[
            DataSourceMetadata(
                endpoint_family="wikimedia-pageviews-per-article",
                project="uk.wikipedia",
                article_title="Київ",
                requested_period=period,
                fetched_at=datetime(2026, 9, 25, tzinfo=UTC),
                access="all-access",
                agent="user",
            )
        ],
        period=period,
        requested_period=period,
        languages={
            language: LanguageReport(
                pageviews=pageviews,
                absolute_metrics=compute_absolute_metrics(pageviews),
                yoy_metrics=compute_yoy_metrics(pageviews),
                warnings=["Coverage is limited in this fixture."] if language == "uk" else [],
            )
            for language in languages
        },
    )


def test_pdf_is_one_page_with_title_period_metrics_warning_and_unicode(tmp_path: Path) -> None:
    report = _report(["uk"])
    chart_path = render_trend_chart(report.languages["uk"].pageviews, "Київ trend", tmp_path / "trend.png")

    pdf_path = write_pdf_report(report, chart_path, tmp_path / "pdf")
    reader = PdfReader(pdf_path)
    text = reader.pages[0].extract_text()

    assert pdf_path.read_bytes().startswith(b"%PDF-")
    assert len(reader.pages) == 1
    assert "Київ" in text
    assert "Jan 2024 - Dec 2024" in text
    assert "2,700" in text
    assert "Coverage is limited in this fixture." in text


def test_pdf_uses_report_chart_metadata_and_represents_multi_language_scope(tmp_path: Path) -> None:
    report = _report(["en", "uk"])
    chart_path = render_multi_language_trend_chart(
        {language: language_report.pageviews for language, language_report in report.languages.items()},
        "Kyiv editions",
        tmp_path / "comparison.png",
    )
    report.artifacts.charts = [str(chart_path)]

    pdf_path = write_pdf_report(report, output_root=tmp_path / "pdf")
    text = PdfReader(pdf_path).pages[0].extract_text()

    assert "en, uk-language Wikipedia edition(s)" in text
    assert "uk: Coverage is limited in this fixture." in text


def test_pdf_rejects_missing_or_non_png_main_chart(tmp_path: Path) -> None:
    report = _report(["uk"])
    invalid_chart = tmp_path / "chart.txt"
    invalid_chart.write_text("not a chart", encoding="utf-8")

    with pytest.raises(ValueError, match="main PNG chart"):
        write_pdf_report(report, output_root=tmp_path / "pdf")
    with pytest.raises(ValueError, match="must be a PNG"):
        write_pdf_report(report, invalid_chart, tmp_path / "pdf")
