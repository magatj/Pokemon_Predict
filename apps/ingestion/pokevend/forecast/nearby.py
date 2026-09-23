"""Nearby-machine contextual signal.

Machines in the same area sometimes see activity at similar times (shared
distribution runs, regional launches). That is weak, circumstantial evidence:
it carries the smallest weight in the model and is never treated as proof that
a particular machine has been restocked.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from pokevend.geo import haversine_miles
from pokevend.models import Machine, Observation
from pokevend.timeutil import minutes_between, parse_iso8601


def neighbours_within(
    machine: Machine, machines: Iterable[Machine], radius_miles: float
) -> List[Machine]:
    """Other machines within ``radius_miles`` of this one."""
    return [
        other
        for other in machines
        if other.id != machine.id
        and haversine_miles(machine.latitude, machine.longitude, other.latitude, other.longitude)
        <= radius_miles
    ]


def nearby_activity(
    machine: Machine,
    machines: Sequence[Machine],
    observations: Sequence[Observation],
    now: datetime,
    radii_miles: Sequence[float] = (3, 5, 10),
    window_minutes: int = 90,
) -> Dict[str, object]:
    """Count recent positive reports from neighbouring machines.

    Returns per-radius counts plus a bounded score for the model. The score
    saturates at three active neighbours - beyond that it says nothing more.
    """
    by_radius: Dict[str, int] = {}
    machine_ids_by_radius: Dict[str, List[str]] = {}

    for radius in radii_miles:
        neighbour_ids = {other.id for other in neighbours_within(machine, machines, radius)}
        active: List[str] = []
        for observation in observations:
            if observation.machine_id not in neighbour_ids:
                continue
            if not observation.is_positive():
                continue
            timestamp = parse_iso8601(observation.effective_at)
            if timestamp is None:
                continue
            age = minutes_between(now, timestamp)
            if 0 <= age <= window_minutes and observation.machine_id not in active:
                active.append(observation.machine_id)
        key = str(int(radius))
        by_radius[key] = len(active)
        machine_ids_by_radius[key] = active

    smallest = str(int(min(radii_miles))) if radii_miles else "0"
    largest = str(int(max(radii_miles))) if radii_miles else "0"
    active_count = by_radius.get(largest, 0)
    score = min(active_count / 3.0, 1.0)

    return {
        "windowMinutes": int(window_minutes),
        "activeByRadiusMiles": by_radius,
        "activeMachineIds": machine_ids_by_radius.get(largest, []),
        "closestRadiusMiles": int(min(radii_miles)) if radii_miles else 0,
        "activeClosest": by_radius.get(smallest, 0),
        "score": round(score, 4),
    }


def nearby_score(activity: Optional[Dict[str, object]]) -> float:
    if not activity:
        return 0.0
    return float(activity.get("score", 0.0))
