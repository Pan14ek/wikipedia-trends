"""Versioned, machine-readable JSON reports for completed analyses.

This module is deliberately an output boundary: it serializes already
calculated and validated analysis results without fetching data or changing
any metric. Keeping report construction separate from collection makes the
artifact reproducible and straightforward to audit.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from wiki_trends.config import AnalysisConfig
from wiki_trends.models import (
    AbsoluteMetrics,
    AnomalyDetection,
    ArticleResolution,
    ConfidenceInterval,
    MonthlyPageview,
    MultiLanguageComparison,
    NormalizedInterest,
    QualityCheck,
    TopicResolution,
    YoYMetrics,
)

__all__ = [
    "ANALYSIS_REPORT_SCHEMA_VERSION",
    "AnalysisReport",
    "DataSourceMetadata",
    "LanguageReport",
    "ReportArtifacts",
    "ReportPeriod",
    "ReportResolution",
    "ReportRun",
    "create_run_slug",
    "write_analysis_report",
]

ANALYSIS_REPORT_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
_RUN_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ReportRun(BaseModel):
    """Identity and generation metadata for one analysis execution."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    slug: str = Field(min_length=1, max_length=120)
    generated_at: datetime
    methodology_version: str = Field(min_length=1)

    @field_validator("slug")
    @classmethod
    def slug_must_be_safe(cls, slug: str) -> str:
        """Reject paths or opaque names before they become output directories."""
        if not _RUN_SLUG_PATTERN.fullmatch(slug):
            raise ValueError("run slug must contain lowercase letters, digits, and single hyphens only")
        return slug


class ReportPeriod(BaseModel):
    """The requested complete-month window represented by this report."""

    model_config = ConfigDict(extra="forbid")

    start: date
    end: date

    @field_validator("start", "end")
    @classmethod
    def month_must_start_on_first_day(cls, value: date) -> date:
        """Use the same canonical month identifiers as the pageview series."""
        if value.day != 1:
            raise ValueError("report period dates must be the first day of a month")
        return value

    @model_validator(mode="after")
    def start_must_not_follow_end(self) -> ReportPeriod:
        """Keep requested windows chronologically valid."""
        if self.start > self.end:
            raise ValueError("report period start must not follow end")
        return self


class DataSourceMetadata(BaseModel):
    """Provenance for one external dataset used by the analysis."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    endpoint_family: str = Field(min_length=1)
    project: str = Field(min_length=1)
    article_title: str | None = Field(default=None, min_length=1)
    requested_period: ReportPeriod
    fetched_at: datetime
    access: str = Field(min_length=1)
    agent: str = Field(min_length=1)
    granularity: Literal["monthly"] = "monthly"
    retrieval: Literal["network", "cache"] = "network"


class ReportResolution(BaseModel):
    """Resolved article or language-local topic selections used by the run."""

    model_config = ConfigDict(extra="forbid")

    article: ArticleResolution | None = None
    topics: list[TopicResolution] = Field(default_factory=list)

    @model_validator(mode="after")
    def must_contain_one_resolution_representation(self) -> ReportResolution:
        """Avoid artifacts that omit how their requested subject was resolved."""
        if (self.article is None) == (not self.topics):
            raise ValueError("report resolution requires exactly one article or topic representation")
        return self


class LanguageReport(BaseModel):
    """All calculated results and limitations for one requested language edition."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    pageviews: list[MonthlyPageview] = Field(default_factory=list)
    absolute_metrics: AbsoluteMetrics | None = None
    yoy_metrics: YoYMetrics | None = None
    normalized_interest: NormalizedInterest | None = None
    anomalies: AnomalyDetection | None = None
    confidence_interval: ConfidenceInterval | None = None
    quality: list[QualityCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("pageviews")
    @classmethod
    def pageview_months_must_be_unique(cls, pageviews: list[MonthlyPageview]) -> list[MonthlyPageview]:
        """Prevent ambiguous monthly evidence in an exported language series."""
        months = [pageview.month for pageview in pageviews]
        if len(months) != len(set(months)):
            raise ValueError("language report pageviews must not contain duplicate months")
        return pageviews


class ReportArtifacts(BaseModel):
    """Paths to generated deliverables, relative or absolute as chosen by the caller."""

    model_config = ConfigDict(extra="forbid")

    analysis_json: str | None = None
    charts: list[str] = Field(default_factory=list)
    pdf: str | None = None


class AnalysisReport(BaseModel):
    """Stable version-one JSON contract for a completed Wikipedia Trends run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = ANALYSIS_REPORT_SCHEMA_VERSION
    run: ReportRun
    input: AnalysisConfig
    resolution: ReportResolution
    sources: list[DataSourceMetadata]
    period: ReportPeriod
    languages: dict[str, LanguageReport]
    comparison: MultiLanguageComparison | None = None
    quality: list[QualityCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifacts: ReportArtifacts = Field(default_factory=ReportArtifacts)

    @model_validator(mode="after")
    def language_keys_must_match_input(self) -> AnalysisReport:
        """Ensure every requested language has a clear report section."""
        if set(self.languages) != set(self.input.languages):
            raise ValueError("report languages must contain exactly the configured languages")
        return self


def create_run_slug(period: ReportPeriod, config: AnalysisConfig) -> str:
    """Create a readable deterministic default slug from date, query, and languages."""
    subject = re.sub(r"[^a-z0-9]+", "-", config.query.value.casefold()).strip("-") or "analysis"
    languages = "-".join(config.languages)
    return f"{period.start:%Y%m}-{period.end:%Y%m}-{subject}-{languages}"[:120].rstrip("-")


def write_analysis_report(report: AnalysisReport, output_root: Path = Path("output")) -> Path:
    """Write one UTF-8, pretty-printed report without overwriting a prior run.

    A suffix is appended to a colliding run directory. Timestamps may differ
    across runs, while the semantic payload stays deterministic for fixed
    normalized inputs and calculation seeds.
    """
    destination = _create_destination(output_root, report.run.slug)
    output_path = destination / "analysis.json"
    report_for_output = report.model_copy(
        update={"artifacts": report.artifacts.model_copy(update={"analysis_json": str(output_path)})}
    )
    payload = report_for_output.model_dump(mode="json", by_alias=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _create_destination(output_root: Path, slug: str) -> Path:
    """Atomically reserve a new safe output directory for a report artifact."""
    output_root.mkdir(parents=True, exist_ok=True)
    for suffix in range(0, 10_000):
        candidate = output_root / (slug if suffix == 0 else f"{slug}-{suffix}")
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise RuntimeError("could not reserve a unique report output directory")
