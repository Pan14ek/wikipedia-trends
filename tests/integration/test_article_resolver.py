"""Mocked integration coverage for M04's MediaWiki article resolver."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from wiki_trends.article_resolver import ArticleNotFoundError, ArticleResolver, TopicSourceLanguageRequiredError
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


def _wikidata_metadata(
    identifier: str,
    *,
    label: str | None = None,
    aliases: list[str] | None = None,
    description: str | None = None,
) -> dict[str, object]:
    entity: dict[str, object] = {}
    if label is not None:
        entity["labels"] = {"en": {"language": "en", "value": label}}
    if aliases is not None:
        entity["aliases"] = {"en": [{"language": "en", "value": alias} for alias in aliases]}
    if description is not None:
        entity["descriptions"] = {"en": {"language": "en", "value": description}}
    return {"entities": {identifier: entity}}


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


def test_source_language_outside_targets_resolves_canonical_target_sitelink() -> None:
    request_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_hosts.append(request.url.host or "")
        if request.url.host == "en.wikipedia.org":
            assert request.url.params["titles"] == "Astronomy"
            return httpx.Response(200, json=_page("Astronomy", 18831, wikidata_id="Q333"))
        if request.url.host == "www.wikidata.org":
            return httpx.Response(
                200,
                json=_wikidata_entity("Q333", {"enwiki": "Astronomy", "ukwiki": "Астрономія"}),
            )
        if request.url.host == "uk.wikipedia.org":
            assert request.url.params["titles"] == "Астрономія"
            return httpx.Response(200, json=_page("Астрономія", 42, wikidata_id="Q333"))
        pytest.fail(f"unexpected host {request.url.host}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_article(
            "Astronomy",
            ["uk"],
            source_language="en",
        )

    assert request_hosts[0] == "en.wikipedia.org"
    assert "uk.wikipedia.org" in request_hosts
    assert "www.wikidata.org" in request_hosts
    assert [article.language for article in result.articles] == ["uk"]
    assert result.articles[0].canonical_title == "Астрономія"
    assert result.articles[0].resolution_method is ResolutionMethod.WIKIDATA_SITELINK
    assert result.articles[0].wikidata_id == "Q333"


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
        if request.url.host == "www.wikidata.org":
            return httpx.Response(200, json=_wikidata_metadata("Q333", label="Astronomy"))
        assert request.url.params["titles"] == "Astronomy"
        return httpx.Response(200, json=_page("Astronomy", 18831, wikidata_id="Q333"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_topic("Astronomy", ["en"])

    assert result[0].status is ResolutionStatus.RESOLVED
    assert result[0].candidate_count == 1
    assert [article.canonical_title for article in result[0].selected_articles] == ["Astronomy"]
    assert result[0].selection_method.value == "mediawiki_semantic_evidence"
    assert result[0].candidate_evidence[0].exact_label_match is True


def test_topic_mode_selects_three_relevant_articles_and_excludes_detectable_lists() -> None:
    pages = {
        "English language": _page("English language", 1, wikidata_id="Q1"),
        "English grammar": _page("English grammar", 2, wikidata_id="Q2"),
        "English literature": _page("English literature", 3, wikidata_id="Q3"),
        "List of English-language topics": _page("List of English-language topics", 4, wikidata_id="Q4"),
    }
    descriptions = {f"Q{index}": "learning English as a useful language subject" for index in range(1, 5)}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_results(list(pages)))
        if request.url.host == "www.wikidata.org":
            identifier = request.url.params["ids"]
            return httpx.Response(200, json=_wikidata_metadata(identifier, description=descriptions[identifier]))
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
    assert result[0].clarification.reason == "disambiguation_page"
    assert result[0].selected_articles == []


def test_ambiguous_topic_returns_a_structured_clarification() -> None:
    pages = {
        "Mercury (planet)": _page("Mercury (planet)", 1, wikidata_id="Q1"),
        "Mercury (element)": _page("Mercury (element)", 2, wikidata_id="Q2"),
    }
    descriptions = {
        "Q1": "Mercury planet in the solar system",
        "Q2": "Mercury chemical element metallic substance",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_results(list(pages)))
        if request.url.host == "www.wikidata.org":
            identifier = request.url.params["ids"]
            return httpx.Response(200, json=_wikidata_metadata(identifier, description=descriptions[identifier]))
        return httpx.Response(200, json=pages[request.url.params["titles"]])

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_topic("Mercury", ["en"])

    assert result[0].status is ResolutionStatus.REQUIRES_CLARIFICATION
    assert result[0].clarification is not None
    assert result[0].clarification.reason == "ambiguous_topic_candidates"


def test_unrelated_rank_one_candidate_is_rejected_and_does_not_block_relevant_candidate() -> None:
    pages = {
        "Da Vinci": _page("Da Vinci", 1, wikidata_id="Q1"),
        "Learning English": _page("Learning English", 2, wikidata_id="Q2"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_results(list(pages)))
        if request.url.host == "www.wikidata.org":
            identifier = request.url.params["ids"]
            if identifier == "Q1":
                return httpx.Response(200, json=_wikidata_metadata(identifier, label="Leonardo da Vinci"))
            return httpx.Response(200, json=_wikidata_metadata(identifier, label="Learning English"))
        return httpx.Response(200, json=pages[request.url.params["titles"]])

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_topic("learning English", ["en"])

    assert result[0].selected_articles[0].canonical_title == "Learning English"
    assert result[0].candidate_evidence[0].decision.value == "rejected"
    assert result[0].candidate_evidence[0].reason == "insufficient_semantic_evidence"
    assert result[0].candidate_evidence[0].search_rank == 1


def test_broad_intermittent_fasting_candidate_does_not_pass_on_one_shared_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_results(["Fasting"]))
        if request.url.host == "www.wikidata.org":
            return httpx.Response(
                200,
                json=_wikidata_metadata("Q1", label="Fasting", description="abstaining from food for health"),
            )
        return httpx.Response(200, json=_page("Fasting", 1, wikidata_id="Q1"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = ArticleResolver(http_client=http_client).resolve_topic("intermittent fasting", ["en"])

    assert result[0].status is ResolutionStatus.REQUIRES_CLARIFICATION
    assert result[0].candidate_evidence[0].query_token_coverage == 0.5
    assert result[0].candidate_evidence[0].decision.value == "rejected"


def test_multi_language_topic_requires_source_language_before_search() -> None:
    query = QueryConfig(mode="topic", value="Astronomy")
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("search must not run"))) as http_client,
        pytest.raises(TopicSourceLanguageRequiredError, match="source_language") as error,
    ):
        ArticleResolver(http_client=http_client).resolve(query, ["en", "uk"])
    assert error.value.reason == "source_language_required"


def test_topic_maps_source_qids_through_sitelinks_without_target_search() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "en.wikipedia.org" and request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_results(["Astronomy"]))
        if request.url.host == "en.wikipedia.org":
            return httpx.Response(200, json=_page("Astronomy", 1, wikidata_id="Q333"))
        if request.url.host == "www.wikidata.org" and request.url.params.get("props") == "labels|aliases|descriptions":
            return httpx.Response(200, json=_wikidata_metadata("Q333", label="Astronomy"))
        if request.url.host == "www.wikidata.org":
            return httpx.Response(200, json=_wikidata_entity("Q333", {"ukwiki": "Астрономія"}))
        if request.url.host == "uk.wikipedia.org":
            assert request.url.params.get("list") is None
            return httpx.Response(200, json=_page("Астрономія", 2, wikidata_id="Q333"))
        pytest.fail(f"unexpected request {request.url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        results = ArticleResolver(http_client=http_client).resolve_topic(
            "Astronomy", ["en", "uk"], source_language="en"
        )

    assert [item.canonical_concept_ids for item in results] == [["Q333"], ["Q333"]]
    assert results[1].selected_articles[0].resolution_method is ResolutionMethod.WIKIDATA_SITELINK
    assert results[1].comparison_equivalent is True


@pytest.mark.parametrize(
    ("fixture_name", "target_languages"),
    [("learning_english", ["simple"]), ("intermittent_fasting", ["pl", "cs"])],
)
def test_canonical_topic_regression_fixtures_map_only_reviewed_qids(
    fixture_name: str,
    target_languages: list[str],
) -> None:
    fixtures_path = Path(__file__).resolve().parents[1] / "fixtures" / "topic_concept_regressions.json"
    fixture = json.loads(fixtures_path.read_text(encoding="utf-8"))[fixture_name]
    requested_topic = fixture["requested_topic"]
    source_title = fixture["source_title"]
    wikidata_id = fixture["wikidata_id"]
    sitelinks = {"enwiki": source_title}
    sitelinks.update({f"{language}wiki": title for language, title in fixture["target_sitelinks"].items()})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "en.wikipedia.org" and request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_results([source_title]))
        if request.url.host == "www.wikidata.org" and request.url.params.get("props") == "labels|aliases|descriptions":
            return httpx.Response(
                200,
                json=_wikidata_metadata(
                    wikidata_id,
                    label=fixture.get("label"),
                    aliases=fixture.get("aliases"),
                    description=fixture.get("description"),
                ),
            )
        if request.url.host == "www.wikidata.org":
            return httpx.Response(200, json=_wikidata_entity(wikidata_id, sitelinks))
        if request.url.host == "en.wikipedia.org":
            return httpx.Response(200, json=_page(source_title, 1, wikidata_id=wikidata_id))
        target_title = fixture["target_sitelinks"].get(request.url.host.split(".")[0])
        if target_title is None:
            pytest.fail(f"target search or non-canonical lookup is forbidden: {request.url}")
        return httpx.Response(200, json=_page(target_title, 2, wikidata_id=wikidata_id))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        results = ArticleResolver(http_client=http_client).resolve_topic(
            requested_topic,
            target_languages,
            source_language="en",
        )

    by_language = {result.language: result for result in results}
    if fixture_name == "learning_english":
        resolved = by_language["simple"]
        assert resolved.status is ResolutionStatus.RESOLVED
        assert resolved.selected_articles[0].wikidata_id == "Q130192"
    else:
        assert by_language["pl"].status is ResolutionStatus.REQUIRES_CLARIFICATION
        assert by_language["pl"].clarification is not None
        assert by_language["pl"].clarification.reason == "missing_canonical_sitelink"
        assert by_language["cs"].selected_articles[0].canonical_title == "Přerušovaný půst"
        assert by_language["cs"].selected_articles[0].wikidata_id == "Q1666254"


def test_missing_topic_sitelink_does_not_search_target_language() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "en.wikipedia.org" and request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_results(["Astronomy"]))
        if request.url.host == "en.wikipedia.org":
            return httpx.Response(200, json=_page("Astronomy", 1, wikidata_id="Q333"))
        if request.url.host == "www.wikidata.org" and request.url.params.get("props") == "labels|aliases|descriptions":
            return httpx.Response(200, json=_wikidata_metadata("Q333", label="Astronomy"))
        if request.url.host == "www.wikidata.org":
            return httpx.Response(200, json=_wikidata_entity("Q333", {"enwiki": "Astronomy"}))
        pytest.fail(f"target fallback request is forbidden: {request.url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        results = ArticleResolver(http_client=http_client).resolve_topic(
            "Astronomy", ["en", "uk"], source_language="en"
        )

    assert results[1].status is ResolutionStatus.REQUIRES_CLARIFICATION
    assert results[1].clarification is not None
    assert results[1].clarification.reason == "missing_canonical_sitelink"


@pytest.mark.parametrize(("target_qid", "expected_equivalent"), [("Q333", True), ("Q999", False)])
def test_topic_override_qid_equivalence_controls_direct_comparison(
    target_qid: str,
    expected_equivalent: bool,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "en.wikipedia.org" and request.url.params.get("list") == "search":
            return httpx.Response(200, json=_search_results(["Astronomy"]))
        if request.url.host == "en.wikipedia.org":
            return httpx.Response(200, json=_page("Astronomy", 1, wikidata_id="Q333"))
        if request.url.host == "www.wikidata.org" and request.url.params.get("props") == "labels|aliases|descriptions":
            return httpx.Response(200, json=_wikidata_metadata("Q333", label="Astronomy"))
        if request.url.host == "www.wikidata.org":
            return httpx.Response(200, json=_wikidata_entity("Q333", {"ukwiki": "Астрономія"}))
        return httpx.Response(200, json=_page("Astronomy proxy", 2, wikidata_id=target_qid))

    query = QueryConfig(
        mode="topic",
        value="Astronomy",
        source_language="en",
        article_overrides={"uk": ["Astronomy proxy"]},
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        results = ArticleResolver(http_client=http_client).resolve(query, ["en", "uk"])

    assert isinstance(results, list)
    assert results[1].comparison_equivalent is expected_equivalent
    assert results[1].selected_articles[0].wikidata_id == target_qid


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
