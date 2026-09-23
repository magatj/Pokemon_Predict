"""Reddit community observations via the official API.

Compliance note, verified against the live site while building this adapter:

  * https://www.reddit.com/robots.txt is ``User-agent: * / Disallow: /``
  * unauthenticated ``.json`` endpoints return HTTP 403

HTML scraping and unauthenticated JSON are therefore both off the table. This
adapter talks only to the official OAuth API, which is an approved access
method. With no credentials in the environment it reports SOURCE_SKIPPED with
reason NO_CREDENTIALS and contributes nothing - it does not fall back to
scraping.

Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (a "script" app) to enable it.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

from pokevend.http import SourceSkipped
from pokevend.models import ObservationSource, SourceAuthority, SourceHealth, SourceStatus
from pokevend.sources.community_source import CommunityObservationSource
from pokevend.timeutil import now_utc, to_iso8601

LOGGER = logging.getLogger(__name__)


def parse_listing(payload: Any) -> List[Dict[str, Any]]:
    """Flatten a Reddit listing into source-agnostic post dicts.

    Pure function: tested against a saved fixture, no network required.
    """
    posts: List[Dict[str, Any]] = []
    if not isinstance(payload, dict):
        return posts
    children = (payload.get("data") or {}).get("children")
    if not isinstance(children, list):
        return posts

    for child in children:
        if not isinstance(child, dict):
            continue
        data = child.get("data")
        if not isinstance(data, dict):
            continue
        permalink = data.get("permalink")
        posts.append(
            {
                "id": data.get("name") or data.get("id"),
                "title": data.get("title"),
                "text": data.get("selftext"),
                "created_at": data.get("created_utc"),
                "url": f"https://www.reddit.com{permalink}" if permalink else data.get("url"),
                "has_photo": bool(data.get("post_hint") == "image" or data.get("preview")),
                "subreddit": data.get("subreddit"),
            }
        )
    return posts


class RedditSource(CommunityObservationSource):
    name = "reddit"
    authority = SourceAuthority.COMMUNITY
    observation_source = ObservationSource.REDDIT

    def __init__(self, settings: Dict[str, Any], enabled: bool = True, weight_lookup=None,
                 session: Optional[requests.Session] = None, env=None):
        super().__init__(settings, enabled=enabled, weight_lookup=weight_lookup)
        self.env = env if env is not None else os.environ
        self.session = session or requests.Session()
        self.api_base_url = str(self.setting("api_base_url", "https://oauth.reddit.com"))
        self.token_url = str(
            self.setting("oauth_token_url", "https://www.reddit.com/api/v1/access_token")
        )
        self.user_agent = str(self.setting("user_agent", "pokemon-vending-forecast/0.1"))
        self.timeout = float(self.setting("timeout_seconds", 20))
        self.subreddits = list(self.setting("subreddits", []) or [])
        self.queries = list(self.setting("queries", []) or [])
        self._token: Optional[str] = None

    # -- credentials ------------------------------------------------------
    def _credentials(self):
        client_id = self.env.get(str(self.setting("client_id_env", "REDDIT_CLIENT_ID")))
        client_secret = self.env.get(
            str(self.setting("client_secret_env", "REDDIT_CLIENT_SECRET"))
        )
        return client_id, client_secret

    def has_credentials(self) -> bool:
        client_id, client_secret = self._credentials()
        return bool(client_id and client_secret)

    def _authenticate(self) -> str:
        if self._token:
            return self._token
        client_id, client_secret = self._credentials()
        if not (client_id and client_secret):
            raise SourceSkipped(
                "NO_CREDENTIALS",
                "reddit requires OAuth credentials; HTML scraping is disallowed by robots.txt",
            )
        try:
            response = self.session.post(
                self.token_url,
                auth=(client_id, client_secret),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise SourceSkipped("AUTH_FAILED", str(exc)) from exc
        if response.status_code != 200:
            raise SourceSkipped(
                "AUTH_FAILED", f"token endpoint returned HTTP {response.status_code}"
            )
        token = (response.json() or {}).get("access_token")
        if not token:
            raise SourceSkipped("AUTH_FAILED", "no access_token in token response")
        self._token = token
        return token

    # -- fetch ------------------------------------------------------------
    def _search(self, subreddit: str, query: str) -> Any:
        token = self._authenticate()
        url = "{}/r/{}/search".format(self.api_base_url.rstrip("/"), subreddit)
        try:
            response = self.session.get(
                url,
                params={"q": query, "restrict_sr": 1, "sort": "new", "limit": 50, "t": "month"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": self.user_agent,
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise SourceSkipped("FETCH_FAILED", str(exc)) from exc
        if response.status_code == 429:
            raise SourceSkipped("RATE_LIMITED", "reddit returned HTTP 429")
        if response.status_code >= 400:
            raise SourceSkipped(
                "HTTP_ERROR", f"reddit search returned HTTP {response.status_code}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise SourceSkipped("BAD_PAYLOAD", str(exc)) from exc

    def fetch(self) -> List[Dict[str, Any]]:
        if not self.has_credentials():
            raise SourceSkipped(
                "NO_CREDENTIALS",
                "set REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET to enable the reddit source",
            )
        posts: List[Dict[str, Any]] = []
        seen = set()
        for subreddit in self.subreddits:
            for query in self.queries:
                try:
                    payload = self._search(subreddit, query)
                except SourceSkipped as exc:
                    # One blocked subreddit should not lose the others.
                    LOGGER.warning("SOURCE_SKIPPED reddit r/%s (%s)", subreddit, exc.reason)
                    continue
                for post in parse_listing(payload):
                    if post.get("id") and post["id"] not in seen:
                        seen.add(post["id"])
                        posts.append(post)
        return posts

    # -- health -----------------------------------------------------------
    def health_check(self) -> SourceHealth:
        checked_at = to_iso8601(now_utc())
        if not self.enabled:
            return self._health(SourceStatus.DISABLED, checked_at,
                                message="disabled in sources.yaml", reason="DISABLED")
        if not self.has_credentials():
            return self._health(
                SourceStatus.SKIPPED, checked_at,
                message=("reddit robots.txt disallows crawling and unauthenticated JSON returns "
                         "403; supply OAuth credentials to enable this source"),
                reason="NO_CREDENTIALS",
            )
        try:
            self._authenticate()
        except SourceSkipped as exc:
            return self._health(SourceStatus.ERROR, checked_at, message=str(exc),
                                reason=exc.reason)
        return self._health(SourceStatus.HEALTHY, checked_at, message="OAuth token acquired")
