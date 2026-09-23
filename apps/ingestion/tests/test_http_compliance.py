"""The shared HTTP client's compliance guarantees.

These are the rules the ingestion policy rests on, so they are asserted rather
than assumed: robots.txt is honoured, refusals are never worked around, and
unchanged pages are not re-downloaded.
"""
from __future__ import annotations

import pytest
import requests

from pokevend.http import PoliteSession, SourceSkipped


class FakeResponse:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class FakeSession:
    """Stands in for requests.Session, recording every call."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers or {}})
        handler = self.responses.get(url)
        if handler is None:
            return FakeResponse(404, "not found")
        if callable(handler):
            return handler(len([c for c in self.calls if c["url"] == url]))
        return handler


def make_session(responses, tmp_path, **kwargs):
    settings = {
        "user_agent": "pokemon-vending-forecast/0.1",
        "rate_limit_seconds": 0,
        "max_retries": 2,
        "cache_dir": tmp_path / "cache",
        "session": FakeSession(responses),
    }
    settings.update(kwargs)
    return PoliteSession(**settings)


ROBOTS_ALLOW_ALL = "https://example.test/robots.txt"
ROBOTS_DENY_ALL = "https://denied.test/robots.txt"


def test_robots_disallow_blocks_the_request(tmp_path):
    session = make_session(
        {ROBOTS_DENY_ALL: FakeResponse(200, "User-agent: *\nDisallow: /")}, tmp_path
    )

    with pytest.raises(SourceSkipped) as excinfo:
        session.get("https://denied.test/anything")

    assert excinfo.value.reason == "ROBOTS_DISALLOWED"
    # Only robots.txt was ever fetched; the disallowed URL was not requested.
    assert [call["url"] for call in session.session.calls] == [ROBOTS_DENY_ALL]


def test_robots_partial_disallow_is_respected(tmp_path):
    robots = "User-agent: *\nDisallow: /locator\n"
    session = make_session(
        {
            ROBOTS_ALLOW_ALL: FakeResponse(200, robots),
            "https://example.test/store.html": FakeResponse(200, "<html>ok</html>"),
        },
        tmp_path,
    )

    assert session.get("https://example.test/store.html").text == "<html>ok</html>"
    with pytest.raises(SourceSkipped):
        session.get("https://example.test/locator/search")


def test_missing_robots_is_treated_as_unrestricted(tmp_path):
    session = make_session(
        {
            ROBOTS_ALLOW_ALL: FakeResponse(404, "nope"),
            "https://example.test/api": FakeResponse(200, "{}"),
        },
        tmp_path,
    )
    assert session.get("https://example.test/api").status == 200


def test_forbidden_response_is_never_retried(tmp_path):
    """A 403 means "not welcome". We stop rather than trying to get around it."""
    session = make_session(
        {
            ROBOTS_ALLOW_ALL: FakeResponse(404, ""),
            "https://example.test/blocked": FakeResponse(403, "denied"),
        },
        tmp_path,
    )

    with pytest.raises(SourceSkipped) as excinfo:
        session.get("https://example.test/blocked")

    assert excinfo.value.reason == "ACCESS_DENIED"
    attempts = [c for c in session.session.calls if c["url"].endswith("/blocked")]
    assert len(attempts) == 1


@pytest.mark.parametrize("status", [401, 403, 451])
def test_all_refusal_statuses_are_treated_as_skips(status, tmp_path):
    session = make_session(
        {
            ROBOTS_ALLOW_ALL: FakeResponse(404, ""),
            "https://example.test/x": FakeResponse(status, ""),
        },
        tmp_path,
    )
    with pytest.raises(SourceSkipped) as excinfo:
        session.get("https://example.test/x")
    assert excinfo.value.reason == "ACCESS_DENIED"


def test_conditional_headers_are_sent_on_the_second_fetch(tmp_path):
    url = "https://example.test/page"

    def handler(call_number):
        if call_number == 1:
            return FakeResponse(200, "body-v1", {"ETag": "abc", "Last-Modified": "Mon"})
        return FakeResponse(304, "", {})

    session = make_session({ROBOTS_ALLOW_ALL: FakeResponse(404, ""), url: handler}, tmp_path)

    first = session.get(url)
    second = session.get(url)

    assert first.text == "body-v1" and not first.from_cache
    assert second.not_modified and second.text == "body-v1"

    conditional = [c for c in session.session.calls if c["url"] == url][1]["headers"]
    assert conditional["If-None-Match"] == "abc"
    assert conditional["If-Modified-Since"] == "Mon"


def test_transient_errors_are_retried_then_skipped(tmp_path):
    url = "https://example.test/flaky"
    session = make_session(
        {ROBOTS_ALLOW_ALL: FakeResponse(404, ""), url: FakeResponse(503, "")},
        tmp_path,
        rate_limit_seconds=0,
    )
    session.max_retries = 2

    with pytest.raises(SourceSkipped) as excinfo:
        session.get(url)

    assert excinfo.value.reason == "FETCH_FAILED"
    assert len([c for c in session.session.calls if c["url"] == url]) == 2


def test_network_failure_falls_back_to_cache(tmp_path):
    url = "https://example.test/page"
    calls = {"n": 0}

    def handler(_call_number):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse(200, "cached-body", {"ETag": "v1"})
        raise requests.RequestException("connection reset")

    session = make_session({ROBOTS_ALLOW_ALL: FakeResponse(404, ""), url: handler}, tmp_path)
    session.rate_limit_seconds = 0

    assert session.get(url).text == "cached-body"
    stale = session.get(url)
    assert stale.from_cache and stale.text == "cached-body"


def test_user_agent_identifies_the_project(tmp_path):
    session = make_session({}, tmp_path)
    assert "pokemon-vending-forecast" in session.session.headers["User-Agent"]
