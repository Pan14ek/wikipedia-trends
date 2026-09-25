"""Foundational domain models for Wikipedia Trends analyses."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from math import isclose
from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "AbsoluteMetrics",
    "AbsoluteMetricsStatus",
    "AnomalyDetection",
    "AnomalyDetectionMethod",
    "AnomalyDirection",
    "AnomalyRecord",
    "ArticleResolution",
    "ConfidenceInterval",
    "ConfidenceIntervalStatus",
    "ComparisonPeriod",
    "LanguageComparisonInput",
    "LanguageComparisonMetrics",
    "MissingLanguageEquivalent",
    "MultiLanguageComparison",
    "MonthlyPageview",
    "NormalizedInterest",
    "NormalizedInterestPoint",
    "ObservationStatus",
    "QualityCheck",
    "QualityCheckId",
    "QualityReport",
    "QualityStatus",
    "ResolutionClarification",
    "ResolutionMethod",
    "ResolutionStatus",
    "ResolvedArticle",
    "TopicResolution",
    "TopicSelectionMethod",
    "YoYMetrics",
    "YoYStatus",
]


class ObservationStatus(StrEnum):
    """How confidently a monthly pageview value is known."""

    OBSERVED = "observed"
    ZERO_INFERRED = "zero_inferred"
    UNKNOWN = "unknown"


class AnomalyDirection(StrEnum):
    """Whether an unusual observation is above or below the series center."""

    HIGH = "high"
    LOW = "low"


class AnomalyDetectionMethod(StrEnum):
    """The statistical rule used to identify a monthly anomaly."""

    ROBUST_Z_MAD = "robust_z_mad"
    IQR_FALLBACK = "iqr_fallback"


class AnomalyRecord(BaseModel):
    """One unusual observed month and the score that caused it to be flagged."""

    model_config = ConfigDict(extra="forbid")

    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    views: int = Field(ge=0)
    direction: AnomalyDirection
    score: float
    method: AnomalyDetectionMethod


class AnomalyDetection(BaseModel):
    """Anomaly findings and an explicit limitation when statistics are unavailable."""

    model_config = ConfigDict(extra="forbid")

    anomalies: list[AnomalyRecord] = Field(default_factory=list)
    observed_months: int = Field(ge=0)
    method: AnomalyDetectionMethod | None = None
    limitation: str | None = None

    @model_validator(mode="after")
    def validate_detection_state(self) -> AnomalyDetection:
        """Keep anomaly records consistent with their detection method."""
        if self.method is None:
            if self.anomalies:
                raise ValueError("anomaly records require a detection method")
            if self.limitation is None:
                raise ValueError("unavailable anomaly detection requires a limitation")
        elif any(record.method is not self.method for record in self.anomalies):
            raise ValueError("anomaly record methods must match the detection method")
        return self


class QualityStatus(StrEnum):
    """The outcome of one explainable data-quality check."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


class QualityCheckId(StrEnum):
    """Stable identifiers for the M08 quality checks."""

    COMPLETENESS = "completeness"
    PERIOD_SUFFICIENCY = "period_sufficiency"
    ARTICLE_RESOLUTION = "article_resolution"
    TREND_CONSISTENCY = "trend_consistency"
    SPIKE_SENSITIVITY = "spike_sensitivity"
    COMPARISON_VALIDITY = "comparison_validity"


QualityDetailValue = str | int | float | bool | None | list[str]


class QualityCheck(BaseModel):
    """One machine-readable quality finding with an explanation and diagnostics."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: QualityCheckId
    status: QualityStatus
    message: str = Field(min_length=1)
    details: dict[str, QualityDetailValue] = Field(default_factory=dict)


class QualityReport(BaseModel):
    """The complete, explicit quality assessment for one completed analysis."""

    model_config = ConfigDict(extra="forbid")

    checks: list[QualityCheck] = Field(min_length=len(QualityCheckId))

    @model_validator(mode="after")
    def validate_complete_check_set(self) -> QualityReport:
        """Require each M08 check exactly once so callers cannot omit a finding."""
        actual_ids = [check.id for check in self.checks]
        expected_ids = set(QualityCheckId)
        if set(actual_ids) != expected_ids or len(actual_ids) != len(expected_ids):
            raise ValueError("quality reports must include each M08 quality check exactly once")
        return self


class MonthlyPageview(BaseModel):
    """A single monthly pageview observation for an article edition."""

    model_config = ConfigDict(extra="forbid")

    month: date
    views: int | None = Field(default=None, ge=0)
    status: ObservationStatus = ObservationStatus.OBSERVED

    @field_validator("month")
    @classmethod
    def month_must_start_on_first_day(cls, month: date) -> date:
        """Require a canonical month identifier rather than an arbitrary date."""
        if month.day != 1:
            raise ValueError("monthly pageview dates must be the first day of the month")
        return month

    @model_validator(mode="after")
    def validate_observation(self) -> MonthlyPageview:
        """Keep unknown and inferred values unambiguous for later analytics."""
        if self.status is ObservationStatus.UNKNOWN and self.views is not None:
            raise ValueError("unknown observations must not include a view count")
        if self.status is not ObservationStatus.UNKNOWN and self.views is None:
            raise ValueError("known observations must include a view count")
        if self.status is ObservationStatus.ZERO_INFERRED and self.views != 0:
            raise ValueError("zero_inferred observations must have zero views")
        return self


class NormalizedInterestPoint(BaseModel):
    """One calendar-month article-interest value relative to project traffic."""

    model_config = ConfigDict(extra="forbid")

    month: date
    value: float | None = Field(default=None, ge=0)
    status: ObservationStatus = ObservationStatus.OBSERVED

    @field_validator("month")
    @classmethod
    def month_must_start_on_first_day(cls, month: date) -> date:
        """Require a canonical month identifier rather than an arbitrary date."""
        if month.day != 1:
            raise ValueError("normalized-interest dates must be the first day of the month")
        return month

    @model_validator(mode="after")
    def validate_point_state(self) -> NormalizedInterestPoint:
        """Keep unavailable normalization values distinct from measured values."""
        if self.status is ObservationStatus.ZERO_INFERRED:
            raise ValueError("normalized-interest observations cannot be zero_inferred")
        if self.status is ObservationStatus.UNKNOWN and self.value is not None:
            raise ValueError("unknown normalized-interest observations must not include a value")
        if self.status is ObservationStatus.OBSERVED and self.value is None:
            raise ValueError("observed normalized-interest observations must include a value")
        return self


class NormalizedInterest(BaseModel):
    """Monthly and period-summary interest per one million project pageviews."""

    model_config = ConfigDict(extra="forbid")

    unit: Literal["views_per_1m_project_views"] = "views_per_1m_project_views"
    monthly: list[NormalizedInterestPoint]
    mean: float | None = Field(default=None, ge=0)
    median: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_summary(self) -> NormalizedInterest:
        """Require the summary to exactly describe the known monthly values."""
        months = [point.month for point in self.monthly]
        if len(months) != len(set(months)):
            raise ValueError("normalized-interest observations must have unique months")

        known_values = [point.value for point in self.monthly if point.value is not None]
        if not known_values:
            if self.mean is not None or self.median is not None:
                raise ValueError("normalized-interest summaries require known monthly values")
            return self

        expected_mean = sum(known_values) / len(known_values)
        expected_median = median(known_values)
        if self.mean is None or self.median is None:
            raise ValueError("normalized-interest summaries require mean and median")
        if not isclose(self.mean, expected_mean) or not isclose(self.median, expected_median):
            raise ValueError("normalized-interest summaries must match known monthly values")
        return self


class AbsoluteMetricsStatus(StrEnum):
    """Whether a pageview series contains numeric observations to aggregate."""

    AVAILABLE = "available"
    INSUFFICIENT_DATA = "insufficient_data"


class AbsoluteMetrics(BaseModel):
    """Deterministic baseline metrics for a requested monthly pageview series.

    Numeric aggregate fields are ``None`` when every requested observation is
    unknown. Counts and completeness remain available so callers can report
    that insufficient-data state without inferring a zero-valued series.
    """

    model_config = ConfigDict(extra="forbid")

    status: AbsoluteMetricsStatus
    total_views: int | None = Field(default=None, ge=0)
    mean_monthly_views: float | None = Field(default=None, ge=0)
    median_monthly_views: float | None = Field(default=None, ge=0)
    min_monthly_views: int | None = Field(default=None, ge=0)
    max_monthly_views: int | None = Field(default=None, ge=0)
    observed_months: int = Field(ge=0)
    requested_months: int = Field(ge=0)
    completeness_ratio: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_metric_state(self) -> AbsoluteMetrics:
        """Keep status, counts, completeness, and aggregate fields coherent."""
        if self.observed_months > self.requested_months:
            raise ValueError("observed_months must not exceed requested_months")

        expected_completeness = self.observed_months / self.requested_months if self.requested_months else 0.0
        if not isclose(self.completeness_ratio, expected_completeness):
            raise ValueError("completeness_ratio must equal observed_months / requested_months")

        aggregate_values = (
            self.total_views,
            self.mean_monthly_views,
            self.median_monthly_views,
            self.min_monthly_views,
            self.max_monthly_views,
        )
        if self.status is AbsoluteMetricsStatus.INSUFFICIENT_DATA:
            if self.observed_months != 0 or any(value is not None for value in aggregate_values):
                raise ValueError("insufficient_data metrics require zero observations and no numeric aggregates")
        elif self.observed_months == 0 or any(value is None for value in aggregate_values):
            raise ValueError("available metrics require observations and all numeric aggregates")
        return self


class YoYStatus(StrEnum):
    """Whether year-over-year growth can be calculated without miscomparison."""

    AVAILABLE = "available"
    INSUFFICIENT_DATA = "insufficient_data"
    ZERO_BASELINE = "zero_baseline"
    NON_COMPARABLE_PERIODS = "non_comparable_periods"


class YoYMetrics(BaseModel):
    """Calendar-aligned year-over-year totals, growth, and validity details.

    ``previous_total`` and ``recent_total`` are present only when both windows
    have enough comparable observations. ``mean_growth_pct`` is a diagnostic
    equivalent of total-based growth for the equal-sized paired windows.
    """

    model_config = ConfigDict(extra="forbid")

    previous_total: int | None = Field(default=None, ge=0)
    recent_total: int | None = Field(default=None, ge=0)
    growth_pct: float | None = None
    mean_growth_pct: float | None = None
    status: YoYStatus
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_yoy_state(self) -> YoYMetrics:
        """Keep calculated values consistent with their availability state."""
        if self.status is YoYStatus.AVAILABLE:
            if (
                self.previous_total is None
                or self.recent_total is None
                or self.growth_pct is None
                or self.mean_growth_pct is None
            ):
                raise ValueError("available YoY metrics require totals and growth percentages")
            if self.previous_total == 0:
                raise ValueError("available YoY metrics require a positive previous total")

            expected_growth = ((self.recent_total / self.previous_total) - 1) * 100
            if not isclose(self.growth_pct, expected_growth) or not isclose(self.mean_growth_pct, expected_growth):
                raise ValueError("YoY growth percentages must match the supplied totals")
        elif self.status is YoYStatus.ZERO_BASELINE:
            if self.previous_total is None or self.recent_total is None or self.previous_total != 0:
                raise ValueError("zero_baseline YoY metrics require a zero previous total and a recent total")
            if self.growth_pct is not None or self.mean_growth_pct is not None:
                raise ValueError("zero_baseline YoY metrics must not include growth percentages")
        else:
            if (
                self.previous_total is not None
                or self.recent_total is not None
                or self.growth_pct is not None
                or self.mean_growth_pct is not None
            ):
                raise ValueError("unavailable YoY metrics must not include totals or growth percentages")
            if not self.notes:
                raise ValueError("unavailable YoY metrics require an explanatory note")
        return self


class ConfidenceIntervalStatus(StrEnum):
    """Whether a bootstrap confidence interval could be calculated."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ConfidenceInterval(BaseModel):
    """Bootstrap uncertainty bounds for calendar-aligned YoY growth.

    The interval describes variation in the supplied monthly observations under
    the documented bootstrap procedure. It is not a market-demand estimate.
    """

    model_config = ConfigDict(extra="forbid")

    metric: Literal["yoy_growth_pct"] = "yoy_growth_pct"
    method: Literal["paired_month_bootstrap"] = "paired_month_bootstrap"
    level: float = Field(gt=0, lt=1)
    iterations: int = Field(gt=0)
    seed: int
    lower: float | None = None
    upper: float | None = None
    status: ConfidenceIntervalStatus

    @model_validator(mode="after")
    def validate_interval_state(self) -> ConfidenceInterval:
        """Require bounds exactly when the bootstrap produced valid samples."""
        if self.status is ConfidenceIntervalStatus.AVAILABLE:
            if self.lower is None or self.upper is None:
                raise ValueError("available confidence intervals require lower and upper bounds")
            if self.lower > self.upper:
                raise ValueError("confidence interval lower bound must not exceed its upper bound")
        elif self.lower is not None or self.upper is not None:
            raise ValueError("unavailable confidence intervals must not include bounds")
        return self


class ResolutionMethod(StrEnum):
    """Evidence used to identify a language-edition article."""

    INPUT_ARTICLE = "input_article"
    REDIRECT = "redirect"
    LANGUAGE_LINK = "language_link"
    WIKIDATA_SITELINK = "wikidata_sitelink"


class ResolutionStatus(StrEnum):
    """Whether article resolution can safely proceed to pageview collection."""

    RESOLVED = "resolved"
    PARTIAL = "partial"
    REQUIRES_CLARIFICATION = "requires_clarification"


class ResolvedArticle(BaseModel):
    """A canonical Wikipedia article identity with resolution provenance."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    language: str = Field(min_length=1)
    project: str = Field(min_length=1)
    requested_title: str = Field(min_length=1)
    canonical_title: str = Field(min_length=1)
    page_id: int = Field(gt=0)
    wikidata_id: str | None = Field(default=None, min_length=1)
    url: str = Field(min_length=1)
    resolution_method: ResolutionMethod


class MissingLanguageEquivalent(BaseModel):
    """An explicitly unavailable equivalent for one requested language edition."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    language: str = Field(min_length=1)
    project: str = Field(min_length=1)
    requested_title: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ResolutionClarification(BaseModel):
    """Information an agent needs before choosing between multiple concepts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    language: str = Field(min_length=1)
    title: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ArticleResolution(BaseModel):
    """The complete, machine-readable result of one article-resolution attempt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    requested_title: str = Field(min_length=1)
    source_language: str = Field(min_length=1)
    status: ResolutionStatus
    articles: list[ResolvedArticle] = Field(default_factory=list)
    missing_languages: list[MissingLanguageEquivalent] = Field(default_factory=list)
    clarification: ResolutionClarification | None = None

    @model_validator(mode="after")
    def validate_status_contents(self) -> ArticleResolution:
        """Require result fields that match the declared resolution status."""
        if self.status is ResolutionStatus.RESOLVED:
            if not self.articles or self.missing_languages or self.clarification is not None:
                raise ValueError("resolved results require articles and no missing languages or clarification")
        elif self.status is ResolutionStatus.PARTIAL:
            if not self.articles or not self.missing_languages or self.clarification is not None:
                raise ValueError("partial results require articles and missing languages without clarification")
        elif self.clarification is None:
            raise ValueError("clarification results require clarification details")
        return self


class TopicSelectionMethod(StrEnum):
    """The transparent rule used to choose articles for a topic."""

    MEDIAWIKI_SEARCH_RANK_PLUS_TITLE_OVERLAP = "mediawiki_search_rank_plus_title_overlap"
    EXPLICIT_ARTICLE_OVERRIDE = "explicit_article_override"


class TopicResolution(BaseModel):
    """Selected canonical articles for one topic in one language edition.

    Topic resolution is deliberately language-local. Later multi-language
    orchestration can collect one of these records per requested edition
    without implying that titles in different languages are equivalents.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    requested_topic: str = Field(min_length=1)
    language: str = Field(min_length=1)
    status: ResolutionStatus
    selected_articles: list[ResolvedArticle] = Field(default_factory=list, max_length=3)
    candidate_count: int = Field(ge=0, le=5)
    selection_method: TopicSelectionMethod
    clarification: ResolutionClarification | None = None

    @model_validator(mode="after")
    def validate_status_contents(self) -> TopicResolution:
        """Keep selected articles and clarification state unambiguous."""
        if self.status is ResolutionStatus.RESOLVED:
            if not self.selected_articles or self.clarification is not None:
                raise ValueError("resolved topic results require selected articles and no clarification")
            if any(article.language != self.language for article in self.selected_articles):
                raise ValueError("topic selected articles must match the result language")
            page_ids = [article.page_id for article in self.selected_articles]
            if len(page_ids) != len(set(page_ids)):
                raise ValueError("topic selected articles must not contain duplicate pages")
        elif self.status is ResolutionStatus.REQUIRES_CLARIFICATION:
            if self.selected_articles or self.clarification is None:
                raise ValueError("clarification topic results require details and no selected articles")
        else:
            raise ValueError("topic resolution does not support partial status")
        return self


class ComparisonPeriod(BaseModel):
    """The explicit common calendar span used for direct language comparison."""

    model_config = ConfigDict(extra="forbid")

    start: date
    end: date

    @field_validator("start", "end")
    @classmethod
    def month_must_start_on_first_day(cls, month: date) -> date:
        """Require canonical month identifiers for shared-period reporting."""
        if month.day != 1:
            raise ValueError("comparison period dates must be the first day of the month")
        return month

    @model_validator(mode="after")
    def start_must_not_follow_end(self) -> ComparisonPeriod:
        """Keep a comparison period chronologically valid."""
        if self.start > self.end:
            raise ValueError("comparison period start must not follow end")
        return self


class LanguageComparisonInput(BaseModel):
    """One language's pageview evidence before multi-language alignment."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    language: str = Field(min_length=1)
    pageviews: list[MonthlyPageview] = Field(default_factory=list)
    normalized_interest: NormalizedInterest | None = None
    resolved: bool = True
    resolution_reason: str | None = None

    @model_validator(mode="after")
    def validate_resolution_state(self) -> LanguageComparisonInput:
        """Require an explainable reason when a language has no equivalent."""
        months = [observation.month for observation in self.pageviews]
        if len(months) != len(set(months)):
            raise ValueError("language comparison inputs must not contain duplicate pageview months")
        if self.resolved:
            if self.resolution_reason is not None:
                raise ValueError("resolved language comparison inputs must not include a resolution reason")
        elif self.resolution_reason is None:
            raise ValueError("unresolved language comparison inputs require a resolution reason")
        elif self.pageviews:
            raise ValueError("unresolved language comparison inputs must not include pageviews")
        return self


class LanguageComparisonMetrics(BaseModel):
    """Comparable metrics and language-local caveats for one edition."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    language: str = Field(min_length=1)
    absolute_metrics: AbsoluteMetrics | None = None
    normalized_interest: NormalizedInterest | None = None
    yoy_metrics: YoYMetrics | None = None
    requested_months: int = Field(ge=0)
    available_months: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_metric_availability(self) -> LanguageComparisonMetrics:
        """Keep unavailable-language metrics distinct from a zero-valued series."""
        if self.available_months > self.requested_months:
            raise ValueError("available_months must not exceed requested_months")
        if self.absolute_metrics is None and (
            self.normalized_interest is not None or self.yoy_metrics is not None or not self.warnings
        ):
            raise ValueError("unavailable language metrics require warnings and no calculated metrics")
        return self


class MultiLanguageComparison(BaseModel):
    """Typed, explanation-first output for one aligned language comparison."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    languages: list[str] = Field(min_length=2, max_length=20)
    effective_period: ComparisonPeriod | None = None
    comparable: bool
    normalized_comparable: bool
    warnings: list[str] = Field(default_factory=list)
    metrics_by_language: dict[str, LanguageComparisonMetrics]
    comparison_validity: QualityCheck

    @model_validator(mode="after")
    def validate_comparison_shape(self) -> MultiLanguageComparison:
        """Require one metrics record and a validity check for every language."""
        if len(self.languages) != len(set(self.languages)):
            raise ValueError("comparison languages must be unique")
        if set(self.metrics_by_language) != set(self.languages):
            raise ValueError("comparison metrics must contain exactly the requested languages")
        if any(metrics.language != language for language, metrics in self.metrics_by_language.items()):
            raise ValueError("comparison metrics keys must match their language field")
        if self.comparison_validity.id is not QualityCheckId.COMPARISON_VALIDITY:
            raise ValueError("comparison output requires the comparison_validity quality check")
        if self.comparable and self.effective_period is None:
            raise ValueError("comparable output requires an effective comparison period")
        return self
