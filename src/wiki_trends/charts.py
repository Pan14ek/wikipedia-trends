"""Deterministic, headless PNG charts for monthly pageview series."""

from __future__ import annotations

from collections.abc import Sequence
from math import ceil
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)

from matplotlib import pyplot as plt
from matplotlib.dates import DateFormatter, MonthLocator

from wiki_trends.models import MonthlyPageview, ObservationStatus

__all__ = ["render_trend_chart"]

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_SOURCE_LABEL = "Wikimedia Pageviews API"


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
        axis.set_xlabel("Month")
        axis.set_ylabel("Pageviews")
        axis.set_ylim(bottom=0)
        axis.grid(axis="y", alpha=0.3)

        locator = MonthLocator(interval=_month_tick_interval(len(months)))  # type: ignore[no-untyped-call]
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


def _validate_png(output_path: Path) -> None:
    """Confirm that chart rendering created a non-empty PNG at the target."""
    try:
        with output_path.open("rb") as image_file:
            signature = image_file.read(len(_PNG_SIGNATURE))
    except OSError as error:
        raise RuntimeError(f"chart output could not be read: {output_path}") from error

    if output_path.stat().st_size == 0 or signature != _PNG_SIGNATURE:
        raise RuntimeError(f"chart output is not a valid non-empty PNG: {output_path}")


def _month_tick_interval(month_count: int) -> int:
    """Return a readable tick interval with no more than twelve month labels."""
    return max(1, ceil(month_count / 12))
