"""Structural coverage for M07 PNG trend-chart generation."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import cast

import pytest
from matplotlib.axes import Axes
from PIL import Image

from wiki_trends.charts import render_comparison_charts, render_multi_language_trend_chart, render_trend_chart
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


def test_renders_a_legend_labelled_multi_language_png_with_unknown_gaps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_labels: list[str] = []
    captured_pageviews: list[list[int | None]] = []
    legend_calls = 0
    original_plot = Axes.plot
    original_legend = Axes.legend

    def capture_plot(axis: Axes, *args: object, **kwargs: object) -> object:
        captured_labels.append(cast(str, kwargs["label"]))
        captured_pageviews.append(cast(list[int | None], args[1]))
        return original_plot(axis, *args, **kwargs)

    def capture_legend(axis: Axes, *args: object, **kwargs: object) -> object:
        nonlocal legend_calls
        legend_calls += 1
        return original_legend(axis, *args, **kwargs)

    monkeypatch.setattr("matplotlib.axes.Axes.plot", capture_plot)
    monkeypatch.setattr("matplotlib.axes.Axes.legend", capture_legend)
    output_path = tmp_path / "comparison.png"
    rendered = render_multi_language_trend_chart(
        {
            "en": _complete_series(),
            "uk": [
                MonthlyPageview(month=date(2026, 1, 1), views=20),
                MonthlyPageview(month=date(2026, 2, 1), status=ObservationStatus.UNKNOWN),
                MonthlyPageview(month=date(2026, 3, 1), views=40),
            ],
        },
        "Astronomy (2026-01 to 2026-03)",
        output_path,
    )

    assert rendered == output_path
    assert output_path.read_bytes().startswith(_PNG_SIGNATURE)
    assert captured_labels == ["en", "uk"]
    assert captured_pageviews == [[10, 25, 15], [20, None, 40]]
    assert legend_calls == 1


def test_seven_language_comparison_uses_readable_per_language_chart_fallback(tmp_path: Path) -> None:
    outputs = render_comparison_charts(
        {f"l{index}": _complete_series() for index in range(7)},
        "Astronomy (2026-01 to 2026-03)",
        tmp_path / "comparison.png",
    )

    assert len(outputs) == 7
    assert all(path.read_bytes().startswith(_PNG_SIGNATURE) for path in outputs)
    assert not (tmp_path / "comparison.png").exists()


def _complete_series() -> list[MonthlyPageview]:
    """Build a small, complete series with varying pageview counts."""
    return [
        MonthlyPageview(month=date(2026, 1, 1), views=10),
        MonthlyPageview(month=date(2026, 2, 1), views=25),
        MonthlyPageview(month=date(2026, 3, 1), views=15),
    ]
