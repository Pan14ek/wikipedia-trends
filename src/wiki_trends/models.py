"""Foundational domain models for Wikipedia Trends analyses."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from math import isclose

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "AbsoluteMetrics",
    "AbsoluteMetricsStatus",
    "ArticleResolution",
    "MissingLanguageEquivalent",
    "MonthlyPageview",
    "ObservationStatus",
    "ResolutionClarification",
    "ResolutionMethod",
    "ResolutionStatus",
    "ResolvedArticle",
]


class ObservationStatus(StrEnum):
    """How confidently a monthly pageview value is known."""

    OBSERVED = "observed"
    ZERO_INFERRED = "zero_inferred"
    UNKNOWN = "unknown"


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
