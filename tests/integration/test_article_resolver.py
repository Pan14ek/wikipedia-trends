"""Mocked integration coverage for M04's MediaWiki article resolver."""

from __future__ import annotations

import httpx
import pytest

from wiki_trends.article_resolver import ArticleNotFoundError, ArticleResolver
from wiki_trends.config import QueryConfig
from wiki_trends.models import ResolutionMethod, ResolutionStatus


def _page(
    title: str,
    page_id: int,
    *,
    wikidata_id: str | None = None,
    disambiguation: bool = False,
    langlinks: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    pageprops: dict[str, str] = {}
    if wikidata_id is not None:
        pageprops["wikibase_item"] = wikidata_id
    if disambiguation:
        pageprops["disambiguation"] = ""
    return {
        "query": {
            "pages": [
                {
                    "title": title,
                    "pageid": page_id,
                    "fullurl": f"https://example.test/wiki/{title.replace(' ', '_')}",
                    "pageprops": pageprops,
                    "langlinks": langlinks or [],
                },
            ],
        },
    }


def _wikidata_entity(identifier: str, sitelinks: dict[str, str]) -> dict[str, object]:
    return {
        "entities": {
            identifier: {
                "sitelinks": {site: {"title": title} for site, title in sitelinks.items()},
            },
        },
    }


def _search_results(titles: list[str]) -> dict[str, object]:
    return {"query": {"search": [{"title": title} for title in titles]}}


def test_exact_article_resolves_in_the_only_requested_language() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "uk.wikipedia.org"
        assert request.url.params["titles"] == "Астрономія"
        return httpx.Response(200, json=_page("Астрономія", 42, wikidata_id="Q333"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_article("Астрономія", ["uk"])

    assert result.status is ResolutionStatus.RESOLVED
    assert result.source_language == "uk"
    assert result.articles[0].canonical_title == "Астрономія"
    assert result.articles[0].resolution_method is ResolutionMethod.INPUT_ARTICLE
    assert result.articles[0].project == "uk.wikipedia"


def test_redirect_resolves_to_the_canonical_source_title() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page("Astronomy", 18831, wikidata_id="Q333"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_article("Astronomy (science)", ["en"])

    assert result.articles[0].canonical_title == "Astronomy"
    assert result.articles[0].resolution_method is ResolutionMethod.REDIRECT


def test_wikidata_sitelink_resolves_a_second_language_edition() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "en.wikipedia.org":
            return httpx.Response(200, json=_page("Astronomy", 18831, wikidata_id="Q333"))
        if request.url.host == "www.wikidata.org":
            return httpx.Response(200, json=_wikidata_entity("Q333", {"enwiki": "Astronomy", "ukwiki": "Астрономія"}))
        if request.url.host == "uk.wikipedia.org":
            return httpx.Response(200, json=_page("Астрономія", 42, wikidata_id="Q333"))
        pytest.fail(f"unexpected host {request.url.host}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_article(
            "Astronomy",
            ["en", "uk"],
            source_language="en",
        )

    assert [article.canonical_title for article in result.articles] == ["Astronomy", "Астрономія"]
    assert result.articles[1].resolution_method is ResolutionMethod.WIKIDATA_SITELINK
    assert result.articles[1].wikidata_id == "Q333"


def test_mediawiki_language_link_is_used_when_no_wikidata_item_is_available() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "en.wikipedia.org":
            return httpx.Response(
                200,
                json=_page("Kyiv", 18831, langlinks=[{"lang": "uk", "title": "Київ"}]),
            )
        if request.url.host == "uk.wikipedia.org":
            return httpx.Response(200, json=_page("Київ", 42, wikidata_id="Q1899"))
        pytest.fail(f"unexpected host {request.url.host}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_article(
            "Kyiv",
            ["en", "uk"],
            source_language="en",
        )

    assert result.articles[1].canonical_title == "Київ"
    assert result.articles[1].resolution_method is ResolutionMethod.LANGUAGE_LINK


def test_missing_sitelink_is_an_explicit_partial_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "en.wikipedia.org":
            return httpx.Response(200, json=_page("Astronomy", 18831, wikidata_id="Q333"))
        if request.url.host == "www.wikidata.org":
            return httpx.Response(200, json=_wikidata_entity("Q333", {"enwiki": "Astronomy"}))
        pytest.fail(f"unexpected host {request.url.host}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_article(
            "Astronomy",
            ["en", "uk"],
            source_language="en",
        )

    assert result.status is ResolutionStatus.PARTIAL
    assert [missing.language for missing in result.missing_languages] == ["uk"]
    assert result.missing_languages[0].reason == "no_linked_article"


def test_disambiguation_returns_structured_clarification_without_guessing() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page("Mercury", 1, disambiguation=True))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_article("Mercury", ["en"])

    assert result.status is ResolutionStatus.REQUIRES_CLARIFICATION
    assert result.clarification is not None
    assert result.clarification.reason == "disambiguation_page"
    assert result.articles == []


def test_non_ascii_title_is_preserved_when_sent_to_mediawiki() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["titles"] == "Київ"
        return httpx.Response(200, json=_page("Київ", 123, wikidata_id="Q1899"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_article("Київ", ["uk"])

    assert result.articles[0].requested_title == "Київ"


def test_missing_source_page_fails_validation_before_downstream_resolution() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"query": {"pages": [{"missing": True}]}})

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as http_client,
        pytest.raises(ArticleNotFoundError, match="does not exist"),
    ):
        ArticleResolver(http_client=http_client).resolve_article("Not a real page", ["en"])


def test_multi_language_query_requires_an_explicit_source_language() -> None:
    query = QueryConfig(mode="article", value="Astronomy")
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500))) as http_client,
        pytest.raises(ValueError, match="source_language"),
    ):
        ArticleResolver(http_client=http_client).resolve(query, ["en", "uk"])


def test_topic_mode_selects_one_obvious_canonical_article() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list") == "search":
            assert request.url.params["srsearch"] == "Astronomy"
            assert request.url.params["srlimit"] == "5"
            return httpx.Response(200, json=_search_results(["Astronomy"]))
        assert request.url.params["titles"] == "Astronomy"
        return httpx.Response(200, json=_page("Astronomy", 18831, wikidata_id="Q333"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_topic("Astronomy", ["en"])

    assert result[0].status is ResolutionStatus.RESOLVED
    assert result[0].candidate_count == 1
    assert [article.canonical_title for article in result[0].selected_articles] == ["Astronomy"]
    assert result[0].selection_method.value == "mediawiki_search_rank_plus_title_overlap"


def test_topic_mode_selects_three_relevant_articles_and_excludes_detectable_lists() -> None:
    pages = {
        "English language": _page("English language", 1),
        "English grammar": _page("English grammar", 2),
        "English literature": _page("English literature", 3),
        "List of English-language topics": _page("List of English-language topics", 4),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_results(list(pages)))
        return httpx.Response(200, json=pages[request.url.params["titles"]])

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_topic("learning English", ["en"])

    assert [article.canonical_title for article in result[0].selected_articles] == [
        "English language",
        "English grammar",
        "English literature",
    ]


def test_topic_mode_excludes_disambiguation_pages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_results(["Mercury"]))
        return httpx.Response(200, json=_page("Mercury", 1, disambiguation=True))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_topic("Mercury", ["en"])

    assert result[0].status is ResolutionStatus.REQUIRES_CLARIFICATION
    assert result[0].clarification is not None
    assert result[0].clarification.reason == "no_valid_topic_candidates"
    assert result[0].selected_articles == []


def test_ambiguous_topic_returns_a_structured_clarification() -> None:
    pages = {
        "Mercury (planet)": _page("Mercury (planet)", 1),
        "Mercury (element)": _page("Mercury (element)", 2),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_results(list(pages)))
        return httpx.Response(200, json=pages[request.url.params["titles"]])

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_topic("Mercury", ["en"])

    assert result[0].status is ResolutionStatus.REQUIRES_CLARIFICATION
    assert result[0].clarification is not None
    assert result[0].clarification.reason == "ambiguous_topic_candidates"


def test_topic_mode_uses_explicit_per_language_override_without_searching() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("list") is None
        assert request.url.params["titles"] == "English language"
        return httpx.Response(200, json=_page("English language", 1))

    query = QueryConfig(
        mode="topic",
        value="learning English",
        article_overrides={"en": ["English language"]},
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve(query, ["en"])

    assert isinstance(result, list)
    assert result[0].selection_method.value == "explicit_article_override"
    assert result[0].selected_articles[0].canonical_title == "English language"
