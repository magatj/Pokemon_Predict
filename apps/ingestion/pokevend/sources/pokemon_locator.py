"""Official Pokemon vending-machine locator.

The locator web app at vending.pokemon.com is served behind a bot-protection
layer, so the HTML is never scraped. It calls a public, unauthenticated JSON
API, and that endpoint is what this adapter uses:

    GET {base}/v1/machines?swLat&swLng&neLat&neLng&unit

The endpoint returns at most `result_cap` machines per bounding box, so a dense
search area silently truncates. The search box is therefore tiled into a grid,
each tile queried separately, and results merged and de-duplicated by id.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pokevend.geo import BoundingBox, bounding_box, parse_coordinate, tile_bounding_box
from pokevend.http import PoliteSession, SourceSkipped
from pokevend.models import Machine, SourceAuthority, SourceHealth, SourceStatus
from pokevend.sources.base import BaseSource
from pokevend.timeutil import now_utc, to_iso8601

LOGGER = logging.getLogger(__name__)

LOCATOR_PUBLIC_URL = "https://vending.pokemon.com/en-us/"


def parse_machines_payload(payload: Any, source_url: str = LOCATOR_PUBLIC_URL) -> List[Machine]:
    """Convert one API response into Machine records.

    Pure and side-effect free so it can be tested against a saved fixture. A row
    missing an id or usable coordinates is dropped rather than raising, so one
    bad record cannot abort discovery.
    """
    machines: List[Machine] = []
    if not isinstance(payload, dict):
        return machines
    rows = payload.get("machines")
    if not isinstance(rows, list):
        return machines

    timestamp = to_iso8601(now_utc())
    for row in rows:
        if not isinstance(row, dict):
            continue
        machine_id = row.get("id")
        latitude = parse_coordinate(row.get("lat"))
        longitude = parse_coordinate(row.get("lng"))
        if not machine_id or latitude is None or longitude is None:
            LOGGER.debug("skipping locator row without id/coordinates: %r", row)
            continue
        machines.append(
            Machine(
                id=str(machine_id),
                retailer=(row.get("retailer") or "Unknown retailer").strip(),
                name=(row.get("name") or str(machine_id)).strip(),
                address=(row.get("street") or "").strip(),
                city=(row.get("city") or "").strip(),
                state=(row.get("stateProvince") or "").strip(),
                zip=str(row.get("zipPostalCode") or "").strip(),
                latitude=latitude,
                longitude=longitude,
                source="pokemon_locator",
                source_authority=SourceAuthority.OFFICIAL,
                source_url=source_url,
                discovered_at=timestamp,
                last_verified_at=timestamp,
            )
        )
    return machines


class PokemonLocatorSource(BaseSource):
    """Machine discovery from the official locator API."""

    name = "pokemon_locator"
    authority = SourceAuthority.OFFICIAL

    def __init__(self, settings: Dict[str, Any], session: PoliteSession, enabled: bool = True):
        super().__init__(settings, enabled=enabled)
        self.session = session
        self.base_url = str(self.setting("base_url", "https://api.vending.prod.pokemon.com"))
        self.machines_path = str(self.setting("machines_path", "/v1/machines"))
        self.result_cap = int(self.setting("result_cap", 20))
        self.tile_grid = int(self.setting("tile_grid", 4))

    # -- fetch ------------------------------------------------------------
    def _query_tile(self, tile: BoundingBox) -> Any:
        url = self.base_url.rstrip("/") + self.machines_path
        params = {
            "swLat": round(tile.sw_lat, 6),
            "swLng": round(tile.sw_lng, 6),
            "neLat": round(tile.ne_lat, 6),
            "neLng": round(tile.ne_lng, 6),
            "unit": "mi",
        }
        result = self.session.get(url, params=params, headers={"Accept": "application/json"})
        return result.json()

    def fetch(self, latitude: float, longitude: float, radius_miles: float) -> List[Any]:
        """Query every tile covering the search radius."""
        box = bounding_box(latitude, longitude, radius_miles)
        tiles = tile_bounding_box(box, self.tile_grid)
        payloads = []
        for index, tile in enumerate(tiles, start=1):
            try:
                payload = self._query_tile(tile)
            except SourceSkipped:
                raise
            except ValueError as exc:
                # Malformed JSON from one tile must not lose the other tiles.
                LOGGER.warning("tile %s/%s returned unparseable JSON: %s", index, len(tiles), exc)
                continue
            payloads.append(payload)
            count = len(payload.get("machines") or []) if isinstance(payload, dict) else 0
            if count >= self.result_cap:
                LOGGER.warning(
                    "tile %s/%s hit the %s-result cap; increase sources.pokemon_locator.tile_grid",
                    index, len(tiles), self.result_cap,
                )
        return payloads

    # -- normalize --------------------------------------------------------
    def normalize(self, raw: List[Any]) -> List[Machine]:
        """Merge tile payloads, de-duplicating by machine id."""
        merged: Dict[str, Machine] = {}
        for payload in raw or []:
            for machine in parse_machines_payload(payload):
                merged.setdefault(machine.id, machine)
        return list(merged.values())

    # -- health -----------------------------------------------------------
    def health_check(self, latitude: Optional[float] = None,
                     longitude: Optional[float] = None) -> SourceHealth:
        checked_at = to_iso8601(now_utc())
        if not self.enabled:
            return self._health(SourceStatus.DISABLED, checked_at,
                                message="disabled in sources.yaml", reason="DISABLED")
        if latitude is None or longitude is None:
            return self._health(SourceStatus.HEALTHY, checked_at, message="configured")
        try:
            payload = self._query_tile(bounding_box(latitude, longitude, 1.0))
        except SourceSkipped as exc:
            return self._health(SourceStatus.SKIPPED, checked_at, message=str(exc),
                                reason=exc.reason)
        except Exception as exc:  # noqa: BLE001 - health must never raise
            return self._health(SourceStatus.ERROR, checked_at, message=str(exc),
                                reason="UNEXPECTED_ERROR")
        count = len(payload.get("machines") or []) if isinstance(payload, dict) else 0
        return self._health(SourceStatus.HEALTHY, checked_at, records=count,
                            message="locator API reachable")
