"""HTTP access to Wikimedia's monthly article and project Pageviews APIs."""

from __future__ import annotations

import calendar
import logging
import re
import time
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Final
from urllib.parse import quote

import httpx

from wiki_trends.models import MonthlyPageview, ObservationStatus

__all__ = [
    "WikimediaError",
    "WikimediaNotFoundError",
    "WikimediaPageviewsClient",
    "WikimediaRateLimitError",
    "WikimediaUnavailableError",
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
    ) -> None:
        """Initialize the client and its bounded retry policy.

        Args:
            http_client: Optional client used for requests and test transports.
            timeout_seconds: Per-attempt request timeout, in seconds.
            max_attempts: Total attempts, including the first request.
            user_agent: Value sent in every Wikimedia request.
            sleep: Delay function used between retry attempts.
            logger: Optional standard-library logger for retry diagnostics.

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
        start_month: str,
        end_month: str,
    ) -> list[MonthlyPageview]:
        """Return one observation for every requested calendar month.

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
        validated_project = _require_nonblank_text(project, "project")
        validated_article = _require_nonblank_text(article, "article")
        start = _parse_month(start_month, "start_month")
        end = _parse_month(end_month, "end_month")
        if end < start:
            raise ValueError("'end_month' must not be earlier than 'start_month'")

        response = self._get_with_retries(
            _build_endpoint(validated_project, validated_article, start, end),
        )
        observations = _parse_observations(response)
        return [
            observations.get(
                month,
                MonthlyPageview(month=month, status=ObservationStatus.UNKNOWN),
            )
            for month in _months_inclusive(start, end)
        ]

    def get_project_pageviews(
        self,
        project: str,
        start_month: str,
        end_month: str,
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
        validated_project = _require_nonblank_text(project, "project")
        start = _parse_month(start_month, "start_month")
        end = _parse_month(end_month, "end_month")
        if end < start:
            raise ValueError("'end_month' must not be earlier than 'start_month'")

        response = self._get_with_retries(_build_project_endpoint(validated_project, start, end))
        observations = _parse_observations(response)
        return [
            observations.get(
                month,
                MonthlyPageview(month=month, status=ObservationStatus.UNKNOWN),
            )
            for month in _months_inclusive(start, end)
        ]

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


def _build_endpoint(project: str, article: str, start: date, end: date) -> str:
    """Build the exact AQS per-article monthly endpoint for a date range."""
    encoded_project = quote(project, safe=".-")
    encoded_article = quote(article.replace(" ", "_"), safe="")
    start_timestamp = f"{start:%Y%m}0100"
    end_timestamp = f"{end:%Y%m}{calendar.monthrange(end.year, end.month)[1]:02d}00"
    return (
        f"{_ARTICLE_API_BASE_URL}/{encoded_project}/all-access/user/{encoded_article}/monthly/"
        f"{start_timestamp}/{end_timestamp}"
    )


def _build_project_endpoint(project: str, start: date, end: date) -> str:
    """Build the exact AQS aggregate monthly endpoint for a date range."""
    encoded_project = quote(project, safe=".-")
    start_timestamp = f"{start:%Y%m}0100"
    end_timestamp = f"{end:%Y%m}{calendar.monthrange(end.year, end.month)[1]:02d}00"
    return f"{_PROJECT_API_BASE_URL}/{encoded_project}/all-access/user/monthly/{start_timestamp}/{end_timestamp}"


def _parse_observations(response: httpx.Response) -> dict[date, MonthlyPageview]:
    """Convert the API payload to validated records keyed by calendar month."""
    try:
        payload: object = response.json()
    except ValueError as error:
        raise WikimediaError("Wikimedia returned invalid JSON") from error

    if not isinstance(payload, Mapping):
        raise WikimediaError("Wikimedia response must be a JSON object")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise WikimediaError("Wikimedia response must contain an 'items' list")

    observations: dict[date, MonthlyPageview] = {}
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            raise WikimediaError("Wikimedia response contains an invalid pageview item")
        month = _parse_api_timestamp(raw_item.get("timestamp"))
        views = raw_item.get("views")
        if isinstance(views, bool) or not isinstance(views, int) or views < 0:
            raise WikimediaError("Wikimedia pageview item has an invalid 'views' value")
        if month in observations:
            raise WikimediaError(f"Wikimedia response contains duplicate month {month.isoformat()}")
        observations[month] = MonthlyPageview(month=month, views=views)
    return observations


def _parse_api_timestamp(value: object) -> date:
    """Parse the first day of month encoded by Wikimedia's AQS timestamp."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{10}", value):
        raise WikimediaError("Wikimedia pageview item has an invalid 'timestamp'")
    try:
        parsed = datetime.strptime(value, "%Y%m%d%H")
    except ValueError as error:
        raise WikimediaError("Wikimedia pageview item has an invalid 'timestamp'") from error
    if parsed.day != 1 or parsed.hour != 0:
        raise WikimediaError("Wikimedia monthly timestamp must identify the first day at 00:00")
    return parsed.date()


def _parse_month(value: str, field_name: str) -> date:
    """Parse one public month argument to its canonical first-day date."""
    if not isinstance(value, str):
        raise ValueError(f"'{field_name}' must be a YYYY-MM string")
    match = _MONTH_PATTERN.fullmatch(value)
    if match is not None:
        try:
            return date(int(match["year"]), int(match["month"]), 1)
        except ValueError as error:
            raise ValueError(f"'{field_name}' must be a valid YYYY-MM month") from error
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"'{field_name}' must be YYYY-MM or YYYY-MM-01") from error
    if parsed.day != 1:
        raise ValueError(f"'{field_name}' must identify the first day of a month")
    return parsed


def _months_inclusive(start: date, end: date) -> list[date]:
    """Return canonical months from start through end, preserving request order."""
    months: list[date] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(date(year, month, 1))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


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
