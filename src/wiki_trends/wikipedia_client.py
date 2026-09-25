"""HTTP access to Wikimedia's monthly article and project Pageviews APIs."""

from __future__ import annotations

import calendar
import logging
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Final
from urllib.parse import quote

import httpx

from wiki_trends.cache import CacheNamespace, CacheRetrieval, FilesystemCache, pageviews_ttl
from wiki_trends.models import Granularity, MonthlyPageview, ObservationStatus

__all__ = [
    "WikimediaError",
    "WikimediaNotFoundError",
    "WikimediaPageviewsClient",
    "WikimediaRateLimitError",
    "WikimediaUnavailableError",
    "PageviewsFetchResult",
]

_ARTICLE_API_BASE_URL: Final = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
_PROJECT_API_BASE_URL: Final = "https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate"
_DEFAULT_TIMEOUT_SECONDS: Final = 10.0
_DEFAULT_MAX_ATTEMPTS: Final = 3
_DEFAULT_USER_AGENT: Final = "WikipediaTrends/0.1.0 (https://www.mediawiki.org/wiki/Analytics/AQS/Pageviews)"
_MONTH_PATTERN: Final = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})$")


class WikimediaError(RuntimeError):
    """Base exception for failures communicating with the Wikimedia API."""


class WikimediaNotFoundError(WikimediaError):
    """Raised when Wikimedia reports that the requested article has no endpoint."""


class WikimediaRateLimitError(WikimediaError):
    """Raised after the configured retry budget is exhausted by HTTP 429."""


class WikimediaUnavailableError(WikimediaError):
    """Raised when a transient Wikimedia or transport failure cannot be recovered."""


@dataclass(frozen=True)
class PageviewsFetchResult:
    """Calendar-complete pageviews together with their network/cache provenance."""

    observations: list[MonthlyPageview]
    retrieval: CacheRetrieval


class WikimediaPageviewsClient:
    """Fetch complete monthly article and project pageview series from Wikimedia.

    The client owns retry policy for its one HTTP boundary.  Supplying an
    ``http_client`` and ``sleep`` function makes tests deterministic without
    changing production behavior.  An injected HTTP client remains owned by
    its caller and is never closed here.
    """

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
        user_agent: str = _DEFAULT_USER_AGENT,
        sleep: Callable[[float], None] = time.sleep,
        logger: logging.Logger | None = None,
        cache: FilesystemCache | None = None,
    ) -> None:
        """Initialize the client and its bounded retry policy.

        Args:
            http_client: Optional client used for requests and test transports.
            timeout_seconds: Per-attempt request timeout, in seconds.
            max_attempts: Total attempts, including the first request.
            user_agent: Value sent in every Wikimedia request.
            sleep: Delay function used between retry attempts.
            logger: Optional standard-library logger for retry diagnostics.
            cache: Optional local cache. An injected HTTP client disables the
                default cache unless a cache is explicitly supplied.

        Raises:
            ValueError: If timeout, attempts, or user agent is invalid.
        """
        if timeout_seconds <= 0:
            raise ValueError("'timeout_seconds' must be positive")
        if max_attempts < 1:
            raise ValueError("'max_attempts' must be at least 1")
        if not user_agent.strip():
            raise ValueError("'user_agent' must not be blank")

        self._client = http_client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = http_client is None
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._user_agent = user_agent
        self._sleep = sleep
        self._logger = logger or logging.getLogger(__name__)
        self._cache = cache if cache is not None else (None if http_client is not None else FilesystemCache())

    def __enter__(self) -> WikimediaPageviewsClient:
        """Enter a context that closes a client owned by this instance."""
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the internally created HTTP client when leaving a context."""
        del exception_type, exception, traceback
        self.close()

    def close(self) -> None:
        """Close the HTTP client only when this instance created it."""
        if self._owns_client:
            self._client.close()

    def get_article_pageviews(
        self,
        project: str,
        article: str,
        start_month: str | date,
        end_month: str | date,
        *,
        granularity: Granularity = Granularity.MONTHLY,
    ) -> list[MonthlyPageview]:
        """Return one observation for each requested day or calendar month.

        ``start_month`` and ``end_month`` accept ``YYYY-MM`` or a first-day
        ISO date (``YYYY-MM-01``).  Missing API records are represented as
        ``UNKNOWN`` instead of being converted to zero.

        Raises:
            ValueError: If an argument cannot identify a valid month range.
            WikimediaNotFoundError: If the API returns HTTP 404.
            WikimediaRateLimitError: If all attempts receive HTTP 429.
            WikimediaUnavailableError: If timeout, transport, or 5xx retries fail.
            WikimediaError: If Wikimedia returns another error or malformed data.
        """
        return self.get_article_pageviews_result(
            project,
            article,
            start_month,
            end_month,
            granularity=granularity,
        ).observations

    def get_article_pageviews_result(
        self,
        project: str,
        article: str,
        start_month: str | date,
        end_month: str | date,
        *,
        granularity: Granularity = Granularity.MONTHLY,
    ) -> PageviewsFetchResult:
        """Return article pageviews with explicit provenance for report sources."""
        validated_project = _require_nonblank_text(project, "project")
        validated_article = _require_nonblank_text(article, "article")
        start, end = _parse_period(start_month, end_month, granularity)
        if end < start:
            raise ValueError("'end_month' must not be earlier than 'start_month'")
        fields = _article_cache_fields(validated_project, validated_article, start, end, granularity)
        cached = self._load_cached_observations(CacheNamespace.ARTICLE_PAGEVIEWS, fields, start, end, granularity)
        if cached is not None:
            return PageviewsFetchResult(cached, "cache")

        payload = _response_payload(
            self._get_with_retries(_build_endpoint(validated_project, validated_article, start, end, granularity))
        )
        observations = _parse_observation_payload(payload, granularity)
        self._store_payload(CacheNamespace.ARTICLE_PAGEVIEWS, fields, payload)
        completed_observations = _complete_observation_range(observations, start, end, granularity)
        return PageviewsFetchResult(completed_observations, "network")

    def get_project_pageviews(
        self,
        project: str,
        start_month: str | date,
        end_month: str | date,
        *,
        granularity: Granularity = Granularity.MONTHLY,
    ) -> list[MonthlyPageview]:
        """Return one project-total observation for every requested calendar month.

        The aggregate endpoint uses the same ``all-access`` and ``user``
        dimensions as article collection so normalized values compare like
        traffic. Missing API records remain ``UNKNOWN``; the client never
        interpolates project totals.

        Args:
            project: Wikimedia project identifier, such as ``uk.wikipedia``.
            start_month: First requested month as ``YYYY-MM`` or ``YYYY-MM-01``.
            end_month: Final requested month as ``YYYY-MM`` or ``YYYY-MM-01``.

        Returns:
            A calendar-complete series with explicit unknown observations for
            months omitted by Wikimedia.

        Raises:
            ValueError: If an argument cannot identify a valid month range.
            WikimediaNotFoundError: If the aggregate endpoint returns HTTP 404.
            WikimediaRateLimitError: If all attempts receive HTTP 429.
            WikimediaUnavailableError: If timeout, transport, or 5xx retries fail.
            WikimediaError: If Wikimedia returns another error or malformed data.
        """
        return self.get_project_pageviews_result(
            project,
            start_month,
            end_month,
            granularity=granularity,
        ).observations

    def get_project_pageviews_result(
        self,
        project: str,
        start_month: str | date,
        end_month: str | date,
        *,
        granularity: Granularity = Granularity.MONTHLY,
    ) -> PageviewsFetchResult:
        """Return project totals with provenance for normalized-interest sources."""
        validated_project = _require_nonblank_text(project, "project")
        start, end = _parse_period(start_month, end_month, granularity)
        if end < start:
            raise ValueError("'end_month' must not be earlier than 'start_month'")
        fields = _project_cache_fields(validated_project, start, end, granularity)
        cached = self._load_cached_observations(CacheNamespace.PROJECT_PAGEVIEWS, fields, start, end, granularity)
        if cached is not None:
            return PageviewsFetchResult(cached, "cache")

        payload = _response_payload(
            self._get_with_retries(_build_project_endpoint(validated_project, start, end, granularity))
        )
        observations = _parse_observation_payload(payload, granularity)
        self._store_payload(CacheNamespace.PROJECT_PAGEVIEWS, fields, payload)
        completed_observations = _complete_observation_range(observations, start, end, granularity)
        return PageviewsFetchResult(completed_observations, "network")

    def _load_cached_observations(
        self,
        namespace: CacheNamespace,
        fields: Mapping[str, object],
        start: date,
        end: date,
        granularity: Granularity,
    ) -> list[MonthlyPageview] | None:
        """Read valid cached API payloads and discard malformed entries safely."""
        if self._cache is None:
            return None
        payload = self._cache.load(namespace, fields, pageviews_ttl(end, granularity=granularity))
        if payload is None:
            return None
        try:
            observations = _parse_observation_payload(payload, granularity)
            return _complete_observation_range(observations, start, end, granularity)
        except WikimediaError:
            self._cache.discard(namespace, fields)
            self._logger.warning(
                "Discarding malformed cached Wikimedia pageviews", extra={"namespace": namespace.value}
            )
            return None

    def _store_payload(self, namespace: CacheNamespace, fields: Mapping[str, object], payload: object) -> None:
        """Store a successfully validated response when cache support is enabled."""
        if self._cache is not None:
            self._cache.store(namespace, fields, payload)

    def _get_with_retries(self, url: str) -> httpx.Response:
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.get(
                    url,
                    headers={"User-Agent": self._user_agent},
                    timeout=self._timeout_seconds,
                )
            except httpx.TimeoutException as error:
                if attempt == self._max_attempts:
                    raise WikimediaUnavailableError("Wikimedia request timed out after retrying") from error
                self._retry(attempt, "timeout")
                continue
            except httpx.RequestError as error:
                if attempt == self._max_attempts:
                    raise WikimediaUnavailableError("Wikimedia request failed after retrying") from error
                self._retry(attempt, "transport_error")
                continue

            if response.status_code == 200:
                return response
            if response.status_code == 404:
                raise WikimediaNotFoundError("Wikimedia could not find the requested pageviews")
            if response.status_code == 429:
                if attempt == self._max_attempts:
                    raise WikimediaRateLimitError("Wikimedia rate limit persisted after retrying")
                self._retry(attempt, "rate_limited", _retry_after_seconds(response))
                continue
            if 500 <= response.status_code <= 599:
                if attempt == self._max_attempts:
                    raise WikimediaUnavailableError(
                        f"Wikimedia returned HTTP {response.status_code} after retrying",
                    )
                self._retry(attempt, f"http_{response.status_code}")
                continue
            raise WikimediaError(f"Wikimedia returned unexpected HTTP {response.status_code}")

        raise AssertionError("retry loop must return or raise")

    def _retry(self, attempt: int, reason: str, retry_after_seconds: float | None = None) -> None:
        delay_seconds = retry_after_seconds if retry_after_seconds is not None else float(2 ** (attempt - 1))
        self._logger.warning(
            "Retrying Wikimedia pageviews request",
            extra={
                "attempt": attempt,
                "max_attempts": self._max_attempts,
                "reason": reason,
                "delay_seconds": delay_seconds,
            },
        )
        self._sleep(delay_seconds)


def _article_cache_fields(
    project: str,
    article: str,
    start: date,
    end: date,
    granularity: Granularity,
) -> dict[str, str]:
    """Return every API dimension that can alter an article pageview response."""
    return {
        "access": "all-access",
        "agent": "user",
        "article": article,
        "end": end.isoformat(),
        "granularity": granularity.value,
        "project": project,
        "start": start.isoformat(),
    }


def _project_cache_fields(
    project: str,
    start: date,
    end: date,
    granularity: Granularity,
) -> dict[str, str]:
    """Return every API dimension that can alter a project pageview response."""
    return {
        "access": "all-access",
        "agent": "user",
        "end": end.isoformat(),
        "granularity": granularity.value,
        "project": project,
        "start": start.isoformat(),
    }


def _build_endpoint(project: str, article: str, start: date, end: date, granularity: Granularity) -> str:
    """Build the exact AQS per-article endpoint for a daily or monthly range."""
    encoded_project = quote(project, safe=".-")
    encoded_article = quote(article.replace(" ", "_"), safe="")
    if granularity is Granularity.DAILY:
        start_timestamp = f"{start:%Y%m%d}"
        end_timestamp = f"{end:%Y%m%d}"
    else:
        start_timestamp = f"{start:%Y%m}0100"
        end_timestamp = f"{end:%Y%m}{calendar.monthrange(end.year, end.month)[1]:02d}00"
    return (
        f"{_ARTICLE_API_BASE_URL}/{encoded_project}/all-access/user/{encoded_article}/{granularity.value}/"
        f"{start_timestamp}/{end_timestamp}"
    )


def _build_project_endpoint(project: str, start: date, end: date, granularity: Granularity) -> str:
    """Build the exact AQS aggregate endpoint for a daily or monthly range."""
    encoded_project = quote(project, safe=".-")
    if granularity is Granularity.DAILY:
        start_timestamp = f"{start:%Y%m%d}"
        end_timestamp = f"{end:%Y%m%d}"
    else:
        start_timestamp = f"{start:%Y%m}0100"
        end_timestamp = f"{end:%Y%m}{calendar.monthrange(end.year, end.month)[1]:02d}00"
    return (
        f"{_PROJECT_API_BASE_URL}/{encoded_project}/all-access/user/{granularity.value}/"
        f"{start_timestamp}/{end_timestamp}"
    )


def _response_payload(response: httpx.Response) -> object:
    """Read JSON once from a successful HTTP response before cache persistence."""
    try:
        return response.json()
    except ValueError as error:
        raise WikimediaError("Wikimedia returned invalid JSON") from error


def _parse_observation_payload(payload: object, granularity: Granularity) -> dict[date, MonthlyPageview]:
    """Convert a network or cached API payload to typed, date-keyed buckets."""

    if not isinstance(payload, Mapping):
        raise WikimediaError("Wikimedia response must be a JSON object")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise WikimediaError("Wikimedia response must contain an 'items' list")

    observations: dict[date, MonthlyPageview] = {}
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            raise WikimediaError("Wikimedia response contains an invalid pageview item")
        timestamp = _parse_api_timestamp(raw_item.get("timestamp"), granularity)
        views = raw_item.get("views")
        if isinstance(views, bool) or not isinstance(views, int) or views < 0:
            raise WikimediaError("Wikimedia pageview item has an invalid 'views' value")
        if timestamp in observations:
            raise WikimediaError(f"Wikimedia response contains duplicate timestamp {timestamp.isoformat()}")
        observations[timestamp] = MonthlyPageview(month=timestamp, granularity=granularity, views=views)
    return observations


def _parse_api_timestamp(value: object, granularity: Granularity) -> date:
    """Parse a daily or monthly bucket encoded by Wikimedia's AQS timestamp."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{10}", value):
        raise WikimediaError("Wikimedia pageview item has an invalid 'timestamp'")
    try:
        parsed = datetime.strptime(value, "%Y%m%d%H")
    except ValueError as error:
        raise WikimediaError("Wikimedia pageview item has an invalid 'timestamp'") from error
    if parsed.hour != 0 or (granularity is Granularity.MONTHLY and parsed.day != 1):
        raise WikimediaError(f"Wikimedia {granularity.value} timestamp is not a valid bucket boundary")
    return parsed.date()


def _parse_period(start_value: str | date, end_value: str | date, granularity: Granularity) -> tuple[date, date]:
    """Parse a date range and normalize monthly inputs to month keys."""
    start = _parse_date(start_value, "start_month", granularity)
    end = _parse_date(end_value, "end_month", granularity)
    if granularity is Granularity.MONTHLY:
        start = date(start.year, start.month, 1)
        end = date(end.year, end.month, 1)
    return start, end


def _parse_date(value: str | date, field_name: str, granularity: Granularity) -> date:
    """Parse an ISO calendar date or legacy ``YYYY-MM`` month string."""
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"'{field_name}' must be an ISO calendar date")
    match = _MONTH_PATTERN.fullmatch(value)
    if match is not None and granularity is Granularity.MONTHLY:
        try:
            return date(int(match["year"]), int(match["month"]), 1)
        except ValueError as error:
            raise ValueError(f"'{field_name}' must be a valid YYYY-MM month") from error
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"'{field_name}' must be a valid ISO calendar date") from error


def _complete_observation_range(
    observations: Mapping[date, MonthlyPageview],
    start: date,
    end: date,
    granularity: Granularity,
) -> list[MonthlyPageview]:
    """Fill omitted API buckets with explicit unknowns, without imputing zeros."""
    bucket_dates = _months_inclusive(start, end) if granularity is Granularity.MONTHLY else _days_inclusive(start, end)
    return [
        observations.get(
            bucket,
            MonthlyPageview(month=bucket, granularity=granularity, status=ObservationStatus.UNKNOWN),
        )
        for bucket in bucket_dates
    ]


def _months_inclusive(start: date, end: date) -> list[date]:
    """Return canonical months from start through end, preserving request order."""
    months: list[date] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(date(year, month, 1))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _days_inclusive(start: date, end: date) -> list[date]:
    """Return every day in an inclusive date range, preserving order."""
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _require_nonblank_text(value: str, field_name: str) -> str:
    """Reject non-string or blank identifiers before making a network call."""
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise ValueError(f"'{field_name}' must be a non-blank string")
    return normalized


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Return a usable Retry-After duration, including HTTP-date values."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            return None
        seconds = (retry_at - datetime.now(UTC)).total_seconds()
    return max(0.0, seconds)
