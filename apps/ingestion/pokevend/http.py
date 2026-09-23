"""Polite HTTP client shared by every source adapter.

Enforces the ingestion rules in one place: robots.txt is consulted before any
request, requests are rate limited per host, conditional headers (ETag /
Last-Modified) avoid re-downloading unchanged pages, and failures are retried
with backoff instead of hammering the origin.

Nothing here attempts to defeat a bot-protection or authentication control. A
403/401/429 is surfaced to the caller as a skip, never worked around.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

LOGGER = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / ".cache" / "http"

# Statuses that mean "not allowed / not welcome". We stop; we do not retry.
BLOCKED_STATUSES = frozenset({401, 402, 403, 407, 451})
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class SourceSkipped(Exception):
    """Raised when a source must not be fetched.

    Carries a machine-readable reason so jobs can log SOURCE_SKIPPED and carry
    on with the remaining sources.
    """

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class FetchResult:
    """Outcome of a single fetch.

    ``not_modified`` means the cached copy is still current: the body is served
    from cache and the origin was not asked to re-send it.
    """

    def __init__(self, url: str, status: int, text: str, from_cache: bool, not_modified: bool):
        self.url = url
        self.status = status
        self.text = text
        self.from_cache = from_cache
        self.not_modified = not_modified

    def json(self) -> Any:
        return json.loads(self.text)


class PoliteSession:
    def __init__(
        self,
        user_agent: str,
        timeout_seconds: float = 20.0,
        rate_limit_seconds: float = 1.5,
        max_retries: int = 3,
        respect_robots: bool = True,
        cache_dir: Optional[Path] = None,
        session: Optional[requests.Session] = None,
    ):
        self.user_agent = user_agent
        self.timeout_seconds = float(timeout_seconds)
        self.rate_limit_seconds = float(rate_limit_seconds)
        self.max_retries = int(max_retries)
        self.respect_robots = bool(respect_robots)
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_request_at: Dict[str, float] = {}
        self._robots: Dict[str, Optional[RobotFileParser]] = {}

    # -- politeness -------------------------------------------------------
    def _throttle(self, host: str) -> None:
        last = self._last_request_at.get(host)
        if last is not None:
            wait = self.rate_limit_seconds - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request_at[host] = time.monotonic()

    def _robots_for(self, url: str) -> Optional[RobotFileParser]:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        parser = RobotFileParser()
        robots_url = origin + "/robots.txt"
        result = parser
        try:
            response = self.session.get(robots_url, timeout=self.timeout_seconds)
            if response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                # No robots.txt published: nothing is disallowed.
                result = None
        except requests.RequestException as exc:
            LOGGER.warning(
                "robots.txt unreachable for %s (%s); treating as unrestricted", origin, exc
            )
            result = None
        self._robots[origin] = result
        return result

    def is_allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parser = self._robots_for(url)
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)

    # -- conditional-request cache ---------------------------------------
    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, url: str) -> Optional[Dict[str, Any]]:
        path = self._cache_path(url)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return None

    def _write_cache(self, url: str, entry: Dict[str, Any]) -> None:
        path = self._cache_path(url)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(entry, handle)
        except OSError as exc:
            LOGGER.warning("could not write HTTP cache for %s: %s", url, exc)

    # -- fetching ---------------------------------------------------------
    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        use_cache: bool = True,
    ) -> FetchResult:
        """GET a URL, honouring robots.txt, rate limits and HTTP caching."""
        if not self.is_allowed(url):
            raise SourceSkipped(
                "ROBOTS_DISALLOWED",
                f"{url} is disallowed for {self.user_agent}",
            )

        cache_key = url if not params else url + "?" + json.dumps(params, sort_keys=True)
        cached = self._read_cache(cache_key) if use_cache else None

        request_headers = dict(headers or {})
        if cached:
            if cached.get("etag"):
                request_headers["If-None-Match"] = cached["etag"]
            if cached.get("last_modified"):
                request_headers["If-Modified-Since"] = cached["last_modified"]

        host = urlparse(url).netloc
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            self._throttle(host)
            try:
                response = self.session.get(
                    url, params=params, headers=request_headers, timeout=self.timeout_seconds
                )
            except requests.RequestException as exc:
                last_error = str(exc)
                LOGGER.warning(
                    "attempt %s/%s failed for %s: %s", attempt, self.max_retries, url, exc
                )
                time.sleep(min(2 ** attempt, 15))
                continue

            status = response.status_code

            if status == 304 and cached:
                return FetchResult(url, 304, cached.get("body", ""), True, True)

            if status in BLOCKED_STATUSES:
                raise SourceSkipped(
                    "ACCESS_DENIED",
                    f"{url} returned HTTP {status}; not circumventing",
                )

            if status in RETRY_STATUSES:
                last_error = f"HTTP {status}"
                retry_after = response.headers.get("Retry-After") or ""
                delay = float(retry_after) if retry_after.isdigit() else float(2 ** attempt)
                LOGGER.warning(
                    "attempt %s/%s got HTTP %s for %s; backing off %ss",
                    attempt, self.max_retries, status, url, delay,
                )
                time.sleep(min(delay, 30))
                continue

            if status >= 400:
                raise SourceSkipped("HTTP_ERROR", f"{url} returned HTTP {status}")

            if use_cache:
                self._write_cache(
                    cache_key,
                    {
                        "body": response.text,
                        "etag": response.headers.get("ETag"),
                        "last_modified": response.headers.get("Last-Modified"),
                    },
                )
            return FetchResult(url, status, response.text, False, False)

        if cached:
            LOGGER.warning("serving stale cache for %s after %s failures", url, self.max_retries)
            return FetchResult(url, 0, cached.get("body", ""), True, False)

        raise SourceSkipped(
            "FETCH_FAILED",
            f"{url} after {self.max_retries} attempts: {last_error}",
        )


def session_from_config(settings, cache_dir: Optional[Path] = None) -> PoliteSession:
    """Build a session from a merged per-source settings mapping."""
    return PoliteSession(
        user_agent=settings.get("user_agent", "pokemon-vending-forecast/0.1"),
        timeout_seconds=settings.get("timeout_seconds", 20),
        rate_limit_seconds=settings.get("rate_limit_seconds", 1.5),
        max_retries=settings.get("max_retries", 3),
        respect_robots=settings.get("respect_robots", True),
        cache_dir=cache_dir,
    )
