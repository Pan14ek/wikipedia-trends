"""Safe local JSON cache primitives for Wikimedia request and resolution results."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from wiki_trends.models import Granularity

__all__ = [
    "CacheNamespace",
    "CacheRetrieval",
    "FilesystemCache",
    "default_cache_path",
    "pageviews_ttl",
]

_CACHE_DIRECTORY_ENVIRONMENT_VARIABLE: Final = "WIKIPEDIA_TRENDS_CACHE_DIR"
_DEFAULT_CACHE_PATH: Final = Path(".cache/wikipedia")
_HISTORICAL_PAGEVIEWS_TTL: Final = timedelta(days=30)
_RECENT_PAGEVIEWS_TTL: Final = timedelta(hours=24)
_RESOLUTION_TTL: Final = timedelta(days=7)

CacheRetrieval = Literal["network", "cache"]


class CacheNamespace(StrEnum):
    """Stable directory names for independently shaped external results."""

    ARTICLE_PAGEVIEWS = "article-pageviews"
    PROJECT_PAGEVIEWS = "project-pageviews"
    RESOLUTION = "resolution"


class FilesystemCache:
    """Best-effort cache with canonical SHA-256 keys and atomic JSON writes.

    Cache reads and writes intentionally never raise operational filesystem
    errors to callers. A live Wikimedia request remains the source of truth
    whenever local cache state is unavailable, stale, or malformed.
    """

    def __init__(
        self,
        root: Path | None = None,
        *,
        enabled: bool = True,
        now: Callable[[], datetime] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Configure an optional cache location and injectable clock for tests."""
        self._root = root or default_cache_path()
        self._enabled = enabled
        self._now = now or (lambda: datetime.now(UTC))
        self._logger = logger or logging.getLogger(__name__)

    def load(
        self,
        namespace: CacheNamespace,
        request_fields: Mapping[str, object],
        ttl: timedelta,
    ) -> object | None:
        """Return a fresh payload for the canonical request fields, if present."""
        if not self._enabled:
            return None
        serialized_key = _canonical_json(request_fields)
        path = self._entry_path(namespace, serialized_key)
        try:
            raw_entry = json.loads(path.read_text(encoding="utf-8"))
            cached_at, payload, entry_key = _validate_entry(raw_entry)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            if path.exists():
                self._logger.warning("Ignoring unreadable Wikipedia cache entry", extra={"namespace": namespace.value})
                self._discard(path)
            else:
                self._logger.debug("Wikipedia cache miss", extra={"namespace": namespace.value})
            del error
            return None
        if entry_key != serialized_key or self._now() - cached_at > ttl:
            self._logger.debug("Wikipedia cache entry is stale", extra={"namespace": namespace.value})
            return None
        self._logger.debug("Wikipedia cache hit", extra={"namespace": namespace.value})
        return payload

    def store(self, namespace: CacheNamespace, request_fields: Mapping[str, object], payload: object) -> None:
        """Atomically persist a JSON-compatible payload without failing callers."""
        if not self._enabled:
            return
        serialized_key = _canonical_json(request_fields)
        path = self._entry_path(namespace, serialized_key)
        entry = {"cached_at": self._now().isoformat(), "key": serialized_key, "payload": payload}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.stem}-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                json.dump(entry, temporary_file, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                temporary_path = Path(temporary_file.name)
            os.replace(temporary_path, path)
        except (OSError, TypeError, ValueError) as error:
            self._logger.warning("Could not write Wikipedia cache entry", extra={"namespace": namespace.value})
            if "temporary_path" in locals():
                self._discard(temporary_path)
            del error

    def discard(self, namespace: CacheNamespace, request_fields: Mapping[str, object]) -> None:
        """Best-effort removal of an invalid entry so the next request can refill it."""
        if self._enabled:
            self._discard(self._entry_path(namespace, _canonical_json(request_fields)))

    def _entry_path(self, namespace: CacheNamespace, serialized_key: str) -> Path:
        """Map canonical request content to an opaque stable cache filename."""
        digest = hashlib.sha256(serialized_key.encode("utf-8")).hexdigest()
        return self._root / namespace.value / f"{digest}.json"

    def _discard(self, path: Path) -> None:
        """Remove one unusable file while preserving cache-failure transparency."""
        try:
            path.unlink(missing_ok=True)
        except OSError:
            self._logger.warning("Could not remove Wikipedia cache entry")


def default_cache_path() -> Path:
    """Return the optional environment override or the repository-local cache root."""
    configured_path = os.getenv(_CACHE_DIRECTORY_ENVIRONMENT_VARIABLE)
    return Path(configured_path) if configured_path else _DEFAULT_CACHE_PATH


def pageviews_ttl(
    end_period: date,
    reference_date: date | None = None,
    granularity: Granularity = Granularity.MONTHLY,
) -> timedelta:
    """Choose a freshness window suitable for recent or historical buckets."""
    reference = reference_date or date.today()
    if granularity is Granularity.DAILY:
        return _RECENT_PAGEVIEWS_TTL if end_period >= reference - timedelta(days=2) else _HISTORICAL_PAGEVIEWS_TTL
    if end_period.day != 1:
        raise ValueError("monthly 'end_period' must identify the first day of a month")
    latest_complete_month = _previous_month(reference)
    earliest_recent_month = _previous_month(latest_complete_month)
    return _RECENT_PAGEVIEWS_TTL if end_period >= earliest_recent_month else _HISTORICAL_PAGEVIEWS_TTL


def resolution_ttl() -> timedelta:
    """Return the fixed freshness period for MediaWiki and Wikidata metadata."""
    return _RESOLUTION_TTL


def _canonical_json(request_fields: Mapping[str, object]) -> str:
    """Canonicalize JSON-compatible request dimensions before hashing."""
    try:
        return json.dumps(request_fields, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as error:
        raise ValueError("cache request fields must be JSON serializable") from error


def _validate_entry(raw_entry: object) -> tuple[datetime, object, str]:
    """Validate cache envelope shape before its payload is trusted by a client."""
    if not isinstance(raw_entry, dict):
        raise ValueError("cache entry must be a JSON object")
    cached_at = raw_entry.get("cached_at")
    entry_key = raw_entry.get("key")
    if not isinstance(cached_at, str) or not isinstance(entry_key, str) or "payload" not in raw_entry:
        raise ValueError("cache entry is missing required metadata")
    parsed_timestamp = datetime.fromisoformat(cached_at)
    if parsed_timestamp.tzinfo is None:
        raise ValueError("cache entry timestamp must include a timezone")
    return parsed_timestamp.astimezone(UTC), raw_entry["payload"], entry_key


def _previous_month(value: date) -> date:
    """Return the first day of the complete calendar month preceding ``value``."""
    return date(value.year - 1, 12, 1) if value.month == 1 else date(value.year, value.month - 1, 1)
