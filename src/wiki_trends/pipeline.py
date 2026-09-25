"""Thin runtime assembly of existing Wikipedia Trends components."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from wiki_trends.analytics import aggregate_topic_pageviews, compute_absolute_metrics, compute_yoy_metrics
from wiki_trends.anomalies import detect_anomalies
from wiki_trends.article_resolver import ArticleResolver
from wiki_trends.charts import render_comparison_charts, render_trend_chart
from wiki_trends.comparison import compare_languages
from wiki_trends.confidence import compute_yoy_confidence_interval
from wiki_trends.config import AnalysisConfig, complete_month_range
from wiki_trends.models import ArticleResolution, LanguageComparisonInput, MonthlyPageview, TopicResolution
from wiki_trends.quality import evaluate_quality
from wiki_trends.report import (
    AnalysisReport,
    DataSourceMetadata,
    LanguageReport,
    ReportArtifacts,
    ReportPeriod,
    ReportResolution,
    ReportRun,
    create_run_slug,
    write_analysis_report,
    write_pdf_report,
)
from wiki_trends.wikipedia_client import WikimediaPageviewsClient

__all__ = ["run_analysis"]


def run_analysis(config: AnalysisConfig, output_root: Path) -> tuple[Path, Path, Path]:
    """Collect, calculate, and write M14/M15 artifacts from one validated config."""
    start, end = complete_month_range(config.period.months)
    period = ReportPeriod(start=start, end=end)
    with ArticleResolver() as resolver, WikimediaPageviewsClient() as pageviews_client:
        resolved = resolver.resolve(config.query, config.languages)
        topic_mode = isinstance(resolved, list)
        topic_resolutions: list[TopicResolution] = cast(list[TopicResolution], resolved) if topic_mode else []
        article_resolution: ArticleResolution | None = None if topic_mode else cast(ArticleResolution, resolved)
        if article_resolution is None and not topic_mode:
            raise RuntimeError("article resolution result is unexpectedly unavailable")
        resolution = (
            ReportResolution(topics=topic_resolutions) if topic_mode else ReportResolution(article=article_resolution)
        )
        language_series: dict[str, list[MonthlyPageview]] = {}
        sources: list[DataSourceMetadata] = []
        for language in config.languages:
            articles = (
                next((item.selected_articles for item in topic_resolutions if item.language == language), [])
                if topic_mode
                else [
                    item for item in cast(ArticleResolution, article_resolution).articles if item.language == language
                ]
            )
            if not articles:
                language_series[language] = []
                continue
            collected = [
                pageviews_client.get_article_pageviews_result(
                    article.project, article.canonical_title, str(start), str(end)
                )
                for article in articles
            ]
            language_series[language] = (
                aggregate_topic_pageviews([item.observations for item in collected])
                if topic_mode
                else collected[0].observations
            )
            sources.extend(
                DataSourceMetadata(
                    endpoint_family="wikimedia-pageviews-per-article",
                    project=article.project,
                    article_title=article.canonical_title,
                    requested_period=period,
                    fetched_at=datetime.now(UTC),
                    access="all-access",
                    agent="user",
                    retrieval=result.retrieval,
                )
                for article, result in zip(articles, collected, strict=True)
            )
    reports = {
        language: LanguageReport(
            pageviews=series,
            absolute_metrics=compute_absolute_metrics(series) if series else None,
            yoy_metrics=compute_yoy_metrics(series) if series else None,
            anomalies=detect_anomalies(series) if series else None,
            confidence_interval=compute_yoy_confidence_interval(series) if series else None,
            quality=evaluate_quality(series).checks if series else [],
            warnings=[] if series else ["No resolved article is available."],
        )
        for language, series in language_series.items()
    }
    comparison = (
        compare_languages(
            [
                LanguageComparisonInput(
                    language=language,
                    pageviews=series,
                    resolved=bool(series),
                    resolution_reason=None if series else "unresolved",
                )
                for language, series in language_series.items()
            ]
        )
        if len(config.languages) > 1
        else None
    )
    slug = create_run_slug(period, config)
    report = AnalysisReport(
        run=ReportRun(slug=slug, generated_at=datetime.now(UTC), methodology_version="1.0"),
        input=config,
        resolution=resolution,
        sources=sources,
        period=period,
        languages=reports,
        comparison=comparison,
        artifacts=ReportArtifacts(),
    )
    chart_path = output_root / f"{slug}-trend.png"
    charts = (
        render_comparison_charts(language_series, config.query.value, chart_path)
        if len(language_series) > 1
        else [render_trend_chart(next(iter(language_series.values())), config.query.value, chart_path)]
    )
    report.artifacts.charts = [str(charts[0])]
    json_path = write_analysis_report(report, output_root)
    pdf_path = write_pdf_report(report, charts[0], output_root / "pdf")
    return json_path, charts[0], pdf_path
