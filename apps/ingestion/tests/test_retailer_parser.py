"""Retailer store-page parsing and address matching.

The fixture is a trimmed but unmodified extract of a real public Safeway store
page (4010 A St, Auburn WA), which is the store behind machine Q00804.
"""
from __future__ import annotations

import pytest

from pokevend.sources.retailer_source import (
    RetailerSource,
    address_similarity,
    build_retailer_sources,
    extract_json_value,
    extract_store_links,
    parse_retailer_store_page,
)
from tests.conftest import load_fixture


@pytest.fixture
def store_html():
    return load_fixture("safeway_store_page.html")


def test_extracts_address(store_html):
    profile = parse_retailer_store_page(store_html, "https://example.test/store.html")
    assert profile["address"] == "4010 A St"
    assert profile["city"] == "Auburn"
    assert profile["state"] == "WA"
    assert profile["zip"] == "98002"


def test_extracts_coordinates(store_html):
    profile = parse_retailer_store_page(store_html, "https://example.test/store.html")
    assert profile["latitude"] == pytest.approx(47.2728, abs=0.001)
    assert profile["longitude"] == pytest.approx(-122.227, abs=0.001)


def test_detects_the_pokemon_kiosk_service(store_html):
    profile = parse_retailer_store_page(store_html, "https://example.test/store.html")
    assert profile["kiosk_listed"] is True
    assert any("Kiosk" in service for service in profile["services"])


def test_extracts_store_hours(store_html):
    profile = parse_retailer_store_page(store_html, "https://example.test/store.html")
    assert set(profile["hours"]) >= {"monday", "sunday"}
    start, end = profile["hours"]["monday"][0]
    assert start.count(":") == 1 and end.count(":") == 1


def test_midnight_close_is_not_dropped():
    """Integer 0 means midnight, not "missing" - a falsy check would lose it."""
    html = '{"hours":{"normalHours":[{"day":"MONDAY","intervals":[{"start":530,"end":0}]}]}}'
    profile = parse_retailer_store_page(html, "u")
    assert profile["hours"]["monday"] == [["05:30", "00:00"]]


def test_closed_day_is_recorded_as_empty():
    html = '{"hours":{"normalHours":[{"day":"SUNDAY","isClosed":true,"intervals":[]}]}}'
    profile = parse_retailer_store_page(html, "u")
    assert profile["hours"]["sunday"] == []


def test_page_without_kiosk_reports_false():
    html = '{"services":["Coinstar","Lottery"],"address":{"line1":"1 Main St"}}'
    profile = parse_retailer_store_page(html, "u")
    assert profile["kiosk_listed"] is False


@pytest.mark.parametrize("html", ["", None, "<html></html>", "{ broken json"])
def test_malformed_pages_degrade_instead_of_raising(html):
    profile = parse_retailer_store_page(html, "https://example.test/x.html")
    assert profile["address"] is None
    assert profile["kiosk_listed"] is False
    assert profile["services"] == []


def test_extract_json_value_handles_nesting_and_escapes():
    text = r'{"address":{"line1":"He said \"hi\" {not a brace}","city":"Kent"},"next":1}'
    value = extract_json_value(text, "address")
    assert value["city"] == "Kent"


def test_extract_json_value_returns_none_for_missing_key():
    assert extract_json_value('{"a":1}', "missing") is None


# -- address matching ----------------------------------------------------

def test_address_similarity_matches_the_same_store():
    assert address_similarity("4010 A St SE", "4010 a st") > 0.8


def test_address_similarity_rejects_a_different_street_number():
    high = address_similarity("4010 A St SE", "4010 a st")
    low = address_similarity("4010 A St SE", "101 auburn way s")
    assert low < 0.3 < high


def test_store_links_exclude_robots_disallowed_paths():
    html = (
        '<a href="../../safeway/wa/auburn/4010-a-st.html">A</a>'
        '<a href="/locator/search.html">B</a>'
        '<a href="wa/auburn.html">C</a>'
    )
    links = extract_store_links(html, "https://local.safeway.com")
    assert links == ["https://local.safeway.com/safeway/wa/auburn/4010-a-st.html"]


def test_city_page_url_is_built_from_machine_fields():
    source = RetailerSource("Fred Meyer", {"base_url": "https://example.test"}, session=None)
    assert source.city_page_url("WA", "Maple Valley") == (
        "https://example.test/fredmeyer/wa/maple-valley.html"
    )


def test_disabled_retailer_reports_disabled_health():
    settings = {
        "base_url": "https://example.test",
        "retailers": {"Fred Meyer": {"enabled": False, "base_url": "https://example.test"}},
    }
    sources = build_retailer_sources(settings, session=None)
    assert len(sources) == 1
    health = sources[0].health_check()
    assert health.status == "DISABLED"
    assert health.reason == "DISABLED"
