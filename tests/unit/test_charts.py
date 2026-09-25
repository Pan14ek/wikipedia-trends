"""Structural coverage for M07 PNG trend-chart generation."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import cast

import pytest
from matplotlib.axes import Axes
from PIL import Image

from wiki_trends.charts import render_trend_chart
from wiki_trends.models import MonthlyPageview, ObservationStatus

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_renders_a_non_empty_png_to_a_new_parent_directory(tmp_path: Path) -> None:
    output_path = tmp_path / "charts" / "astronomy.png"

    rendered_path = render_trend_chart(_complete_series(), "Astronomy pageviews", output_path)

    assert rendered_path == output_path
    assert output_path.read_bytes().startswith(_PNG_SIGNATURE)
    assert output_path.stat().st_size > len(_PNG_SIGNATURE)
    with Image.open(output_path) as image:
        assert image.info["Source"] == "Wikimedia Pageviews API"


def test_unknown_observation_is_passed_to_matplotlib_as_a_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_pageviews: list[int | None] = []
    original_plot = Axes.plot

    def capture_plot(axis: Axes, *args: object, **kwargs: object) -> object:
        captured_pageviews.extend(cast(list[int | None], args[1]))
        return original_plot(axis, *args, **kwargs)

    monkeypatch.setattr("matplotlib.axes.Axes.plot", capture_plot)
    series = [
        MonthlyPageview(month=date(2026, 1, 1), views=10),
        MonthlyPageview(month=date(2026, 2, 1), status=ObservationStatus.UNKNOWN),
        MonthlyPageview(month=date(2026, 3, 1), views=30),
    ]

    render_trend_chart(series, "Missing month", tmp_path / "gap.png")

    assert captured_pageviews == [10, None, 30]


def test_renders_a_non_ascii_title(tmp_path: Path) -> None:
    output_path = tmp_path / "ukrainian-title.png"

    render_trend_chart(_complete_series(), "Перегляди сторінки Астрономія", output_path)

    assert output_path.read_bytes().startswith(_PNG_SIGNATURE)


def test_rejects_an_empty_series(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one"):
        render_trend_chart([], "No data", tmp_path / "empty.png")


def test_rejects_a_non_png_output_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must end with"):
        render_trend_chart(_complete_series(), "Wrong extension", tmp_path / "trend.svg")


def _complete_series() -> list[MonthlyPageview]:
    """Build a small, complete series with varying pageview counts."""
    return [
        MonthlyPageview(month=date(2026, 1, 1), views=10),
        MonthlyPageview(month=date(2026, 2, 1), views=25),
        MonthlyPageview(month=date(2026, 3, 1), views=15),
    ]
