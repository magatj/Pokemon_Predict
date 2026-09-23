"""PokeVend Tracker (pokemonmap.com) community machine status.

This is currently the only *credential-free* source of real availability
observations that the project has found. It is a community-contributed status
database: visitors mark a machine in stock, out of stock or under maintenance.

Why it is usable:

  * pokemonmap.com publishes no robots.txt, so nothing is disallowed.
  * Its /api/machines endpoint is unauthenticated and takes a plain bounding
    box (north/south/east/west). One request covers the whole search area -
    it returned 880 records for a multi-state box, so there is no result cap
    to tile around.
  * Records are keyed by `Machine_ID` using the same Q##### identifiers the
    official locator prints on the cabinet, so machine attribution is exact
    rather than fuzzy text matching.

What it is *not*: the API exposes only each machine's **current** status plus
the time it was last changed. There is no history endpoint. A single poll
therefore yields at most one observation per machine, and many of those are
months old.

The history is built by polling. Each scheduled run records the current
status, and the observation fingerprint is derived from the machine plus
`lastUpdated`, so repeated polls of an unchanged status collapse to one
observation while a genuine status change becomes a new one.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pokevend.geo import BoundingBox, bounding_box, parse_coordinate
from pokevend.http import PoliteSession, SourceSkipped
from pokevend.models import (
    Availability,
    EvidenceClass,
    ObservationSource,
    SourceAuthority,
    SourceHealth,
    SourceStatus,
)
from pokevend.models.observation import Observation, build_fingerprint, hash_text
from pokevend.sources.base import BaseSource
from pokevend.timeutil import now_utc, parse_iso8601, to_iso8601

LOGGER = logging.getLogger(__name__)

PUBLIC_URL = "https://pokemonmap.com/"

#: Community status values mapped onto availability outcomes.
#: MAINTENANCE is a negative observation: whatever the cause, the machine
#: could not dispense at that moment, which is exactly what is being forecast.
STATUS_MAP = {
    "INSTOCK": Availability.AVAILABLE,
    "IN_STOCK": Availability.AVAILABLE,
    "RESTOCKED": Availability.RESTOCK,
    "OUT_OF_STOCK": Availability.NOT_AVAILABLE,
    "OUTOFSTOCK": Availability.NOT_AVAILABLE,
    "MAINTENANCE": Availability.NOT_AVAILABLE,
}


def _extra(row: Dict[str, Any], raw_status: Any) -> Dict[str, Any]:
    """Side data kept on the observation.

    Coordinates are retained because the network prior needs each report's
    approximate local time, and a report from a machine outside the search
    radius is never attributed to a machine record.
    """
    extra: Dict[str, Any] = {"communityStatus": str(raw_status).upper()}
    coordinates = row.get("Coordinates")
    if isinstance(coordinates, list) and len(coordinates) == 2:
        longitude, latitude = parse_coordinate(coordinates[0]), parse_coordinate(coordinates[1])
        if latitude is not None and longitude is not None:
            extra["latitude"] = latitude
            extra["longitude"] = longitude
    return extra


def parse_status_payload(
    payload: Any,
    weight_lookup=None,
    source_url: str = PUBLIC_URL,
) -> List[Observation]:
    """Convert an /api/machines response into Observations.

    Pure and side-effect free so it can be tested against a saved fixture.
    Records with no status or no timestamp are skipped: an undated status
    cannot contribute to a timing forecast, and silently dating it "now" would
    invent evidence.
    """
    observations: List[Observation] = []
    if not isinstance(payload, list):
        return observations

    ingested_at = to_iso8601(now_utc())

    for row in payload:
        if not isinstance(row, dict):
            continue

        machine_id = row.get("Machine_ID")
        raw_status = row.get("status")
        last_updated = parse_iso8601(row.get("lastUpdated"))

        if not machine_id or not raw_status or last_updated is None:
            continue

        availability = STATUS_MAP.get(str(raw_status).strip().upper())
        if availability is None:
            LOGGER.debug("unmapped pokemonmap status %r for %s", raw_status, machine_id)
            continue

        observed_at = to_iso8601(last_updated)
        # The status value is part of the hash so a machine flipping back to a
        # previous state at a new time is still a distinct observation.
        raw_hash = hash_text(f"pokemonmap:{machine_id}:{raw_status}")
        fingerprint = build_fingerprint(
            source=ObservationSource.PUBLIC_WEB,
            source_identifier=f"pokemonmap:{machine_id}",
            machine_id=str(machine_id).upper(),
            timestamp=observed_at,
            raw_text_hash=raw_hash,
        )

        observations.append(
            Observation(
                id=fingerprint,
                source=ObservationSource.PUBLIC_WEB,
                availability=availability,
                posted_at=observed_at,
                observed_at=observed_at,
                source_url=source_url,
                # The Q-number is the identifier printed on the machine, so the
                # matcher resolves it to a record exactly.
                machine_id=str(machine_id).upper(),
                machine_match_confidence=1.0,
                retailer=(row.get("Retailer") or None),
                location_text=(row.get("Address") or None),
                evidence_class=EvidenceClass.COMMUNITY_TIMESTAMPED,
                confidence=(
                    weight_lookup(EvidenceClass.COMMUNITY_TIMESTAMPED)
                    if weight_lookup
                    else 0.65
                ),
                raw_text_hash=raw_hash,
                fingerprint=fingerprint,
                ingested_at=ingested_at,
                extra=_extra(row, raw_status),
            )
        )

    return observations


class PokemonMapSource(BaseSource):
    """Community machine-status observations from pokemonmap.com."""

    name = "pokemonmap"
    authority = SourceAuthority.COMMUNITY
    observation_source = ObservationSource.PUBLIC_WEB

    def __init__(
        self,
        settings: Dict[str, Any],
        session: PoliteSession,
        enabled: bool = True,
        weight_lookup=None,
    ):
        super().__init__(settings, enabled=enabled)
        self.session = session
        self.weight_lookup = weight_lookup
        self.base_url = str(self.setting("base_url", "https://pokemonmap.com")).rstrip("/")
        self.machines_path = str(self.setting("machines_path", "/api/machines"))
        self.network_radius_miles = float(self.setting("network_radius_miles", 300))

    def _query(self, box: BoundingBox) -> Any:
        url = self.base_url + self.machines_path
        params = {
            "north": round(box.ne_lat, 6),
            "south": round(box.sw_lat, 6),
            "east": round(box.ne_lng, 6),
            "west": round(box.sw_lng, 6),
        }
        return self.session.get(url, params=params, headers={"Accept": "application/json"}).json()

    def fetch(self, latitude: float, longitude: float, radius_miles: float) -> Any:
        """Fetch the region in one request.

        The query covers `network_radius_miles` rather than just the search
        radius, because the same response feeds both the machines in range and
        the wider sample behind the network prior. The endpoint has no result
        cap, so one request is enough.
        """
        effective = max(float(self.network_radius_miles), float(radius_miles))
        return self._query(bounding_box(latitude, longitude, effective))

    def normalize(self, raw: Any) -> List[Observation]:
        try:
            return parse_status_payload(
                raw, weight_lookup=self.weight_lookup, source_url=PUBLIC_URL
            )
        except Exception as exc:  # noqa: BLE001 - a parse failure must not stop the run
            LOGGER.warning("pokemonmap payload could not be parsed: %s", exc)
            return []

    def health_check(
        self, latitude: Optional[float] = None, longitude: Optional[float] = None
    ) -> SourceHealth:
        checked_at = to_iso8601(now_utc())
        if not self.enabled:
            return self._health(
                SourceStatus.DISABLED, checked_at,
                message="disabled in sources.yaml", reason="DISABLED",
            )
        if latitude is None or longitude is None:
            return self._health(SourceStatus.HEALTHY, checked_at, message="configured")
        try:
            payload = self._query(bounding_box(latitude, longitude, 1.0))
        except SourceSkipped as exc:
            return self._health(
                SourceStatus.SKIPPED, checked_at, message=str(exc), reason=exc.reason
            )
        except Exception as exc:  # noqa: BLE001 - health must never raise
            return self._health(
                SourceStatus.ERROR, checked_at, message=str(exc), reason="UNEXPECTED_ERROR"
            )
        count = len(payload) if isinstance(payload, list) else 0
        return self._health(
            SourceStatus.HEALTHY, checked_at, records=count, message="status API reachable"
        )
