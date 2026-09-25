"""Mocked integration coverage for the Wikimedia monthly Pageviews client."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx
import pytest

from wiki_trends.models import Granularity, ObservationStatus
from wiki_trends.wikipedia_client import (
    WikimediaNotFoundError,
    WikimediaPageviewsClient,
    WikimediaRateLimitError,
    WikimediaUnavailableError,
)

FIXTURES_DIRECTORY = Path(__file__).resolve().parents[1] / "fixtures"
RequestHandler = Callable[[httpx.Request], httpx.Response]


def test_successful_24_month_response_maps_every_observation() -> None:
    payload = json.loads((FIXTURES_DIRECTORY / "pageviews_24_months.json").read_text(encoding="utf-8"))
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = WikimediaPageviewsClient(http_client=http_client)
        observations = client.get_article_pageviews("uk.wikipedia", "Astronomy", "2024-09", "2026-08")

    assert len(observations) == 24
    assert observations[0].month == date(2024, 9, 1)
    assert observations[0].views == 101
    assert observations[-1].month == date(2026, 8, 1)
    assert observations[-1].views == 124
    assert all(item.status is ObservationStatus.OBSERVED for item in observations)
    assert requests[0].headers["User-Agent"].startswith("WikipediaTrends/")


def test_endpoint_percent_encodes_spaces_slashes_and_non_ascii_article_titles() -> None:
    raw_paths: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw_paths.append(request.url.raw_path)
        return httpx.Response(200, json={"items": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = WikimediaPageviewsClient(http_client=http_client)
        client.get_article_pageviews("uk.wikipedia", "Космос / Space", "2026-01", "2026-01")

    assert raw_paths == [
        b"/api/rest_v1/metrics/pageviews/per-article/uk.wikipedia/all-access/user/"
        b"%D0%9A%D0%BE%D1%81%D0%BC%D0%BE%D1%81_%2F_Space/monthly/2026010100/2026013100",
    ]


def test_project_pageviews_use_aggregate_endpoint_and_fill_missing_months() -> None:
    raw_paths: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw_paths.append(request.url.raw_path)
        return httpx.Response(
            200,
            json={
                "items": [
                    {"timestamp": "2026010100", "views": 1_000},
                    {"timestamp": "2026030100", "views": 3_000},
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        observations = WikimediaPageviewsClient(http_client=http_client).get_project_pageviews(
            "uk.wikipedia",
            "2026-01",
            "2026-03",
        )

    assert raw_paths == [
        b"/api/rest_v1/metrics/pageviews/aggregate/uk.wikipedia/all-access/user/monthly/2026010100/2026033100",
    ]
    assert [(item.month, item.views, item.status) for item in observations] == [
        (date(2026, 1, 1), 1_000, ObservationStatus.OBSERVED),
        (date(2026, 2, 1), None, ObservationStatus.UNKNOWN),
        (date(2026, 3, 1), 3_000, ObservationStatus.OBSERVED),
    ]


def test_daily_article_endpoint_honors_exact_dates_and_marks_missing_days_unknown() -> None:
    raw_paths: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw_paths.append(request.url.raw_path)
        return httpx.Response(
            200,
            json={
                "items": [
                    {"timestamp": "2026080100", "views": 25},
                    {"timestamp": "2026080300", "views": 40},
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        observations = WikimediaPageviewsClient(http_client=http_client).get_article_pageviews(
            "uk.wikipedia",
            "Аніме",
            date(2026, 8, 1),
            date(2026, 8, 3),
            granularity=Granularity.DAILY,
        )

    assert raw_paths == [
        b"/api/rest_v1/metrics/pageviews/per-article/uk.wikipedia/all-access/user/"
        b"%D0%90%D0%BD%D1%96%D0%BC%D0%B5/daily/20260801/20260803",
    ]
    assert [(item.month, item.views, item.status, item.granularity) for item in observations] == [
        (date(2026, 8, 1), 25, ObservationStatus.OBSERVED, Granularity.DAILY),
        (date(2026, 8, 2), None, ObservationStatus.UNKNOWN, Granularity.DAILY),
        (date(2026, 8, 3), 40, ObservationStatus.OBSERVED, Granularity.DAILY),
    ]


def test_daily_project_pageviews_use_daily_aggregate_endpoint() -> None:
    raw_paths: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw_paths.append(request.url.raw_path)
        return httpx.Response(200, json={"items": [{"timestamp": "2026080100", "views": 1000}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        observations = WikimediaPageviewsClient(http_client=http_client).get_project_pageviews(
            "ja.wikipedia",
            "2026-08-01",
            "2026-08-01",
            granularity=Granularity.DAILY,
        )

    assert raw_paths == [
        b"/api/rest_v1/metrics/pageviews/aggregate/ja.wikipedia/all-access/user/daily/20260801/20260801",
    ]
    assert len(observations) == 1
    assert observations[0].views == 1000
def test_absent_api_month_becomes_unknown_in_complete_requested_range() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {"timestamp": "2026010100", "views": 20},
                    {"timestamp": "2026030100", "views": 40},
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        observations = WikimediaPageviewsClient(http_client=http_client).get_article_pageviews(
            "uk.wikipedia",
            "Astronomy",
            "2026-01-01",
            "2026-03-01",
        )

    assert [(item.month, item.views, item.status) for item in observations] == [
        (date(2026, 1, 1), 20, ObservationStatus.OBSERVED),
        (date(2026, 2, 1), None, ObservationStatus.UNKNOWN),
        (date(2026, 3, 1), 40, ObservationStatus.OBSERVED),
    ]


def test_not_found_is_explicit_and_not_retried() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = WikimediaPageviewsClient(http_client=http_client, sleep=lambda _: pytest.fail("must not retry 404"))
        with pytest.raises(WikimediaNotFoundError, match="could not find"):
            client.get_article_pageviews("uk.wikipedia", "Missing", "2026-01", "2026-01")

    assert calls == 1


def test_rate_limit_retries_after_server_delay_then_succeeds() -> None:
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json={"items": [{"timestamp": "2026010100", "views": 10}]}),
        ],
    )
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        return next(responses)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = WikimediaPageviewsClient(http_client=http_client, sleep=delays.append).get_article_pageviews(
            "uk.wikipedia",
            "Astronomy",
            "2026-01",
            "2026-01",
        )

    assert result[0].views == 10
    assert delays == [7.0]


def test_persistent_rate_limit_exhausts_the_bounded_retry_budget() -> None:
    calls = 0
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = WikimediaPageviewsClient(http_client=http_client, sleep=delays.append)
        with pytest.raises(WikimediaRateLimitError, match="rate limit"):
            client.get_article_pageviews("uk.wikipedia", "Astronomy", "2026-01", "2026-01")

    assert calls == 3
    assert delays == [1.0, 2.0]


def test_server_error_retries_then_succeeds() -> None:
    responses = iter(
        [
            httpx.Response(500),
            httpx.Response(200, json={"items": [{"timestamp": "2026010100", "views": 10}]}),
        ],
    )
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        return next(responses)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = WikimediaPageviewsClient(http_client=http_client, sleep=delays.append).get_article_pageviews(
            "uk.wikipedia",
            "Astronomy",
            "2026-01",
            "2026-01",
        )

    assert result[0].views == 10
    assert delays == [1.0]


def test_timeout_is_retried_then_translated_to_domain_error() -> None:
    calls = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("simulated timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = WikimediaPageviewsClient(http_client=http_client, sleep=delays.append)
        with pytest.raises(WikimediaUnavailableError, match="timed out"):
            client.get_article_pageviews("uk.wikipedia", "Astronomy", "2026-01", "2026-01")

    assert calls == 3
    assert delays == [1.0, 2.0]
