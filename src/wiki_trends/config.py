"""Validation and date semantics for analysis request configuration."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "AnalysisConfig",
    "CriteriaConfig",
    "Granularity",
    "OutputConfig",
    "PeriodConfig",
    "QueryConfig",
    "QueryMode",
    "complete_month_range",
    "load_config",
]


class QueryMode(StrEnum):
    """Supported ways of identifying the subject of an analysis."""

    ARTICLE = "article"
    TOPIC = "topic"


class Granularity(StrEnum):
    """Time bucket sizes supported by the MVP."""

    MONTHLY = "monthly"


LanguageCode = Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9-]*$")]


class QueryConfig(BaseModel):
    """The subject to analyze."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mode: QueryMode
    value: str = Field(min_length=1)
    source_language: LanguageCode | None = None


class PeriodConfig(BaseModel):
    """A window of complete calendar months."""

    model_config = ConfigDict(extra="forbid")

    months: int = Field(default=24, ge=12, le=120)
    granularity: Granularity = Granularity.MONTHLY


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
    output: OutputConfig = Field(default_factory=OutputConfig)

    @field_validator("languages")
    @classmethod
    def languages_must_be_unique(cls, languages: list[str]) -> list[str]:
        """Reject ambiguous repeated language editions after whitespace trimming."""
        if len(languages) != len(set(languages)):
            raise ValueError("languages must be unique; duplicate language codes are not allowed")
        return languages

    @model_validator(mode="after")
    def config_has_supported_granularity(self) -> AnalysisConfig:
        """Keep this explicit as a guard when future granularities are introduced."""
        if self.period.granularity is not Granularity.MONTHLY:
            raise ValueError("only monthly granularity is supported")
        return self


def complete_month_range(months: int, reference_date: date | None = None) -> tuple[date, date]:
    """Return first-day bounds for the latest ``months`` complete calendar months.

    For example, with a reference date in September 2026 and ``months=24``,
    the range is 2024-09-01 through 2026-08-01.  The current month is never
    included, regardless of the reference date's day.
    """
    validated_months = PeriodConfig(months=months).months
    reference = reference_date or date.today()
    end_year, end_month = reference.year, reference.month - 1
    if end_month == 0:
        end_year, end_month = end_year - 1, 12

    end = date(end_year, end_month, 1)
    start_index = end.year * 12 + (end.month - 1) - (validated_months - 1)
    start = date(start_index // 12, start_index % 12 + 1, 1)
    return start, end


def load_config(path: str | Path) -> AnalysisConfig:
    """Read and validate one JSON analysis configuration file."""
    return AnalysisConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))
