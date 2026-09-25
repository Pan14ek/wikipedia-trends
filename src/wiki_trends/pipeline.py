"""Orchestrate data collection, transparent metrics, and report artifacts."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

from wiki_trends.analytics import aggregate_topic_pageviews, compute_absolute_metrics, compute_yoy_metrics
from wiki_trends.anomalies import detect_anomalies
from wiki_trends.article_resolver import ArticleResolver
from wiki_trends.charts import render_comparison_charts, render_trend_chart
from wiki_trends.comparison import compare_languages
from wiki_trends.confidence import compute_yoy_confidence_interval
from wiki_trends.config import AnalysisConfig, latest_complete_day, resolve_period
from wiki_trends.models import (
    AbsoluteMetrics,
    ArticleResolution,
    CriterionEvaluation,
    CriterionEvaluationStatus,
    CriterionMetric,
    CriterionOperator,
    Granularity,
    LanguageComparisonInput,
    MonthlyPageview,
    NormalizedInterest,
    ObservationStatus,
    PeriodGrowthMetrics,
    PeriodGrowthStatus,
    TopicResolution,
)
from wiki_trends.normalization import compute_normalized_interest
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

_LOGGER = logging.getLogger(__name__)


def run_analysis(config: AnalysisConfig, output_root: Path) -> tuple[Path | None, Path | None, Path | None]:
    """Collect and report one configured daily or monthly analysis run."""
    requested_start, requested_end = resolve_period(config.period)
    granularity = config.period.resolved_granularity
    collection_start, collection_end = _available_window(requested_start, requested_end, granularity)
    requested_period = ReportPeriod(start=requested_start, end=requested_end, granularity=granularity)
    period = ReportPeriod(start=collection_start, end=collection_end, granularity=granularity)
    comparison_period = _report_baseline(config)
    normalized_config = _freeze_resolved_input(config, requested_start, requested_end, granularity)

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
        normalized_by_language = {}
        baseline_series_by_language: dict[str, list[MonthlyPageview]] = {}
        sources: list[DataSourceMetadata] = []
        for language in config.languages:
            articles = (
                next((item.selected_articles for item in topic_resolutions if item.language == language), [])
                if topic_mode
                else [item for item in cast(ArticleResolution, article_resolution).articles if item.language == language]
            )
            if not articles:
                language_series[language] = []
                continue
            collected = [
                pageviews_client.get_article_pageviews_result(
                    article.project,
                    article.canonical_title,
                    collection_start,
                    collection_end,
                    granularity=granularity,
                )
                for article in articles
            ]
            series = (
                aggregate_topic_pageviews([item.observations for item in collected])
                if topic_mode
                else collected[0].observations
            )
            language_series[language] = series
            if comparison_period is not None:
                baseline_results = [
                    pageviews_client.get_article_pageviews_result(
                        article.project,
                        article.canonical_title,
                        comparison_period.start,
                        comparison_period.end,
                        granularity=granularity,
                    )
                    for article in articles
                ]
                baseline_series_by_language[language] = (
                    aggregate_topic_pageviews([item.observations for item in baseline_results])
                    if topic_mode
                    else baseline_results[0].observations
                )
            needs_normalized = config.criteria.normalized_interest or any(
                criterion.metric is CriterionMetric.NORMALIZED_INTEREST_MEAN for criterion in config.thresholds
            )
            if needs_normalized:
                project_results = [
                    pageviews_client.get_project_pageviews_result(
                        article.project,
                        collection_start,
                        collection_end,
                        granularity=granularity,
                    )
                    for article in articles
                ]
                project_series = (
                    aggregate_topic_pageviews([result.observations for result in project_results])
                    if topic_mode
                    else project_results[0].observations
                )
                normalized_by_language[language] = compute_normalized_interest(series, project_series)
                sources.extend(
                    DataSourceMetadata(
                        endpoint_family="wikimedia-pageviews-aggregate",
                        project=article.project,
                        requested_period=period,
                        fetched_at=datetime.now(UTC),
                        access="all-access",
                        agent="user",
                        granularity=granularity,
                        retrieval=result.retrieval,
                    )
                    for article, result in zip(articles, project_results, strict=True)
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
                    granularity=granularity,
                    retrieval=result.retrieval,
                )
                for article, result in zip(articles, collected, strict=True)
            )

    period_growth = (
        _compute_period_growth(language_series, baseline_series_by_language, comparison_period)
        if config.criteria.growth or any(item.metric is CriterionMetric.GROWTH_PCT for item in config.thresholds)
        else {}
    )
    reports: dict[str, LanguageReport] = {}
    for language, series in language_series.items():
        absolute = compute_absolute_metrics(series) if series else None
        yoy = (
            compute_yoy_metrics(series)
            if series and granularity is Granularity.MONTHLY and config.criteria.growth
            else None
        )
        normalized = normalized_by_language.get(language)
        reports[language] = LanguageReport(
            pageviews=series,
            absolute_metrics=absolute,
            yoy_metrics=yoy,
            period_growth=period_growth.get(language),
            normalized_interest=normalized,
            anomalies=detect_anomalies(series) if series and config.criteria.anomalies else None,
            confidence_interval=(
                compute_yoy_confidence_interval(series)
                if series and granularity is Granularity.MONTHLY and config.criteria.confidence_intervals
                else None
            ),
            quality=evaluate_quality(series, yoy_metrics=yoy).checks if series else [],
            criterion_evaluations=_evaluate_thresholds(config, absolute, normalized, period_growth.get(language)),
            warnings=[] if series else ["No resolved article is available."],
        )
    comparison = (
        compare_languages(
            [
                LanguageComparisonInput(
                    language=language,
                    pageviews=series,
                    normalized_interest=normalized_by_language.get(language),
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
        run=ReportRun(slug=slug, generated_at=datetime.now(UTC), methodology_version="2.0"),
        input=normalized_config,
        resolution=resolution,
        sources=sources,
        period=period,
        requested_period=requested_period,
        comparison_period=comparison_period,
        criteria=config.thresholds,
        languages=reports,
        comparison=comparison,
        artifacts=ReportArtifacts(),
    )

    chart_path: Path | None = None
    pdf_path: Path | None = None
    if config.output.charts or config.output.pdf:
        chart_path = output_root / f"{slug}-trend.png"
        charts = (
            render_comparison_charts(language_series, config.query.value, chart_path)
            if len(language_series) > 1
            else [render_trend_chart(next(iter(language_series.values())), config.query.value, chart_path)]
        )
        report.artifacts.charts = [str(chart) for chart in charts] if config.output.charts else []
        if config.output.pdf:
            pdf_path = write_pdf_report(report, charts[0], output_root / "pdf")
            report.artifacts.pdf = str(pdf_path)
    json_path = write_analysis_report(report, output_root) if config.output.json_output else None
    _LOGGER.info(
        "analysis completed",
        extra={"languages": len(config.languages), "granularity": granularity.value, "artifacts": 1 + int(chart_path is not None) + int(pdf_path is not None)},
    )
    return json_path, chart_path if config.output.charts else None, pdf_path


def _available_window(start: date, end: date, granularity: Granularity) -> tuple[date, date]:
    """Clamp an inclusive request to the latest expected complete data bucket."""
    if granularity is Granularity.DAILY:
        available_end = min(end, latest_complete_day())
        if available_end < start:
            raise ValueError("the requested period contains no complete daily observations yet")
        return start, available_end
    today = date.today()
    latest_month_start = date(today.year, today.month, 1)
    available_end = min(end, latest_month_start - timedelta(days=1))
    if available_end < start:
        raise ValueError("the requested period contains no complete monthly observations yet")
    return start, available_end


def _report_baseline(config: AnalysisConfig) -> ReportPeriod | None:
    """Return the configured comparison period for report output."""
    baseline = config.comparison_period
    if baseline is None:
        return None
    return ReportPeriod(start=baseline.start, end=baseline.end, granularity=baseline.granularity)


def _freeze_resolved_input(
    config: AnalysisConfig,
    start: date,
    end: date,
    granularity: Granularity,
) -> AnalysisConfig:
    """Persist the resolved relative window as exact dates for safe follow-ups."""
    period = config.period.model_copy(update={"months": None, "start": start, "end": end, "granularity": granularity})
    return config.model_copy(update={"period": period})


def _compute_period_growth(
    series_by_language: dict[str, list[MonthlyPageview]],
    baseline_by_language: dict[str, list[MonthlyPageview]],
    baseline: ReportPeriod | None,
) -> dict[str, PeriodGrowthMetrics]:
    """Compute growth only when an explicit baseline was selected."""
    if baseline is None:
        return {}
    results: dict[str, PeriodGrowthMetrics] = {}
    for language, current in series_by_language.items():
        previous = baseline_by_language.get(language, [])
        current_known = [item.views for item in current if item.status is not ObservationStatus.UNKNOWN]
        previous_known = [item.views for item in previous if item.status is not ObservationStatus.UNKNOWN]
        if (
            not current
            or len(current) != len(previous)
            or len(current_known) != len(current)
            or len(previous_known) != len(previous)
        ):
            results[language] = PeriodGrowthMetrics(
                status=PeriodGrowthStatus.INSUFFICIENT_DATA,
                notes=["Both equal-length periods require complete observations for growth calculation."],
            )
        else:
            current_total = sum(value for value in current_known if value is not None)
            previous_total = sum(value for value in previous_known if value is not None)
            if previous_total == 0:
                results[language] = PeriodGrowthMetrics(
                    baseline_total=0,
                    period_total=current_total,
                    status=PeriodGrowthStatus.ZERO_BASELINE,
                    notes=["Growth is undefined because the selected baseline total is zero."],
                )
            else:
                results[language] = PeriodGrowthMetrics(
                    baseline_total=previous_total,
                    period_total=current_total,
                    growth_pct=((current_total / previous_total) - 1) * 100,
                    status=PeriodGrowthStatus.AVAILABLE,
                )
    return results


def _evaluate_thresholds(
    config: AnalysisConfig,
    absolute: AbsoluteMetrics | None,
    normalized: NormalizedInterest | None,
    growth: PeriodGrowthMetrics | None,
) -> list[CriterionEvaluation]:
    """Evaluate configured numeric rules independently, without ranking languages."""
    evaluations: list[CriterionEvaluation] = []
    for criterion in config.thresholds:
        value: float | None
        if criterion.metric is CriterionMetric.COMPLETENESS_RATIO and absolute is not None:
            value = absolute.completeness_ratio
        elif criterion.metric is CriterionMetric.NORMALIZED_INTEREST_MEAN and normalized is not None:
            value = normalized.mean
        elif criterion.metric is CriterionMetric.GROWTH_PCT and growth is not None:
            value = growth.growth_pct
        else:
            value = None
        if value is None:
            evaluations.append(
                CriterionEvaluation(
                    name=criterion.name,
                    metric=criterion.metric,
                    operator=criterion.operator,
                    threshold=criterion.threshold,
                    status=CriterionEvaluationStatus.NOT_EVALUABLE,
                    reason="Required observations or comparison baseline are unavailable.",
                )
            )
            continue
        met = {
            CriterionOperator.GT: value > criterion.threshold,
            CriterionOperator.GTE: value >= criterion.threshold,
            CriterionOperator.LT: value < criterion.threshold,
            CriterionOperator.LTE: value <= criterion.threshold,
        }[criterion.operator]
        evaluations.append(
            CriterionEvaluation(
                name=criterion.name,
                metric=criterion.metric,
                operator=criterion.operator,
                threshold=criterion.threshold,
                value=value,
                status=CriterionEvaluationStatus.MET if met else CriterionEvaluationStatus.NOT_MET,
            )
        )
    return evaluations
