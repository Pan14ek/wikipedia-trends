"""Resolve article queries to canonical, linked Wikipedia edition identities."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Final

import httpx

from wiki_trends.config import QueryConfig, QueryMode
from wiki_trends.models import (
    ArticleResolution,
    MissingLanguageEquivalent,
    ResolutionClarification,
    ResolutionMethod,
    ResolutionStatus,
    ResolvedArticle,
)

__all__ = [
    "ArticleNotFoundError",
    "ArticleResolver",
    "ArticleResolverError",
    "ArticleResolverUnavailableError",
]

_DEFAULT_TIMEOUT_SECONDS: Final = 10.0
_DEFAULT_USER_AGENT: Final = "WikipediaTrends/0.1.0 (https://www.mediawiki.org/wiki/API:Main_page)"
_LANGUAGE_PATTERN: Final = re.compile(r"^[a-z][a-z0-9-]*$")


class ArticleResolverError(RuntimeError):
    """Base exception for invalid or malformed article-resolution operations."""


class ArticleNotFoundError(ArticleResolverError):
    """Raised when the requested source article does not exist."""


class ArticleResolverUnavailableError(ArticleResolverError):
    """Raised when a MediaWiki or Wikidata request cannot be completed."""


class ArticleResolver:
    """Resolve one concrete Wikipedia article across requested language editions.

    The resolver keeps all HTTP calls at this boundary and relies only on
    MediaWiki language links and Wikidata sitelinks; it never translates or
    searches titles heuristically. An injected HTTP client remains owned by its
    caller, which keeps mocked integration tests deterministic.
    """

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = _DEFAULT_USER_AGENT,
        logger: logging.Logger | None = None,
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

    def resolve(self, query: QueryConfig, languages: Sequence[str]) -> ArticleResolution:
        """Resolve an article-mode configuration to canonical edition articles.

        A single requested language is sufficient to infer the source language.
        Multi-language inputs must set ``query.source_language`` explicitly,
        because guessing which edition owns a title can select a different
        concept.

        Raises:
            ArticleResolverError: If the query is not an article or source page is absent.
            ValueError: If requested languages cannot safely identify a source.
        """
        if query.mode is not QueryMode.ARTICLE:
            raise ArticleResolverError("article resolution only supports query.mode='article'")
        return self.resolve_article(query.value, languages, source_language=query.source_language)

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
        return _parse_sitelinks(payload, wikidata_id)

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
