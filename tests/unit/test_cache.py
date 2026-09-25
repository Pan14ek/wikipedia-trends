"""Regression coverage for safe local Wikimedia cache behavior."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from wiki_trends.cache import CacheNamespace, FilesystemCache, pageviews_ttl
from wiki_trends.models import Granularity
from wiki_trends.wikipedia_client import WikimediaPageviewsClient


def test_article_pageviews_use_network_then_cache_with_provenance(tmp_path: Path) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"items": [{"timestamp": "2026080100", "views": 42}]})

    cache = FilesystemCache(tmp_path / "cache")
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = WikimediaPageviewsClient(http_client=http_client, cache=cache)
        first = client.get_article_pageviews_result("uk.wikipedia", "Київ", "2026-08", "2026-08")
        second = client.get_article_pageviews_result("uk.wikipedia", "Київ", "2026-08", "2026-08")

    assert calls == 1
    assert first.retrieval == "network"
    assert second.retrieval == "cache"
    assert second.observations == first.observations


def test_stale_and_corrupted_entries_are_ignored_without_preventing_refetch(tmp_path: Path) -> None:
    clock = datetime(2026, 9, 1, tzinfo=UTC)
    cache = FilesystemCache(tmp_path / "cache", now=lambda: clock)
    fields = {"project": "uk.wikipedia"}
    cache.store(CacheNamespace.PROJECT_PAGEVIEWS, fields, {"items": []})
    clock += timedelta(days=31)

    assert cache.load(CacheNamespace.PROJECT_PAGEVIEWS, fields, timedelta(days=30)) is None

    cache.store(CacheNamespace.PROJECT_PAGEVIEWS, fields, {"items": []})
    entry_path = next((tmp_path / "cache" / CacheNamespace.PROJECT_PAGEVIEWS.value).glob("*.json"))
    entry_path.write_text("{broken", encoding="utf-8")

    assert cache.load(CacheNamespace.PROJECT_PAGEVIEWS, fields, timedelta(days=30)) is None


def test_keys_do_not_collide_and_writes_leave_no_temporary_files(tmp_path: Path) -> None:
    cache = FilesystemCache(tmp_path / "cache")
    first_fields = {"article": "Kyiv", "project": "en.wikipedia"}
    second_fields = {"article": "Kyiv", "project": "uk.wikipedia"}
    cache.store(CacheNamespace.ARTICLE_PAGEVIEWS, first_fields, {"items": [1]})
    cache.store(CacheNamespace.ARTICLE_PAGEVIEWS, second_fields, {"items": [2]})

    namespace_path = tmp_path / "cache" / CacheNamespace.ARTICLE_PAGEVIEWS.value
    assert cache.load(CacheNamespace.ARTICLE_PAGEVIEWS, first_fields, timedelta(days=1)) == {"items": [1]}
    assert cache.load(CacheNamespace.ARTICLE_PAGEVIEWS, second_fields, timedelta(days=1)) == {"items": [2]}
    assert len(list(namespace_path.glob("*.json"))) == 2
    assert not list(namespace_path.glob("*.tmp"))


def test_disabled_cache_does_not_create_entries_and_ttl_tracks_recent_months(tmp_path: Path) -> None:
    cache = FilesystemCache(tmp_path / "cache", enabled=False)
    cache.store(CacheNamespace.RESOLUTION, {"query": "Kyiv"}, {"result": "cached"})

    assert cache.load(CacheNamespace.RESOLUTION, {"query": "Kyiv"}, timedelta(days=1)) is None
    assert not (tmp_path / "cache").exists()
    assert pageviews_ttl(date(2026, 8, 1), date(2026, 9, 25)) == timedelta(hours=24)
    assert pageviews_ttl(date(2026, 6, 1), date(2026, 9, 25)) == timedelta(days=30)


def test_daily_and_monthly_ranges_have_distinct_cache_keys(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"items": [{"timestamp": "2026080100", "views": calls}]})

    cache = FilesystemCache(tmp_path / "cache")
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = WikimediaPageviewsClient(http_client=http_client, cache=cache)
        monthly = client.get_article_pageviews_result("uk.wikipedia", "Kyiv", date(2026, 8, 1), date(2026, 8, 1))
        daily = client.get_article_pageviews_result(
            "uk.wikipedia",
            "Kyiv",
            date(2026, 8, 1),
            date(2026, 8, 1),
            granularity=Granularity.DAILY,
        )

    assert calls == 2
    assert monthly.observations[0].granularity is Granularity.MONTHLY
    assert daily.observations[0].granularity is Granularity.DAILY
