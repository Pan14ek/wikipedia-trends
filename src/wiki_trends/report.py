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
from reportlab import __file__ as reportlab_package_path
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from wiki_trends.config import AnalysisConfig, CriterionConfig
from wiki_trends.models import (
    AbsoluteMetrics,
    AnomalyDetection,
    ArticleResolution,
    ConfidenceInterval,
    CriterionEvaluation,
    DescriptiveTrend,
    Granularity,
    MonthlyPageview,
    MultiLanguageComparison,
    NormalizedInterest,
    PeriodGrowthMetrics,
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
    "write_pdf_report",
    "write_analysis_report",
]

ANALYSIS_REPORT_SCHEMA_VERSION: Final[Literal["2.2.0"]] = "2.2.0"
_RUN_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PAGE_WIDTH, _PAGE_HEIGHT = A4
_PAGE_MARGIN = 36
_PDF_FONT_NAME = "WikipediaTrendsVera"
_PDF_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    Path("/System/Library/Fonts/Supplemental/Verdana.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path(reportlab_package_path).parent / "fonts" / "Vera.ttf",
)


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
    """An inclusive requested or available daily/monthly date window."""

    model_config = ConfigDict(extra="forbid")

    start: date
    end: date
    granularity: Granularity = Granularity.MONTHLY

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
    granularity: Granularity = Granularity.MONTHLY
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
    period_growth: PeriodGrowthMetrics | None = None
    descriptive_trend: DescriptiveTrend | None = None
    normalized_interest: NormalizedInterest | None = None
    anomalies: AnomalyDetection | None = None
    confidence_interval: ConfidenceInterval | None = None
    quality: list[QualityCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    criterion_evaluations: list[CriterionEvaluation] = Field(default_factory=list)

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
    """Stable version-two JSON contract for a completed Wikipedia Trends run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["2.2.0"] = ANALYSIS_REPORT_SCHEMA_VERSION
    run: ReportRun
    input: AnalysisConfig
    resolution: ReportResolution
    sources: list[DataSourceMetadata]
    period: ReportPeriod
    requested_period: ReportPeriod
    comparison_period: ReportPeriod | None = None
    languages: dict[str, LanguageReport]
    comparison: MultiLanguageComparison | None = None
    criteria: list[CriterionConfig] = Field(default_factory=list)
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
    date_format = "%Y%m%d" if period.granularity is Granularity.DAILY else "%Y%m"
    return f"{period.start:{date_format}}-{period.end:{date_format}}-{subject}-{languages}"[:120].rstrip("-")


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


def write_pdf_report(
    report: AnalysisReport,
    chart_path: Path | None = None,
    output_root: Path = Path("output/pdf"),
) -> Path:
    """Render a one-page A4 PDF from an already validated analysis report.

    The function formats report values only; it does not calculate metrics or
    alter the structured analysis result. When ``chart_path`` is omitted, the
    first chart registered in the report artifact metadata is used.

    Args:
        report: Structured M14 analysis output to present.
        chart_path: Existing PNG trend chart, or ``None`` to use report metadata.
        output_root: Directory in which to create one collision-safe PDF.

    Returns:
        Path to the written, single-page PDF.

    Raises:
        ValueError: If no usable PNG chart path is available.
        RuntimeError: If the PDF cannot be written as exactly one page.
    """
    resolved_chart_path = _resolve_chart_path(report, chart_path)
    output_root.mkdir(parents=True, exist_ok=True)
    output_path = _next_pdf_path(output_root, report.run.slug)
    _register_pdf_font()

    canvas = Canvas(str(output_path), pagesize=A4, pageCompression=1)
    canvas.setTitle(f"Wikipedia Trends - {report.input.query.value}")
    _draw_pdf_page(canvas, report, resolved_chart_path)
    canvas.showPage()
    canvas.save()
    _validate_single_page_pdf(output_path)
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


def _resolve_chart_path(report: AnalysisReport, chart_path: Path | None) -> Path:
    """Select and validate the one main PNG chart required by the PDF layout."""
    candidate = chart_path or (Path(report.artifacts.charts[0]) if report.artifacts.charts else None)
    if candidate is None:
        raise ValueError("a main PNG chart is required; pass chart_path or populate report.artifacts.charts")
    if candidate.suffix.lower() != ".png":
        raise ValueError(f"main chart must be a PNG file, got {candidate}")
    try:
        with candidate.open("rb") as chart_file:
            signature = chart_file.read(len(_PNG_SIGNATURE))
    except OSError as error:
        raise ValueError(f"main chart could not be read: {candidate}") from error
    if signature != _PNG_SIGNATURE:
        raise ValueError(f"main chart is not a valid PNG: {candidate}")
    return candidate


def _next_pdf_path(output_root: Path, slug: str) -> Path:
    """Return a non-overwriting report filename within the requested output root."""
    for suffix in range(0, 10_000):
        name = f"{slug}.pdf" if suffix == 0 else f"{slug}-{suffix}.pdf"
        candidate = output_root / name
        if not candidate.exists():
            return candidate
    raise RuntimeError("could not reserve a unique PDF output path")


def _register_pdf_font() -> None:
    """Embed a platform Unicode font once, with ReportLab's font as fallback."""
    if _PDF_FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return
    font_path = next((path for path in _PDF_FONT_CANDIDATES if path.is_file()), None)
    if font_path is None:
        raise RuntimeError("no supported TrueType font is available for PDF generation")
    pdfmetrics.registerFont(TTFont(_PDF_FONT_NAME, str(font_path)))


def _draw_pdf_page(canvas: Canvas, report: AnalysisReport, chart_path: Path) -> None:
    """Lay out the fixed-height, one-page PDF using only report fields."""
    y = _PAGE_HEIGHT - _PAGE_MARGIN
    canvas.setFillColor(HexColor("#1F2937"))
    canvas.setFont(_PDF_FONT_NAME, 18)
    canvas.drawString(_PAGE_MARGIN, y, _truncate(f"Wikipedia Trends: {report.input.query.value}", 76))
    y -= 19
    canvas.setFont(_PDF_FONT_NAME, 9)
    languages = ", ".join(report.input.languages)
    canvas.drawString(_PAGE_MARGIN, y, _truncate(f"Interest in the {languages}-language Wikipedia edition(s)", 110))
    y -= 15
    canvas.drawString(_PAGE_MARGIN, y, f"Analysis period: {_period_label(report.period)}")
    y -= 10
    canvas.setStrokeColor(HexColor("#D1D5DB"))
    canvas.line(_PAGE_MARGIN, y, _PAGE_WIDTH - _PAGE_MARGIN, y)
    y -= 12

    _draw_section_title(canvas, "Executive summary", y)
    y -= 12
    for bullet in _summary_lines(report)[:3]:
        canvas.setFont(_PDF_FONT_NAME, 8.5)
        canvas.drawString(_PAGE_MARGIN + 5, y, _truncate(f"- {bullet}", 132))
        y -= 11
    y -= 2

    image = ImageReader(str(chart_path))
    image_width, image_height = image.getSize()
    chart_height = 260
    chart_width = min(_PAGE_WIDTH - 2 * _PAGE_MARGIN, chart_height * image_width / image_height)
    canvas.drawImage(
        image,
        _PAGE_MARGIN + ((_PAGE_WIDTH - 2 * _PAGE_MARGIN - chart_width) / 2),
        y - chart_height,
        width=chart_width,
        height=chart_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    y -= chart_height + 12

    _draw_section_title(canvas, "Key metrics", y)
    y -= 12
    _draw_metrics_table(canvas, report, y)
    y -= 52

    _draw_section_title(canvas, "Reliability and limitations", y)
    y -= 12
    for note in _reliability_lines(report)[:2]:
        canvas.setFont(_PDF_FONT_NAME, 7.5)
        canvas.drawString(_PAGE_MARGIN + 5, y, _truncate(f"- {note}", 145))
        y -= 9
    canvas.setFont(_PDF_FONT_NAME, 7.5)
    canvas.drawString(
        _PAGE_MARGIN + 5,
        y,
        _truncate(
            "- Pageviews indicate Wikipedia-edition interest, not demand, willingness to pay, or country-level interest.",
            145,
        ),
    )
    y -= 13
    canvas.setStrokeColor(HexColor("#D1D5DB"))
    canvas.line(_PAGE_MARGIN, y, _PAGE_WIDTH - _PAGE_MARGIN, y)
    y -= 10
    canvas.setFont(_PDF_FONT_NAME, 6.8)
    footer = (
        f"Wikimedia Pageviews API | Methodology {report.run.methodology_version} | "
        f"Generated {report.run.generated_at.date().isoformat()}"
    )
    canvas.drawString(_PAGE_MARGIN, y, footer)


def _draw_section_title(canvas: Canvas, title: str, y: float) -> None:
    """Draw a small consistently styled section heading."""
    canvas.setFillColor(HexColor("#1F2937"))
    canvas.setFont(_PDF_FONT_NAME, 10)
    canvas.drawString(_PAGE_MARGIN, y, title)


def _summary_lines(report: AnalysisReport) -> list[str]:
    """Format existing report metrics as concise summary text without recalculation."""
    lines: list[str] = []
    for language, language_report in report.languages.items():
        metrics = language_report.absolute_metrics
        if metrics is None or metrics.total_views is None:
            lines.append(f"{language}: pageview summary is unavailable.")
            continue
        lines.append(
            f"{language}: {metrics.total_views:,} total pageviews across "
            f"{metrics.observed_months}/{metrics.requested_months} available months."
        )
    if report.comparison is not None and not report.comparison.comparable:
        lines.append("Cross-language comparison is not valid for the available shared data.")
    return lines or ["No language metrics were available for this report."]


def _draw_metrics_table(canvas: Canvas, report: AnalysisReport, y: float) -> None:
    """Draw a bounded table from supplied language metrics and YoY outcomes."""
    columns = (_PAGE_MARGIN, 105, 255, 380)
    headers = ("Language", "Total views", "YoY growth", "Completeness")
    canvas.setFillColor(HexColor("#E5E7EB"))
    canvas.rect(_PAGE_MARGIN, y - 10, _PAGE_WIDTH - 2 * _PAGE_MARGIN, 12, fill=1, stroke=0)
    canvas.setFillColor(HexColor("#1F2937"))
    canvas.setFont(_PDF_FONT_NAME, 7.5)
    for x, header in zip(columns, headers, strict=True):
        canvas.drawString(x + 3, y - 6, header)

    row_y = y - 21
    for language, language_report in list(report.languages.items())[:3]:
        metrics = language_report.absolute_metrics
        total = f"{metrics.total_views:,}" if metrics and metrics.total_views is not None else "Unavailable"
        completeness = f"{metrics.completeness_ratio:.0%}" if metrics else "Unavailable"
        yoy = language_report.yoy_metrics
        growth = f"{yoy.growth_pct:.1f}%" if yoy and yoy.growth_pct is not None else "Unavailable"
        values = (language, total, growth, completeness)
        canvas.setFont(_PDF_FONT_NAME, 7.5)
        for x, value in zip(columns, values, strict=True):
            canvas.drawString(x + 3, row_y, value)
        row_y -= 10


def _reliability_lines(report: AnalysisReport) -> list[str]:
    """Collect only explicit existing warnings and non-passing quality findings."""
    lines = list(report.warnings)
    for language, language_report in report.languages.items():
        lines.extend(f"{language}: {warning}" for warning in language_report.warnings)
        lines.extend(
            f"{language}: {check.message}" for check in language_report.quality if check.status.value != "pass"
        )
    lines.extend(check.message for check in report.quality if check.status.value != "pass")
    if report.comparison is not None and not report.comparison.comparable:
        lines.append("Comparison validity: direct cross-language comparison is unavailable.")
    return lines or ["No report warnings were recorded."]


def _period_label(period: ReportPeriod) -> str:
    """Return an unambiguous date or month range for visible report text."""
    if period.granularity is Granularity.DAILY:
        return f"{period.start.isoformat()} - {period.end.isoformat()}"
    return f"{period.start:%b %Y} - {period.end:%b %Y}"


def _truncate(value: str, limit: int) -> str:
    """Keep one-page text bounded while leaving complete details in analysis.json."""
    return value if len(value) <= limit else f"{value[: limit - 3].rstrip()}..."


def _validate_single_page_pdf(output_path: Path) -> None:
    """Verify ReportLab wrote a non-empty single-page PDF without parsing report data."""
    try:
        content = output_path.read_bytes()
    except OSError as error:
        raise RuntimeError(f"PDF output could not be read: {output_path}") from error
    page_objects = re.findall(rb"/Type /Page(?!s)", content)
    if not content.startswith(b"%PDF-") or len(page_objects) != 1:
        raise RuntimeError(f"PDF output is not a valid single-page file: {output_path}")
