"""Resolve article queries to canonical, linked Wikipedia edition identities."""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Final

import httpx
from pydantic import ValidationError

from wiki_trends.cache import CacheNamespace, FilesystemCache, resolution_ttl
from wiki_trends.config import QueryConfig, QueryMode
from wiki_trends.models import (
    ArticleResolution,
    MissingLanguageEquivalent,
    ResolutionClarification,
    ResolutionMethod,
    ResolutionStatus,
    ResolvedArticle,
    TopicCandidateDecision,
    TopicCandidateEvidence,
    TopicResolution,
    TopicSelectionMethod,
)

__all__ = [
    "ArticleNotFoundError",
    "ArticleResolver",
    "ArticleResolverError",
    "ArticleResolverUnavailableError",
    "TopicSourceLanguageRequiredError",
]

_DEFAULT_TIMEOUT_SECONDS: Final = 10.0
_DEFAULT_USER_AGENT: Final = "WikipediaTrends/0.1.0 (https://www.mediawiki.org/wiki/API:Main_page)"
_LANGUAGE_PATTERN: Final = re.compile(r"^[a-z][a-z0-9-]*$")
_TITLE_TOKEN_PATTERN: Final = re.compile(r"\w+", re.UNICODE)
_TOPIC_MIN_TOKEN_COVERAGE: Final = 0.80
_PARENTHETICAL_QUALIFIER_PATTERN: Final = re.compile(r"\(([^()]+)\)")
_TOPIC_SEARCH_RESULT_LIMIT: Final = 5
_TOPIC_SELECTION_LIMIT: Final = 3


class ArticleResolverError(RuntimeError):
    """Base exception for invalid or malformed article-resolution operations."""


class ArticleNotFoundError(ArticleResolverError):
    """Raised when the requested source article does not exist."""


class ArticleResolverUnavailableError(ArticleResolverError):
    """Raised when a MediaWiki or Wikidata request cannot be completed."""


class TopicSourceLanguageRequiredError(ValueError):
    """Raised before search when a multi-language topic lacks its source language."""

    reason = "source_language_required"

    def __init__(self) -> None:
        super().__init__("'source_language' is required for multi-language topic resolution")


class ArticleResolver:
    """Resolve concrete articles and transparent language-local topic selections.

    The resolver keeps all HTTP calls at this boundary. Article mode relies on
    MediaWiki language links and Wikidata sitelinks without translation or
    heuristic search; topic mode accepts deterministic semantic evidence and
    maps canonical source concepts through Wikidata. An injected HTTP client
    remains owned by its caller, which keeps mocked integration tests deterministic.
    """

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = _DEFAULT_USER_AGENT,
        logger: logging.Logger | None = None,
        cache: FilesystemCache | None = None,
    ) -> None:
        """Initialize the resolver's HTTP boundary.

        Raises:
            ValueError: If the timeout or User-Agent is invalid.
        """
        if timeout_seconds <= 0:
            raise ValueError("'timeout_seconds' must be positive")
        if not user_agent.strip():
            raise ValueError("'user_agent' must not be blank")

        self._client = http_client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = http_client is None
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self._logger = logger or logging.getLogger(__name__)
        self._cache = cache if cache is not None else (None if http_client is not None else FilesystemCache())
        self._semantic_metadata_cache: dict[tuple[str, str], _SemanticMetadata] = {}
        self._sitelink_cache: dict[str, Mapping[str, str]] = {}

    def __enter__(self) -> ArticleResolver:
        """Enter a context that closes an internally created HTTP client."""
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close only the HTTP client created by this resolver."""
        del exception_type, exception, traceback
        self.close()

    def close(self) -> None:
        """Close the internally owned HTTP client, if any."""
        if self._owns_client:
            self._client.close()

    def resolve(self, query: QueryConfig, languages: Sequence[str]) -> ArticleResolution | list[TopicResolution]:
        """Resolve an article or topic configuration to canonical edition articles.

        A single requested language is sufficient to infer the source language.
        Multi-language inputs must set ``query.source_language`` explicitly,
        because guessing which edition owns a title can select a different
        concept.

        Raises:
            ArticleResolverError: If a requested source page is absent.
            ValueError: If requested languages cannot safely identify a source.
        """
        requested_languages = _validate_languages(languages)
        if query.mode is QueryMode.TOPIC:
            _resolve_topic_source_language(query.source_language, requested_languages)
        fields = {
            "languages": requested_languages,
            "operation": "resolve",
            "query": query.model_dump(mode="json", by_alias=True),
        }
        cached = self._load_cached_resolution(query.mode, fields)
        if cached is not None:
            return cached
        if query.mode is QueryMode.ARTICLE:
            result: ArticleResolution | list[TopicResolution] = self.resolve_article(
                query.value,
                requested_languages,
                source_language=query.source_language,
            )
        else:
            result = self.resolve_topic(
                query.value,
                requested_languages,
                source_language=query.source_language,
                article_overrides=query.article_overrides,
            )
        if self._cache is not None:
            payload = (
                result.model_dump(mode="json")
                if isinstance(result, ArticleResolution)
                else [resolution.model_dump(mode="json") for resolution in result]
            )
            self._cache.store(CacheNamespace.RESOLUTION, fields, payload)
        return result

    def _load_cached_resolution(
        self,
        mode: QueryMode,
        fields: Mapping[str, object],
    ) -> ArticleResolution | list[TopicResolution] | None:
        """Validate cached public resolution output before returning it to callers."""
        if self._cache is None:
            return None
        payload = self._cache.load(CacheNamespace.RESOLUTION, fields, resolution_ttl())
        if payload is None:
            return None
        try:
            if mode is QueryMode.ARTICLE:
                return ArticleResolution.model_validate(payload)
            if not isinstance(payload, list):
                raise ValueError("topic cache payload must be a list")
            return [TopicResolution.model_validate(item) for item in payload]
        except (ValidationError, ValueError):
            self._cache.discard(CacheNamespace.RESOLUTION, fields)
            self._logger.warning("Discarding malformed cached Wikipedia resolution")
            return None

    def resolve_article(
        self,
        requested_title: str,
        languages: Sequence[str],
        *,
        source_language: str | None = None,
    ) -> ArticleResolution:
        """Resolve a concrete title using MediaWiki and Wikidata identifiers.

        ``source_language`` is inferred only when exactly one language is
        requested. Missing secondary equivalents return a ``PARTIAL`` result;
        a disambiguation page returns a structured clarification result.
        """
        title = _require_nonblank_text(requested_title, "requested_title")
        requested_languages = _validate_languages(languages)
        source = _resolve_source_language(source_language, requested_languages)

        self._logger.info(
            "Resolving Wikipedia article",
            extra={"source_language": source, "requested_language_count": len(requested_languages)},
        )
        source_page = self._lookup_page(source, title)
        if source_page is None:
            raise ArticleNotFoundError(f"Wikipedia article '{title}' does not exist in {source}.wikipedia")
        if source_page.is_disambiguation:
            return _clarification_result(title, source, source_page)

        sitelinks = (
            self._get_sitelinks(source_page.wikidata_id)
            if any(language != source for language in requested_languages)
            else {}
        )
        resolved_articles: list[ResolvedArticle] = []
        missing_languages: list[MissingLanguageEquivalent] = []
        for language in requested_languages:
            candidate_title, method = _candidate_for_language(
                language,
                source,
                source_page,
                sitelinks,
            )
            if candidate_title is None or method is None:
                missing_languages.append(_missing_equivalent(language, title))
                continue

            page = source_page if language == source else self._lookup_page(language, candidate_title)
            if page is None:
                missing_languages.append(_missing_equivalent(language, title, "linked_article_not_found"))
                continue
            if page.is_disambiguation:
                return _clarification_result(title, source, page, language)
            resolved_articles.append(
                ResolvedArticle(
                    language=language,
                    project=f"{language}.wikipedia",
                    requested_title=title,
                    canonical_title=page.title,
                    page_id=page.page_id,
                    wikidata_id=page.wikidata_id or source_page.wikidata_id,
                    url=page.url,
                    resolution_method=_resolution_method_for_page(method, title, page.title),
                ),
            )

        status = ResolutionStatus.PARTIAL if missing_languages else ResolutionStatus.RESOLVED
        self._logger.info(
            "Wikipedia article resolution completed",
            extra={
                "source_language": source,
                "resolved_language_count": len(resolved_articles),
                "missing_language_count": len(missing_languages),
            },
        )
        return ArticleResolution(
            requested_title=title,
            source_language=source,
            status=status,
            articles=resolved_articles,
            missing_languages=missing_languages,
        )

    def resolve_topic(
        self,
        requested_topic: str,
        languages: Sequence[str],
        *,
        source_language: str | None = None,
        article_overrides: Mapping[str, Sequence[str]] | None = None,
    ) -> list[TopicResolution]:
        """Resolve source concepts once and map them to requested editions.

        For multi-language requests the source language is required. Search
        runs only in that edition; target editions are resolved by the source
        concepts' Wikidata sitelinks. Explicit overrides remain reviewable and
        are marked non-equivalent when their QID set differs.

        Raises:
            ValueError: If the topic, languages, or override keys are invalid.
            ArticleResolverError: If MediaWiki returns malformed data.
        """
        topic = _require_nonblank_text(requested_topic, "requested_topic")
        requested_languages = _validate_languages(languages)
        source = _resolve_topic_source_language(source_language, requested_languages)
        validated_overrides = _validate_topic_overrides(article_overrides, requested_languages)
        self._logger.info(
            "Resolving Wikipedia topic",
            extra={
                "requested_language_count": len(requested_languages),
                "override_language_count": len(validated_overrides),
            },
        )
        source_override = validated_overrides.get(source)
        source_resolution = self.resolve_topic_language(
            topic,
            source,
            article_override=source_override,
        )
        canonical_ids = [
            article.wikidata_id for article in source_resolution.selected_articles if article.wikidata_id is not None
        ]
        complete_canonical_set = bool(canonical_ids) and len(canonical_ids) == len(source_resolution.selected_articles)
        resolutions: list[TopicResolution] = []
        for language in requested_languages:
            if language == source:
                resolutions.append(source_resolution)
                continue
            override = validated_overrides.get(language)
            if source_resolution.status is ResolutionStatus.REQUIRES_CLARIFICATION:
                resolutions.append(
                    _topic_clarification(
                        topic,
                        language,
                        source_resolution.candidate_count,
                        source_resolution.clarification.reason
                        if source_resolution.clarification
                        else "source_unresolved",
                        TopicSelectionMethod.WIKIDATA_SITELINK,
                        source_language=source,
                        canonical_concept_ids=canonical_ids,
                    )
                )
            elif override is not None:
                resolutions.append(
                    self._resolve_topic_override(
                        topic,
                        language,
                        override,
                        source_language=source,
                        canonical_concept_ids=canonical_ids,
                    )
                )
            elif not complete_canonical_set:
                resolutions.append(
                    _topic_clarification(
                        topic,
                        language,
                        source_resolution.candidate_count,
                        "missing_canonical_sitelink",
                        TopicSelectionMethod.WIKIDATA_SITELINK,
                        source_language=source,
                        canonical_concept_ids=canonical_ids,
                    )
                )
            else:
                resolutions.append(
                    self._map_topic_concepts(
                        topic,
                        language,
                        source,
                        source_resolution,
                        canonical_ids,
                    )
                )
        self._logger.info(
            "Wikipedia topic resolution completed",
            extra={
                "requested_language_count": len(requested_languages),
                "resolved_language_count": sum(
                    resolution.status is ResolutionStatus.RESOLVED for resolution in resolutions
                ),
                "clarification_language_count": sum(
                    resolution.status is ResolutionStatus.REQUIRES_CLARIFICATION for resolution in resolutions
                ),
            },
        )
        return resolutions

    def resolve_topic_language(
        self,
        requested_topic: str,
        language: str,
        *,
        article_override: Sequence[str] | None = None,
    ) -> TopicResolution:
        """Resolve source-language concepts through semantic evidence."""
        topic = _require_nonblank_text(requested_topic, "requested_topic")
        validated_language = _validate_language(language)
        if article_override is not None:
            return self._resolve_topic_override(topic, validated_language, article_override)

        search_titles = self._search_titles(validated_language, topic)
        candidates, evidence = self._valid_topic_candidates(topic, validated_language, search_titles)
        direct_disambiguation = any(
            item.exact_title_match and item.reason == "disambiguation_page" for item in evidence
        )
        if direct_disambiguation or _topic_candidates_are_ambiguous(candidates):
            return _topic_clarification(
                topic,
                validated_language,
                len(search_titles),
                "disambiguation_page" if direct_disambiguation else "ambiguous_topic_candidates",
                TopicSelectionMethod.MEDIAWIKI_SEMANTIC_EVIDENCE,
                candidate_evidence=evidence,
            )
        selected_articles = [_resolved_topic_article(candidate) for candidate in candidates[:_TOPIC_SELECTION_LIMIT]]
        if not selected_articles:
            return _topic_clarification(
                topic,
                validated_language,
                len(search_titles),
                "insufficient_semantic_evidence",
                TopicSelectionMethod.MEDIAWIKI_SEMANTIC_EVIDENCE,
                candidate_evidence=evidence,
            )
        return TopicResolution(
            requested_topic=topic,
            language=validated_language,
            status=ResolutionStatus.RESOLVED,
            selected_articles=selected_articles,
            candidate_count=len(search_titles),
            selection_method=TopicSelectionMethod.MEDIAWIKI_SEMANTIC_EVIDENCE,
            source_language=validated_language,
            canonical_concept_ids=[
                article.wikidata_id for article in selected_articles if article.wikidata_id is not None
            ],
            candidate_evidence=evidence,
        )

    def _resolve_topic_override(
        self,
        topic: str,
        language: str,
        article_override: Sequence[str],
        *,
        source_language: str | None = None,
        canonical_concept_ids: Sequence[str] = (),
    ) -> TopicResolution:
        """Resolve reviewed topic article titles without hidden search selection."""
        titles = _validate_override_titles(article_override, language)
        selected_articles: list[ResolvedArticle] = []
        selected_page_ids: set[int] = set()
        for title in titles:
            page = self._lookup_page(language, title)
            if page is None:
                raise ArticleNotFoundError(f"Wikipedia article '{title}' does not exist in {language}.wikipedia")
            if page.is_disambiguation or _is_detectable_list_page(page.title):
                return _topic_clarification(
                    topic,
                    language,
                    len(titles),
                    "override_not_article",
                    TopicSelectionMethod.EXPLICIT_ARTICLE_OVERRIDE,
                )
            if page.page_id in selected_page_ids:
                continue
            selected_page_ids.add(page.page_id)
            selected_articles.append(_resolved_article_from_page(language, title, page))

        if not selected_articles:
            return _topic_clarification(
                topic,
                language,
                len(titles),
                "no_valid_topic_candidates",
                TopicSelectionMethod.EXPLICIT_ARTICLE_OVERRIDE,
            )
        comparison_equivalent = source_language is None or source_language == language
        if source_language is not None and source_language != language:
            override_qids = [article.wikidata_id for article in selected_articles]
            comparison_equivalent = (
                bool(canonical_concept_ids)
                and len(selected_articles) == len(canonical_concept_ids)
                and all(qid is not None for qid in override_qids)
                and set(override_qids) == set(canonical_concept_ids)
            )
            if comparison_equivalent:
                articles_by_qid = {article.wikidata_id: article for article in selected_articles}
                selected_articles = [articles_by_qid[concept_id] for concept_id in canonical_concept_ids]
        return TopicResolution(
            requested_topic=topic,
            language=language,
            status=ResolutionStatus.RESOLVED,
            selected_articles=selected_articles,
            candidate_count=len(titles),
            selection_method=TopicSelectionMethod.EXPLICIT_ARTICLE_OVERRIDE,
            source_language=source_language or language,
            canonical_concept_ids=list(canonical_concept_ids),
            comparison_equivalent=comparison_equivalent,
        )

    def _map_topic_concepts(
        self,
        topic: str,
        language: str,
        source_language: str,
        source_resolution: TopicResolution,
        canonical_ids: Sequence[str],
    ) -> TopicResolution:
        """Resolve every canonical concept by its target-edition sitelink."""
        selected: list[ResolvedArticle] = []
        for concept_id in canonical_ids:
            title = self._get_sitelinks(concept_id).get(f"{language}wiki")
            if title is None:
                return _topic_clarification(
                    topic,
                    language,
                    source_resolution.candidate_count,
                    "missing_canonical_sitelink",
                    TopicSelectionMethod.WIKIDATA_SITELINK,
                    source_language=source_language,
                    canonical_concept_ids=canonical_ids,
                )
            page = self._lookup_page(language, title)
            if page is None or page.wikidata_id != concept_id:
                return _topic_clarification(
                    topic,
                    language,
                    source_resolution.candidate_count,
                    "missing_canonical_sitelink",
                    TopicSelectionMethod.WIKIDATA_SITELINK,
                    source_language=source_language,
                    canonical_concept_ids=canonical_ids,
                )
            selected.append(_resolved_article_from_page(language, title, page, ResolutionMethod.WIKIDATA_SITELINK))
        return TopicResolution(
            requested_topic=topic,
            language=language,
            status=ResolutionStatus.RESOLVED,
            selected_articles=selected,
            candidate_count=source_resolution.candidate_count,
            selection_method=TopicSelectionMethod.WIKIDATA_SITELINK,
            source_language=source_language,
            canonical_concept_ids=list(canonical_ids),
            comparison_equivalent=True,
        )

    def _search_titles(self, language: str, topic: str) -> list[str]:
        """Retrieve the bounded, rank-ordered MediaWiki search titles."""
        payload = self._get_json(
            _mediawiki_url(language),
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "list": "search",
                "srsearch": topic,
                "srlimit": str(_TOPIC_SEARCH_RESULT_LIMIT),
                "srnamespace": "0",
            },
        )
        return _parse_search_titles(payload)

    def _valid_topic_candidates(
        self,
        topic: str,
        language: str,
        search_titles: Sequence[str],
    ) -> tuple[list[_TopicCandidate], list[TopicCandidateEvidence]]:
        """Canonicalize candidates and apply deterministic semantic gates."""
        candidates: list[_TopicCandidate] = []
        evidence: list[TopicCandidateEvidence] = []
        seen_page_ids: set[int] = set()
        seen_wikidata_ids: set[str] = set()
        semantic_metadata_by_qid: dict[str, _SemanticMetadata] = {}
        for search_rank, title in enumerate(search_titles, start=1):
            page = self._lookup_page(language, title)
            if page is None:
                continue
            if page.page_id in seen_page_ids:
                continue
            if page.wikidata_id is not None and page.wikidata_id in seen_wikidata_ids:
                continue
            seen_page_ids.add(page.page_id)
            if page.wikidata_id is not None:
                seen_wikidata_ids.add(page.wikidata_id)
            if page.wikidata_id is None:
                semantic_metadata = self._get_semantic_metadata(None, language)
            else:
                existing_metadata = semantic_metadata_by_qid.get(page.wikidata_id)
                if existing_metadata is None:
                    existing_metadata = self._get_semantic_metadata(page.wikidata_id, language)
                    semantic_metadata_by_qid[page.wikidata_id] = existing_metadata
                semantic_metadata = existing_metadata
            candidate_evidence = _topic_candidate_evidence(
                topic,
                page,
                search_rank,
                semantic_metadata,
            )
            if page.is_disambiguation or _is_detectable_list_page(page.title):
                reason = "disambiguation_page" if page.is_disambiguation else "non_article_page"
                candidate_evidence = candidate_evidence.model_copy(
                    update={"decision": TopicCandidateDecision.REJECTED, "reason": reason}
                )
            evidence.append(candidate_evidence)
            if page.is_disambiguation or _is_detectable_list_page(page.title):
                continue
            if candidate_evidence.decision is TopicCandidateDecision.ACCEPTED:
                candidates.append(_TopicCandidate(language, search_rank, title, page, candidate_evidence))
        candidates.sort(
            key=lambda candidate: (
                not candidate.evidence.exact_title_match,
                not candidate.evidence.exact_label_match,
                not candidate.evidence.exact_alias_match,
                -candidate.evidence.query_token_coverage,
                candidate.search_rank,
                normalize_topic_text(candidate.page.title),
            )
        )
        return candidates, evidence

    def _get_semantic_metadata(self, wikidata_id: str | None, source_language: str) -> _SemanticMetadata:
        if wikidata_id is None:
            return _SemanticMetadata(None, (), (), (), None)
        cache_key = (wikidata_id, source_language)
        if cache_key in self._semantic_metadata_cache:
            return self._semantic_metadata_cache[cache_key]
        payload = self._get_json(
            "https://www.wikidata.org/w/api.php",
            {
                "action": "wbgetentities",
                "format": "json",
                "formatversion": "2",
                "ids": wikidata_id,
                "props": "labels|aliases|descriptions",
                "languages": f"{source_language}|en",
            },
        )
        metadata = _parse_semantic_metadata(payload, wikidata_id, source_language)
        self._semantic_metadata_cache[cache_key] = metadata
        return metadata

    def _lookup_page(self, language: str, title: str) -> _PageLookup | None:
        payload = self._get_json(
            _mediawiki_url(language),
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "redirects": "1",
                "prop": "info|pageprops|langlinks",
                "inprop": "url",
                "lllimit": "max",
                "llprop": "url",
                "titles": title,
            },
        )
        return _parse_page_lookup(payload, language)

    def _get_sitelinks(self, wikidata_id: str | None) -> Mapping[str, str]:
        if wikidata_id is None:
            return {}
        if wikidata_id in self._sitelink_cache:
            return self._sitelink_cache[wikidata_id]
        payload = self._get_json(
            "https://www.wikidata.org/w/api.php",
            {
                "action": "wbgetentities",
                "format": "json",
                "formatversion": "2",
                "ids": wikidata_id,
                "props": "sitelinks",
            },
        )
        sitelinks = _parse_sitelinks(payload, wikidata_id)
        self._sitelink_cache[wikidata_id] = sitelinks
        return sitelinks

    def _get_json(self, url: str, params: Mapping[str, str]) -> Mapping[str, object]:
        try:
            response = self._client.get(
                url,
                params=params,
                headers={"User-Agent": self._user_agent},
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise ArticleResolverUnavailableError("MediaWiki request timed out") from error
        except httpx.RequestError as error:
            raise ArticleResolverUnavailableError("MediaWiki request failed") from error
        if response.status_code != 200:
            raise ArticleResolverUnavailableError(f"MediaWiki returned HTTP {response.status_code}")
        try:
            payload: object = response.json()
        except ValueError as error:
            raise ArticleResolverError("MediaWiki returned invalid JSON") from error
        if not isinstance(payload, Mapping):
            raise ArticleResolverError("MediaWiki response must be a JSON object")
        return payload


class _PageLookup:
    """Internal normalized representation of a MediaWiki page lookup."""

    def __init__(
        self,
        *,
        title: str,
        page_id: int,
        url: str,
        wikidata_id: str | None,
        language_links: Mapping[str, str],
        is_disambiguation: bool,
    ) -> None:
        self.title = title
        self.page_id = page_id
        self.url = url
        self.wikidata_id = wikidata_id
        self.language_links = language_links
        self.is_disambiguation = is_disambiguation


@dataclass(frozen=True)
class _TopicCandidate:
    """One valid, canonical topic-search result before final selection."""

    language: str
    search_rank: int
    requested_title: str
    page: _PageLookup
    evidence: TopicCandidateEvidence


@dataclass(frozen=True)
class _SemanticMetadata:
    """Source-language Wikidata text with explicit fallback language."""

    label: str | None
    aliases: tuple[str, ...]
    description: tuple[str, ...]
    metadata_languages: tuple[str, ...]
    wikidata_id: str | None


def _parse_search_titles(payload: Mapping[str, object]) -> list[str]:
    """Validate MediaWiki's rank-ordered search response."""
    query = _require_mapping(payload.get("query"), "MediaWiki response must contain a query object")
    raw_results = query.get("search")
    if not isinstance(raw_results, list):
        raise ArticleResolverError("MediaWiki search response must contain a search result list")
    if len(raw_results) > _TOPIC_SEARCH_RESULT_LIMIT:
        raise ArticleResolverError("MediaWiki search response exceeded the requested result limit")
    return [
        _require_text(
            _require_mapping(raw_result, "MediaWiki search response contains an invalid result").get("title"),
            "MediaWiki search result has an invalid title",
        )
        for raw_result in raw_results
    ]


def _validate_topic_overrides(
    article_overrides: Mapping[str, Sequence[str]] | None,
    languages: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    """Validate direct callers' per-language override mapping at the boundary."""
    if article_overrides is None:
        return {}
    valid_languages = set(languages)
    validated: dict[str, tuple[str, ...]] = {}
    for language, titles in article_overrides.items():
        validated_language = _validate_language(language)
        if validated_language not in valid_languages:
            raise ValueError(f"article override language '{validated_language}' is not in 'languages'")
        validated[validated_language] = _validate_override_titles(titles, validated_language)
    return validated


def _validate_override_titles(titles: Sequence[str], language: str) -> tuple[str, ...]:
    """Require one to three unique, non-blank reviewed article titles."""
    normalized_titles = tuple(_require_nonblank_text(title, "article_override") for title in titles)
    if not 1 <= len(normalized_titles) <= _TOPIC_SELECTION_LIMIT:
        raise ValueError(f"article override for '{language}' must contain one to three article titles")
    if len(normalized_titles) != len(set(normalized_titles)):
        raise ValueError(f"article override for '{language}' must not contain duplicate article titles")
    return normalized_titles


def normalize_topic_text(value: str) -> str:
    """Normalize lexical evidence deterministically across Unicode text."""
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("_", " ")
    normalized = "".join(character if character.isalnum() else " " for character in normalized)
    return " ".join(normalized.split())


def _topic_candidate_evidence(
    topic: str,
    page: _PageLookup,
    search_rank: int,
    metadata: _SemanticMetadata,
) -> TopicCandidateEvidence:
    """Build inspectable evidence and decide through hard semantic gates."""
    normalized_query = normalize_topic_text(topic)
    title = normalize_topic_text(page.title)
    label = normalize_topic_text(metadata.label or "")
    aliases = {normalize_topic_text(alias) for alias in metadata.aliases}
    query_tokens = set(_TITLE_TOKEN_PATTERN.findall(normalized_query))
    semantic_tokens = set(
        _TITLE_TOKEN_PATTERN.findall(
            normalize_topic_text(" ".join([page.title, metadata.label or "", *metadata.aliases, *metadata.description]))
        )
    )
    anchor_tokens = set(
        _TITLE_TOKEN_PATTERN.findall(
            normalize_topic_text(" ".join([page.title, metadata.label or "", *metadata.aliases]))
        )
    )
    coverage = len(query_tokens & semantic_tokens) / len(query_tokens) if query_tokens else 0.0
    exact_title = bool(normalized_query) and normalized_query == title
    exact_label = bool(label) and normalized_query == label
    exact_alias = normalized_query in aliases
    lexical_anchor = bool(query_tokens & anchor_tokens)
    accepted = exact_title or exact_label or exact_alias or (coverage >= _TOPIC_MIN_TOKEN_COVERAGE and lexical_anchor)
    reason = (
        "exact_title_match"
        if exact_title
        else "exact_label_match"
        if exact_label
        else "exact_alias_match"
        if exact_alias
        else "token_coverage_and_anchor"
        if accepted
        else "insufficient_semantic_evidence"
    )
    return TopicCandidateEvidence(
        canonical_title=page.title,
        wikidata_id=page.wikidata_id,
        search_rank=search_rank,
        exact_title_match=exact_title,
        exact_label_match=exact_label,
        exact_alias_match=exact_alias,
        query_token_coverage=coverage,
        lexical_anchor=lexical_anchor,
        metadata_languages=list(metadata.metadata_languages),
        decision=TopicCandidateDecision.ACCEPTED if accepted else TopicCandidateDecision.REJECTED,
        reason=reason,
    )


def _topic_candidates_are_ambiguous(candidates: Sequence[_TopicCandidate]) -> bool:
    """Detect near-equal top results that name distinct parenthetical concepts."""
    if len(candidates) < 2:
        return False
    first, second = candidates[0], candidates[1]
    first_qualifier = _parenthetical_qualifier(first.page.title)
    second_qualifier = _parenthetical_qualifier(second.page.title)
    return first_qualifier is not None and second_qualifier is not None and first_qualifier != second_qualifier


def _parenthetical_qualifier(title: str) -> str | None:
    """Return a normalized title qualifier when a title explicitly provides one."""
    match = _PARENTHETICAL_QUALIFIER_PATTERN.search(title)
    if match is None:
        return None
    qualifier = normalize_topic_text(match.group(1))
    return qualifier or None


def _is_detectable_list_page(title: str) -> bool:
    """Exclude the common explicit list-page title form from search selection."""
    return title.casefold().startswith("list of ")


def _resolved_article_from_page(
    language: str,
    requested_title: str,
    page: _PageLookup,
    method: ResolutionMethod = ResolutionMethod.INPUT_ARTICLE,
) -> ResolvedArticle:
    """Expose the canonical article and redirect provenance for one topic page."""
    return ResolvedArticle(
        language=language,
        project=f"{language}.wikipedia",
        requested_title=requested_title,
        canonical_title=page.title,
        page_id=page.page_id,
        wikidata_id=page.wikidata_id,
        url=page.url,
        resolution_method=_resolution_method_for_page(method, requested_title, page.title),
    )


def _resolved_topic_article(candidate: _TopicCandidate) -> ResolvedArticle:
    """Convert one selected topic candidate to public resolution provenance."""
    return _resolved_article_from_page(candidate.language, candidate.requested_title, candidate.page)


def _topic_clarification(
    topic: str,
    language: str,
    candidate_count: int,
    reason: str,
    selection_method: TopicSelectionMethod = TopicSelectionMethod.MEDIAWIKI_SEMANTIC_EVIDENCE,
    *,
    source_language: str | None = None,
    canonical_concept_ids: Sequence[str] = (),
    candidate_evidence: Sequence[TopicCandidateEvidence] = (),
) -> TopicResolution:
    """Construct one structured topic clarification result without selecting pages."""
    return TopicResolution(
        requested_topic=topic,
        language=language,
        status=ResolutionStatus.REQUIRES_CLARIFICATION,
        candidate_count=candidate_count,
        selection_method=selection_method,
        clarification=ResolutionClarification(language=language, title=topic, reason=reason),
        source_language=source_language or language,
        canonical_concept_ids=list(canonical_concept_ids),
        candidate_evidence=list(candidate_evidence),
    )


def _parse_page_lookup(payload: Mapping[str, object], language: str) -> _PageLookup | None:
    query = _require_mapping(payload.get("query"), "MediaWiki response must contain a query object")
    raw_pages = query.get("pages")
    if not isinstance(raw_pages, list) or len(raw_pages) != 1:
        raise ArticleResolverError("MediaWiki response must contain exactly one page")
    page = _require_mapping(raw_pages[0], "MediaWiki response contains an invalid page")
    if page.get("missing") is True:
        return None
    title = _require_text(page.get("title"), "MediaWiki page has an invalid title")
    page_id = page.get("pageid")
    if isinstance(page_id, bool) or not isinstance(page_id, int) or page_id <= 0:
        raise ArticleResolverError("MediaWiki page has an invalid page ID")
    url = _require_text(page.get("fullurl"), "MediaWiki page has no canonical URL")
    pageprops = _optional_mapping(page.get("pageprops"), "MediaWiki page has invalid page properties")
    wikidata_id = _optional_text(pageprops.get("wikibase_item"))
    raw_links = page.get("langlinks", [])
    if not isinstance(raw_links, list):
        raise ArticleResolverError("MediaWiki page has invalid language links")
    language_links: dict[str, str] = {}
    for raw_link in raw_links:
        link = _require_mapping(raw_link, "MediaWiki page contains an invalid language link")
        linked_language = _require_text(link.get("lang"), "MediaWiki language link has an invalid language")
        linked_title = _optional_text(link.get("title")) or _optional_text(link.get("*"))
        if linked_title is None:
            raise ArticleResolverError("MediaWiki language link has an invalid title")
        language_links[linked_language] = linked_title
    return _PageLookup(
        title=title,
        page_id=page_id,
        url=url,
        wikidata_id=wikidata_id,
        language_links=language_links,
        is_disambiguation="disambiguation" in pageprops,
    )


def _parse_sitelinks(payload: Mapping[str, object], wikidata_id: str) -> Mapping[str, str]:
    entities = _require_mapping(payload.get("entities"), "Wikidata response must contain entities")
    entity = _require_mapping(entities.get(wikidata_id), "Wikidata response has no requested entity")
    sitelinks = _optional_mapping(entity.get("sitelinks"), "Wikidata entity has invalid sitelinks")
    parsed_sitelinks: dict[str, str] = {}
    for site, raw_sitelink in sitelinks.items():
        sitelink = _require_mapping(raw_sitelink, "Wikidata entity contains an invalid sitelink")
        title = _require_text(sitelink.get("title"), "Wikidata sitelink has an invalid title")
        parsed_sitelinks[site] = title
    return parsed_sitelinks


def _parse_semantic_metadata(
    payload: Mapping[str, object],
    wikidata_id: str,
    source_language: str,
) -> _SemanticMetadata:
    """Read source-language labels, aliases, and descriptions with English fallback."""
    entities = _require_mapping(payload.get("entities"), "Wikidata response must contain entities")
    entity = _require_mapping(entities.get(wikidata_id), "Wikidata response has no requested entity")
    used_languages: list[str] = []

    def localized_value(field: str) -> str | None:
        localized = _optional_mapping(entity.get(field), f"Wikidata entity has invalid {field}")
        for language in (source_language, "en") if source_language != "en" else ("en",):
            raw_value = localized.get(language)
            if raw_value is None:
                continue
            value = _require_mapping(raw_value, f"Wikidata {field} entry is invalid").get("value")
            parsed = _optional_text(value)
            used_languages.append(language)
            return parsed
        return None

    def localized_aliases() -> tuple[str, ...]:
        aliases_by_language = _optional_mapping(entity.get("aliases"), "Wikidata entity has invalid aliases")
        for language in (source_language, "en") if source_language != "en" else ("en",):
            raw_aliases = aliases_by_language.get(language)
            if raw_aliases is None:
                continue
            if not isinstance(raw_aliases, list):
                raise ArticleResolverError("Wikidata aliases entry is invalid")
            aliases = tuple(
                _require_text(
                    _require_mapping(item, "Wikidata alias is invalid").get("value"), "Wikidata alias is invalid"
                )
                for item in raw_aliases
            )
            if aliases:
                used_languages.append(language)
            return aliases
        return ()

    return _SemanticMetadata(
        label=localized_value("labels"),
        aliases=localized_aliases(),
        description=(description,) if (description := localized_value("descriptions")) is not None else (),
        metadata_languages=tuple(dict.fromkeys(used_languages)),
        wikidata_id=wikidata_id,
    )


def _candidate_for_language(
    language: str,
    source_language: str,
    source_page: _PageLookup,
    sitelinks: Mapping[str, str],
) -> tuple[str | None, ResolutionMethod | None]:
    if language == source_language:
        return source_page.title, ResolutionMethod.INPUT_ARTICLE
    if (sitelink_title := sitelinks.get(f"{language}wiki")) is not None:
        return sitelink_title, ResolutionMethod.WIKIDATA_SITELINK
    if (language_link_title := source_page.language_links.get(language)) is not None:
        return language_link_title, ResolutionMethod.LANGUAGE_LINK
    return None, None


def _resolution_method_for_page(
    initial_method: ResolutionMethod,
    requested_title: str,
    canonical_title: str,
) -> ResolutionMethod:
    if initial_method is ResolutionMethod.INPUT_ARTICLE and requested_title != canonical_title:
        return ResolutionMethod.REDIRECT
    return initial_method


def _clarification_result(
    requested_title: str,
    source_language: str,
    page: _PageLookup,
    language: str | None = None,
) -> ArticleResolution:
    clarification_language = language or source_language
    return ArticleResolution(
        requested_title=requested_title,
        source_language=source_language,
        status=ResolutionStatus.REQUIRES_CLARIFICATION,
        clarification=ResolutionClarification(
            language=clarification_language,
            title=page.title,
            reason="disambiguation_page",
        ),
    )


def _missing_equivalent(
    language: str, requested_title: str, reason: str = "no_linked_article"
) -> MissingLanguageEquivalent:
    return MissingLanguageEquivalent(
        language=language,
        project=f"{language}.wikipedia",
        requested_title=requested_title,
        reason=reason,
    )


def _resolve_source_language(source_language: str | None, languages: list[str]) -> str:
    if source_language is not None:
        return _validate_language(source_language)
    if len(languages) == 1:
        return languages[0]
    raise ValueError("'source_language' is required when resolving multiple language editions")


def _resolve_topic_source_language(source_language: str | None, languages: list[str]) -> str:
    """Infer a one-edition topic source or raise a machine-identifiable error."""
    if source_language is None and len(languages) > 1:
        raise TopicSourceLanguageRequiredError
    return _resolve_source_language(source_language, languages)


def _validate_languages(languages: Sequence[str]) -> list[str]:
    if not languages:
        raise ValueError("'languages' must contain at least one language code")
    validated = [_validate_language(language) for language in languages]
    if len(validated) != len(set(validated)):
        raise ValueError("'languages' must not contain duplicates")
    return validated


def _validate_language(value: str) -> str:
    normalized = _require_nonblank_text(value, "language")
    if _LANGUAGE_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"invalid language code '{value}'")
    return normalized


def _mediawiki_url(language: str) -> str:
    return f"https://{language}.wikipedia.org/w/api.php"


def _require_nonblank_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise ValueError(f"'{field_name}' must be a non-blank string")
    return normalized


def _require_text(value: object, message: str) -> str:
    if not isinstance(value, str) or not value:
        raise ArticleResolverError(message)
    return value


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _require_mapping(value: object, message: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ArticleResolverError(message)
    return value


def _optional_mapping(value: object, message: str) -> Mapping[str, object]:
    if value is None:
        return {}
    return _require_mapping(value, message)
