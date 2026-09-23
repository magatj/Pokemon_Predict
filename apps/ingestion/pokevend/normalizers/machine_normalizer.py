"""Machine normalization: distance filtering and authority-aware merging."""
from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional, Tuple

from pokevend.geo import haversine_miles
from pokevend.models import Machine, SourceAuthority
from pokevend.timeutil import now_utc, to_iso8601

LOGGER = logging.getLogger(__name__)

#: Distances are compared with a small tolerance so a machine sitting exactly on
#: the radius is included rather than lost to floating-point noise.
BOUNDARY_TOLERANCE_MILES = 1e-6


def annotate_distances(machines: Iterable[Machine], origin: Tuple[float, float]) -> List[Machine]:
    """Set ``distance_miles`` on each machine, measured from the search origin."""
    result = []
    for machine in machines:
        machine.distance_miles = haversine_miles(
            origin[0], origin[1], machine.latitude, machine.longitude
        )
        result.append(machine)
    return result


def filter_by_radius(
    machines: Iterable[Machine],
    origin: Tuple[float, float],
    radius_miles: float,
) -> List[Machine]:
    """Keep machines within ``radius_miles`` of the origin, nearest first.

    The test is purely geometric. City and ZIP are descriptive only: a machine
    in a neighbouring city inside the radius is kept, and a machine in the
    search ZIP's own city outside the radius is dropped.
    """
    annotated = annotate_distances(machines, origin)
    kept = [
        machine
        for machine in annotated
        if machine.distance_miles is not None
        and machine.distance_miles <= radius_miles + BOUNDARY_TOLERANCE_MILES
    ]
    kept.sort(key=lambda machine: machine.distance_miles)
    return kept


def merge_machine(incumbent: Machine, candidate: Machine) -> Machine:
    """Merge two records for the same machine, respecting source authority.

    A lower-authority source can only fill in fields the higher-authority one
    left blank. It can never overwrite an established value, so a third-party
    directory cannot quietly move an officially-listed machine.
    """
    if SourceAuthority.outranks(candidate.source_authority, incumbent.source_authority):
        primary, secondary = candidate, incumbent
    else:
        primary, secondary = incumbent, candidate

    for field_name in ("retailer", "name", "address", "city", "state", "zip",
                       "source_url", "store_hours"):
        if not getattr(primary, field_name) and getattr(secondary, field_name):
            setattr(primary, field_name, getattr(secondary, field_name))

    if primary.kiosk_listed is None and secondary.kiosk_listed is not None:
        primary.kiosk_listed = secondary.kiosk_listed

    # Keep the earliest discovery and the most recent verification.
    discovered = [d for d in (primary.discovered_at, secondary.discovered_at) if d]
    if discovered:
        primary.discovered_at = min(discovered)
    verified = [v for v in (primary.last_verified_at, secondary.last_verified_at) if v]
    if verified:
        primary.last_verified_at = max(verified)

    aliases = set(primary.aliases) | set(secondary.aliases)
    primary.aliases = sorted(aliases)
    primary.verifications = (primary.verifications or []) + [
        v for v in (secondary.verifications or []) if v not in (primary.verifications or [])
    ]
    return primary


def normalize_machines(
    discovered: Iterable[Machine],
    origin: Tuple[float, float],
    radius_miles: float,
    existing: Optional[Iterable[Machine]] = None,
) -> List[Machine]:
    """Merge newly discovered machines with stored ones, then filter by radius."""
    merged: Dict[str, Machine] = {}

    for machine in existing or []:
        merged[machine.id] = machine

    for machine in discovered:
        if machine.id in merged:
            merged[machine.id] = merge_machine(merged[machine.id], machine)
        else:
            merged[machine.id] = machine

    for machine in merged.values():
        if not machine.aliases:
            machine.aliases = build_aliases(machine)

    return filter_by_radius(merged.values(), origin, radius_miles)


def build_aliases(machine: Machine) -> List[str]:
    """Phrases a community post might use for this machine.

    e.g. "Covington Fred Meyer", "Fred Meyer Covington", "Q01401".
    """
    aliases = set()
    retailer = (machine.retailer or "").strip()
    city = (machine.city or "").strip()
    if retailer and city:
        aliases.add(f"{city} {retailer}".lower())
        aliases.add(f"{retailer} {city}".lower())
    if machine.name:
        aliases.add(machine.name.lower())
    if retailer and machine.address:
        aliases.add(f"{retailer} {machine.address}".lower())
    return sorted(aliases)


def apply_verification(machine: Machine, profile: Dict) -> Machine:
    """Fold a retailer store-page profile into a machine record.

    Verification data is VERIFICATION authority: it adds hours and kiosk
    listings and refreshes ``last_verified_at``, but never moves coordinates or
    renames a machine established by the official locator.
    """
    if not profile:
        return machine

    machine.store_hours = profile.get("hours") or machine.store_hours
    if profile.get("kiosk_listed") is not None:
        machine.kiosk_listed = bool(profile.get("kiosk_listed"))
    machine.last_verified_at = to_iso8601(now_utc())

    entry = {
        "source": "retailer_pages",
        "retailer": profile.get("retailer"),
        "url": profile.get("source_url"),
        "verified_at": machine.last_verified_at,
        "kiosk_listed": bool(profile.get("kiosk_listed")),
        "address_match_score": round(float(profile.get("match_score") or 0.0), 3),
    }
    machine.verifications = [
        v for v in (machine.verifications or []) if v.get("url") != entry["url"]
    ] + [entry]
    return machine
