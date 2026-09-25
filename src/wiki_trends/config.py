"""Validation and date semantics for analysis request configuration."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from wiki_trends.models import CriterionMetric, CriterionOperator, Granularity

__all__ = [
    "AnalysisConfig",
    "CriteriaConfig",
    "ComparisonPeriodConfig",
    "CriterionConfig",
    "CriterionMetric",
    "CriterionOperator",
    "Granularity",
    "OutputConfig",
    "PeriodConfig",
    "QueryConfig",
    "QueryMode",
    "complete_month_range",
    "load_config",
    "resolve_period",
    "latest_complete_day",
]


class QueryMode(StrEnum):
    """Supported ways of identifying the subject of an analysis."""

    ARTICLE = "article"
    TOPIC = "topic"


LanguageCode = Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9-]*$")]
ArticleTitle = Annotated[str, Field(min_length=1)]


class QueryConfig(BaseModel):
    """The subject to analyze."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mode: QueryMode
    value: str = Field(min_length=1)
    source_language: LanguageCode | None = None
    article_overrides: dict[LanguageCode, list[ArticleTitle]] = Field(default_factory=dict)

    @field_validator("article_overrides")
    @classmethod
    def article_overrides_must_be_nonempty_and_bounded(
        cls,
        article_overrides: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        """Require each topic override to name one to three articles."""
        for language, titles in article_overrides.items():
            if not 1 <= len(titles) <= 3:
                raise ValueError(f"article override for '{language}' must contain one to three article titles")
            if len(titles) != len(set(titles)):
                raise ValueError(f"article override for '{language}' must not contain duplicate article titles")
        return article_overrides

    @model_validator(mode="after")
    def article_overrides_require_topic_mode(self) -> QueryConfig:
        """Keep article-mode resolution unchanged and topic overrides explicit."""
        if self.article_overrides and self.mode is not QueryMode.TOPIC:
            raise ValueError("article_overrides are supported only when query.mode is 'topic'")
        return self


class PeriodConfig(BaseModel):
    """An inclusive date window or a legacy count of complete months."""

    model_config = ConfigDict(extra="forbid")

    months: int | None = Field(default=24, ge=1, le=120)
    start: date | None = None
    end: date | None = None
    granularity: Granularity | None = None

    @model_validator(mode="before")
    @classmethod
    def explicit_dates_replace_the_legacy_month_count(cls, value: object) -> object:
        """Allow date-window configs to omit ``months`` despite its legacy default."""
        if isinstance(value, dict) and ("start" in value or "end" in value) and "months" not in value:
            return {**value, "months": None}
        return value

    @model_validator(mode="after")
    def validate_window(self) -> PeriodConfig:
        """Require either a legacy month count or one complete explicit window."""
        if (self.start is None) != (self.end is None):
            raise ValueError("period.start and period.end must be provided together")
        start, end = self.start, self.end
        if start is None:
            if self.months is None:
                raise ValueError("period.months is required when explicit dates are not provided")
            if self.granularity not in (None, Granularity.MONTHLY):
                raise ValueError("legacy period.months supports monthly granularity only")
            if self.granularity is None:
                object.__setattr__(self, "granularity", Granularity.MONTHLY)
            return self
        if self.months is not None:
            raise ValueError("period.months cannot be combined with explicit start and end dates")
        if end is None:
            raise ValueError("period.start and period.end must be provided together")
        if start > end:
            raise ValueError("period.start must not follow period.end")
        if self.granularity is Granularity.MONTHLY and not _is_full_calendar_month_window(start, end):
            raise ValueError("monthly granularity requires a first-of-month start and last-of-month end")
        if self.granularity is None:
            object.__setattr__(
                self,
                "granularity",
                Granularity.MONTHLY
                if _is_full_calendar_month_window(start, end)
                else Granularity.DAILY,
            )
        return self

    @property
    def resolved_granularity(self) -> Granularity:
        """Return explicit granularity or infer it from the selected window."""
        if self.granularity is None:
            raise ValueError("period granularity has not been resolved")
        return self.granularity


class ComparisonPeriodConfig(BaseModel):
    """An explicit baseline window used for user-requested growth comparisons."""

    model_config = ConfigDict(extra="forbid")

    start: date
    end: date
    granularity: Granularity

    @model_validator(mode="after")
    def validate_period(self) -> ComparisonPeriodConfig:
        """Reject invalid baseline ranges and misaligned monthly bounds."""
        if self.start > self.end:
            raise ValueError("comparison_period.start must not follow comparison_period.end")
        if self.granularity is Granularity.MONTHLY and not _is_full_calendar_month_window(self.start, self.end):
            raise ValueError("monthly comparison_period requires a first-of-month start and last-of-month end")
        return self


class CriterionConfig(BaseModel):
    """One user-owned numerical rule evaluated independently for each language."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    metric: CriterionMetric
    operator: CriterionOperator
    threshold: float = Field(allow_inf_nan=False)

class CriteriaConfig(BaseModel):
    """Analyses requested for the configured pageview series."""

    model_config = ConfigDict(extra="forbid")

    growth: bool = True
    normalized_interest: bool = True
    stability: bool = True
    anomalies: bool = True
    confidence_intervals: bool = True


class OutputConfig(BaseModel):
    """Artifacts to produce for an analysis.

    The public configuration key is ``json``. The Python attribute deliberately
    avoids shadowing Pydantic's legacy ``BaseModel.json`` method.
    """

    model_config = ConfigDict(extra="forbid")

    json_output: bool = Field(default=True, validation_alias="json", serialization_alias="json")
    charts: bool = True
    pdf: bool = True


class AnalysisConfig(BaseModel):
    """The stable, version-one input contract for an analysis request."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: QueryConfig
    languages: list[LanguageCode] = Field(min_length=1, max_length=20)
    period: PeriodConfig = Field(default_factory=PeriodConfig)
    criteria: CriteriaConfig = Field(default_factory=CriteriaConfig)
    thresholds: list[CriterionConfig] = Field(default_factory=list, max_length=20)
    comparison_period: ComparisonPeriodConfig | None = None
    output: OutputConfig = Field(default_factory=OutputConfig)

    @field_validator("languages")
    @classmethod
    def languages_must_be_unique(cls, languages: list[str]) -> list[str]:
        """Reject ambiguous repeated language editions after whitespace trimming."""
        if len(languages) != len(set(languages)):
            raise ValueError("languages must be unique; duplicate language codes are not allowed")
        return languages

    @model_validator(mode="after")
    def validate_analysis_contract(self) -> AnalysisConfig:
        """Validate cross-field constraints before data retrieval starts."""
        if len(self.languages) > 1 and self.query.source_language is None:
            raise ValueError(
                "query.source_language is required when analyzing multiple Wikipedia language editions"
            )
        unknown_override_languages = set(self.query.article_overrides) - set(self.languages)
        if unknown_override_languages:
            unknown_languages = ", ".join(sorted(unknown_override_languages))
            raise ValueError(f"article_overrides include language(s) not listed in languages: {unknown_languages}")
        if self.comparison_period is not None:
            if self.comparison_period.granularity is not self.period.resolved_granularity:
                raise ValueError("comparison_period granularity must match period granularity")
            recent_start, recent_end = resolve_period(self.period)
            recent_bucket_count = _bucket_count(recent_start, recent_end, self.period.resolved_granularity)
            baseline_bucket_count = _bucket_count(
                self.comparison_period.start,
                self.comparison_period.end,
                self.comparison_period.granularity,
            )
            if recent_bucket_count != baseline_bucket_count:
                raise ValueError("comparison_period must have the same number of buckets as period")
            if self.comparison_period.end >= recent_start:
                raise ValueError("comparison_period must end before the analysis period starts")
        threshold_names = [item.name.casefold() for item in self.thresholds]
        if len(threshold_names) != len(set(threshold_names)):
            raise ValueError("threshold names must be unique")
        growth_threshold_requested = any(item.metric is CriterionMetric.GROWTH_PCT for item in self.thresholds)
        if growth_threshold_requested and self.comparison_period is None:
            raise ValueError("comparison_period is required for growth_pct thresholds")
        if growth_threshold_requested and not self.criteria.growth:
            raise ValueError("criteria.growth must be enabled when a growth_pct threshold is configured")
        if any(item.metric is CriterionMetric.NORMALIZED_INTEREST_MEAN for item in self.thresholds) and not (
            self.criteria.normalized_interest
        ):
            raise ValueError("criteria.normalized_interest must be enabled for normalized-interest thresholds")
        return self


def complete_month_range(months: int, reference_date: date | None = None) -> tuple[date, date]:
    """Return first-day bounds for the latest ``months`` complete calendar months.

    For example, with a reference date in September 2026 and ``months=24``,
    the range is 2024-09-01 through 2026-08-01.  The current month is never
    included, regardless of the reference date's day.
    """
    validated_months = PeriodConfig(months=months).months
    if validated_months is None:
        raise ValueError("'months' is required")
    reference = reference_date or date.today()
    end_year, end_month = reference.year, reference.month - 1
    if end_month == 0:
        end_year, end_month = end_year - 1, 12

    end = date(end_year, end_month, 1)
    start_index = end.year * 12 + (end.month - 1) - (validated_months - 1)
    start = date(start_index // 12, start_index % 12 + 1, 1)
    return start, end


def resolve_period(period: PeriodConfig, reference_date: date | None = None) -> tuple[date, date]:
    """Return inclusive calendar dates for an explicit or relative month window."""
    if period.start is not None and period.end is not None:
        return period.start, period.end
    if period.months is None:
        raise ValueError("period.months is required when explicit dates are not provided")
    first_month, last_month = complete_month_range(period.months, reference_date)
    if period.resolved_granularity is Granularity.MONTHLY:
        last_month = last_month.replace(day=monthrange(last_month.year, last_month.month)[1])
    return first_month, last_month


def latest_complete_day(reference_date: date | None = None) -> date:
    """Return the latest daily bucket expected to be complete."""
    return (reference_date or date.today()) - timedelta(days=1)


def _is_full_calendar_month_window(start: date, end: date) -> bool:
    """Return whether inclusive dates describe a sequence of whole months."""
    return start.day == 1 and end.day == monthrange(end.year, end.month)[1]


def _bucket_count(start: date, end: date, granularity: Granularity) -> int:
    """Count inclusive daily or calendar-month buckets for a validated period."""
    if granularity is Granularity.DAILY:
        return (end - start).days + 1
    return ((end.year - start.year) * 12) + end.month - start.month + 1


def load_config(path: str | Path) -> AnalysisConfig:
    """Read and validate one JSON analysis configuration file."""
    return AnalysisConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))
