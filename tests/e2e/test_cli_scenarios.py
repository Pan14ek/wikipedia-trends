"""Deterministic CLI scenarios for M17's three product configurations."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pypdf import PdfReader

from wiki_trends import cli, pipeline
from wiki_trends.config import AnalysisConfig
from wiki_trends.models import (
    ArticleResolution,
    MonthlyPageview,
    ResolutionMethod,
    ResolutionStatus,
    ResolvedArticle,
    TopicResolution,
    TopicSelectionMethod,
)
from wiki_trends.wikipedia_client import PageviewsFetchResult


@pytest.mark.parametrize(
    ("name", "query", "languages"),
    [
        ("astronomy", {"mode": "article", "value": "Astronomy", "source_language": "uk"}, ["uk"]),
        ("fasting", {"mode": "article", "value": "Intermittent fasting", "source_language": "pl"}, ["pl", "cs"]),
        ("learning-english", {"mode": "topic", "value": "Learning English"}, ["pl", "cs", "uk"]),
    ],
)
def test_cli_invokes_the_shared_analysis_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    query: dict[str, str],
    languages: list[str],
) -> None:
    """Ensure every canonical config reaches the one shared CLI execution seam."""
    config_path = tmp_path / f"{name}.json"
    config_path.write_text(json.dumps({"query": query, "languages": languages}), encoding="utf-8")
    expected_paths = (tmp_path / "analysis.json", tmp_path / "trend.png", tmp_path / "report.pdf")
    received_languages: list[list[str]] = []

    def run_stub(config: object, output_root: Path) -> tuple[Path, Path, Path]:
        received_languages.append(config.languages)  # type: ignore[attr-defined]
        assert output_root == tmp_path / "output"
        return expected_paths

    monkeypatch.setattr(cli, "run_analysis", run_stub)

    assert cli.main(["--config", str(config_path), "--output-dir", str(tmp_path / "output")]) == 0
    assert received_languages == [languages]


class _Resolver:
    def __init__(self, result: ArticleResolution | list[TopicResolution]) -> None:
        self._result = result

    def __enter__(self) -> _Resolver:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def resolve(self, _: object, __: list[str]) -> ArticleResolution | list[TopicResolution]:
        return self._result


class _Pageviews:
    def __enter__(self) -> _Pageviews:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get_article_pageviews_result(self, _: str, __: str, start: str, end: str) -> PageviewsFetchResult:
        return PageviewsFetchResult(_series(start, end), "network")


def _series(start: str, end: str) -> list[MonthlyPageview]:
    start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    months: list[MonthlyPageview] = []
    year, month = start_date.year, start_date.month
    while (year, month) <= (end_date.year, end_date.month):
        months.append(MonthlyPageview(month=date(year, month, 1), views=100 + len(months) * 10))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _article(language: str, title: str) -> ResolvedArticle:
    return ResolvedArticle(
        language=language,
        project=f"{language}.wikipedia",
        requested_title=title,
        canonical_title=title,
        page_id=1,
        url=f"https://{language}.wikipedia.org/wiki/{title}",
        resolution_method=ResolutionMethod.INPUT_ARTICLE,
    )


@pytest.mark.parametrize(
    ("query", "languages", "topic_mode"),
    [
        ({"mode": "article", "value": "Astronomy", "source_language": "uk"}, ["uk"], False),
        ({"mode": "article", "value": "Intermittent fasting", "source_language": "pl"}, ["pl", "cs"], False),
        ({"mode": "topic", "value": "Learning English"}, ["pl", "cs", "uk"], True),
    ],
)
def test_mocked_pipeline_writes_json_png_and_one_page_pdf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    query: dict[str, str],
    languages: list[str],
    topic_mode: bool,
) -> None:
    """Exercise the full deterministic artifact path for every canonical scenario."""
    config = AnalysisConfig.model_validate({"query": query, "languages": languages, "output": {"json": True}})
    if topic_mode:
        result: ArticleResolution | list[TopicResolution] = [
            TopicResolution(
                requested_topic=query["value"],
                language=language,
                status=ResolutionStatus.RESOLVED,
                selected_articles=[_article(language, f"{query['value']} {language}")],
                candidate_count=1,
                selection_method=TopicSelectionMethod.EXPLICIT_ARTICLE_OVERRIDE,
            )
            for language in languages
        ]
    else:
        result = ArticleResolution(
            requested_title=query["value"],
            source_language=query.get("source_language", languages[0]),
            status=ResolutionStatus.RESOLVED,
            articles=[_article(language, query["value"]) for language in languages],
        )
    monkeypatch.setattr(pipeline, "ArticleResolver", lambda: _Resolver(result))
    monkeypatch.setattr(pipeline, "WikimediaPageviewsClient", _Pageviews)

    json_path, png_path, pdf_path = pipeline.run_analysis(config, tmp_path / "output")
    report = json.loads(json_path.read_text(encoding="utf-8"))

    assert report["schema_version"] == "1.0.0"
    assert set(report["languages"]) == set(languages)
    assert png_path.read_bytes().startswith(b"\x89PNG")
    assert len(PdfReader(pdf_path).pages) == 1
    assert all(section["absolute_metrics"] is not None for section in report["languages"].values())
    assert all(source["retrieval"] == "network" for source in report["sources"])
