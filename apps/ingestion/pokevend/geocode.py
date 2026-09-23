"""ZIP centroid lookup.

Discovery needs a latitude/longitude for the search ZIP. A small local table
covers the configured area so CI is deterministic and works offline; any other
ZIP is resolved through a public geocoder, falling back to the configured
centroid if that is unreachable.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from pokevend.http import PoliteSession, SourceSkipped

LOGGER = logging.getLogger(__name__)

ZIPPOPOTAM_URL = "https://api.zippopotam.us/us/{zip}"

#: Verified against api.zippopotam.us. Kept local so the default search area
#: resolves with no network call.
KNOWN_ZIP_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "98092": (47.2884, -122.098),   # Auburn, WA - default search area
    "98002": (47.3073, -122.2166),  # Auburn
    "98042": (47.3606, -122.1272),  # Kent / Covington
    "98030": (47.3689, -122.2047),  # Kent
    "98038": (47.3697, -122.0392),  # Maple Valley
    "98003": (47.3070, -122.3175),  # Federal Way
}


def local_lookup(zip_code: str) -> Optional[Tuple[float, float]]:
    return KNOWN_ZIP_CENTROIDS.get(str(zip_code).strip())


def remote_lookup(zip_code: str, session: PoliteSession) -> Optional[Tuple[float, float]]:
    """Resolve a ZIP through the public Zippopotam.us API."""
    url = ZIPPOPOTAM_URL.format(zip=str(zip_code).strip())
    try:
        payload = session.get(url, headers={"Accept": "application/json"}).json()
    except (SourceSkipped, ValueError) as exc:
        LOGGER.warning("ZIP geocode failed for %s: %s", zip_code, exc)
        return None
    places = payload.get("places") if isinstance(payload, dict) else None
    if not places:
        return None
    place = places[0]
    try:
        return float(place["latitude"]), float(place["longitude"])
    except (KeyError, TypeError, ValueError):
        return None


def resolve_zip_centroid(
    zip_code: str,
    session: Optional[PoliteSession] = None,
    fallback: Optional[Tuple[float, float]] = None,
) -> Tuple[Tuple[float, float], str]:
    """Return ``((latitude, longitude), provenance)`` for a ZIP code.

    Provenance is reported so the UI and logs can show where the search
    centroid came from rather than presenting it as a given.
    """
    local = local_lookup(zip_code)
    if local:
        return local, "local_table"

    if session is not None:
        remote = remote_lookup(zip_code, session)
        if remote:
            return remote, "zippopotam"

    if fallback:
        LOGGER.warning("falling back to configured centroid for ZIP %s", zip_code)
        return fallback, "config_fallback"

    raise ValueError(f"cannot resolve a centroid for ZIP {zip_code}")
