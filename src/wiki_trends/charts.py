"""Deterministic, headless PNG charts for monthly pageview series."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import ceil
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)

from matplotlib import pyplot as plt
from matplotlib.dates import DateFormatter, DayLocator, MonthLocator

from wiki_trends.models import Granularity, MonthlyPageview, ObservationStatus

__all__ = ["render_comparison_charts", "render_multi_language_trend_chart", "render_trend_chart"]

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_SOURCE_LABEL = "Wikimedia Pageviews API"
_MAX_MULTI_SERIES_LINES = 6


def render_trend_chart(
    series: Sequence[MonthlyPageview],
    title: str,
    output_path: Path,
) -> Path:
    """Render one monthly pageview trend chart as a validated PNG file.

    Unknown observations are passed to Matplotlib as ``None`` so the rendered
    line contains an explicit gap rather than suggesting that their pageviews
    were zero. The caller-provided sequence is never mutated.

    Args:
        series: Monthly observations for a single language edition.
        title: Human-readable chart title.
        output_path: Destination PNG path for the current analysis run.

    Returns:
        The written ``output_path`` after validating its PNG signature.

    Raises:
        ValueError: If no observations are supplied or the output is not a
            PNG path.
        RuntimeError: If Matplotlib does not produce a non-empty PNG file.
    """
    if not series:
        raise ValueError("'series' must contain at least one monthly observation")
    if output_path.suffix.lower() != ".png":
        raise ValueError(f"'output_path' must end with '.png', got {output_path}")

    ordered_series = sorted(series, key=lambda observation: observation.month)
    months = [observation.month for observation in ordered_series]
    pageviews = [
        observation.views if observation.status is not ObservationStatus.UNKNOWN else None
        for observation in ordered_series
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 5))
    try:
        axis.plot(
            months,  # type: ignore[arg-type]  # Matplotlib's stubs omit datetime support.
            pageviews,  # type: ignore[arg-type]  # Matplotlib's stubs omit None-gap support.
            color="#3366CC",
            linewidth=2,
            marker="o",
            markersize=3,
        )
        axis.set_title(title)
        granularity = ordered_series[0].granularity
        axis.set_xlabel("Date" if granularity is Granularity.DAILY else "Month")
        axis.set_ylabel("Pageviews")
        axis.set_ylim(bottom=0)
        axis.grid(axis="y", alpha=0.3)

        locator = (
            DayLocator(interval=max(1, len(months) // 12))  # type: ignore[no-untyped-call]
            if granularity is Granularity.DAILY
            else MonthLocator(interval=_month_tick_interval(len(months)))  # type: ignore[no-untyped-call]
        )
        axis.xaxis.set_major_locator(locator)
        axis.xaxis.set_major_formatter(DateFormatter("%b\n%Y"))  # type: ignore[no-untyped-call]
        figure.tight_layout()

        figure.savefig(
            output_path,
            format="png",
            dpi=150,
            metadata={"Title": title, "Source": _SOURCE_LABEL},
        )
    finally:
        plt.close(figure)

    _validate_png(output_path)
    return output_path


def render_multi_language_trend_chart(
    series_by_language: Mapping[str, Sequence[MonthlyPageview]],
    title: str,
    output_path: Path,
) -> Path:
    """Render up to six language editions as a single, legend-labelled PNG.

    Unknown observations become ``None`` points so each language line retains
    visible gaps. The title is intentionally caller-provided so comparison
    orchestration can include the requested subject and effective period.

    Args:
        series_by_language: Two to six non-empty language-edition series.
        title: Subject and period-aware chart title.
        output_path: Destination PNG path for the comparison chart.

    Returns:
        The written ``output_path`` after PNG validation.

    Raises:
        ValueError: If the language count, series, title, or output path is
            invalid.
        RuntimeError: If Matplotlib does not produce a non-empty PNG file.
    """
    _validate_multi_series(series_by_language, title, output_path, maximum=_MAX_MULTI_SERIES_LINES)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 5))
    try:
        longest_series = 0
        for language, series in series_by_language.items():
            ordered_series = sorted(series, key=lambda observation: observation.month)
            longest_series = max(longest_series, len(ordered_series))
            axis.plot(
                [observation.month for observation in ordered_series],  # type: ignore[arg-type]
                [
                    observation.views if observation.status is not ObservationStatus.UNKNOWN else None
                    for observation in ordered_series
                ],  # type: ignore[arg-type]
                linewidth=2,
                marker="o",
                markersize=3,
                label=language,
            )
        axis.set_title(title)
        axis.set_xlabel("Month")
        axis.set_ylabel("Pageviews")
        axis.set_ylim(bottom=0)
        axis.grid(axis="y", alpha=0.3)
        axis.legend(title="Language")
        locator = MonthLocator(interval=_month_tick_interval(longest_series))  # type: ignore[no-untyped-call]
        axis.xaxis.set_major_locator(locator)
        axis.xaxis.set_major_formatter(DateFormatter("%b\n%Y"))  # type: ignore[no-untyped-call]
        figure.tight_layout()
        figure.savefig(
            output_path,
            format="png",
            dpi=150,
            metadata={"Title": title, "Source": _SOURCE_LABEL},
        )
    finally:
        plt.close(figure)

    _validate_png(output_path)
    return output_path


def render_comparison_charts(
    series_by_language: Mapping[str, Sequence[MonthlyPageview]],
    title: str,
    output_path: Path,
) -> list[Path]:
    """Render one shared chart or readable per-language fallbacks.

    Up to six language lines fit in one shared comparison chart. Larger M13
    comparisons intentionally produce one chart per language instead of an
    unreadable seven-plus-line legend.
    """
    _validate_multi_series(series_by_language, title, output_path, maximum=20)
    if len(series_by_language) <= _MAX_MULTI_SERIES_LINES:
        return [render_multi_language_trend_chart(series_by_language, title, output_path)]
    return [
        render_trend_chart(
            series,
            f"{title} ({language})",
            output_path.with_name(f"{output_path.stem}-{language}{output_path.suffix}"),
        )
        for language, series in series_by_language.items()
    ]


def _validate_png(output_path: Path) -> None:
    """Confirm that chart rendering created a non-empty PNG at the target."""
    try:
        with output_path.open("rb") as image_file:
            signature = image_file.read(len(_PNG_SIGNATURE))
    except OSError as error:
        raise RuntimeError(f"chart output could not be read: {output_path}") from error

    if output_path.stat().st_size == 0 or signature != _PNG_SIGNATURE:
        raise RuntimeError(f"chart output is not a valid non-empty PNG: {output_path}")


def _validate_multi_series(
    series_by_language: Mapping[str, Sequence[MonthlyPageview]],
    title: str,
    output_path: Path,
    *,
    maximum: int,
) -> None:
    """Validate the bounded multi-language chart API before creating files."""
    if not 2 <= len(series_by_language) <= maximum:
        raise ValueError(f"'series_by_language' must contain two to {maximum} language series")
    if not title.strip():
        raise ValueError("'title' must not be blank")
    if output_path.suffix.lower() != ".png":
        raise ValueError(f"'output_path' must end with '.png', got {output_path}")
    for language, series in series_by_language.items():
        if not language.strip():
            raise ValueError("'series_by_language' language keys must not be blank")
        if not series:
            raise ValueError(f"language series '{language}' must contain at least one monthly observation")


def _month_tick_interval(month_count: int) -> int:
    """Return a readable tick interval with no more than twelve month labels."""
    return max(1, ceil(month_count / 12))
