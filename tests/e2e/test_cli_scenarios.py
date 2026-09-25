"""Deterministic CLI scenarios for M17's three product configurations."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from pypdf import PdfReader

from wiki_trends import cli, pipeline
from wiki_trends.article_resolver import ArticleResolver
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
from wiki_trends.pipeline import AnalysisRunResult
from wiki_trends.report import AnalysisReport
from wiki_trends.wikipedia_client import PageviewsFetchResult


@pytest.mark.parametrize(
    ("name", "query", "languages"),
    [
        ("astronomy", {"mode": "article", "value": "Astronomy", "source_language": "en"}, ["uk"]),
        ("fasting", {"mode": "article", "value": "Intermittent fasting", "source_language": "en"}, ["pl", "cs"]),
        ("learning-english", {"mode": "topic", "value": "learning English", "source_language": "en"}, ["pl", "cs", "uk"]),
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

    def run_stub(config: object, output_root: Path) -> AnalysisRunResult:
        received_languages.append(config.languages)  # type: ignore[attr-defined]
        assert output_root == tmp_path / "output"
        return AnalysisRunResult(expected_paths[0], [expected_paths[1]], expected_paths[2])

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


class _CountingTopicPageviews(_Pageviews):
    def __init__(self) -> None:
        self.article_requests: list[str] = []
        self.project_requests: list[str] = []

    def get_article_pageviews_result(
        self,
        project: str,
        article: str,
        start: date,
        end: date,
        *,
        granularity: Granularity = Granularity.MONTHLY,
    ) -> PageviewsFetchResult:
        self.article_requests.append(article)
        views_by_article = {
            "English language": 100,
            "English as a second or foreign language": 200,
            "English literature": 300,
        }
        return PageviewsFetchResult(_series(start, end, granularity, views=views_by_article[article]), "network")

    def get_project_pageviews_result(
        self,
        project: str,
        start: date,
        end: date,
        *,
        granularity: Granularity = Granularity.MONTHLY,
    ) -> PageviewsFetchResult:
        self.project_requests.append(project)
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
        ({"mode": "article", "value": "Astronomy", "source_language": "en"}, ["uk"], False),
        ({"mode": "article", "value": "Intermittent fasting", "source_language": "en"}, ["pl", "cs"], False),
        ({"mode": "topic", "value": "learning English", "source_language": "en"}, ["pl", "cs", "uk"], True),
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

    run_result = pipeline.run_analysis(config, tmp_path / "output")
    json_path, png_path, pdf_path = run_result.analysis_json, run_result.charts[0], run_result.pdf
    report = json.loads(json_path.read_text(encoding="utf-8"))
    AnalysisReport.model_validate(report)

    assert report["schema_version"] == "2.1.0"
    assert set(report["languages"]) == set(languages)
    assert png_path.read_bytes().startswith(b"\x89PNG")
    assert len(PdfReader(pdf_path).pages) == 1
    assert report["artifacts"]["pdf"] == str(pdf_path)
    assert all(section["absolute_metrics"] is not None for section in report["languages"].values())
    assert all(source["retrieval"] == "network" for source in report["sources"])


def test_seven_language_pipeline_returns_every_generated_chart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pipeline returns actual per-language charts, never its unused base name."""
    languages = ["en", "uk", "pl", "cs", "de", "fr", "es"]
    config = AnalysisConfig.model_validate(
        {
            "query": {"mode": "article", "value": "Astronomy", "source_language": "en"},
            "languages": languages,
            "output": {"json": True, "charts": True, "pdf": False},
        }
    )
    resolution = ArticleResolution(
        requested_title="Astronomy",
        source_language="en",
        status=ResolutionStatus.RESOLVED,
        articles=[_article(language, "Astronomy") for language in languages],
    )
    monkeypatch.setattr(pipeline, "ArticleResolver", lambda: _Resolver(resolution))
    monkeypatch.setattr(pipeline, "WikimediaPageviewsClient", _Pageviews)
    generated_paths: list[Path] = []

    def render_seven_charts(
        series_by_language: dict[str, list[MonthlyPageview]], title: str, base_path: Path
    ) -> list[Path]:
        del title
        paths = [
            base_path.with_name(f"{base_path.stem}-{language}{base_path.suffix}") for language in series_by_language
        ]
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\x89PNG\r\n\x1a\n")
        generated_paths.extend(paths)
        return paths

    monkeypatch.setattr(pipeline, "render_comparison_charts", render_seven_charts)

    result = pipeline.run_analysis(config, tmp_path / "output")
    report = json.loads(result.analysis_json.read_text(encoding="utf-8"))

    assert result.analysis_json is not None
    assert result.pdf is None
    assert result.charts == generated_paths
    assert len(result.charts) == len(languages) == 7
    assert all(path.exists() for path in result.charts)
    assert not (tmp_path / "output" / f"{report['run']['slug']}-trend.png").exists()
    assert report["artifacts"]["charts"] == [str(path) for path in result.charts]


def test_pdf_only_pipeline_hides_its_internal_chart_and_json_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A chart rendered solely as PDF input is not a requested chart artifact."""
    config = AnalysisConfig.model_validate(
        {
            "query": {"mode": "article", "value": "Astronomy", "source_language": "en"},
            "languages": ["en"],
            "output": {"json": False, "charts": False, "pdf": True},
        }
    )
    resolution = ArticleResolution(
        requested_title="Astronomy",
        source_language="en",
        status=ResolutionStatus.RESOLVED,
        articles=[_article("en", "Astronomy")],
    )
    monkeypatch.setattr(pipeline, "ArticleResolver", lambda: _Resolver(resolution))
    monkeypatch.setattr(pipeline, "WikimediaPageviewsClient", _Pageviews)

    result = pipeline.run_analysis(config, tmp_path / "output")

    assert result.analysis_json is None
    assert result.charts == []
    assert result.pdf is not None and result.pdf.exists()
    assert len(PdfReader(result.pdf).pages) == 1


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

    run_result = pipeline.run_analysis(config, tmp_path / "output")
    json_path, chart_path, pdf_path = run_result.analysis_json, run_result.charts[0], run_result.pdf
    assert json_path is not None and chart_path is not None and pdf_path is not None
    report = json.loads(json_path.read_text(encoding="utf-8"))

    assert report["schema_version"] == "2.1.0"
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


def test_topic_pipeline_uses_real_resolver_and_one_project_denominator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise source search, semantic acceptance, aggregation, and report artifacts."""
    pages = {
        "English language": (1, "Q1860"),
        "English as a second or foreign language": (2, "Q130192"),
        "English literature": (3, "Q109587623"),
    }
    metadata = {
        "Q1860": ("English", ["English language"], "West Germanic language"),
        "Q130192": (
            "English as a second or foreign language",
            ["English language learning"],
            "use of English by speakers with different native languages",
        ),
        "Q109587623": (
            "English literature",
            ["study of English literature"],
            "discipline that studies English-language literature",
        ),
    }

    def wiki_handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "en.wikipedia.org" and request.url.params.get("list") == "search":
            return httpx.Response(200, json={"query": {"search": [{"title": title} for title in pages]}})
        if request.url.host == "en.wikipedia.org":
            title = request.url.params["titles"]
            page_id, qid = pages[title]
            return httpx.Response(
                200,
                json={
                    "query": {
                        "pages": [
                            {
                                "title": title,
                                "pageid": page_id,
                                "fullurl": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                                "pageprops": {"wikibase_item": qid},
                                "langlinks": [],
                            }
                        ]
                    }
                },
            )
        if request.url.host == "www.wikidata.org":
            qid = request.url.params["ids"]
            return httpx.Response(
                200,
                json={
                    "entities": {
                        qid: {
                            "labels": {"en": {"language": "en", "value": metadata[qid][0]}},
                            "aliases": {"en": [{"language": "en", "value": alias} for alias in metadata[qid][1]]},
                            "descriptions": {"en": {"language": "en", "value": metadata[qid][2]}},
                        }
                    }
                },
            )
        pytest.fail(f"unexpected resolver request: {request.url}")

    pageviews = _CountingTopicPageviews()
    monkeypatch.setattr(
        pipeline,
        "ArticleResolver",
        lambda: ArticleResolver(http_client=httpx.Client(transport=httpx.MockTransport(wiki_handler))),
    )
    monkeypatch.setattr(pipeline, "WikimediaPageviewsClient", lambda: pageviews)
    config = AnalysisConfig.model_validate(
        {
            "query": {"mode": "topic", "value": "English", "source_language": "en"},
            "languages": ["en"],
            "period": {"start": "2026-07-01", "end": "2026-07-31", "granularity": "monthly"},
            "criteria": {"normalized_interest": True},
            "output": {"json": True, "charts": True, "pdf": True},
        }
    )

    run_result = pipeline.run_analysis(config, tmp_path / "output")
    json_path, chart_path, pdf_path = run_result.analysis_json, run_result.charts[0], run_result.pdf

    assert json_path is not None and chart_path is not None and pdf_path is not None
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "2.1.0"
    assert pageviews.article_requests == list(pages)
    assert pageviews.project_requests == ["en.wikipedia"]
    assert (
        len([source for source in report["sources"] if source["endpoint_family"] == "wikimedia-pageviews-aggregate"])
        == 1
    )
    assert (
        len([source for source in report["sources"] if source["endpoint_family"] == "wikimedia-pageviews-per-article"])
        == 3
    )
    assert report["languages"]["en"]["pageviews"][0]["views"] == 600
    assert report["languages"]["en"]["normalized_interest"]["series"][0]["value"] == pytest.approx(600)
    assert chart_path.read_bytes().startswith(b"\x89PNG")
    assert len(PdfReader(pdf_path).pages) == 1


def test_ambiguous_topic_stops_before_pageview_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A disambiguation result produces clarification without downstream fetches."""
    pageviews = _CountingTopicPageviews()

    def wiki_handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json={"query": {"search": [{"title": "Mercury"}]}})
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "title": "Mercury",
                            "pageid": 1,
                            "fullurl": "https://en.wikipedia.org/wiki/Mercury",
                            "pageprops": {"disambiguation": ""},
                            "langlinks": [],
                        }
                    ]
                }
            },
        )

    monkeypatch.setattr(
        pipeline,
        "ArticleResolver",
        lambda: ArticleResolver(http_client=httpx.Client(transport=httpx.MockTransport(wiki_handler))),
    )
    monkeypatch.setattr(pipeline, "WikimediaPageviewsClient", lambda: pageviews)
    config = AnalysisConfig.model_validate(
        {
            "query": {"mode": "topic", "value": "Mercury", "source_language": "en"},
            "languages": ["en"],
            "period": {"start": "2026-07-01", "end": "2026-07-31", "granularity": "monthly"},
            "output": {"json": True, "charts": False, "pdf": False},
        }
    )

    run_result = pipeline.run_analysis(config, tmp_path / "output")
    json_path = run_result.analysis_json

    assert json_path is not None
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["resolution"]["topics"][0]["clarification"]["reason"] == "disambiguation_page"
    assert pageviews.article_requests == []
    assert pageviews.project_requests == []
    assert report["sources"] == []
