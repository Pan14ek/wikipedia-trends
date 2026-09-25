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
    MissingLanguageEquivalent,
    MonthlyPageview,
    ResolutionClarification,
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
        (
            "learning-english",
            {"mode": "topic", "value": "learning English", "source_language": "en"},
            ["pl", "cs", "uk"],
        ),
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
            "Astronomia": 100,
            "Astronomie": 200,
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
    languages = ["en", "uk", "pl", "cs", "de", "fr", "es", "it"]
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
        status=ResolutionStatus.PARTIAL,
        articles=[_article(language, "Astronomy") for language in languages if language != "it"],
        missing_languages=[
            MissingLanguageEquivalent(
                language="it",
                project="it.wikipedia",
                requested_title="Astronomy",
                reason="no linked equivalent",
            )
        ],
    )
    monkeypatch.setattr(pipeline, "ArticleResolver", lambda: _Resolver(resolution))
    monkeypatch.setattr(pipeline, "WikimediaPageviewsClient", _Pageviews)
    generated_paths: list[Path] = []

    def render_seven_charts(
        series_by_language: dict[str, list[MonthlyPageview]], title: str, base_path: Path
    ) -> list[Path]:
        del title
        assert set(series_by_language) == set(languages) - {"it"}
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
    assert len(result.charts) == 7
    assert all(path.exists() for path in result.charts)
    assert not (tmp_path / "output" / f"{report['run']['slug']}-trend.png").exists()
    assert report["artifacts"]["charts"] == [str(path) for path in result.charts]
    assert set(report["languages"]) == set(languages)
    assert report["languages"]["it"]["pageviews"] == []
    assert report["comparison"]["comparable"] is False
    assert any("it" in warning for warning in report["comparison"]["warnings"])


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


def test_partial_article_resolution_keeps_missing_language_and_renders_available_series(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unresolved requested edition stays in JSON while valid editions render."""
    languages = ["pl", "cs", "uk"]
    config = AnalysisConfig.model_validate(
        {
            "query": {"mode": "article", "value": "Astronomy", "source_language": "en"},
            "languages": languages,
        }
    )
    resolution = ArticleResolution(
        requested_title="Astronomy",
        source_language="en",
        status=ResolutionStatus.PARTIAL,
        articles=[_article("pl", "Astronomia"), _article("cs", "Astronomie")],
        missing_languages=[
            MissingLanguageEquivalent(
                language="uk",
                project="uk.wikipedia",
                requested_title="Astronomy",
                reason="no linked equivalent",
            )
        ],
    )
    monkeypatch.setattr(pipeline, "ArticleResolver", lambda: _Resolver(resolution))
    monkeypatch.setattr(pipeline, "WikimediaPageviewsClient", _Pageviews)
    actual_renderer = pipeline.render_comparison_charts
    received_languages: list[set[str]] = []

    def render_available(
        series_by_language: dict[str, list[MonthlyPageview]], title: str, base_path: Path
    ) -> list[Path]:
        received_languages.append(set(series_by_language))
        return actual_renderer(series_by_language, title, base_path)

    monkeypatch.setattr(pipeline, "render_comparison_charts", render_available)
    result = pipeline.run_analysis(config, tmp_path / "output")

    assert result.analysis_json is not None and result.analysis_json.exists()
    assert len(result.charts) == 1 and result.charts[0].exists()
    assert result.pdf is not None and result.pdf.exists()
    report = json.loads(result.analysis_json.read_text(encoding="utf-8"))
    assert set(report["languages"]) == set(languages)
    assert report["languages"]["uk"]["pageviews"] == []
    assert report["languages"]["uk"]["absolute_metrics"] is None
    assert any("no linked equivalent" in warning for warning in report["languages"]["uk"]["warnings"])
    assert report["comparison"]["comparable"] is False
    assert any("uk" in warning for warning in report["comparison"]["warnings"])
    assert received_languages == [{"pl", "cs"}]
    assert len(PdfReader(result.pdf).pages) == 1


def test_partial_topic_missing_sitelink_keeps_comparison_invalid_and_renders_available_series(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonical topic mappings without one sitelink remain structured and render safely."""
    languages = ["pl", "cs", "uk"]
    topic = "Astronomy"
    config = AnalysisConfig.model_validate(
        {
            "query": {"mode": "topic", "value": topic, "source_language": "en"},
            "languages": languages,
        }
    )
    resolution = [
        TopicResolution(
            requested_topic=topic,
            language="pl",
            source_language="en",
            status=ResolutionStatus.RESOLVED,
            selected_articles=[_article("pl", "Astronomia")],
            candidate_count=1,
            selection_method=TopicSelectionMethod.WIKIDATA_SITELINK,
            canonical_concept_ids=["Q333"],
        ),
        TopicResolution(
            requested_topic=topic,
            language="cs",
            source_language="en",
            status=ResolutionStatus.RESOLVED,
            selected_articles=[_article("cs", "Astronomie")],
            candidate_count=1,
            selection_method=TopicSelectionMethod.WIKIDATA_SITELINK,
            canonical_concept_ids=["Q333"],
        ),
        TopicResolution(
            requested_topic=topic,
            language="uk",
            source_language="en",
            status=ResolutionStatus.REQUIRES_CLARIFICATION,
            clarification=ResolutionClarification(language="uk", title=topic, reason="missing_canonical_sitelink"),
            candidate_count=0,
            selection_method=TopicSelectionMethod.WIKIDATA_SITELINK,
            canonical_concept_ids=["Q333"],
        ),
    ]
    pageviews = _CountingTopicPageviews()
    monkeypatch.setattr(pipeline, "ArticleResolver", lambda: _Resolver(resolution))
    monkeypatch.setattr(pipeline, "WikimediaPageviewsClient", lambda: pageviews)
    result = pipeline.run_analysis(config, tmp_path / "output")

    assert result.analysis_json is not None and result.analysis_json.exists()
    assert result.charts and all(path.exists() for path in result.charts)
    assert result.pdf is not None and result.pdf.exists()
    report = json.loads(result.analysis_json.read_text(encoding="utf-8"))
    assert set(report["languages"]) == set(languages)
    assert report["languages"]["uk"]["pageviews"] == []
    assert any("missing_canonical_sitelink" in warning for warning in report["languages"]["uk"]["warnings"])
    assert report["comparison"]["comparable"] is False
    assert set(pageviews.article_requests) == {"Astronomia", "Astronomie"}


def test_one_analyzable_language_in_multi_language_request_uses_trend_chart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One surviving edition produces a local chart without changing comparison validity."""
    config = AnalysisConfig.model_validate(
        {
            "query": {"mode": "article", "value": "Astronomy", "source_language": "en"},
            "languages": ["pl", "cs", "uk"],
        }
    )
    resolution = ArticleResolution(
        requested_title="Astronomy",
        source_language="en",
        status=ResolutionStatus.PARTIAL,
        articles=[_article("pl", "Astronomia")],
        missing_languages=[
            MissingLanguageEquivalent(
                language=language,
                project=f"{language}.wikipedia",
                requested_title="Astronomy",
                reason="no linked equivalent",
            )
            for language in ("cs", "uk")
        ],
    )
    monkeypatch.setattr(pipeline, "ArticleResolver", lambda: _Resolver(resolution))
    monkeypatch.setattr(pipeline, "WikimediaPageviewsClient", _Pageviews)
    actual_renderer = pipeline.render_trend_chart
    calls: list[int] = []

    def render_one(series: list[MonthlyPageview], title: str, output_path: Path) -> Path:
        calls.append(len(series))
        return actual_renderer(series, title, output_path)

    def comparison_renderer(*_: object, **__: object) -> list[Path]:
        pytest.fail("comparison renderer must not receive a one-language mapping")

    monkeypatch.setattr(pipeline, "render_trend_chart", render_one)
    monkeypatch.setattr(pipeline, "render_comparison_charts", comparison_renderer)
    result = pipeline.run_analysis(config, tmp_path / "output")

    assert calls == [len(_series(date(2024, 9, 1), date(2026, 8, 31)))]
    assert len(result.charts) == 1 and result.charts[0].exists()
    assert result.pdf is not None and result.pdf.exists()
    report = json.loads(result.analysis_json.read_text(encoding="utf-8"))
    assert set(report["languages"]) == {"pl", "cs", "uk"}
    assert report["comparison"]["comparable"] is False


@pytest.mark.parametrize(
    ("outputs", "has_json"),
    [
        ({"json": True, "charts": True, "pdf": True}, True),
        ({"json": True, "charts": False, "pdf": False}, True),
        ({"json": False, "charts": True, "pdf": True}, False),
    ],
)
def test_zero_analyzable_series_skips_renderers_and_preserves_clarification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outputs: dict[str, bool],
    has_json: bool,
) -> None:
    """Clarification-only runs complete without pageview or presentation calls."""
    config = AnalysisConfig.model_validate(
        {
            "query": {"mode": "topic", "value": "Mercury", "source_language": "en"},
            "languages": ["pl", "cs"],
            "output": outputs,
        }
    )
    resolution = [
        TopicResolution(
            requested_topic="Mercury",
            language=language,
            source_language="en",
            status=ResolutionStatus.REQUIRES_CLARIFICATION,
            clarification=ResolutionClarification(language=language, title="Mercury", reason="disambiguation_page"),
            candidate_count=0,
            selection_method=TopicSelectionMethod.MEDIAWIKI_SEMANTIC_EVIDENCE,
        )
        for language in config.languages
    ]

    class NoPageviews:
        def __enter__(self) -> NoPageviews:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get_article_pageviews_result(self, *_: object, **__: object) -> PageviewsFetchResult:
            pytest.fail("clarification results must not request pageviews")

    monkeypatch.setattr(pipeline, "ArticleResolver", lambda: _Resolver(resolution))
    monkeypatch.setattr(pipeline, "WikimediaPageviewsClient", NoPageviews)
    monkeypatch.setattr(pipeline, "render_comparison_charts", lambda *_: pytest.fail("chart render called"))
    monkeypatch.setattr(pipeline, "render_trend_chart", lambda *_: pytest.fail("trend render called"))
    monkeypatch.setattr(pipeline, "write_pdf_report", lambda *_: pytest.fail("PDF render called"))

    result = pipeline.run_analysis(config, tmp_path / "output")

    assert (result.analysis_json is not None) is has_json
    assert result.charts == []
    assert result.pdf is None
    if result.analysis_json is not None:
        report = json.loads(result.analysis_json.read_text(encoding="utf-8"))
        assert report["artifacts"]["charts"] == []
        assert report["artifacts"]["pdf"] is None
        assert report["resolution"]["topics"][0]["clarification"]["reason"] == "disambiguation_page"
        if outputs["charts"] or outputs["pdf"]:
            assert any("analyzable pageview series" in warning for warning in report["warnings"])


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
