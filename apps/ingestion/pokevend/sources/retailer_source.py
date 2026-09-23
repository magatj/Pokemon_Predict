"""Retailer website verification adapters.

These are *verification* sources, not discovery sources. They confirm that the
store behind a machine exists, cross-check its address, capture opening hours
and record whether the retailer lists a Pokemon kiosk as an in-store service.

They never create machines and never overwrite a field set by the official
locator; see `normalizers.machine_normalizer.merge_machine`.

robots.txt is honoured by the shared session. local.safeway.com allows
everything except /locator, which this adapter does not touch. Retailers whose
store pages sit behind bot protection stay disabled in sources.yaml and are
reported as SOURCE_SKIPPED rather than worked around.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from pokevend.geo import parse_coordinate
from pokevend.http import PoliteSession
from pokevend.models import SourceAuthority, SourceHealth, SourceStatus
from pokevend.sources.base import BaseSource
from pokevend.timeutil import now_utc, to_iso8601

LOGGER = logging.getLogger(__name__)

_KIOSK_PATTERN = re.compile(r"pok[eé]mon\s+kiosk", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Street-type words carry no signal when matching one address against another.
_ADDRESS_STOPWORDS = frozenset(
    {"st", "street", "ave", "avenue", "rd", "road", "way", "dr", "drive", "blvd",
     "boulevard", "ln", "lane", "pl", "place", "ct", "court", "hwy", "highway",
     "n", "s", "e", "w", "ne", "nw", "se", "sw", "no", "suite", "ste"}
)


def extract_json_value(text: str, key: str) -> Optional[Any]:
    """Pull one JSON value out of a page by key, using balanced scanning.

    Retailer pages embed a large profile object inside a script tag with no
    stable container variable, so anchoring on the key and reading a balanced
    object/array is far more durable than parsing the whole page.
    """
    needle = f'"{key}":'
    start = text.find(needle)
    if start == -1:
        return None
    cursor = start + len(needle)
    while cursor < len(text) and text[cursor] in " \t\r\n":
        cursor += 1
    if cursor >= len(text):
        return None

    opener = text[cursor]
    if opener not in "{[":
        # Scalar value: read to the next delimiter and let json parse it.
        end = cursor
        while end < len(text) and text[end] not in ",}]":
            end += 1
        try:
            return json.loads(text[cursor:end].strip())
        except ValueError:
            return None

    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escaped = False
    for index in range(cursor, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[cursor:index + 1])
                except ValueError:
                    return None
    return None


def _normalize_hours(raw: Any) -> Optional[Dict[str, Any]]:
    """Reduce a retailer hours object to {day: [[start, end], ...]}."""
    if not isinstance(raw, dict):
        return None
    normal = raw.get("normalHours")
    if not isinstance(normal, list):
        return None
    hours: Dict[str, Any] = {}
    for entry in normal:
        if not isinstance(entry, dict):
            continue
        day = str(entry.get("day") or "").lower()
        if not day:
            continue
        if entry.get("isClosed"):
            hours[day] = []
            continue
        intervals = []
        # Retailers spell this either "intervals" or "openIntervals".
        raw_intervals = entry.get("intervals")
        if not isinstance(raw_intervals, list):
            raw_intervals = entry.get("openIntervals") or []
        for interval in raw_intervals:
            if not isinstance(interval, dict):
                continue
            start = _format_clock(interval.get("start"))
            end = _format_clock(interval.get("end"))
            if start is not None and end is not None:
                intervals.append([start, end])
        hours[day] = intervals
    return hours or None


def _format_clock(value: Any) -> Optional[str]:
    """Normalise a clock value to "HH:MM".

    These pages encode times as integers (530 -> 05:30, 0 -> midnight), so a
    falsy check would silently drop every store that closes at midnight.
    """
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if not 0 <= number <= 2400:
        return None
    return f"{number // 100:02d}:{number % 100:02d}"


def parse_retailer_store_page(html: str, url: str) -> Dict[str, Any]:
    """Extract a store profile from a retailer store page.

    Returns a dict with whatever could be read. Missing fields come back as
    None rather than raising - a layout change degrades verification, it does
    not break ingestion.
    """
    profile: Dict[str, Any] = {
        "source_url": url,
        "address": None,
        "city": None,
        "state": None,
        "zip": None,
        "latitude": None,
        "longitude": None,
        "hours": None,
        "services": [],
        "kiosk_listed": False,
    }
    if not html:
        return profile

    address = extract_json_value(html, "address")
    if isinstance(address, dict):
        profile["address"] = address.get("line1")
        profile["city"] = address.get("city")
        profile["state"] = address.get("region")
        profile["zip"] = address.get("postalCode")

    coordinate = extract_json_value(html, "yextDisplayCoordinate")
    if isinstance(coordinate, dict):
        # Retailer pages use short keys ("lat"/"long"); accept both spellings.
        profile["latitude"] = parse_coordinate(
            coordinate.get("lat", coordinate.get("latitude"))
        )
        profile["longitude"] = parse_coordinate(
            coordinate.get("long", coordinate.get("longitude"))
        )

    profile["hours"] = _normalize_hours(extract_json_value(html, "hours"))

    services = extract_json_value(html, "services")
    if isinstance(services, list):
        profile["services"] = [str(item) for item in services if isinstance(item, str)]

    # The kiosk can be listed in the services array or only in visible markup.
    profile["kiosk_listed"] = any(
        _KIOSK_PATTERN.search(service) for service in profile["services"]
    ) or bool(_KIOSK_PATTERN.search(html))

    return profile


def address_tokens(address: str) -> set:
    """Comparable tokens for an address, minus street-type noise."""
    cleaned = _NON_ALNUM.sub(" ", (address or "").lower())
    return {token for token in cleaned.split() if token and token not in _ADDRESS_STOPWORDS}


def address_similarity(left: str, right: str) -> float:
    """Jaccard overlap of two addresses, with the street number weighted."""
    left_tokens, right_tokens = address_tokens(left), address_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens & right_tokens
    score = len(overlap) / float(len(left_tokens | right_tokens))
    # A matching street number is the strongest single signal.
    left_number = next((t for t in left_tokens if t.isdigit()), None)
    right_number = next((t for t in right_tokens if t.isdigit()), None)
    if left_number and left_number == right_number:
        score = min(1.0, score + 0.4)
    elif left_number and right_number and left_number != right_number:
        score *= 0.3
    return score


def extract_store_links(html: str, base_url: str) -> List[str]:
    """Absolute store-page URLs found on a retailer city page."""
    links = set()
    for match in re.finditer(r'href="([^"]+\.html)"', html or ""):
        href = match.group(1)
        if "/locator" in href:
            continue  # disallowed by robots.txt
        cleaned = href.replace("../", "")
        if cleaned.count("/") < 3:
            continue  # city index pages, not store pages
        links.add(base_url.rstrip("/") + "/" + cleaned.lstrip("/"))
    return sorted(links)


class RetailerSource(BaseSource):
    """Verifies machines against one retailer's public store pages."""

    name = "retailer_pages"
    authority = SourceAuthority.VERIFICATION

    def __init__(self, retailer: str, settings: Dict[str, Any], session: PoliteSession,
                 enabled: bool = True):
        super().__init__(settings, enabled=enabled)
        self.retailer = retailer
        self.session = session
        self.base_url = str(self.setting("base_url", "")).rstrip("/")
        self.name = "retailer_pages:{}".format(retailer.lower().replace(" ", "_"))
        self.min_similarity = float(self.setting("min_address_similarity", 0.45))

    def city_page_url(self, state: str, city: str) -> str:
        slug_retailer = _NON_ALNUM.sub("", self.retailer.lower())
        slug_city = _NON_ALNUM.sub("-", (city or "").lower()).strip("-")
        return "{}/{}/{}/{}.html".format(
            self.base_url, slug_retailer, (state or "").lower(), slug_city
        )

    def fetch(self, machine) -> Optional[Dict[str, Any]]:
        """Find and fetch the store page matching one machine."""
        city_url = self.city_page_url(machine.state, machine.city)
        city_page = self.session.get(city_url)
        candidates = extract_store_links(city_page.text, self.base_url)
        if not candidates:
            return None

        best_url, best_score = None, 0.0
        for url in candidates:
            # The store slug carries the address, so match on the URL first and
            # only download the page that actually looks like the right store.
            slug = url.rsplit("/", 1)[-1].replace(".html", "").replace("-", " ")
            score = address_similarity(machine.address, slug)
            if score > best_score:
                best_url, best_score = url, score

        if not best_url or best_score < self.min_similarity:
            LOGGER.info(
                "no confident store-page match for %s (%s); best score %.2f",
                machine.id, machine.address, best_score,
            )
            return None

        page = self.session.get(best_url)
        profile = parse_retailer_store_page(page.text, best_url)
        profile["match_score"] = best_score
        profile["retailer"] = self.retailer
        return profile

    def normalize(self, raw: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [raw] if raw else []

    def health_check(self) -> SourceHealth:
        checked_at = to_iso8601(now_utc())
        if not self.enabled:
            return self._health(SourceStatus.DISABLED, checked_at,
                                message=f"{self.retailer} disabled in sources.yaml",
                                reason="DISABLED")
        if not self.base_url:
            return self._health(SourceStatus.ERROR, checked_at, message="no base_url configured",
                                reason="MISCONFIGURED")
        try:
            allowed = self.session.is_allowed(self.base_url + "/")
        except Exception as exc:  # noqa: BLE001 - health must never raise
            return self._health(SourceStatus.ERROR, checked_at, message=str(exc),
                                reason="UNEXPECTED_ERROR")
        if not allowed:
            return self._health(SourceStatus.SKIPPED, checked_at,
                                message=f"robots.txt disallows {self.base_url}",
                                reason="ROBOTS_DISALLOWED")
        return self._health(SourceStatus.HEALTHY, checked_at, message="store pages permitted")


def build_retailer_sources(settings: Dict[str, Any], session: PoliteSession,
                           enabled: bool = True) -> List[RetailerSource]:
    """Instantiate one adapter per configured retailer."""
    sources = []
    for retailer, retailer_settings in (settings.get("retailers") or {}).items():
        merged = dict(settings)
        merged.update(retailer_settings or {})
        sources.append(
            RetailerSource(
                retailer=retailer,
                settings=merged,
                session=session,
                enabled=enabled and bool((retailer_settings or {}).get("enabled", True)),
            )
        )
    return sources
