"""Deterministic CLI scenarios for M17's three product configurations."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from pypdf import PdfReader

from wiki_trends import cli, pipeline
from wiki_trends.config import AnalysisConfig
from wiki_trends.models import (
    ArticleResolution,
    Granularity,
    MonthlyPageview,
    ResolutionMethod,
    ResolutionStatus,
    ResolvedArticle,
    TopicResolution,
    TopicSelectionMethod,
)
from wiki_trends.report import AnalysisReport
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

    def get_article_pageviews_result(
        self,
        _: str,
        __: str,
        start: date,
        end: date,
        *,
        granularity: Granularity = Granularity.MONTHLY,
    ) -> PageviewsFetchResult:
        return PageviewsFetchResult(_series(start, end, granularity), "network")

    def get_project_pageviews_result(
        self,
        _: str,
        start: date,
        end: date,
        *,
        granularity: Granularity = Granularity.MONTHLY,
    ) -> PageviewsFetchResult:
        return PageviewsFetchResult(_series(start, end, granularity, views=1_000_000), "network")


def _series(
    start_date: date,
    end_date: date,
    granularity: Granularity = Granularity.MONTHLY,
    *,
    views: int = 100,
) -> list[MonthlyPageview]:
    observations: list[MonthlyPageview] = []
    if granularity is Granularity.DAILY:
        current = start_date
        while current <= end_date:
            observations.append(MonthlyPageview(month=current, granularity=granularity, views=views))
            current += timedelta(days=1)
        return observations
    year, month = start_date.year, start_date.month
    while (year, month) <= (end_date.year, end_date.month):
        observations.append(
            MonthlyPageview(month=date(year, month, 1), granularity=granularity, views=views + len(observations) * 10)
        )
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return observations


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
    AnalysisReport.model_validate(report)

    assert report["schema_version"] == "2.0.0"
    assert set(report["languages"]) == set(languages)
    assert png_path.read_bytes().startswith(b"\x89PNG")
    assert len(PdfReader(pdf_path).pages) == 1
    assert report["artifacts"]["pdf"] == str(pdf_path)
    assert all(section["absolute_metrics"] is not None for section in report["languages"].values())
    assert all(source["retrieval"] == "network" for source in report["sources"])


def test_daily_pipeline_reports_exact_dates_baseline_thresholds_and_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise date-specific retrieval, growth criteria, and schema-v2 artifacts."""
    config = AnalysisConfig.model_validate(
        {
            "query": {"mode": "article", "value": "Astronomy", "source_language": "uk"},
            "languages": ["uk"],
            "period": {"start": "2026-08-01", "end": "2026-08-07"},
            "comparison_period": {
                "start": "2026-07-25",
                "end": "2026-07-31",
                "granularity": "daily",
            },
            "thresholds": [
                {"name": "nonnegative growth", "metric": "growth_pct", "operator": "gte", "threshold": 0},
                {
                    "name": "normalized floor",
                    "metric": "normalized_interest_mean",
                    "operator": "gte",
                    "threshold": 100,
                },
            ],
        }
    )
    result = ArticleResolution(
        requested_title="Astronomy",
        source_language="uk",
        status=ResolutionStatus.RESOLVED,
        articles=[_article("uk", "Астрономія")],
    )
    monkeypatch.setattr(pipeline, "ArticleResolver", lambda: _Resolver(result))
    monkeypatch.setattr(pipeline, "WikimediaPageviewsClient", _Pageviews)
    monkeypatch.setattr(pipeline, "latest_complete_day", lambda: date(2026, 8, 5))

    json_path, chart_path, pdf_path = pipeline.run_analysis(config, tmp_path / "output")
    assert json_path is not None and chart_path is not None and pdf_path is not None
    report = json.loads(json_path.read_text(encoding="utf-8"))

    assert report["schema_version"] == "2.0.0"
    assert report["requested_period"] == {
        "start": "2026-08-01",
        "end": "2026-08-07",
        "granularity": "daily",
    }
    AnalysisReport.model_validate(report)
    assert report["period"] == {
        "start": "2026-08-01",
        "end": "2026-08-05",
        "granularity": "daily",
    }
    assert len(report["languages"]["uk"]["pageviews"]) == 5
    assert report["languages"]["uk"]["criterion_evaluations"][0]["status"] == "not_evaluable"
    assert report["languages"]["uk"]["period_growth"]["status"] == "insufficient_data"
    assert report["languages"]["uk"]["criterion_evaluations"][1]["status"] == "met"
    assert report["artifacts"]["pdf"] == str(pdf_path)
    assert chart_path.exists() and len(PdfReader(pdf_path).pages) == 1
